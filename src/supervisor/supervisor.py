'''

@author: WIN32GG
'''
import json
import os
import signal
import socket
from threading import Thread
import traceback
import struct

import config
import config_checker
from customlogging import debug
import network 
import subprocess as sp

def suicide():
    debug("--> kill <--")
    os.kill(os.getpid(), signal.SIGTERM)        
        
class Supervisor():
    '''
    The supervisor that handles the workers
    '''
    
    def __init__(self):
        self.workers = {}
        self.running = True
        self.startSupervisorServer()
        self.stopping = False
        self.workerConfig = {}
        
    def stop(self):
        if(self.stopping):
            return
        self.stopping = True
        
        debug("[SUPERVISOR] Got HALT request, stopping...")
        self.running = False
        
        debug("[STOP] Stopping workers")
        for proc in self.workers.values():
            proc.terminate()
            
        debug("[STOP] Closing server")
        self.server.close()
            
        suicide()
    
    def startSupervisorServer(self):
        Thread(target=self._listenTarget).start()
        
    def _listenTarget(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.server.bind(('', config.SUPERVISOR_PORT))
            self.server.listen(4)
            debug("[SUPERVISOR] Started Supervisor Server")
            while(self.running):
                client, addr = self.server.accept()
                debug("[SUPERVISOR] Connection from "+str(addr))
                
                Thread(target=self._clientTarget, args=(client,)).start()
            
        except:
            debug("[SUPERVISOR] Supervisor Server Shutting down", 0, True)
            traceback.print_exc()
            self.server.close()
        
    def _detectSpecialAction(self, cmd):
        try:
            cmd = json.loads(cmd)
            if("workername" in cmd.keys()):
                return None
            
            if(cmd["action"] == "halt"):
                self.stop()
                return network.OK
            
            if(cmd['action'] == "status"):
                return json.dumps(list(self.workerConfig.values()))
                
            return "Action not found"
        except:
            traceback.print_exc()
            return "Error in action"
        
    def _clientTarget(self, sock):
        chan = sock.makefile("rwb")
        
        while(self.running):
            try:
                j = network.readString(chan)
                out = network.OK
                
                try:
                    sa = self._detectSpecialAction(j)
                
                    if(sa != None):
                        out = sa
                    else:
                        self.handleConfigInput(j)
                    network.sendString(chan, out)
                except Exception as e:
                    network.sendString(chan, repr(e))
                    raise e
                    
            except struct.error:
                break
            except:
                traceback.print_exc()
                break
        
        debug("[SUPERVISOR] Closing client connection", 1, True)
        sock.shutdown(socket.SHUT_RDWR)
        sock.close()
    
    def startWorker(self, workerConfig, name):
        Thread(target=self._workerManagementThreadTarget, args=(workerConfig, name)).start()
      
    def handleConfigInput(self, workerConfig):
        debug("[SUPERVISOR] Checking config...")
        if(not config_checker.checkWorkerConfigSanity(workerConfig)):
            return
        name = json.loads(workerConfig)['workername']
        debug("[SUPERVISOR] Config is OK")
    
        
        if(name in self.workers):
            debug("[SUPERVISOR] Worker found: "+name)
            self._sendToWorker(name, workerConfig)
        else:
            self.startWorker(workerConfig, name)
        
    def _workerManagementThreadTarget(self, workerConfig, name):
        debug("[WORKER-MGM] Starting worker process...")        
        proc = sp.Popen([config.PYTHON_CMD, "worker.py"], stdin=sp.PIPE, universal_newlines=True)
        self.workers[name] = proc
        self.workerConfig[name] = workerConfig
        debug("[WORKER-MGM] Worker "+name+" started with pid "+str(proc.pid))
        self._sendToWorker(name, workerConfig)
        
        proc.wait()
        debug("[WORKER-MGM] Worker "+name+" ("+str(proc.pid)+") exited with errcode "+str(proc.poll()))
        del self.workers[name]   
        del self.workerConfig[name]
           
    def _sendToWorker(self, wname, config):
        debug("[SUPERVISOR] Sending config to worker")
        proc = self.workers[wname]
        proc.stdin.write(config+"\n")
        proc.stdin.flush()
           
if __name__ == '__main__':
    
    sup = Supervisor()
    debug("[SUPERVISOR] Ready for input")
    while(True):
        try:
            l = input().strip()
            if(sup._detectSpecialAction(l)):   
                continue            
            sup.handleConfigInput(l)
        except KeyboardInterrupt:
            sup.stop()
            
        except:
            if(not sup.running):
                break
            traceback.print_exc()
            
        
                    
    