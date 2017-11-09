'''
Control application

@author: WIN32GG
'''

import __main__ 
import sys
import network
from network import Packet
import socket
from time import sleep
import io
import numpy as np
import json
import random
import numpy as np
from worker import _DEBUG_LEVEL


warden = None
networkmap = {} # wid: addr
aliases = {} # alias: wid
nethandler = None

class ScriptFatalError(BaseException):
    pass

class Warden:
    '''
    Represents a Worker connected to this Supervisor
    Warden can be sent a job, a stream redirection info
    Workers are managed by a Warden
    You can get a Warden's stats, address,  
    '''
    
    def __init__(self, conn):
        self.connection = conn
        
    def requestStats(self):
        pck = Packet()
        pck.setType(network.PACKET_TYPE_WARDEN_STATS)
        self.connection.send(pck)
    
    def startWP(self, name, jobName, maxWorkers = 8, workerAmount = 0):
        pck = Packet()
        pck.setType(network.PACKET_TYPE_WORKER_POOL_CONFIG)
        '''
        id = data["id"]
        mw = int(data["maxWorkers"])
        wa = int(data["workerAmount"])
        jb = str(data["jobName"])
        '''
        
        pck["action"] = "create"
        pck["id"] = name
        pck["maxWorkers"] = maxWorkers
        pck["workerAmount"] = workerAmount
        pck["jobName"] = jobName
        
        self.connection.send(pck)
        
    def plugWP(self, sourceWP, remoteWarden, targetWP):
        pck = Packet()
        pck.setType(network.PACKET_TYPE_PLUG_REQUEST)
        '''
        data["sourceWP"] #the id of the local worker
        data["destinationWP"] #the id of the destination worker, remote or local
        data["remoteWarden"] #the warden holding the workerpool
        '''
        
        pck["sourceWP"] = sourceWP
        pck["destinationWP"] = targetWP
        pck["remoteWarden"] = remoteWarden
        
        self.connection.send(pck)
    
    def feedData(self, wpid, data):
        pck = Packet()
        pck.setType(network.PACKET_TYPE_DATA)
        pck["data"] = data
        pck["target"] = wpid
        
        self.connection.send(pck)
    
    
def supervisorNetworkCallback(nature, data, conn = None):
    global _DEBUG_LEVEL
    
    if(_DEBUG_LEVEL == 3):
        print(str(nature)+ " "+ str(data) +" "+str(conn))


    if(nature == network.PACKET_TYPE_PLUG_ANSWER):
        pass
    
    if(nature == network.PACKET_TYPE_WARDEN_STATS):
        wp = json.loads(data["wp"])
        for w in wp:
            print(str(w))
        pass
    
    if(nature == network.PACKET_TYPE_WORKER_POOL_STATUS):
        pass
    
    if(nature == network.NATURE_ERROR):
        return True

def execScript(path):
    try:
        f = open(path, "r")
    except FileNotFoundError:
        print("Script file not found: "+str(path))
        return
    
    for line in f:
        try:
            execReq(line)
        except ScriptFatalError as fe:
            print("Fatal Error occured, the script cannot continue")
            return
        except BaseException as e:
            print("Error @: "+line)


def cmd_connect(addr="127.0.0.1", alias=None):
    global nethandler
    global aliases
    global networkmap
    global warden
    
    if(addr in aliases):
        addr = aliases[addr]
        print("[SUPERVISOR] Resolved alias name to "+str(addr))
        
    if(addr in networkmap):
        addr = network[addr]
        print("[SUPERVISOR] Warden name resolved to "+str(addr))
        
    print("[SUPERVISOR] Connecting to: "+str(addr))
    warden = Warden(nethandler.connect(addr))
    
    warden.requestStats()
    print("[SUPERVISOR] Connected")


def cmd_plug(sourceWP, targetWP, targetWarden = "self"):
    warden.plugWP(sourceWP, targetWarden, targetWP)

def cmd_stats():
    warden.requestStats()
    
def cmd_stop():
    warden.stop()
    
def cmd_cwp(name, jobName, maxWorkers = 8, workerAmount = 0):
    warden.startWP(name, jobName, maxWorkers, workerAmount)
    
def cmd_stop():
    global warden
    
    if(warden != None):
        warden.connection.close()
    exit(0)
    
def cmd_data(wpName, *args):
    data = ""
    for i in args:
        data += i+" "
    warden.feedData(wpName, data)
  
def cmd_testbin():
    global warden

    arr = np.random.randint(0, 255, size=(1280,1024,3))
    print(str(arr))
    p = network.createImagePacket(arr)
    warden.connection.send(p)

def execReq(cmd):
    global warden
    
    c = cmd.split(" ")
    a = getattr(__main__, "cmd_"+c[0])
    a(*c[1:])
    
        
def handleCommand(cmd):
    try:
        execReq(cmd)
    except ScriptFatalError as e :
        raise e
    except BaseException:
        print("Error in command", file = sys.stderr)


if(__name__ == "__main__"):
    print("============================")
    print("Tid'zam Camera SUPERVISOR")
    print("============================")
    
    nethandler = network.NetworkHandler(network.OBJECT_TYPE_SUPERVISOR, "supervisor", supervisorNetworkCallback, )
    while True:
        inp = input(">>> ")
        handleCommand(inp)
       
       
       