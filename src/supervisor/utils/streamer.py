'''
Created on 8 févr. 2018

@author: win32gg
'''


import copy
import json
from multiprocessing import Lock
from multiprocessing import Queue
from os import listdir
import os
from os.path import isfile
import traceback

import psutil

import PIL.Image as Image
import numpy as np
import subprocess as sp
from utils.config_checker import checkConfigSanity
from utils.custom_logging import debug, _DEBUG_LEVEL
from worker import Job
from threading import Thread


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



class Streamer:

    """
    The streamer uses ffmpeg to get imags from a video or a url
    Here, each call to get_image will get the next frame in the given source
    """

    def __init__(self, name, url, img_rate, resol):
        self.name = name
        self.url = url.strip()
        self.img_rate = img_rate
        self.resolution = resol
        self.resolution = resTextToTuple(self.resolution)
        self.doResize = type(self.resolution)  == type(())
        #debug("Starting streamer "+str(name), 3)
        self.meta = self.meta_data()
        self.shape = int(self.meta['width']),int(self.meta['height'])
        self.img_count = 0
        self.open()
        self.raw_image_prev = None

        debug("Streamer "+str(name)+" ("+str(url)+") opened: img_rate="+str(self.img_rate)+" prefered_resolution="+str(self.resolution)+" original_resolution="+str(self.shape), 2)
        #prof.exit()

    def meta_data(self):
        #metadata of interest
        metadataOI = ['width','height','avg_frame_rate']

        command = ['ffprobe', '-v' , 'error' ,'-show_format' ,'-show_streams' , self.url]
        pipe  = sp.Popen(command, stdout=sp.PIPE, stderr=sp.PIPE)
        infos = pipe.communicate()[0]
        #infos = pipe.stdout.read()
        infos = infos.decode().split('\n')
        dic = {}
        for info in infos:
            #print(info)
            if info.split('=')[0] in metadataOI and dic.get(info.split('=')[0]) is None:
                print(info)
                dic[info.split('=')[0]] = info.split('=')[1]
        print("-----------------------------")
        print(dic)
        #pipe.terminate()
        self.resolution = (self.resolution[0], int( ( int(dic["height"]) / int(dic["width"]) ) * self.resolution[0] ) )
        return dic


    def get_image(self):
        self.psProcess.resume()
        size = self.shape[0]*self.shape[1]*3

        raw_image = self.pipe.stdout.read(size)
        while np.array_equal(self.raw_image_prev, raw_image) is True:
            raw_image = self.pipe.stdout.read(size)
        self.raw_image_prev = np.copy(raw_image)

        raw_image = self.pipe.stdout.read(size)
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
                   '-re',
                   '-i',self.url,
                   '-r',str(self.img_rate),
                   '-f','image2pipe',
                   '-pix_fmt','rgb24',
                   '-vcodec','rawvideo',
                   '-']

        self.pipe = sp.Popen(command,stdout = sp.PIPE,bufsize=10**8)
        self.psProcess = psutil.Process(pid=self.pipe.pid)
        self.psProcess.suspend()

    def terminate(self):
        self.pipe.stdout.flush()
        self.pipe.terminate()



class RealTimeStreamer(Streamer):
    """
    The real time streamer works like the regular Streamer but skips over frames
    and return an image keeping Real-time impression (laggy but on time)
    """

    def __init__(self, name, url, img_rate, resol):
        Streamer.__init__(self, name, url, img_rate, resol)
        self.lock = Lock()
        self.loadingLock = Lock()
        self.loadingLock.acquire()

        self.currentImage = None
        self.loading = True

        Thread(target=self._imageGetterTarget, daemon=True).start()

    def _imageGetterTarget(self):
        while(True):
            img = Streamer.get_image(self)

            self.lock.acquire()
            self.currentImage = img
            try:
                self.loadingLock.release()
            except:
                pass
            self.lock.release()

            if(type(img) == type(None)):
                return


    def get_image(self): #get self.currentImage safely and in a consistent way regarding Streamer
        if(self.loading):
            self.loadingLock.acquire() #wait for loading
            self.loading = False

        self.lock.acquire()

        i = self.currentImage

        self.lock.release()

        return i
