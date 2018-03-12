from worker import Job
from utils.custom_logging import debug, ok, warning, error

import bson
import json
import threading
import inspect

import io
from PIL import Image
import numpy as np

from SimpleWebSocketServer import SimpleWebSocketServer, WebSocket

# This function convert the inline RGB image into JPEG readable image
def build_packet(packet, format='JPEG'):
    inBytes = io.BytesIO()
    inBytes.write(packet.binObj)
    inBytes.seek(0)
    img = np.load(inBytes)['arr_0']
    img = img.reshape(packet.data["shape"])

    pil_raw    = Image.fromarray(img)
    imgByteArr = io.BytesIO()
    pil_raw.save(imgByteArr, format)
    packet.img = imgByteArr.getvalue()
    return packet

# Broadcast all processed image frame as BSON object to the clients
class Websocket(Job):
    def setup(self, data):
        thread = threading.Thread(target = start_server, args=(data["port"],))
        thread.start()

    def loop(self, packet):
        try:
            packet = build_packet(packet)

            for client in clients_debug:
                client.sendMessage(bson.dumps({"meta":packet.data,"img":packet.img}))

            for client in clients:
                client.sendMessage(bson.dumps({"meta":packet.data}))
        except:
            warning("Unable to process packet")

    def destroy(self):
        pass

    def requireData(self):
        return True

# Register all websocket clients
clients = []
clients_debug = []
class WSserver(WebSocket):

    def handleMessage(self):
       for client in clients:
          if client != self:
             client.sendMessage(self.address[0] + u' - ' + self.data)

    def handleConnected(self):
        debug(str(self.address) + ' connected on ' + str(self.request.path), 2)
        if self.request.path == '/':
            clients.append(self)
        elif self.request.path == '/debug/':
            clients_debug.append(self)

    def handleClose(self):
        debug(str(self.address) + ' closed', 2)
        if self in clients:
            clients.remove(self)

        if self in clients_debug:
            clients_debug.remove(self)

def start_server(port):
    ok("Web Socket server on "+str(port)+" [STARTED]")
    server = SimpleWebSocketServer('', port, WSserver)
    server.serveforever()
