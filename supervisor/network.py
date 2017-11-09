'''
 Handles the network between supervisor and warden and between wardens
 
 @author: WIN32GG
'''
import socket
import traceback
import json

from threading import Thread
import time
import hashlib

import numpy as np
from worker import _DEBUG_LEVEL

######## CONSTANTS DEFINITION ###############
PORT = 55555
UDP_HANDSHAKE_PORT = 56756

BIN_RECV_FULL = True

OBJECT_TYPE_SUPERVISOR = 1
OBJECT_TYPE_WARDEN     = 2

NATURE_UDP_HANDSHAKE            = "udp_handshake"
NATURE_CONNECTION_OPEN          = "connection_open"
NATURE_CONNECTION_CLOSED        = "connection_closed"
NATURE_ERROR                    = "error"
PACKET_TYPE_UNDEFINED           = "undefined"
PACKET_TYPE_WARDEN_STATS        = "warden_stats"
PACKET_TYPE_PLUG_REQUEST        = "plug_request"
PACKET_TYPE_PLUG_ANSWER         = "plug_answer"
PACKET_TYPE_DATA                = "data"
PACKET_TYPE_WORKER_POOL_CONFIG  = "wp_config"
PACKET_TYPE_WORKER_POOL_STATUS  = "wp_status"
PACKET_TYPE_WARDEN_CONFIG       = "warden_config"
PACKET_TYPE_AUTH                = "auth"
#PACKET_TYPE_JOB_FILE 

'''
Create a Packet holding the image provided as numpy.ndarray
'''
def createImagePacket(npImg):
    p = Packet()
    p.setType(PACKET_TYPE_DATA) 
    p["img"]   = True
    p["shape"] = npImg.shape
    p["dtype"] = npImg.dtype.name
    p["checksum"] = hashlib.sha1(npImg).hexdigest()
    p.binObj = npImg.tobytes()
    
    return p
    
'''
Read the given packet and returns the 
'''
def readImagePacket(pck):
    if(not pck["img"]):
        return None
    
    img = np.frombuffer(pck.binObj, dtype=pck["dtype"])

    #print(hashlib.sha1(img).hexdigest()+" "+pck["checksum"])
    chk = hashlib.sha1(img).hexdigest()
    if(_DEBUG_LEVEL == 3):
        print("Check = "+str(chk))
        
    if(chk != pck["checksum"]):
        raise ValueError("Error in transmission: checksums do not match")
    if(_DEBUG_LEVEL == 3):
        print("Checksum pass")
    
    img = img.reshape(pck["shape"])
    
    return img
    
    
def listenForUDPHandshake(nh):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', UDP_HANDSHAKE_PORT))
   
    print("[NETWORK] Listening for UDP Handshakes")
   
    while True:
        data, addr = sock.recvfrom(1024)
        print("[NETWORK] UDP Handshake from "+str(addr))
        nh.callbackFunc(NATURE_UDP_HANDSHAKE, (addr, data.decode()))
        
def sendUDPHandshake(wid):
    print("[NETWORK] Broadcasting UDP Handshake")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.sendto(wid.encode(encoding='utf_8', errors='strict'), ("<broadcast>", UDP_HANDSHAKE_PORT))

class NetworkHandler:
    '''
     Handled the network between objects on the network
     This class provides the setHandler method that set a callback called when receiving data from the network

    '''

    def __init__(self, objectType, identifier, callbackFunction):
        self.objType = objectType
        self.identifier = identifier
        self.callbackFunc = callbackFunction

        self.mgmThread = None
        self.isRunning = True

        self.connections = [] #Array of Connections this Handler manages

        tgt = None

        if(objectType == OBJECT_TYPE_SUPERVISOR):
           
            print("[NETWORK] Object type is SUPERVISOR")
            print("[NETWORK] Awaiting connection order")

        if(objectType == OBJECT_TYPE_WARDEN):
            '''
            UDP  broadcast then listen direct connection request from user
            '''
            
            print("[NETWORK] Object type is WARDEN")
            sendUDPHandshake(identifier)
            Thread(target = listenForUDPHandshake, args=[self]).start()
            
            tgt = self._listen
            

        self._startManagementThread(tgt)


    def stop(self):
        self.isRunning = False

    def broadcast(self, pck):
        self._cleanConnList()

        for c in self.connections:
            c.send(pck)


    def connect(self, addr):
        '''
        Used by the warden to connect to the sup or another warden
        '''
        print("[NETWORK] Connecting to "+str(addr))
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((addr, PORT))

        c = Connection(s, self.callbackFunc, self)

        self.connections.append(c)
        return c


    def _listen(self):
        '''
        Open socket as listener an wait an incomming connection
        '''

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        server.bind(('', PORT))
        server.listen()

        print("[NETWORK] Listening on "+str(PORT))

        while(self.isRunning):
            self._cleanConnList()
            try:
                cr, adr = server.accept()
                self._initConn(cr)
            except:
                if(not self.isRunning):
                    return
                traceback.print_exc()

    def _cleanConnList(self):
        for c in self.connections:
            if(c.isclosed()):
                c.close()
                self.connections.remove(c)

    def _initConn(self, cr):
        self.connections.append(Connection(cr, self.callbackFunc, self))


    def _startManagementThread(self, tgt):
        '''
        Starts the monitoring for this handler, with the given function target
        '''
        if(tgt == None):
            return

        th = Thread(target = tgt)
        th.daemon = True
        self.mgmThread = th
        th.start()

class Packet:
    '''
    Represents a packet of data
    values can be set or read depending of the callback
    the packet can be sent over a Connection object
    '''

    BIN_READ_MAX = 524288

    BINARY_DATA_LENGTH_TAG = "binLen"
    PACKET_TYPE = "type"

    RESERVED_NAMES = [BINARY_DATA_LENGTH_TAG, PACKET_TYPE]

    def __init__(self):
        self.data = {"type": PACKET_TYPE_UNDEFINED, self.BINARY_DATA_LENGTH_TAG: 0}
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

        self.data[key] = value

    def _validateType(self, typ):
        if(not type(typ) == type("")):
            raise ValueError("Invalid packet type, use constants")
        
        #check type?

    def setType(self, typ):
        self._validateType(typ)
        self.data[self.PACKET_TYPE] = typ

    def getType(self):
        return self.data[self.PACKET_TYPE]

    def read(self, txtChan, binChan):
        #j = txtChan.readline() #OLD method
        l = int.from_bytes(binChan.read(8), 'big')
        j = binChan.read(l).decode(encoding = 'utf-8')        
        
        self.data = json.loads(j)

        binSize = int(self.data[self.BINARY_DATA_LENGTH_TAG])
        if(binSize > 0):
            self._readBinObject(binChan, binSize)


    def _readBinObject(self, binChan, binSize):
        b = b'' 
        r = 0
        
        print("[NETWORK] Reading bin object of "+str(binSize)+" bytes")
        bufSize = binSize if BIN_RECV_FULL else self.BIN_READ_MAX

        while(r < binSize):
            if(len(b) + bufSize > binSize):
                bufSize = binSize - len(b)
            
            a = binChan.read(bufSize)

            b += a
            r += len(a)

        self.binObj = b
        
        print("------ "+str(len(b))+ " for "+str(binSize))

    def send(self, txtChan, binChan):
        if(not self.binObj is None and not isinstance(self.binObj, bytes)):
            raise ValueError("Bin obj must be bytes")

        if(self.binObj != None):
            self.data[self.BINARY_DATA_LENGTH_TAG] = len(self.binObj)
            
        if(_DEBUG_LEVEL == 3):
            print("[DEBUG] OUT: "+str(self))
            
        s = json.dumps(self.data)+"\n"
        
        #NEW SENDING METHOD
        b = b''
        msgb = s.encode(encoding = 'utf-8')
        b += len(msgb).to_bytes(8, 'big')
        b += msgb
        if(self.binObj != None):
            b += self.binObj
        if(_DEBUG_LEVEL == 3):
            print("[DEBUG] Total packet size is "+str(len(b))+" bytes")
        binChan.write(b)
        binChan.flush()
        return
    
        #OLD sending method        
        txtChan.write(s)
        txtChan.flush()

        if(not self.binObj is None):
            binChan.write(self.binObj)
            binChan.flush()


class Connection:
    '''
    Manages a connection
    '''

    def __init__(self, so, callbackFunc, nh):
        
        self.callback = callbackFunc
        self.nethandler = nh
        self.sockObj = so
        self.addr    = so.getpeername()

        self.txtChan = self.sockObj.makefile(mode="rw", buffering = -1,   encoding="utf-8") #the command text channel
        self.dataChan= self.sockObj.makefile(mode="rwb", buffering = 0)                     #the binary data channel

        print("[NETWORK] Created Connection SELF <-> "+str(self.addr))

        self.callback(NATURE_CONNECTION_OPEN, None, conn = self)
        self.isRunning = True
        self._startManagementThread()
        self.sendHandshake(nh.objType, nh.identifier)
        
        
    def sendHandshake(self, objType, iden):
        pck = Packet()
        pck.setType(PACKET_TYPE_AUTH)
        pck["objType"] = objType
        pck["id"] = iden
        self.send(pck)

    def __str__(self):
        return str(self.addr) # +" f="+str(self.sockObj.fileno())

    def __repr__(self):
        return str(self.__str__())
    
    def toJSON(self):
        return str(self)

    def isclosed(self):
        return self.sockObj._closed

    def _startManagementThread(self):
        self.mgmThread = Thread(target = self._mgmTgt)
        self.mgmThread.daemon = True
        self.mgmThread.start()


    def _mgmTgt(self):
        while(self.isRunning):
            try:

                p = Packet()
                p.read(self.txtChan, self.dataChan)

                self.callback(p.getType(), p, conn = self)
            except Exception as e:
                if(not self.isRunning):
                    break
                #if(_DEBUG_LEVEL > 1):
                traceback.print_exc()
                r = self.callback(NATURE_ERROR, e, conn = self)
                if(not r is None and r):
                    break
        
        self.sockObj.close()        
        self.callback(NATURE_CONNECTION_CLOSED, None, conn = self)
        
    def _receive(self):
        '''
        Waits until a packet of data is received
        then calls the the associated handler
        '''
        p = Packet()
        p.read(self.txtChan, self.dataChan)

        return p

    def send(self, pck):
        '''
        Sends the given Packet on this connection's data channel
        Also sends the requested data on the binary channel
        '''
    
        try:
            pck.send(self.txtChan, self.dataChan)

        except Exception as e:
            self.callback(NATURE_ERROR, e)
            traceback.print_exc()


    def close(self):
        self.sockObj.shutdown(socket.SHUT_RDWR)
        self.sockObj.close()
        print("[NETWORK] Closing Connection to "+str(self.addr))

if(__name__ == "__main__"):
    print("Thid file should not be launched directly")