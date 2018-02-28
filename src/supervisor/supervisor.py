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

from utils import config, custom_logging
from utils import config_checker
from utils.custom_logging import debug, _DEBUG_LEVEL, error, warning
import network
import worker
import sys
import time
import subprocess as sp

def suicide():
    os.kill(os.getpid(), signal.SIGTERM)

class Supervisor():
    '''
    The supervisor that handles the workers
    '''

    def __init__(self):
        sys.stdout = worker.SupervisedProcessStream(sys.stdout, "SUPERVISOR")
        sys.stderr = worker.SupervisedProcessStream(sys.stderr, "SUPERVISOR")

        self.workers = {}
        self.running = True
        self.stopping = False
        self.workerConfig = {}

        self.startSupervisorServer()

    def stop(self):
        if(self.stopping):
            return
        self.stopping = True

        debug("Got STOP request, stopping...")
        self.running = False

        debug("[STOP] Stopping workers")
        for proc in self.workers.values():
            proc.terminate()

        debug("[STOP] Closing server")
        self.server.close()

        debug("[STOP] Terminating in 0.25 sec")
        time.sleep(.25)

        suicide()

    def startSupervisorServer(self):
        Thread(target=self._listenTarget).start()

    def _listenTarget(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.server.bind(('', config.SUPERVISOR_PORT))
            self.server.listen(4)
            debug("Started Supervisor Server")
            while(self.running):
                client, addr = self.server.accept()
                debug("Connection from "+str(addr))

                Thread(target=self._clientTarget, args=(client,)).start()

        except:
            error("Supervisor Server Shutting down", 0)
            traceback.print_exc()
            self.server.close()
            suicide()

    def action_halt(self):
        suicide()
        return network.OK

    def action_stop(self):
        self.stop()
        return network.OK

    def action_status(self):
        return json.dumps(list(self.workerConfig.values()))

    def _detectSpecialAction(self, cmd):
        try:
            cmd = json.loads(cmd)
            if(not "action" in cmd.keys()):
                return None

            if("workername" in cmd.keys()): #action is for a worker
                return None

            actionName = "action_"+cmd['action']

            if(not hasattr(self, actionName)):
                return "Action not found"

            try:
                return getattr(self, actionName)()
            except Exception as ex:
                traceback.print_exc()
                return "err "+repr(ex)
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

        warning("Closing client connection", 1)
        sock.shutdown(socket.SHUT_RDWR)
        sock.close()

    def startWorker(self, workerConfig, name):
        Thread(target=self._workerManagementThreadTarget, args=(workerConfig, name)).start()

    def handleConfigInput(self, workerConfig):
        cfgObj = json.loads(workerConfig)
        if(not 'workername' in cfgObj):
            raise ValueError('The worker name is mandatory')

        name = cfgObj['workername']
        action = False
        if("action" in cfgObj.keys()):
            debug("Got action for worker, skipping config check")
            action = True
        else:
            debug("Checking config...")
            if(not config_checker.checkWorkerConfigSanity(workerConfig)):
                return
            debug("Config is OK")

        if(name in self.workers):
            debug("Worker found: "+name)
            self._sendToWorker(name, workerConfig)
        else:
            if(action):
                raise ValueError('The worker must exist to pass an action to it')
            self.startWorker(workerConfig, name)

        time.sleep(1)

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
    debug("Ready for input")
    while(True):
        try:
            l = input().strip()
            try:
                json.loads(l)
            except Exception as exc:
                if(_DEBUG_LEVEL >= 3):
                    traceback.print_exc()
                debug('Invaiid Configuration provided', 0, True)


            act = sup._detectSpecialAction(l)
            if(act):
                print(act)
                continue

            sup.handleConfigInput(l)
        except KeyboardInterrupt:
            sup.stop()

        except:
            if(not sup.running):
                break
            traceback.print_exc()
