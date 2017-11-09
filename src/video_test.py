import numpy as np
import imageio
import inception
import utils
import image_butcher as ib

from tqdm import tqdm
from PIL import Image
from PIL import ImageDraw

def compress(i):
	return ('%05d' % i) + '.jpg'

def drawRects(top_left, bottom_right, chunk_pred, thickness):
	if "Swift" in chunk_pred:
		for i in range(thickness):
			tl = top_left[0] - i , top_left[1] - i
			br = bottom_right[0] + i , bottom_right[1] + i
			drw.rectangle((tl,br), outline=(0, 255, 0))
	if "Blue Heron" in chunk_pred:
		for i in range(thickness):
			tl = top_left[0] - i , top_left[1] - i
			br = bottom_right[0] + i , bottom_right[1] + i
			drw.rectangle((tl,br), outline=(0, 0, 255))
	if "Canadian Goose" in chunk_pred:
		for i in range(thickness):
			tl = top_left[0] - i , top_left[1] - i
			br = bottom_right[0] + i , bottom_right[1] + i
			drw.rectangle((tl,br), outline=(255, 0, 0))
	if "Black Grouse" in chunk_pred:
		pass
	if "Bee Eater" in chunk_pred:
		pass
	if "Willow Ptarmigan" in chunk_pred:
		pass
	if "Cuckoo" in chunk_pred:
		pass
	if "Woodpecker" in chunk_pred:
		pass
	if "Quail" in chunk_pred:
		pass
	if "Pheasant" in chunk_pred:
		pass
	if "Chicken" in chunk_pred:
		pass

butcher = ib.ImageButcher(2.0, (0, 5))
image_files = [compress(i) for i in range(155, 330)]
model = inception.Model()

for image_file in tqdm(image_files):
	img = Image.open('Images/2/' + image_file)
	res = (1080, 720)
	img = img.resize(res, Image.BILINEAR)
	img = np.array(img)

	sizes, batch = butcher.get_batch(img)

	# ---------------------------------------------------------------------
	patch_number = len(batch)
	max_size = 400
	n = patch_number // max_size
	r = patch_number % max_size

	top_k = []
	for i in range(n):
		From = i * max_size
		To = (i + 1) * max_size
		_top_k = model.classify(batch[From:To], 3)
		for top in _top_k:
			top_k.append(top)
	if r > 0:
		From = n * max_size
		_top_k = model.classify(batch[From:], 3)
		for top in _top_k:
			top_k.append(top)
	top_k = np.array(top_k)

	pred = utils.validate_labels(top_k)

	#----------------------------------------------------------------------
	image = Image.fromarray(img)
	drw = ImageDraw.Draw(image)

	for i in range(len(batch)):
		size = sizes[i]
		top_left, bottom_right = size.top_left, size.bottom_right
		chunk_pred = pred[i]
		if len(chunk_pred) > 0:
			drawRects(top_left, bottom_right, chunk_pred, 3)

	image.save('Video/' + image_file)
