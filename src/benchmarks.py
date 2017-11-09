import numpy as np
import matplotlib.pyplot as plt
import time
import inception

img_filenames = ['Images/c', 'Images/jrp', 'Images/b', 'Images/b1', 'Images/cg',
                 'Images/cg1', 'Images/gbh', 'Images/gbh1']

model = inception.Model()

def test(imgs):
	t0 = time.time()
	top_k = model.classify(imgs, 5)
	t1 = time.time()
	return t1 - t0

m = 51
ns = [(i * 8) for i in range(1, m)]
seconds = [test(inception.get_images(img_filenames * i)) for i in range(1, m)]
images_per_second = [(1.0 * ns[i - 1] / seconds[i - 1]) for i in range(1, m)]

plt.figure(figsize=(12,8))

plt.subplot(211)
plt.plot(ns, seconds, color='blue')
plt.title('Processing time per Batch size')
plt.xlabel('Batch size')
plt.ylabel('Processing time (s)')
plt.grid(True)


plt.subplot(212)
plt.plot(ns, images_per_second, color='blue')
plt.title('Images per second per Batch size')
plt.xlabel('Batch size')
plt.ylabel('Images per second (img/s)')
plt.grid(True)

plt.subplots_adjust(hspace=0.60)

plt.show()