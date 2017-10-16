from PIL import Image
import numpy as np

import imageio

def PILtoNpArray(image):
	return np.array(image.getdata(),np.uint8).reshape(image.size[1],image.size[0],3)

class ImageButcher:
	def __init__(self,size_factor):
		self.IMG_SIZE = (720,500) 
		self.MIN_SIZE = 60
		self.size_factor = size_factor
		
	def get_batches(self,image):
		batches = []
		i = 0
		image = PILtoNpArray(Image.fromarray(image).resize(self.IMG_SIZE,Image.HAMMING))
		windowSize = self.IMG_SIZE
		curr_factor = 1
		while(min(windowSize) > self.MIN_SIZE):
			batches.append(self.get_batch(image, windowSize))
			curr_factor *= self.size_factor
			windowSize = int(self.IMG_SIZE[0] / curr_factor) , int(self.IMG_SIZE[1] / (curr_factor))
			i += 1
		return batches

	def get_batch(self,image,windowSize):
	# slide a window across the image
		batch = []
		step_y = int(windowSize[1]/2)
		step_x = int(windowSize[0]/2)
		for y in range(0, image.shape[0] - step_y , step_y):
			raw = []
			for x in range(0, image.shape[1] - step_x ,step_x):
				# yield the current window
				if(x + windowSize[0] > self.IMG_SIZE[0] or y + windowSize[1] > self.IMG_SIZE[1]):
					break
				raw.append(image[y:y + windowSize[1], x:x + windowSize[0]])
			if len(raw) > 0 :
				batch.append(raw)
		return batch


if __name__ == "__main__":
	img = imageio.imread("bird.jpg")
	batcher = ImageButcher(2.0)
	batches = batcher.get_batches(img)

	for batch in batches:
		all_list = None
		for y in batch:
			xlist = y[0]
			for x in y[1:]:
				xlist = np.concatenate((xlist,x),axis=1)
			if all_list is None:
				all_list = xlist
			else:
				all_list = np.concatenate((all_list,xlist),axis=0)

		Image.fromarray(all_list).show()