'''
To be launched on the worker machines

@author: WIN32GG
'''

import network
from network import Packet
import sys
import socket
import traceback
import numpy as np

nethandler = None
warden_name = "<unknown>"
remotewardens = {} #name: Connection
workerpools = {} #id: WorkerPool

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

def wardenNetworkCallback(nature, data):
    print(str(nature)+ " "+ str(data))
    
    if(nature == network.NATURE_ERROR):
        print("WARDEN NETWORK ERROR, CLOSING CONNECTION", sys.stderr)
        return True
    
    if(nature == network.NATURE_CONNECTION_OPEN):
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
    
    if(nature == network.PACKET_TYPE_WORKER_POOL_CONFIG):
        #Configuring worker pool, creating, deleting, changing config: max_workers
        id = data["id"]
        
        if(data["action"] == "create"):
            #Workerpool creation
            if(id in workerpools):
                #TODO send ERR
                return
            mw = int(data["maxWorkers"])
            w = WorkerPool(id, mw, ) 
            
            workerpools[id] = w
        
        if(data["action"] == "remove"):
            #Workerpool deletion
            try:
                w = workerpools[id]
            except KeyError:
                    return
                
            w.shutdown()
            del workerpools[id]
            
        
        if(data["action"] == "config"):
            #Workerpool edition
            pass
        
        print("Invalid action for wp cfg "+str(data["action"]))
        return

if(__name__ == "__main__"):
    
    nethandler = network.NetworkHandler(network.OBJECT_TYPE_WARDEN, wardenNetworkCallback)
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
