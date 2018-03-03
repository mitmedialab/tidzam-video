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
        packet = build_packet(packet)

        for client in clients:
            client.sendMessage(bson.dumps({"meta":packet.data,"img":packet.img}))

    def destroy(self):
        pass

    def requireData(self):
        return True

# Register all websocket clients
clients = []
class WSserver(WebSocket):

    def handleMessage(self):
       for client in clients:
          if client != self:
             client.sendMessage(self.address[0] + u' - ' + self.data)

    def handleConnected(self):
       debug(str(self.address) + ' connected', 2)
       for client in clients:
          client.sendMessage(self.address[0] + u' - connected')
       clients.append(self)

    def handleClose(self):
       clients.remove(self)
       debug(str(self.address) + ' closed', 2)
       for client in clients:
          client.sendMessage(self.address[0] + u' - disconnected')

def start_server(port):
    ok("Web Socket server on "+str(port)+" [STARTED]")
    server = SimpleWebSocketServer('', port, WSserver)
    server.serveforever()
