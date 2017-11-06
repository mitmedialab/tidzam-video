'''
Control application

@author: WIN32GG
'''

import network
from network import Packet
import socket
from time import sleep
import io
import numpy as np
from worker import _DEBUG_LEVEL

warden = None

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
        
    def plugWP(self, sourceWP, targetWP, remoteWarden):
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
        pass
    
    if(nature == network.PACKET_TYPE_WORKER_POOL_STATUS):
        pass
    
    if(nature == network.NATURE_ERROR):
        return True
    
def handleCommand(cmd):
    global warden
    
    if(cmd == "stats"):
        warden.requestStats()
    
    a = cmd.split(" ")
    if(a[0] == "create_wp"):
        warden.startWP(a[1], a[2])
        
    if(a[0] == "connect"):
        pass
    
    if(a[0] == "data"):
        warden.feedData(a[1], a[2])
        
    if(a[0] == "plug"):
        warden.plugWP(a[1], a[2], a[3])

if(__name__ == "__main__"):
    #create supervisor server
    nt = network.NetworkHandler(network.OBJECT_TYPE_SUPERVISOR, "supervisor", supervisorNetworkCallback, )        
        
    c = nt.connect("127.0.0.1")
    warden = Warden(c)
    
    while True:
        inp = input(">>> ")
        handleCommand(inp)
       
       
       