'''

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
import config_checker
from time import sleep
from multiprocessing.queues import Empty
from random import random

class SupervisedProcessStream():
    def __init__(self, old_std, name):
        self.old_std=old_std
        self.name = name

    def write(self, text):
        text = text.rstrip()
        if len(text) == 0: return
        self.old_std.write("["+str(self.name)+"] ("+str(os.getpid())+") : " + text + '\n')

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

    def __init__(self, port, inputQueue):
        self.job = None # a worker has initially no job
        self.jobSetup = False
        self.jobRunning = Value('b')
        self.jobRunning.value = False
        self.workerShutdown = Value('b')
        self.workerShutdown.value = False
        self.port = port
        self.outputmethod = self._duplicateOverNetwork
        self.inputQueue = Queue(50)
        self.outputQueue = Queue(50)
        self.outputs = {}
        self.server = None
        self.jobThread = None
        
        self._inputQueue = inputQueue #stdin input 
        self._exitCode = None
        self._startNetwork()

    def stop(self, code=1):
        debug("[STOP] Stopping worker (code "+str(code)+")")
        self.jobRunning.value = False
        self.workerShutdown.value = True

        if(self.server != None):
            debug("[STOP] Closing listener")
            self._closeSock(self.server)

        debug("[STOP] Waiting for output queue to empty...")
        self.netOutThread.join()
        debug("[STOP] Closing output connections (if any)")
        for sock in self.outputs.keys():
            try:
                self._closeSock(sock)
            except:
                traceback.print_exc()

        debug("[STOP] Exiting with code "+str(code), 0)
        self._exitCode = code
        self._inputQueue.close() #triggers exception in main thread causing a check of exitCode

    def checkAction(self, config):
        try:
            if("action" in config.keys()):
                debug("Handling action: "+config['action'])
                action = getattr(self, "action_"+config['action'])
                action()
                return True
        except:
            pass
        return False
    
    def action_halt(self):
        debug("[HALT] Halting !", 0)
        suicide()

    def action_stop(self):
        self.stop()

    def loadJob(self, jobName):
        try:
            self.jobName = str(jobName)
            debug("Loading Job file: "+str(jobName), 1)
            mod   = __import__(jobName)
            jobCl = getattr(mod, jobName.capitalize())

            debug("[WARN] WARNING: Skipped subclass test", 0, True)
            '''if(not issubclass(jobCl, Job)):
                debug("The given job class is not a Job", 0, True)
                debug("It is "+str(jobCl))
                self.job = None
                return '''

                #difference btwn import error & load error
            self.job = jobCl.__new__(jobCl)
            self.job.__init__()
            
            debug("[WORKER] Job loaded", 1)

        except:
            if(_DEBUG_LEVEL == 3):
                traceback.print_exc()
            debug("[WORKER] Could not load job", 1, True)
            self.stop(1)

    def updateWithDiff(self, config):
        if(self.checkAction(config)):
            return
        
        debug("[WORKER] Updating worker...")
      
        #update port
        if(int(self.server.getsockname()[1]) != int(config['port'])):
            p = int(config['port'])
            debug("[WORKER] Updating worker port to "+str(p))
            self.port = p
            self._closeSock(self.server)
            self._startListener()
        
        #update job
        if(config['jobname'] != self.jobName):
            debug("[WORKER] Replacing job")
            if("jobreplacemethod" in config):
                if(config['jobreplacemethod'] == "kill"):
                    self.job.shouldStop = True
                    debug("[WORKER] Asked for Job stop")
            
            debug("[WORKER] Waiting for job shutdown...")
            if(self.jobThread != None):
                self.jobThread.join()
            
            debug("[WORKER] Installing new job...")
            jobName = config["jobname"]
            jobData = config["jobdata"]
            self.loadJob(jobName)
            self.setupJobAndLaunch(jobData)

        #update network dispatch method      
        self.setNetworkMethod(config)
            
    def setNetworkMethod(self, config):
        if("outputmethod" in config):
            if(config['outputmethod'] == "distribute"):
                debug("Output method is set to distribution")
                self.outputmethod = self._distrubuteOverNetwork
            else:
                debug("Output method is set to duplication")
                self.outputmethod = self._duplicateOverNetwork 

    def setupJobAndLaunch(self, data):
        self.setupJob(data)
        self.launchJob()

    def setupJob(self, data):
        if(self.job == None):
            raise ValueError("This worker has no job")

        self.job.setup(data)
        self.jobSetup = True
        self.job.shouldStop = False
        debug("[WORKER] Pushing data to ", 1)

    def _startListener(self):
        self.listeningThread = Thread(target=self._listenTarget, daemon = True)
        self.listeningThread.start()

    def _startNetwork(self):    
        self._startListener()
        self.netOutThread = Thread(target=self._clientOutTarget, daemon = True)
        self.netOutThread.start()
        
    def launchJob(self):
        if(self.job == None):
            raise ValueError("This worker has no job")
    
        if(self.jobRunning.value):
            raise AssertionError("Process already running")

        self.jobRunning.value = True
        
        self.jobThread = Thread(target=self._launchTarget, daemon = True)
        self.jobThread.start()

        debug("[WORKER] Job is running", 1)

    def _listenTarget(self):
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(('', self.port))
            server.listen(4)
            debug("Listening on "+str(self.port))
        except:
            traceback.print_exc()
            self.stop(1)
            return

        self.server = server
        try:
            while(not self.workerShutdown.value):
                client, addr = server.accept()
                if(client != None):
                    debug("Input from: "+str(addr), 1)
                    Thread(target=self._clientInTarget, args=(client,), daemon = True).start()
        except:
            if(self.workerShutdown.value):
                return
            
            traceback.print_exc()
            if(not self.jobRunning.value):
                return
        

    def _clientInTarget(self, sock):
        binChan = sock.makefile("rb")
        try:
            while(not self.workerShutdown.value):
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
        if(not sock._closed):
            try:
                sock.shutdown(socket.SHUT_RDWR)
                sock.close()
            except:
                pass

    def _clientOutTarget(self):
        while( (not self.workerShutdown.value or self.jobRunning.value) or not self.outputQueue.empty()):       
            
            try:
                p = self.outputQueue.get(timeout = 1)
            except Empty:
                continue
                      
            if(len(self.outputs) == 0):
                debug("Got output data but nothing is plugged", 1)
                print(str(p))
                continue

            self.outputmethod(p)
            

    def _duplicateOverNetwork(self, p):
        for sock in self.outputs:
            self._sendTo(sock, p)
    
    def _distrubuteOverNetwork(self, p):
        i = random.randint(0, len(self.outputs))
        self._sendTo(self.outputs[i], p)
    
    def _sendTo(self, sock, p):
        binChan = self.outputs[sock]
        try:
            p.send(binChan)
        except:
            if(_DEBUG_LEVEL == 3):
                traceback.print_exc()

            debug("Output Connection was lost", 0, True)

            self._closeSock(sock)
            del self.outputs[sock]


    def plug(self, addr): #addr is (hostname, port)

        debug("Plugging to "+str(addr))
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(addr)

            binChan = sock.makefile("wb")
            self.outputs[sock] = binChan
            debug("Plugged to "+str(addr))
        except:
            if(_DEBUG_LEVEL == 3):
                traceback.print_exc()

            debug("Could not connect to "+str(addr), 0, True)

    def _clearInputQueue(self):
        try:
            while(True):
                self.inputQueue.get_nowait()
        except Empty:
            return
    
    def _doJob(self):
        '''
        Runs the job with input and output
        '''

        while(not self.job.shouldStop and self.jobRunning.value):
            data = None
            if(self.job.requireData()):
                if(self.job.allowDrop() and self.inputQueue.full()):
                    self._clearInputQueue()
                    
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
                else:
                    if(isinstance(out, dict)):
                        for key in out.keys():
                            p[key] = out[key]
                    else:
                        raise TypeError('Can only handle a Packet, npArray or raw types & np array dict')
                    
                self.outputQueue.put(p)

        self.job.destroy()
        #self.jobRunning.value = False
        debug("Reached end of Launch target")
        self.stop(0)

    def _launchTarget(self):
        try:
            self._doJob()
        except:
            debug("Error from job thread", 0, True)
            traceback.print_exc()
            self.stop(1)
   

class Job(object):
    '''
    A job to be executed on a Worker
    '''

    def setup(self, data):
        pass

    def loop(self, data):
        raise NotImplementedError("Main loop not implemented")

    def destroy(self):
        pass

    def requireData(self):
        return False
    
    def allowDrop(self):
        return True

def setupWithJsonConfig(config, inputQueue):
    #Worker setup    
    name = str(config["workername"])
    sys.stdout = SupervisedProcessStream(sys.stdout, name)
    sys.stderr = SupervisedProcessStream(sys.stderr, name)
    
    debug("Worker name is "+name)

    port = int(config["port"])
    debug("Worker port is "+str(port))

    jobName = config["jobname"]
    debug("Worker job is "+str(jobName))

    if("debuglevel" in config):
        debuglevel = int(config["debuglevel"])
        customlogging._DEBUG_LEVEL = debuglevel

        debug("Debug level is "+str(debuglevel)+" ("+str(customlogging._DEBUG_DICT[debuglevel])+")", 0)

    #Worker startup
    worker = Worker(port, inputQueue)
    worker.name = name
    worker.loadJob(jobName)
    
    worker.setNetworkMethod(config)

    if("output" in config):
        for adr in config["output"]:
            host, port = adr.split(":")
            worker.plug((host, int(port)))

    data = None
    if("jobdata" in config):
        data = config["jobdata"]
    worker.setupJobAndLaunch(data)

    return worker

def readerTarget(inputQueue):
    while True:
        line = input().strip() 
        inputQueue.put(line)
        
def suicide():
    os.kill(os.getpid(), signal.SIGTERM)

if __name__ == "__main__":
    worker = None   
    run = True

    debug("[UNASSIGNED-WORKER] Ready for input")    
    inputQueue = Queue()
    
    inputThread = Thread(target = readerTarget, args=(inputQueue,))
    inputThread.daemon = True
    inputThread.start()

    while(run):
        try:
            
            try:
                line = inputQueue.get()
            except: #Queue has been closed
                run = False
                if(worker != None and worker._exitCode != None): #exception from the forced close on stdin
                    code = worker._exitCode
                else:
                    debug("[WARNING] Caught CTRL+C event, stopping")
                    code = 35
                    
                sys.exit(code)
                
            # getting input
            #-------------------------------------
            # handling input
                     
            config = json.loads(line)
            
            if(worker == None):
                worker = setupWithJsonConfig(config, inputQueue)
            else:
                worker.updateWithDiff(config)
        
        except SystemExit as e:
            raise e #must be transmitted
        except:
            worker = None
            run = False
            debug("Uncaught exception, abort", 0, True)
            traceback.print_exc()
            suicide() #cannot stay in this state
