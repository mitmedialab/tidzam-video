from worker import Job
from jobs.boxer.boxer import Detector
import numpy as np

class Boxerjob(Job):
	def setup(self, data):
		config = b"jobs/boxer/darknetnnpack/cfg/yolo9000.cfg"
		weights = b"jobs/boxer/darknetnnpack/weights/yolo9000.weights"
		meta = b"jobs/boxer/darknetnnpack/cfg/combine9k.data"		
		self.detector = Detector(config, weights, meta)
		

	def loop(self, data):
		image = data.img
		print(type(image))

		results = self.detector.run(image)
		image = self.detector.draw_boxes(results, image)
		
		print(str(results))
		return {"img":image, "results":results}

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
