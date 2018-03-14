'''

@author: WIN32GG
'''

from multiprocessing import Queue
from multiprocessing import Value
from threading import Thread
import socket
import traceback
import importlib
import sys
import os
import json
import operator
import numpy as np
from threading import Event
from network import Packet

from utils.custom_logging import _DEBUG_LEVEL, debug, error, warning, ok
from utils import custom_logging
import signal
from multiprocessing.queues import Empty
from datetime import datetime

class SupervisedProcessStream():
    def __init__(self, old_std, name):
        self.old_std=old_std
        self.name = name

    def write(self, text):
        text = text.rstrip()
        if len(text) == 0: return
        d = str(datetime.now())+" "
        self.old_std.write(d+ "["+str(self.name)+"] ("+str(os.getpid())+") \t: " + text + '\n')

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
        self.inputConnections = {} #sock: chan
        self.inputQueue = Queue(50)
        self.outputQueue = Queue(50)

        self.outputWorkerLocks = {} #sock: Event
        self.globalOutputLock = Event()
        self.outputs = {} #sock: chan

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

        debug("[STOP] Exiting with code "+str(code), 1)
        self._exitCode = code
        self._inputQueue.close() #triggers exception in main thread causing a check of exitCode
        self.action_halt()

    def checkAction(self, config):
        try:
            if("action" in config.keys()):
                debug("Handling action: "+config['action'])
                action = getattr(self, "action_"+config['action'])
                action()
                return True
        except:
            warning("Unknown action.")
            pass
        return False

    def action_halt(self):
        ok("[HALT] Worker terminated.")
        suicide()

    def action_stop(self):
        self.stop()

    def loadJob(self, jobName):
        try:
            self.jobName = str(jobName)
            debug("Loading Job file: "+str(jobName), 1)
            mod   = importlib.import_module("jobs."+jobName)
            shortName = jobName.split(".")[-1]
            jobCl = getattr(mod, shortName.capitalize())
                #difference btwn import error & load error
            self.job = jobCl.__new__(jobCl)
            self.job.__init__()

            if(not self.job.isJob):
                error(str(jobCl) + " is not a valid Job")
                self.job = None
                self.action_halt()
                return
            debug("Job loaded", 1)

        except:
            if(_DEBUG_LEVEL == 3):
                traceback.print_exc()
            error("Could not load job")
            self.stop(1)

    def updateWithDiff(self, config):
        if(self.checkAction(config)):
            return

        debug("Updating worker...")

        #update port
        if(int(self.server.getsockname()[1]) != int(config['port'])):
            p = int(config['port'])
            debug("Updating worker port to "+str(p))
            self.port = p
            self._closeSock(self.server)
            self._startListener()

        #update job
        if(config['jobname'] != self.jobName):
            debug("Replacing job")
            if("jobreplacemethod" in config):
                if(config['jobreplacemethod'] == "kill"):
                    self.job.shouldStop = True
                    debug("Asked for Job stop")

            debug("Waiting for job shutdown...")
            if(self.jobThread != None):
                self.jobThread.join()

            debug("Installing new job...")
            jobName = config["jobname"]
            jobData = config["jobdata"]
            self.loadJob(jobName)
            self.setupJobAndLaunch(jobData)

        #update network dispatch method
        self.setNetworkMethod(config)
        #TODO plug

    def setNetworkMethod(self, config):
        if("outputmethod" in config):
            if(config['outputmethod'] == "distribute"):
                debug("Output method is set to distribution")
                self.outputmethod = self._distributeOverNetwork
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
        debug("Pushing data", 1)

    def _startListener(self):
        self.listeningThread = Thread(target=self._listenTarget, daemon = True)
        self.listeningThread.start()

    def _startNetwork(self):
        self.brokenOutputs = []
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

        debug("Job is running", 1)

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
        binChan = sock.makefile("wrb") #w for sending back ack
        self.inputConnections[sock]  = binChan
        try:
            while(not self.workerShutdown.value):
                p = Packet()
                p.read(binChan)
                self.inputQueue.put(p) #hold for next packet if Queue is full

        except:
            if(_DEBUG_LEVEL == 3):
                traceback.print_exc()
            warning("Incoming Connection was lost")
        finally:
            self._closeSock(sock)
            del self.inputConnections[sock]
            self.action_halt()

    def _closeSock(self, sock):
        if(not sock._closed):
            try:
                sock.shutdown(socket.SHUT_RDWR)
                sock.close()
            except:
                pass

    def _clientOutTarget(self):
        """
        Sends the Packets to the plugged Workers
        """

        while( (not self.workerShutdown.value or self.jobRunning.value) or not self.outputQueue.empty()):

            try:
                p = self.outputQueue.get(timeout = 1)
            except Empty:
                continue

            if(len(self.outputs) == 0):
                debug("Got output data but nothing is plugged", 1)
                print(str(p)) #FIXME
                continue

            self.outputmethod(p)
            self._outputsClean()

    def _outputsClean(self):
        for sock in self.brokenOutputs:
            del self.outputs[sock]
            del self.outputWorkerLocks[sock]

        self.brokenOutputs.clear()

    def _sendJobCompletionAck(self):
        for chan in self.inputConnections.values():
            try:
                chan.write(b'a') #whatever
                chan.flush()
            except BrokenPipeError:
                warning("input connection closed")

    def _childWorkerAckTarget(self, sock):
        """
        Receives Acknoledgement info: the transmitted Packed has been processed and its ok to send another
        """

        debug("Started ChildWorkerNetworkACK", 3)
        binChan = sock.makefile("rb")
        try:
            while(not self.workerShutdown.value):
                if(binChan.read(1) != b'a' and not self.workerShutdown.value): #magic value
                    raise ValueError("Wrong ack value")

                self.outputWorkerLocks[sock].set()
                debug("Ack from "+str(sock.getpeername()), 3)
                #Let the unblock if it is a distribute network bahaviour
                self.globalOutputLock.set()


        except:
            if(_DEBUG_LEVEL == 3):
                traceback.print_exc()
            warning("Output network callback error", 0)
            self._closeSock(sock)
            return


    ## Network strategies:
    #duplicate: send to all the plugged workers regardless of the availability (the output/input queue grows)
    #distribute: send to an available worker only suspending the job if none os found at the moment

    def _checkNetworkOutputStatus(self):
        if(self.outputmethod == self._duplicateOverNetwork):
            #duplicate: wait for all
            for evt in self.outputWorkerLocks.values():
                debug("Entering Network Wait...",3)
                evt.wait()
                debug("Exiting Network Wait...",3)
        else:
            #distributed wait for one
            flag = True
            for e in self.outputWorkerLocks.values():
                if(e.is_set()):
                    flag = False
                    break

            if(flag):
                debug("Entering Global Network Wait...",3)
                self.globalOutputLock.wait()
                debug("Exiting Global Network Wait...",3)

        #debug("Done waiting for network synchronization", 3)

    def _duplicateOverNetwork(self, p):
        for sock in self.outputs:
            self._sendTo(sock, p)

    def _distributeOverNetwork(self, p):
        for sock in self.outputs:
            if(self.outputWorkerLocks[sock].is_set()):
                self._sendTo(sock, p)
                break

    def _sendTo(self, sock, p):
        binChan = self.outputs[sock]
        try:
            p.send(binChan)

            #Network lock management
            self.outputWorkerLocks[sock].clear()
            self.globalOutputLock.clear()
        except:
            if(_DEBUG_LEVEL == 3):
                traceback.print_exc()

            debug("Output Connection was lost", 0)

            self._closeSock(sock)
            self.brokenOutputs.append(sock)


    def plug(self, addr): #addr is (hostname, port)
        """
        Connect the output of this Worker to the input of another one
        """

        debug("Plugging to "+str(addr))
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(addr)

            binChan = sock.makefile("wb")
            self.outputs[sock] = binChan
            self.outputWorkerLocks[sock] = Event()
            self.outputWorkerLocks[sock].set()
            self.globalOutputLock.set()
            Thread(target=self._childWorkerAckTarget, args=(sock,), daemon = True).start()
            debug("Plugged to "+str(addr))
        except:
            if(_DEBUG_LEVEL == 3):
                traceback.print_exc()

            debug("Could not connect to "+str(addr), 0)

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

                #FIXME: new network archi
                if(self.job.allowDrop() and self.inputQueue.full()):
                    self._clearInputQueue()
                    debug("Input queue overflow", 0)

                data = self.inputQueue.get()

            out = self.job.loop(data)

            self._sendJobCompletionAck()
            self._checkNetworkOutputStatus() #FIXME parameter

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
                            raise TypeError('Can only handle a Packet, npArray & np array dict')

                self.outputQueue.put(p) #Packets to be sent


        self.job.destroy()
        #self.jobRunning.value = False
        debug("Reached end of Launch target")
        self.stop(0)

    def _launchTarget(self):
        try:
            self._doJob()
        except:
            error("Error from job thread", 0)
            traceback.print_exc()
            self.stop(1)


class Job(object):
    '''
    A job to be executed on a Worker
    '''
    isJob = True

    def setup(self, data):
        """
        Setup the job, open ressources
        """
        pass

    def loop(self, data):
        """
        Called when the job has to run, the job can return data
        Either: np.ndarray
                network.Packet
                dictionnary with an optional np array in the 'img' key
        """
        raise NotImplementedError("Main loop not implemented")

    def destroy(self):
        """
        Stop job, close ressources
        """
        pass

    def requireData(self):
        """
        Does this job requires data to run?
        """
        return False

    def allowDrop(self):
        """
        Allow Packets to be dropped if this job is too slow
        """
        return True

def setupWithJsonConfig(config, inputQueue):
    #Worker setup
    if(not "workername" in config.keys()):
        raise ValueError("Workername is not set")
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
        custom_logging._DEBUG_LEVEL = debuglevel

        debug("Debug level is "+str(debuglevel)+" ("+str(custom_logging._DEBUG_DICT[debuglevel])+")", 0)

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
    os.kill(os.getpid(), signal.SIGKILL)

def getJsonFromParameters():
    sys.argv

if __name__ == "__main__":
    """
    The Worker can be launched directly, the configuration must be given in stdin in a single json line
    TODO: pass by argv
    """

    worker = None
    run = True



    #debug("Ready for input")
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
            error("Uncaught exception, abort", 0)
            traceback.print_exc()
            suicide() #cannot stay in this state
