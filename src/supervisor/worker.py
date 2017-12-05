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

OUTPUT_DUPLICATE = 0
OUTPUT_DISTRIBUTE = 1

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
        self.port = port
        self.outputmethod = 0
        self.inputQueue = Queue(50)
        self.outputQueue = Queue(50)
        self.outputs = {}
        self.server = None
        
        self._inputQueue = inputQueue #stdin input 
        self._exitCode = None

    def stop(self, code=1):
        debug("[STOP] Stopping worker (code "+str(code)+")")
        self.jobRunning.value = False

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
            debug("[WORKER] Job is loaded", 1)

        except:
            if(_DEBUG_LEVEL == 3):
                traceback.print_exc()
            debug("[WORKER] Could not load job", 1, True)
            self.stop(1)

    def updateWithDiff(self, config):
        if(self.checkAction(config)):
            return
        debug("[WORKER] Updating worker...")
        
        #TODO

    def setupJobAndLaunch(self, data):
        self.setupJob(data)
        self.launchJob()

    def setupJob(self, data):
        if(self.job == None):
            raise ValueError("This worker has no job")

        self.job.setup(data)
        self.jobSetup = True
        debug("[WORKER] Job is set up", 1)

    def launchJob(self):
        if(self.job == None):
            raise ValueError("This worker has no job")

        if(self.jobRunning.value):
            raise AssertionError("Process already running")

        self.jobRunning.value = True

        self.listeningThread = Thread(target=self._listenTarget)
        self.netOutThread    = Thread(target=self._clientOutTarget)
        self.jobThread       = Thread(target=self._launchTarget)
        
        self.listeningThread.daemon = True
        self.netOutThread.daemon    = True
        self.jobThread.daemon       = True

        self.listeningThread.start()
        self.netOutThread.start()
        self.jobThread.start()

        debug("[WORKER] Job is running", 1)

    def _listenTarget(self):
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind( ('', self.port))
            server.listen(4)
        except:
            traceback.print_exc()
            self.stop(1)
            return

        self.server = server
        try:
            while(self.jobRunning.value):
                client, addr = server.accept()
                if(client != None):
                    debug("Input from: "+str(addr), 1)
                    Thread(target=self._clientInTarget, args=(client,), daemon = True).start()
        except:
            if(not self.jobRunning.value):
                return
            traceback.print_exc()


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
        if(not sock._closed):
            try:
                sock.shutdown(socket.SHUT_RDWR)
                sock.close()
            except:
                pass

    def _clientOutTarget(self):
        while(self.jobRunning.value or not self.outputQueue.empty()):
            
            try:
                p = self.outputQueue.get(timeout = 1)
            except Empty:
                continue
                      
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

                    debug("Output Connection was lost", 0, True)

                    self._closeSock(sock)
                    self.outputs.remove(sock)


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

    def _doJob(self):
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
        self.stop(0)

    def _launchTarget(self):
        try:
            self._doJob()
        except:
            debug("Error from job thread", 0, True)
            traceback.print_exc()
            #TODO event: error from job
            self.stop(1)
   

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

    if("debuglevel" in config.keys()):
        debuglevel = int(config["debuglevel"])
        customlogging._DEBUG_LEVEL = debuglevel

        debug("Debug level is "+str(debuglevel)+" ("+str(customlogging._DEBUG_DICT[debuglevel])+")", 0)

    #Worker startup
    worker = Worker(port, inputQueue)
    worker.name = name
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
        
'''
try:
    cmd = line.split(" ")
    fnc = getattr(__main__, "cmd_"+cmd[0])
    fnc(*cmd[1:])
except:
    traceback.print_exc()
    debug("Error in command", 0, True)
    exit(300)'''
