'''
 Handles the network between supervisor and warden and between wardens
 
 @author: WIN32GG
'''
import socket
import traceback
import json

from threading import Thread
import time

######## CONSTANTS DEFINITION ###############
PORT = 55555
SUPERVISOR_BROADCAST = 55556

BIN_RECV_FULL = True

OBJECT_TYPE_SUPERVISOR = 1
OBJECT_TYPE_WARDEN     = 2

NATURE_CONNECTION_OPEN          = -3
NATURE_CONNECTION_CLOSED        = -2
NATURE_ERROR                    = -1
PACKET_TYPE_UNDEFINED           = 0
PACKET_TYPE_WARDEN_STATS        = 1
PACKET_TYPE_PLUG_REQUEST        = 2
PACKET_TYPE_PLUG_ANSWER         = 3
PACKET_TYPE_DATA                = 4
PACKET_TYPE_WORKER_POOL_CONFIG  = 5
PACKET_TYPE_WORKER_POOL_STATUS  = 6
PACKET_TYPE_WARDEN_CONFIG       = 7
#PACKET_TYPE_JOB_FILE = 8


class NetworkHandler:
    '''
     Handled the network between objects on the network
     This class provides the setHandler method that set a callback called when receiving data from the network

    '''

    def __init__(self, objectType, callbackFunction):
        self.objType = objectType
        self.callbackFunc = callbackFunction

        self.mgmThread = None
        self.isRunning = True

        self.connections = [] #Array of Connections this Handler manages

        tgt = None

        if(objectType == OBJECT_TYPE_SUPERVISOR):
            '''
            do the udp broadcast
            '''
            tgt = self._listen
            print("[NETWORK] Object type is SUPERVISOR")
            pass

        if(objectType == OBJECT_TYPE_WARDEN):
            '''
            UDP supervisor broadcast listen (later) or direct connection request from user
            '''
            print("[NETWORK] Object type is WARDEN")
            pass

        self._startManagementThread(tgt)


    def stop(self):
        self.isRunning = False
        self.mgmThread.stop()

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

        c = Connection(s, self.callbackFunc)

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
                self.connections.remove(c)

    def _initConn(self, cr):
        self.connections.append(Connection(cr, self.callbackFunc))


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

    BINARY_DATA_LENGTH_TAG = "binDataLength"
    PACKET_TYPE = "type"

    RESERVED_NAMES = [BINARY_DATA_LENGTH_TAG, PACKET_TYPE]

    def __init__(self):
        self.data = {"type": PACKET_TYPE_UNDEFINED, self.BINARY_DATA_LENGTH_TAG: 0}
        self.binObj = None

    def __str__(self):
        return json.dumps(self.data) + " binHash = "+ (0 if self.binObj == None else hash(self.binObj))

    def __getitem__(self, key):
        if(not key in self.data):
            return None
        return self.data[key]

    def __setitem__(self, key, value):
        if(key in self.RESERVED_NAMES):
            raise KeyError("Key name is reserved")

        self.data[key] = value

    def _validateType(self, typ):
        if(not typ is int):
            raise ValueError("Invalid packet type, use constants")

        if(type < -1 or type > 4):
            raise ValueError("Invalid packet type, use constants")

    def setType(self, typ):
        self._validateType(typ)
        self.data[self.PACKET_TYPE] = typ

    def getType(self):
        return self.data[self.PACKET_TYPE]

    def read(self, txtChan, binChan):

        j = txtChan.readline()

        self.data = json.loads(j)

        binSize = int(self.data[self.BINARY_DATA_LENGTH_TAG])
        if(binSize > 0):
           self._readBinObject(binChan, binSize)


    def _readBinObject(self, binChan, binSize):
        b = b''
        r = 0
        print("[NETWORK] Reading bin object "+str(binSize))
        bufSize = binSize if BIN_RECV_FULL else self.BIN_READ_MAX

        while(r < binSize):
            a = binChan.read(bufSize)

            b += a
            r += len(a)
            #print(r)

        self.binObj = b

    def send(self, txtChan, binChan):
        if(not self.binObj is None and not isinstance(self.binObj, bytes)):
            raise ValueError("Bin obj must be bytes")

        if(self.binObj != None):
            self.data[self.BINARY_DATA_LENGTH_TAG] = len(self.binObj)

        #jObj = json.dumps(self.data)
        #log obj?

        s = json.dumps(self.data)+"\n"
        txtChan.write(s)
        txtChan.flush()

        if(not self.binObj is None):
            binChan.write(self.binObj)
            binChan.flush()



class Connection:
    '''
    Manages a connection
    '''

    def __init__(self, so, callbackFunc):
        '''
        Initialize the Connection pbject with the raw output of sockt.accept() (socket, adrr)
        '''
        self.callback = callbackFunc
        self.sockObj = so
        self.addr    = so.getpeername()

        self.txtChan = self.sockObj.makefile(mode="rw", buffering = -1,   encoding="utf-8") #the command text channel
        self.dataChan= self.sockObj.makefile(mode="rwb", buffering = 0) #the binary data channel

        print("[NETWORK] Created Connection SELF <-> "+str(self.addr))

        self.callback(NATURE_CONNECTION_OPEN, self)
        self.isRunning = True
        self._startManagementThread()

    def stop(self):
        pass

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

                self.callback(p.getType(), p)
            except Exception as e:
                if(not self.isRunning):
                    return
                traceback.print_exc()
                r = self.callback(NATURE_ERROR, e)
                if(not r is None and r):
                    return


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
        self.sockObj.close()
        print("[NETWORK] Closing Connection to "+str(self.addr))
