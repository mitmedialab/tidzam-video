from PIL import Image
import numpy as np
import imageio
from utils import *

def PILtoNpArray(image):
	return np.array(image.getdata(),np.uint8).reshape(image.size[1],image.size[0],3)

class ImageButcher:
	def __init__(self,size_factor,batch_depth):
		self.size_factor = size_factor
		self.batch_depth = batch_depth
		
	def get_batches(self,image):
		batches = []
		i = 0
		for i in range(self.batch_depth[0],self.batch_depth[1]):
			factor = (self.size_factor ** i)
			batch_size = int(image.shape[0] / factor), int(image.shape[1] / factor)
			batches.append(self.get_batch(image, batch_size))
		return batches

	def get_batch(self,image,windowSize):
	# slide a window across the image
		batch = []
		step_y = int(windowSize[1]/2)
		step_x = int(windowSize[0]/2)
		for y in range(0, image.shape[0] - step_y , step_y):
			raw = []
			for x in range(0, image.shape[1] - step_x,step_x):
				raw.append(image[y:y + windowSize[1], x:x + windowSize[0]])
			if len(raw) > 0 :
				batch.append(raw)
		return batch

	def get_metadata(self,image,x,y,z):
		factor = (self.size_factor ** (z + self.batch_depth[0]))
		batch_size = int(image.shape[0] / factor), int(image.shape[1] / factor)
		step_x = batch_size[0] / 2.0
		step_y = batch_size[1] / 2.0
		return	(batch_size,step_x * x,step_y * y)

if __name__ == "__main__":

	from utils import *
	from PIL import ImageDraw
	import argparse

	parser = argparse.ArgumentParser(description="This script allow you to try out the image segmentation")

	parser.add_argument("-f","--factor",default="1.5",help="Size factor by which the patch is reduce at each iteration",type=float)
	parser.add_argument("-i","--image",default="bird.jpg",help="Image to segment")
	parser.add_argument("-pf","--patch_factor",default="1:4",help="Reduction factor boundaries")
	args = parser.parse_args()

	img = imageio.imread(args.image)
	args.patch_factor = int(args.patch_factor.split(':')[0]) , int(args.patch_factor.split(':')[1])

	batcher = ImageButcher(args.factor,args.patch_factor)
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
		#Image.fromarray(all_list).show()
	model = load_inception()
	pred = batch_label_matching(model,batches)
	image = Image.fromarray(img)
	drw = ImageDraw.Draw(image)
	for z in range(len(pred)):
		for y in range(len(pred[z])):
			for x in range(len(pred[z][0])):
				#print("{0} for {1}".format(pred[z][y][x],batcher.get_metadata(x,y,z)))
				metadata = batcher.get_metadata(img,x,y,z)
				pos = int(metadata[1]) , int(metadata[2])
				pos2 = int(pos[0] + metadata[0][0]) , int(pos[1] + metadata[0][1])
				if(len(pred[z][y][x]) == 1 and "Bee Eater" in pred[z][y][x]):
					print(pos)
					print(pos2)
					drw.rectangle((pos , pos2),outline=(0,255,0))

	image.show()



