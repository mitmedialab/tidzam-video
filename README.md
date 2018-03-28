<img src="imgs/logo.png" width="30%">
# Introduction
<a href="https://www.youtube.com/watch?v=lvAROVP-RQ8"><img src="https://img.youtube.com/vi/lvAROVP-RQ8/0.jpg" width="30%" style="float:right;"></a>
<div>
Tidzam-video is a system component for the wildlife tracking during an ecological documentation of a wetland restoration program of a large scale industrial cramberry farm Tidmarsh located in the south of Massachusetts. This system analysis in real-time the different cameras deployed on site in order to detect, identify and geolocalize wildlife activity all over the year.
More informations about Tidmarch can be found at [http://www.livingobservatory.org/](http://www.livingobservatory.org/)  and [http://tidmarsh.media.mit.edu/](http://tidmarsh.media.mit.edu/)
</div>

<div style="float:none">
Based on the recent improvement in Computer Vision and more precisely based on Yolo2, this piece of software allows such classifier to be integrated in a cluster based infrastructure as illustrated in following figure. Several types of workers can be configured and connected together over the network in order to process in parallel multiple of input video streams:
<ul>
<li> <strong>Websocket</strong> is a websocket interface which broadcasts to the clients the detection and boxing informations regarding the frames of processed streams.</li>
<li> <strong>Classifier</strong> receives incoming frame and analyzes them in order to provide boxing around the identified objects (based on Yolo2)</li>
<li> <strong>Streamer</strong> receives incoming stream url requests in order to load them and extract the frames which are transmitted to the classifiers.</li>
<li> <strong>Unify</strong> is a websocket interface in order to add new video streams which should be processed by Tidzam. This job can be also configured for communicating with a unify-video server.</li>
</ul>
</div>

<center>
<img src="imgs/tidzam-video.png" width="90%">
</center>

# Usage
Each machines which are part of the Tidzam-video cluster, the supervisor should be started by the following command. It will received its works and jobs configuration from the master node.
```
tidzam-video init
```
The master node sents the workers, jobs and networks configurations to the different supervisors running on the cluster's machines through the following command:
```
tidzam-video start cfg/config.json
```
Stopping the   supervisor on a server with its workers:
```
tidzam-video stop
```

## Configuration Example
The first section "units" defines the list of server members of the Tidzam-video cluster. The "workers" section defines the location of the workers, their jobs, their initial configurations and their outputs.
```
{
  "units": [
    {
      "name":"serv1.network",
      "address":"x.x.x.x"
    },
    {
      "name":"serv2.network",
      "address":"x.x.x.x"
    }
  ],
"workers": {
  "serv1.network": [
    {
      "workername" : "dl1",
      "port":	25224,
      "jobname": "boxer.darknet.boxerjob",
      "jobdata":"none",
      "debuglevel": 0,
      "output": ["websocket"]
    },
    {
      "workername" : "dl2",
      "port":	25225,
      "jobname": "boxer.darknet.boxerjob",
      "jobdata":"none",
      "debuglevel": 0,
      "output": ["websocket"]
    }],
    "serv2.network": [
    {
      "workername" : "streamer",
      "port":	25223,
      "jobname": "multistreamer",
      "debuglevel": 1,
      "jobdata":
      },
      "outputmethod":"distribute",
      "output": ["dl1","dl2"]
    },
    {
      "workername" : "websocket",
      "port":	25222,
      "jobname": "websocket",
      "jobdata":{
        "port":8765
      },
      "debuglevel":0
    }
    ]
  }
}
```
# Installation



## Dependencies
- Python 3.5+
- CUDA and cudNN
- FFmpeg and FFprobe


### Dependencies Installation

For python dependencies, run
```
./install_python_packages.sh
```

For ffmpeg
```
sudo apt-get install ffmpeg
```
**If you plan on using the processing part you will have to install the darknet job, see below**
#### Darknet Job installation
Run the installation script from project root:
```
sudo ./install_boxer_job.sh
```

**NOTE**: If CUDA or CUDNN are not installed properly you will notice errors when building. To use CPU computation (hence no cuda or cudnn) use the following header in
>src/supervisor/jobs/boxer/MakefileDarknet

before running the install_boxer_job.sh script

Change header to:
```
GPU=0
CUDNN=0
OPENCV=0
NNPACK=0
ARM_NEON=0
OPENMP=1
DEBUG=0
```
this will disable gpu usage
## Quickstart

- Clone this repo
- Install dependencies (check Dependencies Installation)
- Run ``` scripts/start_web_server.sh ``` to start the django web server
- Run ``` scripts/start_supervisor.sh ``` to start the supervisor on this pc
- Run ``` scripts/start_local.sh ``` to start the local instance (everything on this pc)
**Tid'Zam video is now running**

## Configuration

Config files are in ``` src/supervisor/cfg ```

To Tid'Zam main config file for a local deployment is ``` alone_cluster.json ```

The default is:
```
{

  "units": [
    {
      "name":"serv1.network",
      "address":"x.x.x.x"
    },
    {
      "name":"serv2.network",
      "address":"x.x.x.x"
    }
  ],

"workers": {

  "serv1.network": [
    {
      "workername" : "dl1",
      "port":	25224,
      "jobname": "boxer.darknet.boxerjob",
      "jobdata":"none",
      "debuglevel": 0,
      "output": ["websocket"]
    },
    {
      "workername" : "dl2",
      "port":	25225,
      "jobname": "boxer.darknet.boxerjob",
      "jobdata":"none",
      "debuglevel": 0,
      "output": ["websocket"]
    }],
    "serv2.network": [
    {

      "workername" : "streamer",
      "port":	25223,
      "jobname": "multistreamer",
      "debuglevel": 1,
      "jobdata":{
        "options": {
          "default_img_rate":10,
          "defaut_resolution":"800x600",
          "max_streamers":3,
          "video_extensions": ".mp4;.avi",
          "realtime": 1
        }
      },
      "outputmethod":"distribute",
      "output": ["dl1","dl2"]
    },
    {
      "workername" : "websocket",
      "port":	25222,
      "jobname": "websocket",
      "jobdata":{
        "port":8765
      },
      "debuglevel":0
    }
    ]
  }
}
```

The config file is divided in two main parts

First, you may set the units hosting a *supervisor*
Here, we only use the local unit but of course more can be added

```
  "units": [
    {
      "name":"mypc",
      "address":"127.0.0.1"
    }
   ],
```

Then, for each unit, you may define the worker that will be running on it

Each worker is assigned a single job,
The jobs are defined in ``` src/supervisor/jobs ```

#### Job list
- unifyvideo: A websocket interface which allows multistreamer job to be configured remotely: for local files, remote stream or unify infrastructure processing.
- multistreamer:  reads from several video sources at the same time and outputs an image cycling through each source
- boxer/darknet/boxerjob: given an input image, returns a list of animals in the image
- websocket: broadcasts processing results to web consumers through websocket
- djangotransfer:  transfers a input image data to the django server given in input
- identityjob: outputs its input

##### Debug Jobs

- printjob: prints a string representation of in put to the console
- showjob: shows a given inout image using matplotlib
- failsafejob: will raise an exception in its loop

A worker config chunk is as follows:
```
   {
        "workername" : The name of the worker,
        "port":	The port of this worker,			
        "jobname": The job running on this worker,		
        "debuglevel": The requested loglevel,					
        "jobdata":The setup data, depends of the job,
        "outputmethod":"distribute" or "duplicate",
        "output": [list of output worker name]
     }
```
A worker can either **distribute** or **duplicate** its output
If **distribute** is used the output will go to the first available worker
if **duplicate** is used the output will go to all of the listed output workers

### Unifyvideo Job
The unify job can requested indifferently through its initial configuration file or remotely by its websocket. When new stream are added, the Unifyvideo job requests the Multistreamer to process them. with The following example presents the different possibilities from unify-video API, through a direct Web link or from a local file directory.
```
{
  "workername" : "unify",
  "port":	25221,
  "jobname": "unifyvideo",
  "jobdata":{
    "streams":[
      {
      "unify":"https://example:7443",
      "apiKey":"gfdsgfsgfdsgfds",
      "starttime":null,
      "endtime":null
    },
    {
        "name": "camera1",
        "url":"rtsp://tidmarsh.link:7447/5a9ee6046bb61c79a4fba8cc_2"
    },
      {
        "name":"tidzam-video",
        "path":"/opt/video/",
        "recursive":1
      }
    ],
    "port-ws":4652
  },
  "debuglevel": 1,
  "output": ["streamer"]
  }
```

### Multistreamer Job
```
 {
  "options": {
    "default_img_rate":60,
    "defaut_resolution":"800x600",
    "max_streamers":5,
    "video_extensions": ".mp4;.avi",
    "realtime": 1
  },

  "stream": [
 	{
	    "name": "camera1",
	    "url":"http://fakepath.truc/pathtocamera1"
	}
  ],

  "folders": [
    {
      "name":"tidzam-video",
      "path":"data",
      "recursive":1
    }
  ]
}

```

This is the multistreamer job configuration. The file path is given as jobdata to the multistreamer
The frst part are the default options:

```
  "options": {
    "default_img_rate":default rate,
    "defaut_resolution":default resolution set it to 'auto' to use the resolution from the input
    "max_streamers":max number of streamers working at the same time
    "video_extensions":Extensions to recognize videos when exploring folders
    "realtime": Skip frames to keep real time video ?
  },
```

Then you can set the streamer path, the streamers will be opened first at startup

```
{
	"name": name of this stream,
	"url":"http://fakepath.truc/pathtocamera1",
	"resolution"; "auto" to keep the original resolution
	"realtime": 1 to have a realtime stream
}
```
You can specifically define the resolution for each stream

Finally, you can give some folders you would like to analyse,
Use the recursive tag to explore sub-folders and set realtime to 0 to miss 0 frames

```
 {
      "name":"tidzam-video",
      "path":"/mnt/fakepath",
      "realtime":0  to get each frame
      "recursive": 1 to explore sub folders
 }
```



## TODO
- Fix logging level changing
- Use multiple GPU in darknet
- Write log to files
- Worker can be started with command line, without supervisor
- Multistreamer must support *on the fly* video changes
- Ensure frame order in djangotranfer
- Connect to Chain API
