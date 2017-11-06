'''
 
 Manages the WorkerPool
 
 @author: WIN32GG
 '''
 
import network
import atexit
from multiprocessing import Process
from multiprocessing import Queue
from multiprocessing import Value
import os
from queue import Empty
from queue import Full
import time
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
_DEBUG_LEVEL = 3
_DEBUG_DICT  = {0:"Minimum", 1: "Warden only", 2: "Workers status", 3: "Everything"}
def debug(msg, level = 1, err= False):
    stream = sys.stderr if err else sys.stdout
    msg    = "[ERROR] "+msg if err else "[INFO] "+msg
    if(level <= _DEBUG_LEVEL):
        stream.write(msg+"\n")
        stream.flush()


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
        super(SupervisedProcess, self).__init__() #init super class
        self.daemon = True
        self.errQ   = errQ

    def run(self):
        try:
            sys.stdout = SupervisedProcessStream(self, sys.stdout)
            sys.stderr = SupervisedProcessStream(self, sys.stderr)

            self.doWork()
        except Exception:
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
    The Job is first initialized with the setup() then called by the worker with loop(data)
    If a job sets his self.shouldExit to True, the worker will call the destroy() method and return
"""
class Job(object):

    def __init__(self):
        self.shouldExit = False
        debug("Loaded Job: "+str(self), 2)

    def setup(self):
        return;

    def loop(self, data):
        raise NotImplementedError("The loop method has not been implemented")

    def destroy(self):
        return
    
    def requireData(self):
        return False
    
    def __str__(self, *args, **kwargs):
        return "Job Object: "+ str(self.__class__.__name__)

"""
    Worker implementation with a specific dataQueue
    A Worker should no be spawned on it own without a WorkerPool
"""
class Worker(SupervisedProcess):

    def __init__(self, name, jobc, errQ, dtaQ, calQ):
        super(Worker, self).__init__(errQ)
        self.id = name
        self.jobClass  = jobc
        self.dataQueue = dtaQ     #the input data
        self.callBackQueue = calQ #where the results are put
        self.isRunning = Value('i', 1)
        
    def __str__(self, *args, **kwargs):
        return "Worker: id="+self.id+" job="+str(self.jobClass)+" running="+str(self.isRunning.value)

    #get awaiting data
    def pullData(self):
        try:
            data = self.dataQueue.get(timeout = 0.01)
        except Empty:
            return None

        return data


    def doWork(self):
        debug("Starting worker", level= 3)
        self.job = self.jobClass.__new__(self.jobClass)
        self.job.__init__()

        self.job.setup()
        debug("Executing job "+str(self.job), level = 2)
        while self.isRunning.value and not self.job.shouldExit:
            data = self.pullData()
            if(data == None and self.job.requireData()):
                break
            
            debug("Data: "+str(data), level= 3) #Early debug
            
            r = self.job.loop(data)
            if(type(r) != type(None) and self.callBackQueue != None):
                self.callBackQueue.put(r)

        self.stop()
        print("exiting worker normally")

    def stop(self):
        self.job.destroy()
        self.isRunning.value = 0

'''
Represents a WorkerPool ona remote Warden
'''
class RemoteWorkerPool:
    
    def __init__(self, identifier, conn):
        self.identifier = identifier
        self.connection = conn
        
    def __str__(self):
        return "RemoteWorkerPool: "+str(self.identifier)+"@"+str(self.connection.nh.identifier)
        
    def __repr__(self):
        return str(self.__str__())
        
    def feedData(self, data): #usable with nparray
        debug("[NETWORK] Feeding data to remote WP: "+str(self.connection))
        pck = network.createImagePacket(data)
        pck["target"] = self.identifier
        self.conn.send(pck)
    
    @property
    def runing(self):
        return True

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

    '''
    @note: The job is the jobClass object not a job instance
    '''
    def __init__(self, name, job, workersAmount = 0, maxWorkers = os.cpu_count()):
        if(type(name) != type("str")):
            raise ValueError("name must be a string")
        if(type(workersAmount) != type(42) or workersAmount < 0):
            raise ValueError("workersAmount must be a int >= 0")
        if(maxWorkers <= 0):
            raise ValueError("maxWorkers must be > 0")
        if(workersAmount > maxWorkers):
            raise ValueError("workersAmount can't be more than the max workers")

        self.name = name
        self.autoWorkers             = workersAmount == 0
        self.workersAmount           = workersAmount
        self.workers                 = {}      # dictionnay of workers, key is the pid
        self.jobClass                = job     # job class (not instance) for this pool
        self.errorQueue              = Queue() # queue containing unhandled exceptions from subprocesses
        self.dataQueue               = Queue() # the data to be distributed
        self.resultQueue             = Queue()
        self.maxWorkers              = maxWorkers
              
        self.workersManagementThread = None
        self.running                 = True

        self.transferThread          = None #thread used to transfer result to the pluged wp
        self._plugged                = []
        self._startManagementThread()

        self.pools.append(self)

    @classmethod
    def shutdownAll(cls): #used to shutdown all pools when exiting
        if(len(cls.pools) == 0):
            return

        debug("--- Stopping "+str(len(cls.pools))+" pools ---")
        for pool in cls.pools:
            pool.shutdown()

    def feedData(self, data):
        self.checkPoolState()
        self.dataQueue.put(data)

    def shutdown(self):
        debug(self.name+": stopping")
        self.running = False
        self._stopWorkers()
        self.pools.remove(self)

    #broadcast to workers and ask to stop
    def _stopWorkers(self):
        for pid in self.workers.keys():
            self.workers[pid].stop()

    def checkPoolState(self):
        if(not self.running):
            raise EnvironmentError("Pool is not running")

    def pollResult(self):
        self.checkPoolState()
        try :
            return self.resultQueue.get(timeout=0.01)
        except Empty: #Queue is empty, no big deal
            return None

    def __str__(self):
        return "WorkerPool: "+self.name+" job="+self.jobClass.__name__+" "+str(len(self.workers))+" active workers"

    def __repr__(self):
        return str(self.__str__())

    def _getWorkerNumber(self, avbl):
        i = 1
        k = avbl.values()
        while i in k:
            i += 1

        return i

    def _manageWorkers(self):
        avbl = {} #worker pid -> worker number
        if(self.autoWorkers):
            debug("[WORKERPOOL] "+self.name+" started with auto worker count")
        else:
            debug("[WORKERPOOL] "+self.name+" started with "+str(self.workersAmount)+" workers")

        while self.running and threading.main_thread().isAlive(): #if the program is exiting (ie main tread has died) we should not start new workers

            #start processes until max amount is reached
            while len(self.workers) < self.workersAmount and threading.main_thread().isAlive():
                number = self._getWorkerNumber(avbl)
                
                w = Worker(self.name+" Worker-"+str(number), self.jobClass, self.errorQueue, self.dataQueue, self.resultQueue)
                
                try:
                    w.start()
                except: #this is considered fatal
                    print(self.name+": process start failed, mgmt will stop\nPlease stop the pool properly")
                    return

                self.workers[w.pid] = w
                avbl[w.pid] = number
                debug(self.name+": worker "+w.name+" started: pid="+str(w.pid), level=2)
                
                sleep(1) #Workers takes about 1 sec to start
                
            if(self.autoWorkers):
                #increase or decrease the amount of workers regarding the jobQueue
                if(not self.dataQueue.empty()):
                    self.workersAmount += 1
                else:
                    self.workersAmount -= 1

                if(self.workersAmount < 0):
                    self.workersAmount = 0;
                if(self.workersAmount > self.maxWorkers):
                    self.workersAmount = self.maxWorkers

            #poll error from errorQueue
            try:
                while True:
                    stack = self.errorQueue.get(timeout=0.01)
                    #if an error has occured, print it, remove process and (maybe) dump process in log file
                    #print("Unhandled error from process "+str(stack[0]))
                    debug(self.name+": err in worker: "+str(stack[1].__name__), level = 0, err=True)

                    #del self.workers[stack[0]] #done below

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

    #Plug this Pool to another pool of workers, local or remote
    def plug(self, target):
        if(target == None):
            raise ValueError("Cannot plug to None")
        if(type(target) != type(self) ): #or type(target) != type(self.plug)
            raise ValueError("Can only plug to a WorkerPool ")
        if(self._plugged.__contains__(target)):
            raise ValueError("Already plugged")

        debug(self.name+": --> "+target.identifier)
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

    def _startManagementThread(self):
        if(self.workersManagementThread != None):
            raise ValueError("Mgm thread already started")

        self.workersManagementThread = Thread(target=self._manageWorkers, name="WorkerPool "+self.name+" mgm")
        self.workersManagementThread.daemon = True
        self.workersManagementThread.start()


if __name__ == "__main__":
    print("Don't launch this, launch the warden")

   
