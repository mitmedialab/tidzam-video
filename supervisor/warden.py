'''
To be launched on the worker machines

@author: WIN32GG
'''

import atexit
import os
import socket
import sys
import traceback

from network import Packet
import network
import numpy as np
from worker import WorkerPool
from worker import _DEBUG_DICT
from worker import _DEBUG_LEVEL
from worker import debug
import worker


nethandler = None
supervisorConnection = None # A warden can only be connected to one supervisor, the reference is kept here
warden_name = "<unknown>"
remotewardens = {} #name: Connection
workerpools = {} #id: WorkerPool

def handleExit():
    return


def loadJob(jobModuleName):
    try:
        mod   = __import__(jobModuleName)
        jobCl = getattr(mod, jobModuleName)
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

def wardenNetworkCallback(nature, data, conn = None):
    print(str(nature)+ " "+ str(data))
    
    if(nature == network.NATURE_ERROR):
        print("WARDEN NETWORK ERROR, CLOSING CONNECTION", sys.stderr)
        return True
    
    if(nature == network.NATURE_CONNECTION_OPEN):
        print("Connection "+str(conn)+ " opened")
        return
    
    if(nature == network.NATURE_CONNECTION_CLOSED):
        print("Connection "+str(conn)+ " closed")
        return
    
    if(nature == network.PACKET_TYPE_WARDEN_CONFIG):
        who = data["target"]
        if(who == "self"):
            warden_name = data["name"]
        else:
            addr = data["addr"]
            print("[WARDEN] Connecting to Warden "+str(who)+" @ "+str(addr))
            if(not connectWarden(who, addr)):
                pass #TODO answer: ERR
                return
        #TODO: answer: OK
        return    
    
    if(nature == network.PACKET_TYPE_DATA):
        targetWorker = data["target"] #the WP pool id
        if(not targetWorker in workerpools):
            debug("Worker id not in local workers: "+str(targetWorker), level = 0, err = True)
            return
        img = network.readImagePacket(data)
        
        workerpools[targetWorker].feedData(img if img != None else data.binObj) #pass image or byte directly
        return
    
    if(nature == network.PACKET_TYPE_PLUG_REQUEST):
        localWP  = data["sourceWP"] #the id of the local worker
        remoteWP = data["destinationWP"] #the id of the destination worker, remote or local
        
        if(not localWP in workerpools):
            #TODO
            return
        
        if(not remoteWP in workerpools):
            #TODO
            return
        
        debug("Plugging "+localWP+" to "+remoteWP)
        workerpools[localWP].plug(workerpools[remoteWP])
        #TODO send ok
        
        return        
    
    if(nature == network.PACKET_TYPE_PLUG_ANSWER):
        #should not be received by a warden
        return
    
    if(nature == network.PACKET_TYPE_WORKER_POOL_CONFIG):
        #Configuring worker pool, creating, deleting, changing config: max_workers
        id = data["id"]
        #TODO check if id registred
        
        if(data["action"] == "create"):
            #Workerpool creation
            if(id in workerpools):
                #TODO send ERR
                return
            
            try:
                mw = int(data["maxWorkers"])
                wa = int(data["workerAmount"])
                jb = str(data["jobName"])
                
                w = WorkerPool(id, loadJob(jb), wa, mw) 
                
                workerpools[id] = w
            except:
                pass #send error
            
            #TODO send ok
            
        if(data["action"] == "remove"):
            #Workerpool deletion
            try:
                w = workerpools[id]
            except KeyError:
                    return #TODO send error
                
            w.shutdown()
            del workerpools[id]
            
        
        if(data["action"] == "config"):
            #Workerpool edition
            pass
        
        print("Invalid action for wp cfg "+str(data["action"]))
        return

if(__name__ == "__main__"):
    atexit.register(handleExit)
    print("============================================================")
    print("Starting TidCam WARDEN (pid="+str(os.getpid())+")")
    print("The debug level is "+str(_DEBUG_LEVEL)+ " ("+_DEBUG_DICT[_DEBUG_LEVEL]+")")
    print("============================================================")
    
    nethandler = network.NetworkHandler(network.OBJECT_TYPE_WARDEN, wardenNetworkCallback)
    
    debug("Started NetHandler")
    
    
    ########################## TESTING ######################################
    c = nethandler.connect("127.0.0.1")
    
    while True:
        
        inp  = input(">>>")
        
        p = network.Packet()
        p["msg"] = inp
        ar = np.random.randint(0, 255, 1908*1080)
        
        print(str(ar))
        p.binObj = ar.tobytes()
        
        c.send(p)
        
    
    pass
