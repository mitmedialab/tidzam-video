'''
Created on 28 nov. 2017

@author: WIN32GG
'''

import hashlib
import json
import struct

from customlogging import _DEBUG_LEVEL
from customlogging import debug
import numpy as np
import time
import io

OK = "ok"

def readString(fo):
    header = struct.Struct("i")
    l = header.unpack(fo.read(header.size))[0]
    return fo.read(l).decode(encoding="utf-8")
    
def sendString(fo, string):
    b = string.encode(encoding="utf-8")
    fo.write(struct.pack("i", len(b)))
    fo.write(b)
    fo.flush()
    

'''
Create a Packet holding the image provided as numpy.ndarray
'''
def createImagePacket(p, npImg):
    p["isImage"]   = True
    p["shape"] = npImg.shape
    p["dtype"] = npImg.dtype.name
    p["checksum"] = hashlib.sha1(npImg).hexdigest()
    
    #compression
    stream = io.BytesIO()
    np.savez_compressed(stream, npImg)
    stream.seek(0)
    
    p.binObj = stream.read()
    
    return p
    
'''
Read the given packet and returns the 
'''
def readImagePacket(pck):
    if(not pck["isImage"]):
        return None
    
    #img = np.frombuffer(pck.binObj, dtype=pck["dtype"])
    inBytes = io.BytesIO()
    inBytes.write(pck.binObj)
    inBytes.seek(0)
    
    img = np.load(inBytes)['arr_0']

    #print(hashlib.sha1(img).hexdigest()+" "+pck["checksum"])
    chk = hashlib.sha1(img).hexdigest()
    if(_DEBUG_LEVEL == 3):
        print("Check = "+str(chk))
        
    if(chk != pck["checksum"]):
        raise ValueError("Error in transmission: checksums do not match")
    if(_DEBUG_LEVEL == 3):
        print("Checksum pass")
    
    img = img.reshape(pck["shape"])
    
    pck.img = img


class Packet:
    '''
    Represents a packet of data
    values can be set or read depending of the callback (Job)
    the packet can be sent over a Connection object
    '''

    BIN_READ_MAX = 524288
    BIN_RECV_FULL = True

    BINARY_DATA_LENGTH_TAG = "binLen"

    RESERVED_NAMES = [BINARY_DATA_LENGTH_TAG]

    def __init__(self):
        self.data = { self.BINARY_DATA_LENGTH_TAG: 0}
        self.binObj = None

    def __str__(self):
        return json.dumps(self.data) + " binHash = "+ ("0" if self.binObj == None else str(hash(self.binObj)))

    def __getitem__(self, key):
        if(not key in self.data):
            return None
        return self.data[key]

    def __setitem__(self, key, value):
        if(key in self.RESERVED_NAMES):
            raise KeyError("Key name is reserved")

        #TODO check types

        if(key in ["img", "image", "bin"]):
            createImagePacket(self, value)
            return

        self.data[key] = value


    def read(self, binChan):
        l = int.from_bytes(binChan.read(8), 'big') #moins lourd qu'un struct
        j = binChan.read(l).decode(encoding = 'utf-8')        
        
        self.data = json.loads(j)

        binSize = int(self.data[self.BINARY_DATA_LENGTH_TAG])
        if(binSize > 0):
            self._readBinObject(binChan, binSize)
        
        readImagePacket(self)
            
    def _readBinObject(self, binChan, binSize):
        b = b'' 
        r = 0
        
        debug("[NETWORK] Reading bin object of "+str(binSize)+" bytes", 3)
        bufSize = binSize if self.BIN_RECV_FULL else self.BIN_READ_MAX
        st = time.time()
        while(r < binSize):
            if(len(b) + bufSize > binSize):
                bufSize = binSize - len(b)
            
            a = binChan.read(bufSize)

            b += a
            r += len(a)
        debug("READ "+str(len(b)) +" in "+str(time.time()-st), 3)
        self.binObj = b
        

    def send(self, binChan):
        if(not self.binObj is None and not isinstance(self.binObj, bytes)):
            raise ValueError("Bin obj must be bytes")

        if(self.binObj != None):
            self.data[self.BINARY_DATA_LENGTH_TAG] = len(self.binObj)
            
        debug("[DEBUG] OUT: "+str(self), 3)
            
        s = json.dumps(self.data)+"\n"
        
        #SENDING
        b = b'' #message buffer
        msgb = s.encode(encoding = 'utf-8')
        b += len(msgb).to_bytes(8, 'big')
        b += msgb
        if(self.binObj != None):
            b += self.binObj
            
        debug("[DEBUG] Total packet size is "+str(len(b))+" bytes", 3)
        binChan.write(b)
        binChan.flush()
    