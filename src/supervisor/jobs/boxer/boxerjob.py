import os
from utils.custom_logging import debug, error, warning, ok
os.chdir(os.path.dirname(__file__))

from worker import Job
from .boxer import Detector
import numpy as np
import inspect

def encode_results(results):
	r = []
	for elem in results:
		r.append( (elem[0].decode(encoding="utf-8"), elem[1], elem[2]) )

	return r

class Boxerjob(Job):
	def setup(self, data):
		self.debug_boxing = False
		if type(data) == type({}):
			self.debug_boxing = data.get("debug_boxing")

		config = b"cfg/yolo9000.cfg"
		weights = b"weights/yolo9000.weights"
		meta = b"cfg/combine9k.data"

		self.detector = Detector(config, weights, meta)
		ok("Starting boxing identifier.")
		debug("cfg="+str(config)+" weights="+str(weights)+" meta="+str(meta), 3)


	def loop(self, data):
		if data is None:
			return
		try:
			image = data.img
		except:
			warning("nothing to do.",2)
			time.sleep(0.2)
			return data

		results = self.detector.run(image)
		image = self.detector.draw_boxes(results, image)

		if self.debug_boxing is True:
			data['img'] = image # COMMENT OUT TO UNDO BOXES DRAWING
		data['detection'] = encode_results(results)

		return data

	def requireData(self):
		return True

if __name__ == "__main__":
	from scipy.misc import imread

	job = Boxerjob()
	job.setup()
	image = imread('data/dog.jpg')
	print(str(image))
	job.data.put(image)
	p = Process(target=job.loop)
	p.start()

	#print(str(job.loop(image)))
	p.join()
