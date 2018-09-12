import urllib3
import urllib3.request
import json
import traceback
import threading
import collections
import numpy as np

from worker import Job
from utils.custom_logging import debug,error,warning,ok, _DEBUG_LEVEL
from SimpleWebSocketServer import SimpleWebSocketServer, WebSocket
from jobs.multistreamer import checkStreamerConfigSanity

http        = urllib3.PoolManager()
requests    = collections.deque()
clients     = []
unify       = {}
class Unifyvideo(Job):


    def unify(self, req):
        try:
            print(req["unify"])
            response = http.request("GET", req["unify"] + '/api/2.0/recording',fields=req)
            items = json.loads(response.data.decode('utf8'))
            debug("Connected to " + req["unify"] + "("+str(len(items['data']))+" available videos)",1)
        except:
            debug("Unable to connect to " + req["unify"],0)
            return None

        for r in items['data']:
            if "locked" in req:
                if req["locked"] == True and r["locked"] == False:
                    continue
            requests.append({
                    "name":r["meta"]["cameraName"]+"-"+str(r["endTime"]),
                    "url":req["unify"] + '/api/2.0/recording/'+r["_id"]+'/download?apiKey='+req["apiKey"],
                    "startTime":r["startTime"],
                    "endTime":r["endTime"]
                    })

    def setup(self, conf):
        self.conf = conf

        # Start web socket server for incoming configuration
        self.thread = threading.Thread(target = start_server, args=(self.conf["port-ws"],))
        self.thread.start()

        # Load the
        for req in conf["streams"]:
            if "unify" in req:
                self.unify(req)
            else:
                requests.append(req)

    def loop(self, data):
        try:
            r = requests.pop()
            #debug("ici,="+str(len(requests)),0)
            return r
        except IndexError:
            pass
        return

    def requireData(self):
        return False

    def destroy(self):
        return


# Register all websocket clients
class WSserver(WebSocket):
    @staticmethod
    def client_broadcast(message):
        for client in clients:
            client.sendMessage(message)

    def handleMessage(self):
        try:
            #print(self.data)
            data = json.loads(self.data)

            if "unify" in data:
                Unifyvideo.unify(None,data)
                debug("Incoming unify server request." + str(data["unify"]), 1)
                self.sendMessage( json.dumps({"unifyvideo":{"stream-add":data["unify"]}}) )

            elif "get_list" in data:
                self.sendMessage( json.dumps({"get_list":list(requests)} ) )

            elif "del_list" in data:
                requests.clear()
                self.sendMessage( json.dumps({"get_list":list(requests)} ) )

            elif(checkStreamerConfigSanity(self.data)):
                requests.append(json.loads(self.data))
                debug("Incoming url server request." + str(data["url"]), 1)
                self.sendMessage( json.dumps({"unifyvideo":{"stream-add":data["url"]}}))
            else:
                debug("Bad configuration received on unify websocket" + self.data)
                self.sendMessage( json.dumps({"unifyvideo": {"error":"Bad request", "req":self.data} } ))
        except:
            debug("Bad configuration received on unify websocket" + self.data)
            self.sendMessage( json.dumps( {"unifyvideo": {"error":"Bad request", "req":self.data} } ))


    def handleConnected(self):
        debug(str(self.address) + ' connected on ' + str(self.request.path), 1)
        if self.request.path == '/unify/':
            clients.append(self)

    def handleClose(self):
        debug(str(self.address) + ' closed', 1)
        if self in clients:
            clients.remove(self)

def start_server(port):
    ok("Web Socket server on "+str(port)+" [STARTED]")
    server = SimpleWebSocketServer('', port, WSserver)
    server.serveforever()
