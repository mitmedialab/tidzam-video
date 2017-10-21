import subprocess as sp
import psutil
import numpy as np

class Streamer:
	def __init__(self,url,img_rate):
		self.url = url
		self.img_rate = img_rate
		infos = self.meta_data()
		self.shape = int(infos['width']),int(infos['height'])
		self.open()

	def meta_data(self):
		#metadata of interest
		metadataOI = ['width','height']

		command = ['ffprobe', '-v' , 'error' ,'-show_format' ,'-show_streams' , self.url]

		pipe  = sp.Popen(command,stdout=sp.PIPE,stderr=sp.PIPE)
		infos = pipe.stdout.read()
		pipe.terminate()
		infos = infos.split('\n')
		dic = {}
		for info in infos:
			if info.split('=')[0] in metadataOI:
				dic[info.split('=')[0]] = info.split('=')[1]
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
