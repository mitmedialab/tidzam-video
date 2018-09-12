from utils.custom_logging import debug, ok, warning, error
from worker import Job

import datetime
import json
import urllib.request, ssl
import threading
import os,sys,shutil
import pymediainfo

import traceback

stored_video = []
def download_video(url, path):
    debug("Prepare video loading ("+url+")",3)
    tmp_path = urllib.request.urlretrieve (url)[0]
    video_info = pymediainfo.MediaInfo.parse(tmp_path)
    video_type = video_info.to_data()["tracks"][0]["internet_media_type"]

    if "video" not in video_type:
        error("The downloaded file is not a valid video ("+url+")")
        return
    path += "."+video_type.split("/")[1]
    shutil.move(tmp_path, path)
    debug("Video saved in "+ path, 0)

class Storage(Job):

    def setup(self, data):
        try:
            if os.path.isdir(data["storage_path"]) is False:
                raise Exception('Invalid storage path.')
        except:
            error("A valid storage path must be defined, please read the doc. ("+data["storage_path"]+")")
            sys.exit(-1)

        self.storage_path = data["storage_path"]
        ssl._create_default_https_context = ssl._create_unverified_context

    def loop(self, packet):
        if packet.data["detection"] == []:
            return

        filename = "['tidzam-video']("
        filename += "-".join(packet.data["from"].split("-")[:-1])
        filename += ")_"+datetime.datetime.utcfromtimestamp(packet.data["meta"]["startTime"]/1000).strftime('%Y-%m-%dT%H:%M:%S')
        filename = os.path.join(self.storage_path,filename)

        # Retrieve the video file
        if filename not in stored_video:
            stored_video.append(filename)
            threading.Thread(
                target=download_video,
                kwargs=dict(url=packet.data["path"],path=filename )
                ).start()


        if os.path.isfile(filename+".json") is False:
            with open(filename+".json", "w") as f:
                json.dump([], f)

        # Store the detections
        with open(filename+".json", "r+") as f:
            data_json = json.loads(str(f.read()))

            data_json.append(packet.data)
            f.seek(0)
            f.write(json.dumps(data_json))
            f.truncate()

    def requireData(self):
        return True
