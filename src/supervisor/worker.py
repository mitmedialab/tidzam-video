'''
Created on 27 nov. 2017

@author: WIN32GG
'''

from multiprocessing import Queue
from multiprocessing import Value
from threading import Thread
import socket
import traceback
import sys
import os
import json
import numpy as np
from network import Packet

from customlogging import debug
from customlogging import _DEBUG_LEVEL
import customlogging
import signal



class SupervisedProcessStream():
    def __init__(self, old_std):
        self.old_std=old_std
 
    def write(self, text):
        text = text.rstrip()
        if len(text) == 0: return
        self.old_std.write("> pid "+str(os.getpid())+" : " + text + '\n')
 
    def flush(self):
        self.old_std.flush()

    
class Worker(object):
    '''
    A worker that can execute one job, listen on a port for incoming data and on stdin
    for commands. 
    
    The correct call order is
        loadJob            to get the job class from the requested name
        setupJob(data)     to let the job set itself up with the given data
        launchJob          to launch the in/ out sequence for the job
        opt: plug to redirect the output of the job to the given address
    '''
    
    def __init__(self, port):
        self.job = None # a worker has initially no job
        self.jobSetup = False
        self.jobRunning = Value('b')
        self.jobRunning.value = False
        self.port = port
        self.inputQueue = Queue(50)
        self.outputQueue = Queue(50)
        self.outputs = {}
        
    def stop(self):
        self.jobRunning.value = False
        
        debug("Closing listener")
        self._closeSock(self.server)
        
        self.netOutThread.join(timeout=1)
        debug("Closing output connections (if any)")
        for sock in self.outputs.keys():
            try:
                self._closeSock(sock)
            except:
                traceback.print_exc()
        
        debug("Exiting", 0)
        self.suicide()
        
    def suicide(self):
        os.kill(os.getpid(), signal.SIGTERM) #splendide, suicide
        
    def loadJob(self, jobName):
        try: 
            debug("Loading Job file: "+str(jobName), 1)
            mod   = __import__(jobName) 
            jobCl = getattr(mod, jobName.capitalize()) 
            
            '''if(not issubclass(jobCl, Job)): 
                debug("The given job class is not a Job", 0, True)
                debug("It is "+str(jobCl))
                self.job = None
                return '''
            
                #difference btwn import error & load error 
            self.job = jobCl.__new__(jobCl)
            
            self.job.__init__()
            debug("Job is loaded", 1)  
            
        except:  
            if(_DEBUG_LEVEL == 3):
                traceback.print_exc()
            debug("Could not load job", 1, True)
            self.suicide()

    
    def setupJobAndLaunch(self, data):
        self.setupJob(data)
        self.launchJob()
    
    def setupJob(self, data):
        if(self.job == None):
            raise ValueError("This worker has no job")
        
        self.job.setup(data)
        self.jobSetup = True
        debug("Job is set up", 1)
    
    def launchJob(self):
        if(self.job == None):
            raise ValueError("This worker has no job")
        
        if(self.jobRunning.value):
            raise AssertionError("Process already running")
        
        self.jobRunning.value = True
        
        self.listeningThread = Thread(target=self._listenTarget)
        self.netOutThread    = Thread(target=self._clientOutTarget)
        self.jobThread       = Thread(target=self._launchTarget)
        
        self.listeningThread.start()
        self.netOutThread.start()
        self.jobThread.start()
        
        debug("Job is running", 1)
        
    def _listenTarget(self):
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.bind( ('', self.port))
            server.listen()
        except:
            traceback.print_exc()
            self.suicide()
            return
        
        self.server = server
        while(self.jobRunning.value):
            client, addr = server.accept()
            if(client != None):
                debug("Input from: "+str(addr), 1)
                Thread(target=self._clientInTarget, args=(client,), daemon = True).start()
            
        
    def _clientInTarget(self, sock):
        binChan = sock.makefile("rb")
        try:
            while(self.jobRunning.value):
                p = Packet()
                p.read(binChan)
                self.inputQueue.put(p) #hold for next packet if Queue is full
                
        except:
            if(_DEBUG_LEVEL == 3):
                traceback.print_exc()
            debug("Incoming Connection was lost", 0, True)
        finally:
            self._closeSock(sock)
            
    def _closeSock(self, sock):
        #sock.shutdown(socket.SHUT_RDWR)
        sock.close()        
            
    def _clientOutTarget(self):
        while(self.jobRunning.value or not self.outputQueue.empty()):
            p = self.outputQueue.get()
            if(len(self.outputs) == 0):
                debug("Got output data but nothing is plugged", 1)
                print(str(p))
                
            for sock in self.outputs:
                binChan = self.outputs[sock]
                try:
                    p.send(binChan)
                except:
                    if(_DEBUG_LEVEL == 3):
                        traceback.print_exc()
                        
                    debug("Incoming Connection was lost", 0, True)
                    
                    self._closeSock(sock)
                    self.outputs.remove(sock)
                    

    def plug(self, addr): #addr is (hostname, port)
        
        debug("Plugging to "+str(addr))
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(addr)
            
            binChan = sock.makefile("wb")
            self.outputs[sock] = binChan
            
        except:
            if(_DEBUG_LEVEL == 3):
                traceback.print_exc()
                        
            debug("Could not connect to "+str(addr), 0, True)
            

    def _launchTarget(self):
        '''
        Runs the job with input and output
        '''
        
        while(not self.job.shouldStop and self.jobRunning.value):
            data = None
            if(self.job.requireData()):
                data = self.inputQueue.get()
            
            out = self.job.loop(data)
            
            if(type(out) != type(None)):
                p = None
                if(isinstance(out, Packet)):
                    p = out
                else:
                    p = Packet()
                    
                if(isinstance(out, np.ndarray)):
                    p["img"] = out
                
                self.outputQueue.put(p)
        
        self.job.destroy()        
        #self.jobRunning.value = False
        debug("Reached end of Launch target")
        self.stop()
          
        
class Job(object):
    '''
    A job to be executed on a Worker
    '''
    
    def __init__(self):
        self.shouldStop = False
  
    def setup(self, data):
        pass
        
    def loop(self, data):
        raise NotImplementedError("Main loop not implemented")
    
    def destroy(self):
        pass
    
    def requireData(self):
        return False
  
def setupWithJsonConfig(config):
    #Worker setup
    if("workername" in config.keys()):
        debug("Worker name is "+str(config["workername"]))
    
    port = int(config["port"])
    debug("Worker port is "+str(port))
    jobName = config["jobname"]
    debug("Worker job is "+str(jobName))
    
    if("debuglevel" in config.keys()):
        debuglevel = int(config["debuglevel"])
        customlogging._DEBUG_LEVEL = debuglevel
        
        print("Debug level is "+str(debuglevel)+" ("+str(customlogging._DEBUG_DICT[debuglevel])+")")
    
    #Worker startup
    worker = Worker(port)
    worker.loadJob(jobName)
    
   
    
    if("output" in config):
        for adr in config["output"]:
            host, port = adr.split(":")
            worker.plug((host, int(port)))
   
    data = None
    if("jobdata" in config.keys()):
        data = config["jobdata"]   
    worker.setupJobAndLaunch(data)

    return worker


def cmd_launch(port, jobname, data=None):
    worker = Worker(int(port))
    worker.loadJob(jobname)
    if(data != None):
        worker.setupJob(data)
    worker.launchJob()
    
    return worker

if __name__ == "__main__":
    worker = None
    import __main__
    
    sys.stdout = SupervisedProcessStream(sys.stdout)
    sys.stderr = SupervisedProcessStream(sys.stderr)
    
    debug("Worker listening")
   
    line = input().strip()#sys.stdin.readline().strip()
    
    try:
        config = json.loads(line)
        worker = setupWithJsonConfig(config)
        
    except:
        worker = None
        traceback.print_exc()
        exit(300)
        #debug("The given input is not a valid json, trying as cmd")
'''   
try:
    cmd = line.split(" ")
    fnc = getattr(__main__, "cmd_"+cmd[0])
    fnc(*cmd[1:])
except:
    traceback.print_exc()
    debug("Error in command", 0, True)
    exit(300)'''
