import numpy as np
import imageio

from PIL import Image

class Size:
	def __init__(self, top_left, bottom_right):
		self.top_left = top_left
		self.bottom_right = bottom_right

class ImageButcher:
	def __init__(self,size_factor, batch_depth):
		self.size_factor = size_factor
		self.batch_depth = batch_depth

	def get_batch(self, image):
		sizes = []
		chunks = []
		
		image_shape_y, image_shape_x, _ = image.shape
		#img_c = None
		for z in range(self.batch_depth[0], self.batch_depth[1]):
			factor = self.size_factor**z 
			chunk_size_x, chunk_size_y = int(image_shape_x / factor), int(image_shape_y / factor)	
			
			step_x, step_y = int(chunk_size_x * 0.5), int(chunk_size_y * 0.5)
			#all_list = None
			for y in range(0, image_shape_y - step_y, step_y):
				x_list = None
				for x in range(0, image_shape_x - step_x, step_x):
					top_left = x , y 
					bottom_right =  x + chunk_size_x, y + chunk_size_y
					sizes.append(Size(top_left, bottom_right))

					image_chunk = image[y:(y + chunk_size_y), x:(x + chunk_size_x)]
					res = (299, 299)
					image_chunk = Image.fromarray(image_chunk)
					image_chunk = image_chunk.resize(res, Image.BILINEAR)
					image_chunk = np.array(image_chunk)
					if(image_chunk is not None):
						chunks.append(image_chunk)
					"""if x_list is not None:
						x_list = np.concatenate((x_list,image_chunk),axis=1)
					else:
						x_list = image_chunk
				if all_list is not None:
						all_list = np.concatenate((all_list,x_list),axis=0)
				else:
					all_list = x_list"""

		#Image.fromarray(all_list).show()
		return sizes, (((np.asarray(chunks, np.float32) / 255.0) - 0.5) * 0.2)