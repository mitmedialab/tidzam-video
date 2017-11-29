'''
Created on 29 nov. 2017

@author: WIN32GG
'''

'''
Master file to control all supervisors
Receive the config for the cluster, checks it and run sends to supervisor
(V1.5: Also asks and get the supervisor status and can show it in a web application) 
'''

class Master:
    
    def __init__(self):
        self.supervisors = []
        
class RemoteSupervisor:
    
    def __init__(self, addr, name = None):
        self.addr = addr
        self.name = name

if __name__ == '__main__':
    # read config, 
    # parse & check
    
    pass