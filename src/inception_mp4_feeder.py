from mp4_slicer import *
from image_butcher import *
from utils import batch_label_matching

import argparser



if __name__ == "main":
	parser = argparse.ArgumentParser(description="Feed the inception model with a given mp4 and perform detection over the stream")
	parser.add_argument("-f","--file",help="The mp4 file")
	parser.add_argument("-t","--timestamp",default=1,help="The elapsed time between each detection update")
	parser.add_argument("-r","--imgRate",default=30,help="The image rate of the given mp4")



	args = parser.parse_args()
	imgs = slice_mp4(args.file,args.timestamp,args.imgRate)
	image_butcher = ImageButcher(2.0)
	probability = []
	for img in imgs:
		batches = image_butcher.get_batches(img)
		probability.append(batch_label_matching(batches))

