import subprocess as sp
import psutil
import numpy as np

class Streamer:
	def __init__(self,url,img_rate):
		self.url = url
		self.img_rate = img_rate
		self.open()
		infos = self.meta_data()

	def meta_data(self):
		command = ['ffmpeg','-i',self.url,'-']
		pipe  = sp.Popen(command,stdout=sp.PIPE,stderr=sp.PIPE)
		pipe.stdout.readline()
		infos = pipe.stderr.read()
		pipe.terminate()
		
		infos = infos.split('\n')

		for i in infos:
			if 'Stream' in i:
				info = i.split(' ')
				dic = {'shape':info[13]} #,'frame_rate':info[20]}
				return dic

	
	def get_image(self):
		self.psProcess.resume()
		raw_image = self.pipe.stdout.read(640*360*3)
		image = np.fromstring(raw_image,dtype='uint8')

		if image.shape[0] == 0:
			return None

		image = image.reshape((360,640,3))

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
