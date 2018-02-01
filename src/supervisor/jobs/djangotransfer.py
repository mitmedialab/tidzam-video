'''
@author: win32gg
'''
from worker import Job
from utils.custom_logging import debug
import websockets
import asyncio
import json

class Djangotransfer(Job):
    
    async def sendImage(self, imagePacket):
        url = "ws://"+self.config['server']
    
        async with websockets.connect(url) as ws:
            debug("Connected to "+str(url), 3)
            await ws.send(self.config['auth_key'])
            debug("Sent authentication key", 3)

            await ws.send(imagePacket.binObj)
            debug("Image sent", 3)


    def setup(self, data):
        
        self.config = {
                "server": "127.0.0.1:8000/push/",
                "auth_key": "5edb6a02bc2c1a6ecd1e2c7f30b80d6f",
            }
        
        self.eventLoop = asyncio.new_event_loop()
        

    def loop(self, data):
        self.eventLoop.run_until_complete(self.sendImage(data))
        
    def destroy(self):
        pass
    
    def requireData(self):
        return True
  
        