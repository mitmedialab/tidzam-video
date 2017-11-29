'''
Created on 27 nov. 2017

@author: WIN32GG
'''
import subprocess as sp
import config
from customlogging import debug
from threading import Thread
import socket
import traceback
import struct
import os
import network 
import sys
import json
        
        
class Supervisor():
    '''
    The supervisor that handles the workers
    '''
    
    def __init__(self):
        self.workers = {}
        self.running = True
        self.startSupervisorServer()
        
    def stop(self):
        self.running = False
        
        for proc in self.workers.values():
            proc.terminate()
        exit(0)
    
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
                
        sock.shutdown(socket.SHUT_RDWR)
        sock.close()
    
    def startWorker(self, workerConfig):
        Thread(target=self._workerManagementThreadTarget, args=(workerConfig,)).start()
        
    def _checkConfigSanity(self, cfg):
        MANDATORY = ["port", "jobname"]
        OPTIONAL  = ["workername", "debuglevel", "output", "jobdata"]
        TOTAL = MANDATORY + OPTIONAL
        
        try:
            j = json.loads(cfg)
            
            for k in j.keys():
                if(not k in TOTAL):
                    raise ValueError("Unknown parameter: "+str(k))
                
            for k in MANDATORY:
                if(not k in j.keys()):
                    raise ValueError("Missing mandatory parameter: "+str(k))
        
        except ValueError as ve: 
            debug("Error in worker configuration: "+str(ve), 0, True)   
            return False 
        except json.JSONDecodeError:
            debug("Error in worker configuration: The provided configuration is not valid", 0, True)
            return False
        except:
            traceback.print_exc()
            return False
        
        return True
        
        
    def _workerManagementThreadTarget(self, workerConfig):
        debug("[WORKER-MGM] Starting worker...")
        if(not self._checkConfigSanity(workerConfig)):
            return
        debug("[WORKER-MGM] Config is OK")
        
        proc = sp.Popen([config.PYTHON_CMD, "worker.py"], stdin=sp.PIPE, encoding="utf-8")
        self.workers[proc.pid] = proc
        debug("[WORKER-MGM] Worker started with pid "+str(proc.pid))
        proc.communicate(workerConfig)
        debug("[WORKER-MGM] Worker "+str(proc.pid)+" exited with errcode "+str(proc.poll()))
           
if __name__ == '__main__':
    
    sup = Supervisor()
    
    while(True):
        try:
            l = input()
            if(sup._detectSpecialAction(l)): #refaire ça pour le stop²²    
                continue
            sup.startWorker(l)
        except:
            if(not sup.running):
                break
            traceback.print_exc()
                    
    