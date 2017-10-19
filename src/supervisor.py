# ====================================================================
# Main file for the Supervisor part of the TidCam Project
# The Supervisor manages the workers for streamers and the ROI generator
# ====================================================================

import atexit
from builtins import property
from multiprocessing import Pipe
from multiprocessing import Process
from multiprocessing import Queue
from multiprocessing import Value
import os
from queue import Empty
from queue import Full
import sys
from threading import Thread
import threading
from time import sleep
import traceback

import numpy as np

#from tensorflow.python.client import device_lib



"""
    DEBUG OUTPUT HANDLING
"""
#debug level 0,1,2,3 the higher, the depper debug
_DEBUG_LEVEL = 1
_DEBUG_DICT  = {0:"Minimum", 1: "Supervisor only", 2: "Worker status", 3: "Worker deep state"}
def debug(msg, level = 1, err= False):
    stream = sys.stderr if err else sys.stdout
    
    if(level <= _DEBUG_LEVEL):
        stream.write(msg+"\n")
        stream.flush()

def handleExit():
    WorkerPool.shutdownAll()
    
    

"""
    Used for custom writing to a stream, so we can see quickly which process emmited
""" 
class SupervisedProcessStream():
    def __init__(self, proc, old_std):
        self.old_std=old_std
        self.proc = proc

    def write(self, text):
        text = text.rstrip()
        if len(text) == 0: return
        self.old_std.write(">Sub "+str(self.proc.pid)+" ("+self.proc.name+") : " + text + '\n')
        
    def flush(self):
        self.old_std.flush()
        

"""
    Process called by the supervisor with exception handling and custom std outputs
"""
class SupervisedProcess(Process):

    def __init__(self, errQ):
        super().__init__() #init super class
        self.daemon = True
        self.errQ = errQ

        
    def run(self):
        try:
            sys.stdout = SupervisedProcessStream(self, sys.stdout)
            sys.stderr = SupervisedProcessStream(self, sys.stderr)
            
            self.doWork()
        except Exception as e:
            if(_DEBUG_LEVEL >= 2):
                traceback.print_exc()
            self.handleError(sys.exc_info())
                   
        #debug
        debug("Process exited", level=2)
            
    def doWork(self):
        raise NotImplementedError() # defined in sub-classes depending of the work
    
    def handleError(self, err):
        infos = (self.pid, err[0])
        
        self.errQ.put_nowait(infos)

"""
    Represents a Job that can be executed by a Worker
"""
class Job(object):
    
    def __init__(self, func, *args):
        self.func = func
        self.args = args
        self.repeat = False
        self.monopole = False
        
    #indicate that this job should be repeated if no other job is found
    def setRepeat(self):
        self.repeat = True
        return self
    
    #indicate that this job is the only job that should be run on the underlying process
    #other job-finding operations should not be attempted
    def setMonopole(self):
        self.monopole = True
        return self
    
    def __str__(self, *args, **kwargs):
        return "Job: func="+self.func.__name__+" args="+str(self.args)+" repeated="+str(self.repeat)+" monopole="+str(self.monopole)
    
    @property
    def hasMonopole(self):
        return self.monopole
    
    @property
    def name(self):
        return "f:"+self.func.__name__+" a:"+str(self.args)
    
    def execute(self):
        return self.func(self.args)

"""
    Worker implementation with a specific jobQueue
    A Worker should no be spawned on it own without a WorkerPool
"""
class Worker(SupervisedProcess):
     
    def __init__(self, errQ, jobQ, calQ = None):
        super().__init__(errQ)
        self.jobQueue = jobQ
        self.callBackQueue = calQ #where the results are put
        self.isRunning = Value('i', 1)

    #get the nextjob to run
    def nextJob(self, lastJob):
        if(lastJob != None and lastJob.hasMonopole):
            return lastJob
        
        try:
            newer = self.jobQueue.get(timeout = 0.01)
        except Empty:
            newer = None
        
        if(lastJob == None or not lastJob.repeat):
            return newer
        else:
            return newer if newer != None else lastJob
        

    def doWork(self):
        debug("Starting worker", level= 3)
        
        job = None
        while self.isRunning.value: 
            job = self.nextJob(job)
            debug("Executing: "+str(job), level= 3) #Early debug
            if(job != None):
                debug("Executing job "+job.name, level = 2)
                r = job.execute()
                if(type(r) != type(None) and self.callBackQueue != None):
                    self.callBackQueue.put(r)
            else:
                break;
       
        #print("exiting worker normally")
    
    def stop(self):
        self.isRunning.value = 0
        
"""
    Contains a set of Workers, a JobQueue and eventually a return Queue and a callback function when a value is returned
    If crashed a Worker can be automatically restarted
    
    WorkerPool objects can be plugged together to form a network, for instance an acquisition WorkerPool can be plugged to a processing Pool
    The process of transmitting data from a Pool to another in done in another thread
    
    If workersAmount is set to 0, the number of workers requiered is dynamically determined
    
    Note that all WorkerPool should be shutdown before exit
"""
class WorkerPool(object):

    pools = []

    def __init__(self, name, workersAmount = 0, function = None):
        if(type(name) != type("str")):
            raise ValueError("name must be a string")
        if(type(workersAmount) != type(42) or workersAmount < 0):
            raise ValueError("workersAmount must be a int >= 0")
        
        self.name = name
        self.autoWorkers             = workersAmount == 0
        self.workersAmount           = workersAmount
        self.workers                 = {} #dictionnay of workers, key is the pid
        self.errorQueue              = Queue() # queue containing unhandled exceptions from subprocesses
        self.jobQueue                = Queue()
        self.resultQueue             = Queue()
        self.workersManagementThread = None
        self.running                 = True

        self.transferThread          = None #when plugged @see plug    
        self._plugged                = []       
        self.defaultFunction         = function
        self._startManagementThread()
        
        self.pools.append(self)
    
    @classmethod
    def shutdownAll(cls): #used to shutdown all pools when exiting
        if(len(cls.pools) == 0):
            return
        debug("--- Stopping all pools ---")
        for pool in cls.pools:
            pool.shutdown()
    
    def feedData(self, data):
        self.checkPoolState()
        if(self.defaultFunction == None):
            raise ValueError("Default function is null")
        
        self.addJob(Job(self.defaultFunction, data))
        
    def shutdown(self):
        debug(self.name+": stopping")
        self.running = False
        self._stopWorkers()
        self.pools.remove(self)
        
    #broadcast to workers and ask to stop
    def _stopWorkers(self):
        for pid in self.workers.keys():
            self.workers[pid].stop()
        
    def addJob(self, job):
        self.checkPoolState()
        try:
            self.jobQueue.put(job)
        except Full:
            #print("==== FAILED TO ADD JOB ====") #debug
            return False
        return True
    
    def checkPoolState(self):
        if(not self.running):
            raise EnvironmentError("Pool is not running")
        
    def pollResult(self):
        self.checkPoolState()
        try :
            return self.resultQueue.get(timeout=0.01)
        except Empty: #Queue is empty, no big deal
            return None
      
    def __str__(self, *args, **kwargs):
        return "WorkerPool: "+self.name    
        
    def _getWorkerName(self, avbl):
        i = 1
        k = avbl.values()
        
        while i in k:
            i += 1
        
        return i
        
    def _manageWorkers(self):
        avbl = {} #worker pid -> worker number
        if(self.autoWorkers):
            debug(self.name+" started with auto worker count")
        else:
            debug(self.name+" started with "+str(self.workersAmount)+" workers")
            
        while self.running and threading.main_thread().isAlive(): #if the program is exiting (ie main tread has died) we should not start new workers
            
            #start processes until max amount is reached
            while len(self.workers) < self.workersAmount and threading.main_thread().isAlive():
                worker = Worker(self.errorQueue, self.jobQueue, self.resultQueue)
                number = self._getWorkerName(avbl)
                worker.name = self.name+" Worker-"+str(number)
                try:
                    worker.start()
                except OSError:
                    print(self.name+": process start failed, mgmt will stop\nPlease stop the pool properly", file=sys.stderr)
                    return
                
                self.workers[worker.pid] = worker
                avbl[worker.pid] = number
                debug(self.name+": worker started: pid="+str(worker.pid), level=2)

            if(self.autoWorkers):
                #increase or decrease the amount of workers regarding the jobQueue
                if(not self.jobQueue.empty()):
                    self.workersAmount += 1
                else:
                    self.workersAmount -= 1
            
                if(self.workersAmount < 0):
                    self.workersAmount = 0;
                if(self.workersAmount > os.cpu_count()):
                    self.workersAmount = os.cpu_count()
            
            #poll error from errorQueue
            try:
                while True:
                    stack = self.errorQueue.get(timeout=0.01)
                    #if an error has occured, print it, remove process and (maybe) dump process in log file
                    #print("Unhandled error from process "+str(stack[0]))  
                    debug(self.name+": err in worker: "+str(stack[1].__name__), level = 0, err=True)
                    
                    del self.workers[stack[0]]
            except Empty:
                pass
            
            #check if processes are still alive
            toRemove = [] #cannot remove from a dictionary while iterating over it
            for pid in self.workers.keys():
                if(not self.workers[pid].is_alive()):
                    toRemove.append(pid)
                    
                    
            for pid in toRemove:
                del self.workers[pid]
                del avbl[pid]
                
        
        self.workersManagementThread = None            
        
    #Plug this Pool to another pool of workers
    #directing the output data to the input of the parameter pool
    #=====================================================================================================
    # NOTE THAT: The default function must be set on otherPool, having defaultFunction to None is an Error  
    #=====================================================================================================    
    def plug(self, target):
        if(target == None):
            raise ValueError("Cannot plug to None")
        if(type(target) != type(self) ): #or type(target) != type(self.plug)
            raise ValueError("Can only plug to a WorkerPool ")
        if(self._plugged.__contains__(target)):
            raise ValueError("Already plugged")
        
        debug(self.name+": --> "+target.name)
        self._plugged.append(target)   
        self._startTransferThread()  
    
    def _doTransfer(self):
        while self.running:
            val = self.resultQueue.get() #we don't care if blocked
            for plugged in self._plugged:
                try:
                    if(plugged.running):
                        plugged.feedData(val)
                except Exception as e:
                    debug(self.name+": exception while feeding data", err=True)
                    traceback.print_exc()
        
        self.transferThread = None
    
    def _startTransferThread(self):
        if(self.transferThread != None):
            return
        
        self.transferThread = Thread(target=self._doTransfer)
        self.transferThread.daemon = True
        self.transferThread.start()
        
    
    def unplug(self, otherPool = None):
        if(otherPool == None):
            debug(self.name+": unplugged from all")
            self._plugged = []
            return True
        
        if(not self._plugged.__contains__(otherPool)):
            return False;
        debug(self.name+": -X-> "+otherPool.name)
        self._plugged.remove(otherPool)
        
        return True     
              
    #wait until the jobQueue is empty, can have a 0.001 sec delay
    def join(self):
        while not self.jobQueue.empty():
            sleep(0.001)                 #if not, --> cpu overload
    
    def _startManagementThread(self):
        if(self.workersManagementThread != None):
            raise ValueError("Mgm thread already started")
            
        self.workersManagementThread = Thread(target=self._manageWorkers, name="WorkerPool "+self.name+" mgm")
        self.workersManagementThread.daemon = True
        self.workersManagementThread.start()


###############################################################
################### TESTS AND EXAMPLES ########################
###############################################################

def fakeFunc(arr):
    #return ( (np.random.normal(size=3), np.random.normal(size=3), np.random.normal(size=3)), np.random.normal(size=3), np.random.normal(size=3))
    sleep(0.5)
    return np.random.normal(size=2)
    
def reception(data):
    #sleep(0.01)
    return np.abs(data)
    
def recep(data):
    #sleep(0.1)
    return data*2

def afficher(data):
    print(data)


##########################################################
################# Supervisor starter #####################
##########################################################
if __name__ == "__main__":
    atexit.register(handleExit)
    print("============================================================")
    print("Starting TidCam supervisor (pid="+str(os.getpid())+")")
    print("The debug level is "+str(_DEBUG_LEVEL)+ " ("+_DEBUG_DICT[_DEBUG_LEVEL]+")")
    print("============================================================")
    
    
    pow = WorkerPool("InputPool") 
    rec = WorkerPool("ReceptionPool",  function=reception)
    dep = WorkerPool("2ndReceptor",  function=recep)
    prt = WorkerPool("Printer", function=afficher)
    
    pow.plug(rec)
    rec.plug(dep)
    dep.plug(prt)
    
    #pow.addJob(Job(fakeFunc, None).setMonopole())
    
    for i in range(100):  
        pow.addJob(Job(fakeFunc, np.random.normal(size=3)  ))

    sleep(12)
    

    