import imageio
from PIL import Image

"""
Given an mp4 file , a timestamp , and the image rate of the mp4 
this function will return a list of np.array each representing 
a frame. 
Between each of these frame t = timestamp has elapsed
"""
def slice_mp4(filename,timestamp,image_rate):
	vid = imageio.get_reader(filename,"ffmpeg")
	max_time = len(vid) / image_rate
	image_index = [int(time * image_rate) for time in range(0,int(max_time),timestamp)]
	return [vid.get_data(i) for i in image_index]


if __name__ == "__main__":
	from image_butcher import ImageButcher
	import numpy as np
	imgs = slice_mp4("mario.mp4",int(36*60 / 5),30)
	for img in imgs:
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