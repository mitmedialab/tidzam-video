import cv2
import numpy as np

class ImageButcher:
	def __init__(self,size_factor):
		self.IMG_SIZE = (720,500) 
		self.MIN_SIZE = 15
		self.size_factor = size_factor
		
	def get_batches(self,image):
		batches = []
		i = 0
		image = cv2.resize(image,self.IMG_SIZE,interpolation=cv2.INTER_AREA)
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
		step_y = windowSize[1]/2
		step_x = windowSize[0]/2
		for y in xrange(0, image.shape[0], step_y):
			raw = []
			for x in xrange(0, image.shape[1],step_x):	
				# yield the current window
				if(x + windowSize[0] > self.IMG_SIZE[0] or y + windowSize[1] > self.IMG_SIZE[1]):
					break
				raw.append(image[y:y + windowSize[1], x:x + windowSize[0]])
			if len(raw) > 0 :
				batch.append(raw)
		return batch


def show(image,nameWindow="title"):
	cv2.imshow(nameWindow,image)
	cv2.waitKey(0)
	cv2.destroyWindow(nameWindow)

img = cv2.imread("grg",3)
batcher = ImageBatcher(2.0)
batches = batcher.get_batches(img)

cv2.namedWindow("main")
cv2.imshow("main",img)

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

	show(all_list)