import json
from multiprocessing import Queue
from os import listdir
import os
from os.path import isfile
import traceback

import psutil

import PIL.Image as Image
import copy
import numpy as np
import subprocess as sp
from utils.config_checker import checkConfigSanity
from utils.custom_logging import debug
from worker import Job


def read(fil):
    fd = open(fil, "r")
    d = ""
    
    for k in fd:
        d += k.strip()
        
    fd.close()
    
    return d

def checkMultiStreamerConfigSanity(cfgTxt):
    return checkConfigSanity(cfgTxt, [], ["stream", "options", "folders"])
    
def checkStreamerConfigSanity(cfgTxt):
    return checkConfigSanity(cfgTxt, ["name"], ["url", "path", "resolution", "recursive"])

def getWithDefault(obj, propName, default = None):
    try:
        return getattr(obj, propName)
    except AttributeError:
        try:
            return obj[propName]
        except:
            return default

def resTextToTuple(resText):
    separators = ["x", ":", ";", "/"]
    
    for sep in separators:
        a = resText.split(sep)
        if(len(a) != 2):
            continue
        
        try:
            x, y = int(a[0]), int(a[1])
            return (x, y)
        except:
            continue
        
    return None
        

class Multistreamer(Job):
    
    DEFAULT_RESOLUTION_TAG = "defaut_resolution"
    DEFAULT_IMG_RATE_TAG = "default_img_rate"
    MAX_STREAMERS_TAG = "max_streamers"
    VIDEO_EXTENSION_TAG = "video_extensions"
    
    def destroy(self):
        self._shutdownAllStreamers()
    
    def setup(self, data):
        debug("Starting Multi Streamer...", 2)
        debug("Using config file: "+str(data), 3)
        cfgTxt = read(str(data))
        debug(cfgTxt, 3)
        
        debug("Checking multistreamer config sanity...", 2)
        if(not checkMultiStreamerConfigSanity(cfgTxt)): # pass this point the configuration is considered acceptable
            raise ValueError("Error in configuration")
         
        self.cfg = json.loads(cfgTxt)
        
        self.streamerCount = 0
        self.streamerIndex = 0
        
        self.options =  {
            self.DEFAULT_IMG_RATE_TAG:8,
            self.DEFAULT_RESOLUTION_TAG: (800,600),
            self.MAX_STREAMERS_TAG: 10,
            self.VIDEO_EXTENSION_TAG: ".mp4;.avi"
        }
        
        self.setGlobalOptions(getWithDefault(self.cfg, "options"))
        debug("Config loaded succesfully", 3)
        self.streamers = []
        self.streamerStartQueue = Queue()
        
        debug("Starting streamers...", 3)
    
        if('stream'in self.cfg):
            for streamerInfo in self.cfg['stream']:
                self.startStreamer(streamerInfo)
            
        if('folders' in self.cfg):
            debug("Starting folder exploration...", 3)
            for streamerInfo in self.cfg['folders']:
                if(getWithDefault(streamerInfo, "recursive")):
                    self._recFolderExploration(streamerInfo['path'], streamerInfo)
                    
            while(self.streamerCount < self.options[self.MAX_STREAMERS_TAG] and not self.streamerStartQueue.empty()):
                self._startNewStreamerFromExploration()
                
    def _recFolderExploration(self, folderPath, streamerInfo):
        for b in listdir(folderPath):
            file = os.path.abspath(folderPath)+os.path.sep+b
            if(os.path.isfile(file)):
                if(os.path.splitext(file)[1] in self.options[self.VIDEO_EXTENSION_TAG]):
                    info = copy.copy(streamerInfo)
                    info['path'] = file
                    self.streamerStartQueue.put(info)
                    debug("Found: "+file, 3)
            else:
                self._recFolderExploration(file, streamerInfo)
            
            
    def _shutdownAllStreamers(self):
        debug("Stopping all streamers", 2)
        for streamer in self.streamers:
            streamer.terminate()
            

    def setGlobalOptions(self, cfgOptions):
        if(cfgOptions == None):
            return
        #FIXME overwritting
        self.options = cfgOptions
        
    def _startNewStreamerFromExploration(self):
        try:
            streamerInfo =  self.streamerStartQueue.get(False)
        except:
            return None
        
        try:
            self.startStreamer(streamerInfo)
        except:
            traceback.print_exc()
    
    def startStreamer(self, streamerInfo):
        if(not checkStreamerConfigSanity(json.dumps(streamerInfo))):
            raise ValueError("Error in configuration")        
        
        resolution = getWithDefault(streamerInfo, "resolution", self.options[self.DEFAULT_RESOLUTION_TAG])
        img_rate   = getWithDefault(streamerInfo, "img_rate", self.options[self.DEFAULT_IMG_RATE_TAG])
        name       = getWithDefault(streamerInfo, "name", "streamer"+str(self.streamerCount))
        location   = getWithDefault(streamerInfo, "url")
        if(location == None):
            location = getWithDefault(streamerInfo, "path")
        
        streamer = Streamer(name, location, img_rate, resolution)
        self.streamers.append(streamer)
        self.streamerCount += 1
    
    def loop(self, data):    
        img = None
        while type(img) == type(None):
            if(self.streamerIndex >= len(self.streamers)):
                self.streamerIndex = 0
                
            streamer = self.streamers[self.streamerIndex]
            
            img = streamer.get_image()
            if(type(img) == type(None)):
                self.streamers.remove(streamer)
                print("Streamer "+streamer.name+" is done reading")
                self._startNewStreamerFromExploration()
                
                if(len(self.streamers) == 0):
                    debug("Reached end of multistreamer job, successfull exit", 2)
                    self.shouldStop = True
                    return None
                
        img2 = np.array(Image.fromarray(img))
        
        self.streamerIndex += 1
        return {
                "from" : str(streamer.name),
                "frame_count": str(streamer.img_count),
                "img": img2
            } 
    

class Streamer:
    def __init__(self, name, url, img_rate, resol):
        self.name = name
        self.url = url.strip()
        self.img_rate = img_rate
        self.resolution = resol
        self.resolution = resTextToTuple(self.resolution)
        self.doResize = type(self.resolution)  == type(())
        debug("Starting streamer "+str(name), 3)
        infos = self.meta_data()
        self.shape = int(infos['width']),int(infos['height'])
        self.img_count = 0
        self.open()
        
        debug("Streamer "+str(name)+" ("+str(url)+") opened: img_rate="+str(self.img_rate)+" prefered_resolution="+str(self.resolution)+" original_resolution="+str(self.shape), 3)

    def meta_data(self):
        #metadata of interest
        metadataOI = ['width','height']

        command = ['ffprobe', '-v' , 'error' ,'-show_format' ,'-show_streams' , self.url]
        
        
        pipe  = sp.Popen(command, stdout=sp.PIPE, stderr=sp.PIPE)
        infos = pipe.communicate()[0]
        #infos = pipe.stdout.read()
        infos = infos.decode().split('\n')
        dic = {}
        for info in infos:
            if info.split('=')[0] in metadataOI:
                dic[info.split('=')[0]] = info.split('=')[1]
        #pipe.terminate()
        #print(str(dic))
        return dic
    
    def get_image(self):
        self.psProcess.resume()
        raw_image = self.pipe.stdout.read(self.shape[0]*self.shape[1]*3)
        image = np.fromstring(raw_image,dtype='uint8')

        if image.shape[0] == 0:
            return None

        image = image.reshape((self.shape[1],self.shape[0],3))
        
        
        self.pipe.stdout.flush()
        self.psProcess.suspend()
        
        if(self.doResize):
            image = np.array(Image.fromarray(image, 'RGB').resize(self.resolution))
        
        self.img_count += 1
        return image


    def open(self):
        command = ['ffmpeg',
                   '-i',self.url,
                   '-r',str(self.img_rate),
                   '-f','image2pipe',
                       '-pix_fmt','rgb24',
                       '-vcodec','rawvideo','-']

        self.pipe = sp.Popen(command,stdout = sp.PIPE,bufsize=10**8)
        self.psProcess = psutil.Process(pid=self.pipe.pid)
        self.psProcess.suspend()

    def terminate(self):
        self.pipe.stdout.flush()
        self.pipe.terminate()
       
    
