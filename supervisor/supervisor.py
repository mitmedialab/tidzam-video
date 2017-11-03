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

class Worker:
    '''
    Represents a Worker connected to this Supervisor
    Worker can be sent a job, a stream redirection info
    Workers are managed by a Warden
    You can get a Worker's stats, address,  
    '''
    
    def __init__(self, socketObject):
        self.connection = socketObject
        
    
def supervisorNetworkCallback(nature, packet):
    #print(str(nature)+ " "+ str(packet))
    if(nature == network.PACKET_TYPE_UNDEFINED):
        img = np.frombuffer(packet.binObj, dtype="i")
        print(str(img))
        print(str(packet))
              
    
    if(nature == network.NATURE_ERROR):
        return True
    
    

if(__name__ == "__main__"):
    #create supervisor server
    nt = network.NetworkHandler(network.OBJECT_TYPE_SUPERVISOR, supervisorNetworkCallback)
    
    sleep(100)
    
    
    
    
    
    