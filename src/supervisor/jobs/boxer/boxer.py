from . import darknet as dn
import numpy as np
import io

class Detector:
	def __init__(self, config, weights, meta):
		dn.set_gpu(0)
		f = io.BytesIO()
		
		with dn.stderr_redirector(f):
			self.net = dn.load_net(config, weights, 0)
			self.meta = dn.load_meta(meta)
		#print('Got stdout: "{0}"'.format(f.getvalue().decode('utf-8')))

	def run(self, image_array):
		image = self._array_to_image(image_array)
		results = dn.detect(self.net, self.meta, image)
		return results

	def draw_boxes(self, results, image_array):
		for result in results:
			x, y, w, h = result[2]
			box_coords = int(x - w / 2.0), int(y - h / 2.0), int(x + w / 2.0), int(y + h / 2.0)
			image_array = self._draw_box(box_coords, image_array)
		return image_array

	def _draw_box(self, box_coords, image_array):
		top_left_x, top_left_y, bottom_right_x, bottom_right_y = box_coords
		color = np.array([0, 255, 0], dtype = np.uint8)
		for i in range(-1, 2):
			try:
				image_array[top_left_y + i, top_left_x:bottom_right_x] = color
			except:
				pass
			try:
				image_array[bottom_right_y + i, top_left_x:bottom_right_x] = color
			except:
				pass
			try:
				image_array[top_left_y:bottom_right_y ,top_left_x + i] = color
			except:
				pass
			try:
				image_array[top_left_y:bottom_right_y ,bottom_right_x + i] = color
			except:
				pass
		return image_array

	def _array_to_image(self, image_array):
		image_array = image_array.transpose(2,0,1)
		c = image_array.shape[0]
		h = image_array.shape[1]
		w = image_array.shape[2]
		image_array = (image_array/255.0).flatten()
		data = dn.c_array(dn.c_float, image_array)
		image = dn.IMAGE(w,h,c,data)
		return image

if __name__ == '__main__':
	from scipy.misc import imread, imsave
	from time import time

	import os
	os.chdir("darknetnnpack")

	config = b"cfg/yolo9000.cfg"
	weights = b"weights/yolo9000.weights"
	meta = b"cfg/combine9k.data"

	detector = Detector(config, weights, meta)
	image = imread('data/dog.jpg')

	a = time()
	results = detector.run(image)
	print(str(time() - a))
	print(results)
	print(image.shape)

	image = detector.draw_boxes(results, image)
	imsave('debug.png', image)
