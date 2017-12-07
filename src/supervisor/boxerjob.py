from worker import Job
from boxer import Detector
import numpy as np

class Boxerjob(Job):
	def setup(self, data):
		config = b"cfg/yolo9000.cfg"
		weights = b"weights/yolo9000.weights"
		meta = b"cfg/combine9k.data"
		self.detector = Detector(config, weights, meta)
		return

	def loop(self, data):
		image = data.img
		print(type(image))

		results = self.detector.run(image)
		image = self.detector.draw_boxes(results, image)
		
		print(str(results))

	def requireData(self):
		return True

if __name__ == "__main__":
	from scipy.misc import imread

	job = boxerjob()
	job.setup()
	image = imread('data/dog.jpg')
	print(str(image))
	job.data.put(image)
	p = Process(target=job.loop)
	p.start()

	#print(str(job.loop(image)))
	p.join()
