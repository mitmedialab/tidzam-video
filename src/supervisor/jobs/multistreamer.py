import copy
import json
from multiprocessing import Queue
from os import listdir
import os
from utils.config_checker import checkConfigSanity
from utils.custom_logging import debug,error,warning,ok, _DEBUG_LEVEL
from utils.streamer import *
from worker import Job


#import utils.custom_logging.#profiler as #prof
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
    return checkConfigSanity(cfgTxt, ["name"], ["url", "path", "resolution", "recursive", "realtime"])

def getWithDefault(obj, propName, default = None):
    try:
        return getattr(obj, propName)
    except AttributeError:
        try:
            return obj[propName]
        except:
            return default



class Multistreamer(Job):

    DEFAULT_RESOLUTION_TAG = "defaut_resolution"
    DEFAULT_IMG_RATE_TAG = "default_img_rate"
    MAX_STREAMERS_TAG = "max_streamers"
    VIDEO_EXTENSION_TAG = "video_extensions"
    REALTIME_TAG = "realtime"

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
            self.VIDEO_EXTENSION_TAG: ".mp4;.avi",
            self.REALTIME_TAG: 1
        }

        self.setGlobalOptions(getWithDefault(self.cfg, "options"))
        debug("Config loaded succesfully", 3)
        self.streamers = []
        self.streamerStartQueue = Queue()

        ok("Starting streamers...")

        if('stream'in self.cfg):
            for streamerInfo in self.cfg['stream']:
                self.startStreamer(streamerInfo)

        if('folders' in self.cfg):
            #prof.enter("FOLDER_EXPLORATION")
            debug("Starting folder exploration...", 3)
            for streamerInfo in self.cfg['folders']:
                if(getWithDefault(streamerInfo, "recursive")):
                    self._recFolderExploration(streamerInfo['path'], streamerInfo)

            #prof.exit()
            while(self.streamerCount < self.options[self.MAX_STREAMERS_TAG] and not self.streamerStartQueue.empty()):
                self._startNewStreamerFromExploration()


    def _recFolderExploration(self, folderPath, streamerInfo):
        for b in listdir(folderPath):
            file = os.path.abspath(folderPath)+os.path.sep+b
            if(os.path.isfile(file)):
                if(os.path.splitext(file)[1] in self.options[self.VIDEO_EXTENSION_TAG]):
                    info = copy.copy(streamerInfo)
                    info['path'] = file
                    info['name'] = info['name']+os.path.basename(file)
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
        debug("Cycling through videos...", 3)
        try:
            streamerInfo =  self.streamerStartQueue.get(False)
        except:
            return None

        try:
            return self.startStreamer(streamerInfo)
        except:
            traceback.print_exc()

    def startStreamer(self, streamerInfo):
        if(not checkStreamerConfigSanity(json.dumps(streamerInfo))):
            raise ValueError("Error in configuration")

        resolution = getWithDefault(streamerInfo, "resolution", self.options[self.DEFAULT_RESOLUTION_TAG])
        img_rate   = getWithDefault(streamerInfo, "img_rate", self.options[self.DEFAULT_IMG_RATE_TAG])
        name       = getWithDefault(streamerInfo, "name", "streamer"+str(self.streamerCount))
        location   = getWithDefault(streamerInfo, "url")
        realtime   = getWithDefault(streamerInfo, "realtime", self.options[self.REALTIME_TAG])

        if(location == None):
            location = getWithDefault(streamerInfo, "path")

        try:
            if(realtime):
                streamer = RealTimeStreamer(name, location, img_rate, resolution)
            else:
                streamer = Streamer(name, location, img_rate, resolution)

        except:
            warning("Cannot start streamer "+name+" ("+str(location)+")", 0)
            if(_DEBUG_LEVEL >= 3):
                traceback.print_exc()
            return False

        self.streamers.append(streamer)
        self.streamerCount += 1
        return True

    def loop(self, data):
        img = None
        while type(img) == type(None):
            if(self.streamerIndex >= len(self.streamers)):
                self.streamerIndex = 0

            if(len(self.streamers) == 0):
                return None

            streamer = self.streamers[self.streamerIndex]
            img = streamer.get_image()

            # If there is no frame, this is the end of the stream.
            if(type(img) == type(None)):
                self.streamers.remove(streamer)
                debug("Streamer "+streamer.name + " is terminated.",1)
                while(len(self.streamers) < self.options[self.MAX_STREAMERS_TAG] and not self.streamerStartQueue.empty()):
                    self._startNewStreamerFromExploration()

                # If there is no more streamer, there is no more video to process
                if(len(self.streamers) == 0):
                    ok("Reached end of multistreamer job, successfull exit")
                    self.shouldStop = True
                    return None


        img2 = np.array(Image.fromarray(img))

        self.streamerIndex += 1
        return {
                "from" : str(streamer.name),
                "path" : str(streamer.url),
                "frame_count": str(streamer.img_count),
                "img": img2,
                "meta": streamer.meta
            }
