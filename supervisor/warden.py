'''
To be launched on the worker machines

@author: WIN32GG
'''



import atexit
import os
import socket
import sys
import traceback
import __main__

import network
from threading import Thread
import numpy as np
from time import sleep
import hashlib
import json
import random
from worker import WorkerPool
from worker import _DEBUG_DICT
from worker import _DEBUG_LEVEL
from worker import debug
import worker
from worker import RemoteWorkerPool
from builtins import issubclass
from json import JSONEncoder


nethandler = None
supervisorConnection = None # A warden can only be connected to one supervisor, the reference is kept here
warden_name = None
remotewardens = {} #name: Connection
workerpools = {
        'self': {}
    } #id: WorkerPool | RemoteWorkerPool


def handleExit():
    nethandler.stop()
    
def sendWardenStats(conn):
    pck = network.Packet()
    pck.setType(network.PACKET_TYPE_WARDEN_STATS)
    pck["name"] = warden_name
    pck["wp"]   = json.dumps(workerpools, default = jsonCustom)
    pck["warden"] = json.dumps(remotewardens, default = jsonCustom)
    conn.send(pck)    

def broadcastStats():
    global remotewardens
    
    for wid in remotewardens:
        sendWardenStats(remotewardens[wid])
        

def getWorkerPools(wid="self"):
    global workerpools
    
    if(not wid in workerpools):
        return None
    return workerpools[wid]
    

def setAutoName():
    global warden_name
    
    if(warden_name != None):
        return
    
    if(os.path.isfile("wid")):
        mod = "read"
        f = open("wid", "r")
        warden_name = f.read()
        f.close()
    else:
        mod = "set to"
        warden_name = hashlib.sha1(str(random.random()).encode()).hexdigest()[:8]
        f = open("wid", "w")
        f.write(warden_name)
        f.close()
        
    debug("[WARDEN] This warden name was automatically "+mod+": "+str(warden_name))
    

def loadJob(jobModuleName):
    try:
        mod   = __import__(jobModuleName)
        jobCl = getattr(mod, jobModuleName)
        if(not issubclass(jobCl, worker.Job)):
            return None
        #difference btwn import error & load error
        return jobCl
    except: 
        return None

def connectWarden(name, adrr):
    if(nethandler == None):
        print("Nethandler not set")
        return False
    
    if(name in remotewardens):
        return True
    try:
        c = nethandler.connect(adrr)
    except:
        traceback.print_exc()
        return False
    
    remotewardens[name] = c
    return True

def requestWardenInfo(wid):
    global remotewardens
    
    conn = remotewardens[wid]
    if(conn == None):
        debug("[WARDEN] Unknown remote warden: "+wid, 0, True)
        return
    
    pck = network.Packet()
    pck.setType(network.PACKET_TYPE_WARDEN_STATS)
    conn.send(pck)
    
def sendStatusPacket(conn, sts, typ):
    pck = network.Packet()
    pck.setType(typ)
    pck["status"] = sts
    conn.send(pck)

def jsonCustom(obj):
    return obj.toJSON()

'''
Main network function, called when a packet is received, or when an event append on a connection
'''
def wardenNetworkCallback(nature, data, conn = None):
    #globals used
    global warden_name
    global remotewardens
    global supervisorConnection
    global nethandler
    global workerpools
    global _DEBUG_LEVEL
    
    if(_DEBUG_LEVEL == 3):
        print(str(nature)+ " "+ str(data) +" "+str(conn))
    
    if(nature == network.NATURE_ERROR):
        debug("WARDEN NETWORK ERROR, CLOSING CONNECTION", 0, True)
        return True
    
    if(nature == network.NATURE_CONNECTION_OPEN):
        debug("Connection "+str(conn)+ " opened, awaiting identification")
        return
    
    if(nature == network.NATURE_CONNECTION_CLOSED):
        debug("Connection "+str(conn)+ " closed")
        if(supervisorConnection == conn):
            debug("Supervisor connection closed")
            supervisorConnection = None
            return
        
        wid = None
        for w in remotewardens:
            if(remotewardens[w] == conn):
                wid = w
                break
            
        if(wid == None):
            debug("[WARDEN] Aborted warden connection", 3)
            return
            
        del remotewardens[wid]
        del workerpools[wid]
         
        return
    
    if(nature == network.NATURE_UDP_HANDSHAKE): #another warden just went online        
        debug("[WARDEN] Auto connection to "+str(data[1])+" @ "+str(data[0][0]))
        if(not connectWarden(data[1], data[0][0])):
            debug("Failed!", err = True)
        return
    
    if(nature == network.PACKET_TYPE_WARDEN_STATS): #request for stats or remote warden stats info
        if(data["name"] == None):
            #request      
            debug("[WARDEN] Stats request from "+str(conn))
            sendWardenStats(conn)
        
        else:
            #warden stats info
            wid = data["name"]
            rwps = getWorkerPools(wid)
            
            debug("[WARDEN] Got stats from "+str(wid))
            wardens = json.loads(data["wp"])['self'] #we only want the workers on the remote
            print(str(wardens))
            rwps.clear() #we clean before updating            
            for w in wardens: 
                rwps[wardens[w]['name']] = worker.RemoteWorkerPool(wardens[w]['name'], conn, wid)
            
        return
    
    if(nature == network.PACKET_TYPE_AUTH): #sent right after connection
        typ = data["objType"]
        if(typ == network.OBJECT_TYPE_SUPERVISOR):
            if(supervisorConnection != None):
                if(supervisorConnection.isclosed()):
                    supervisorConnection = None
                else:
                    debug("Rejected Supervisor connection: a supervisor is already here", 0, True)
                    conn.close()
                    return
            
            supervisorConnection = conn
            debug("[WARDEN] Supervisor connected", 0)      

        elif(typ == network.OBJECT_TYPE_WARDEN):
            wid  = data["id"]
            rwps = getWorkerPools(wid)                  
                
            if(not wid in remotewardens):
                remotewardens[wid] = conn
                debug("[WARDEN] Accepted Warden: "+str(wid), 1)
            else:
                debug("[WARDEN] Got "+str(wid)+" answer")
                
            workerpools[wid] = {}
        
            requestWardenInfo(wid)      
        return
    
    if(nature == network.PACKET_TYPE_WARDEN_CONFIG): #supervisor can force connection to a warden outside LAN
        who = data["target"]
        if(who == "self"):
            warden_name = data["name"]
        else: #we are forced into registering a remote warden
            addr = data["addr"]
            debug("[WARDEN] Connecting to Warden "+str(who)+" @ "+str(addr))
            if(not connectWarden(who, addr)):
                #ERR
                sendStatusPacket(conn, "CONN_FAILED", network.PACKET_TYPE_PLUG_ANSWER)
                debug("[WARDEN] Failed connection to Warden")
                return
        #answer: OK
        sendStatusPacket(conn, "OK", network.PACKET_TYPE_WARDEN_CONFIG)
        return    
    
    if(nature == network.PACKET_TYPE_DATA): #data for a wp
        targetWorker = data["target"] #the WP pool id
        wps = getWorkerPools() #local WPs
        
        try:
            img = network.readImagePacket(data)
        except ValueError:
            debug("[WARDEN] Checksums don't match", 0, True)
            return
        
        if(not targetWorker in wps):
            debug("[WARDEN] WP id unknown: "+str(targetWorker), level = 0, err = True)
            return
        
        debug("[WARDEN] Got data for WP "+targetWorker, 2)
        wps[targetWorker].feedData(img if not type(img) == type(None) else data["data"]) #pass image or byte directly
        return
    
    if(nature == network.PACKET_TYPE_PLUG_REQUEST): #request to plug a wp to another
        localWP   = data["sourceWP"] #the id of the local worker
        remoteWP  = data["destinationWP"] #the id of the destination worker, remote or local
        remoteWPW = data["remoteWarden"] #the warden holding the workerpool
        
        debug("[WARDEN] Plug request: "+str(localWP)+" --> "+str(remoteWP)+"@"+str(remoteWP), level = 2)
        
        lwps = getWorkerPools()          #local  worker pools
        rwps = getWorkerPools(remoteWPW) #remote worker pools
        
        if(rwps == None):
            debug("[WARDEN] Remote Warden not found ", level = 0, err = True)
            sendStatusPacket(conn, "REMOTE_NOT_FOUND", network.PACKET_TYPE_PLUG_ANSWER)
            return
        
        if(not localWP in lwps):
            debug("[WARDEN] Local WP not found ", level = 0, err = True)
            sendStatusPacket(conn, "WP_NOT_FOUND", network.PACKET_TYPE_PLUG_ANSWER)
            return
        
        if(not remoteWP in rwps):
            debug("[WARDEN] Remote WP not found", level = 0, err = True)
            sendStatusPacket(conn, "WP_NOT_FOUND", network.PACKET_TYPE_PLUG_ANSWER)
            return
    
        lwps[localWP].plug(rwps[remoteWP])
        
        #send ok
        sendStatusPacket(conn, "OK", network.PACKET_TYPE_PLUG_ANSWER)       
        return        
    
    if(nature == network.PACKET_TYPE_WORKER_POOL_CONFIG): #manage wp
        #Configuring worker pool, creating, deleting, changing config: max_workers
        wid = data["id"]
        if(data["action"] == "create"):
            #Workerpool creation
            debug("[WARDEN] Requested WP creation: "+str(wid), 1)
            lwps = getWorkerPools()
            
            if(wid in lwps):
                sendStatusPacket(conn, "ID_IN_USE", network.PACKET_TYPE_WORKER_POOL_STATUS)
                debug("[WARDEN] WP ID already in use", 0, True)
                return
            
            try:
                mw = int(data["maxWorkers"])
                wa = int(data["workerAmount"])
                jb = str(data["jobName"])
                j  = loadJob(jb)
                
                if(j == None):
                    raise ValueError()
                
                debug("[WARDEN] Loaded JobClass: "+str(j.__name__), 2)
                
                w = WorkerPool(wid, j, wa, mw)  
                lwps[wid] = w
            except:
                debug("[WARDEN] Error setting up WP", 0, True)
                sendStatusPacket(conn, "ERR", network.PACKET_TYPE_WORKER_POOL_STATUS)
                return #send error
            
            #TODO send ok
            debug("[WARDEN] Created WorkerPool: "+wid, 0)
            sendStatusPacket(conn, "OK", network.PACKET_TYPE_WORKER_POOL_STATUS)
            
            
        if(data["action"] == "remove"):
            #Workerpool deletion
            try:
                w = workerpools[wid]
            except KeyError:
                    return #TODO send error
                
            w.shutdown()
            del workerpools[wid]
        
    
        if(data["action"] == "config"):
            #Workerpool edition
            pass
        
        broadcastStats()   
        return
        
        
    try:
        a = getattr(__main__, "network_"+str(nature))
        a(data, conn)
    except AttributeError:
        print("NO SUCH NETWORK METHOD "+nature)    
    except BaseException:
        traceback.print_exc()
    
    return
    

def handleCommand(cmd):
    if(cmd == "status"):
        print("Warden "+str(warden_name))
        print("Supervisor: "+str(supervisorConnection))
        for wp in WorkerPool.pools:
            print(str(wp))
        
        print("Connected Workers: "+str(len(remotewardens)))
        for w in remotewardens:
            print(w+ " -> "+str(remotewardens[w]))
            
def startupWarden():
    global nethandler
    
    atexit.register(handleExit)
    print("============================================================")
    print("Starting TidCam WARDEN (pid="+str(os.getpid())+")")
    print("The log level is "+str(_DEBUG_LEVEL)+ " ("+_DEBUG_DICT[_DEBUG_LEVEL]+")")
    print("============================================================")
    setAutoName()
    nethandler = network.NetworkHandler(network.OBJECT_TYPE_WARDEN, warden_name, wardenNetworkCallback)
    debug("[WARDEN] Started NetHandler")

def _cmdExec():
    while True:
        inp  = input()
        handleCommand(inp)
          

'''
The input is main thread is considered a and of program and prevents workers from spawning
The watch dog basically waits forever to prevent this from happening
'''
def runCmdThread():
    t = Thread(target = _cmdExec)
    t.daemon = True
    t.start()
    

if(__name__ == "__main__"):
    startupWarden()    
    #runCmdThread()
   
    while nethandler.isRunning:
        sleep(1)
     
        