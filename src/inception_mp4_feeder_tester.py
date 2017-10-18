from mp4_slicer import *
from image_butcher import *
from utils import batch_label_matching

import argparser
import tqdm


if __name__ == "main":
	parser = argparse.ArgumentParser(description="Feed the inception model with a given mp4 and perform detection over the stream")
	parser.add_argument("-f","--file",help="The mp4 file")
	parser.add_argument("-t","--timestamp",default=1,help="The elapsed time between each detection update",type=float)
	parser.add_argument("-r","--imgRate",default=30,help="The image rate of the given mp4",type=int)
	parser.add_argument("-f","--factor",default="1.5",help="Size factor by which the patch is reduce at each iteration",type=float)
	parser.add_argument("-pf","--patch_factor",default="1:4",help="Reduction factor boundaries")

	args = parser.parse_args()
	args.patch_factor = int(args.patch_factor.split(':')[0]) , int(args.patch_factor.split(':')[1])

	imgs = slice_mp4(args.file,args.timestamp,args.imgRate)
	image_butcher = ImageButcher(args.factor,args.patch_factor)

	for img in tqdm(imgs):
		batches = image_butcher.get_batches(img)
		probability.append(batch_label_matching(batches))
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
