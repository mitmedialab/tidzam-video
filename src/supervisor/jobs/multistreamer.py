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
    return checkConfigSanity(cfgTxt, ["name"], ["url", "path", "resolution", "recursive", "realtime","binLen", "startTime","endTime"])

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
        self.cfg        = {}
        self.streamers  = []
        self.streamerStartQueue = Queue()
        self.streamerCount = 0
        self.streamerIndex = 0

        self.options =  {
            self.DEFAULT_IMG_RATE_TAG:8,
            self.DEFAULT_RESOLUTION_TAG: "800x600",
            self.MAX_STREAMERS_TAG: 2,
            self.VIDEO_EXTENSION_TAG: ".mp4;.avi",
            self.REALTIME_TAG: 1
        }

        debug("Starting Multi Streamer...", 2)
        debug("Using config file: "+str(data), 3)
        if (str(data) != ""):
            cfgTxt = read(str(data))

            debug(cfgTxt, 3)

            debug("Checking multistreamer config sanity...", 2)
            if(not checkMultiStreamerConfigSanity(cfgTxt)): # pass this point the configuration is considered acceptable
                raise ValueError("Error in configuration")

            self.cfg = json.loads(cfgTxt)
            self.setGlobalOptions(getWithDefault(self.cfg, "options"))
            debug("Config loaded succesfully", 3)


            if('stream'in self.cfg):
                for streamerInfo in self.cfg['stream']:
                    self.streamerStartQueue.put(streamerInfo)
                    #self.startStreamer(streamerInfo)

            if('folders' in self.cfg):
                #prof.enter("FOLDER_EXPLORATION")
                debug("Starting folder exploration...", 3)
                self.load_folder(self, self.cfg['folders'])

                #prof.exit()
            while(self.streamerCount < self.options[self.MAX_STREAMERS_TAG] and not self.streamerStartQueue.empty()):
                self.loadStreamFromQueue()
        ok("Multi streamers process ready.")

    def load_folder(self, conf):
        for streamerInfo in conf:
            if(getWithDefault(streamerInfo, "recursive")):
                self._recFolderExploration(streamerInfo['path'], streamerInfo)

    def _recFolderExploration(self, folderPath, streamerInfo):
        try:
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
        except FileNotFoundError:
            debug("No such file or directory: " + folderPath,1)

    def _shutdownAllStreamers(self):
        debug("Stopping all streamers", 2)
        for streamer in self.streamers:
            streamer.terminate()


    def setGlobalOptions(self, cfgOptions):
        if(cfgOptions == None):
            return
        #FIXME overwritting
        self.options = cfgOptions

    def loadStreamFromQueue(self):
        debug("Looking for the next stream in pool...", 3)
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

            try:
                streamer.meta["startTime"] = streamerInfo["startTime"]
                streamer.meta["endTime"]   = streamerInfo["endTime"]
            except:
                debug("No information on starting and ending time on stream" + name, 2)

        except:
            warning("Cannot start streamer "+name+" ("+str(location)+")", 0)
            if(_DEBUG_LEVEL >= 3):
                traceback.print_exc()
            return False

        self.streamers.append(streamer)
        self.streamerCount += 1
        return True

    def loop(self, data):
        # Add the configuration received through the tidzam chain
        if data is not None:
            if "path" in data.data:
                self.load_folder([data.data])
            else:
                self.streamerStartQueue.put(data.data)

        # Select one frame from the available streamer and send it to the next node in tidzam chain
        img = None
        while type(img) == type(None):
            # Try to load new streamers if necessary
            while(len(self.streamers) < self.options[self.MAX_STREAMERS_TAG] and not self.streamerStartQueue.empty()):
                self.loadStreamFromQueue()

            # If there is no more streamer, there is no more video to process
            if(len(self.streamers) == 0):
                return None

            # Select one streamer and extract the frame
            if(self.streamerIndex >= len(self.streamers)):
                self.streamerIndex = 0

            streamer = self.streamers[self.streamerIndex]
            img = streamer.get_image()

            # If there is no frame, this is the end of the stream.
            if(type(img) == type(None)):
                self.streamers.remove(streamer)
                debug("Streamer "+streamer.name + " is terminated.",1)



        img2 = np.array(Image.fromarray(img))

        self.streamerIndex += 1
        return {
                "from" : str(streamer.name),
                "path" : str(streamer.url),
                "frame_count": str(streamer.img_count),
                "img": img2,
                "meta": streamer.meta
            }
