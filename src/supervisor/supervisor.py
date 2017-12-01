'''
Created on 27 nov. 2017

@author: WIN32GG
'''
import json
import os
import signal
import socket
from threading import Thread
import traceback

import config
import config_checker
from customlogging import debug
import network 
import subprocess as sp

def suicide():
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
        
    def stop(self):
        if(self.stopping):
            return
        self.stopping = True
        
        debug("[SUPERVISOR] Got HALT request, stopping...")
        self.running = False
        
        for proc in self.workers.values():
            proc.terminate()
            
        suicide()
    
    def startSupervisorServer(self):
        Thread(target=self._listenTarget).start()
        
    def _listenTarget(self):
        debug("[SUPERVISOR] Starting Supervisor Server")
        try:
            
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.bind(('', config.SUPERVISOR_PORT))
            server.listen()
            
            while(self.running):
                client, addr = server.accept()
                debug("[SUPERVISOR] Connection from "+str(addr))
                
                Thread(target=self._clientTarget, args=(client,)).start()
            
        except:
            debug("[SUPERVISOR] Supervisor Server Shutting down", 0, True)
            traceback.print_exc()
        
    def _detectSpecialAction(self, cmd):
        
        try:
            cmd = json.loads(cmd)
            if(cmd["action"] == "stop"):
                self.stop()
                
            return True
        except:
            #traceback.print_exc()#
            return False
        
    def _clientTarget(self, sock):
        chan = sock.makefile("rwb")
        
        while(self.running):
            try:
                j = json.loads(network.readString(chan))
                if(self._detectSpecialAction(j)):
                    continue
                
                self.startWorker(j)
                
            except:
                debug("[SUPERVISOR] Closing client connection", 1, True)
                traceback.print_exc()
                break
                
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
        proc = sp.Popen([config.PYTHON_CMD, "worker.py"], stdin=sp.PIPE, encoding="utf-8", universal_newlines=True)
        self.workers[name] = proc
        debug("[WORKER-MGM] Worker "+name+" started with pid "+str(proc.pid))
        self._sendToWorker(name, workerConfig)
        
        proc.wait()
        debug("[WORKER-MGM] Worker "+name+" ("+str(proc.pid)+") exited with errcode "+str(proc.poll()))
           
    def _sendToWorker(self, wname, config):
        debug("[SUPERVISOR] Sending config to worker")
        proc = self.workers[wname]
        proc.stdin.write(config+"\n")
        proc.stdin.flush()
           
if __name__ == '__main__':
    
    sup = Supervisor()
    
    while(True):
        try:
            l = input().strip()
            if(sup._detectSpecialAction(l)): #refaire ça pour le stop²²    
                continue
            sup.handleConfigInput(l)
        except KeyboardInterrupt:
            sup.stop()
            
        except:
            if(not sup.running):
                break
            traceback.print_exc()
            
        
                    
    