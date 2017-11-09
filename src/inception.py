import tensorflow as tf
slim = tf.contrib.slim
import model.inception_v4 as net
import numpy as np
import cv2
import imagenet

class Prediction:
    def __init__(self, score, label):
        self.score = score * 100
        self.label = label

    def __str__(self):
        return('{0}: {1}%'.format(self.label, round(self.score, 3)))


class Model:
	def __init__(self, checkpoint_file='./model/inception_v4.ckpt', batch_size=None, height=299, width=299, channels=3):
		self.width = width
		self.height = height
		self.channels = channels

		self.names = imagenet.create_readable_names_for_imagenet_labels()

		print('[+] Model loading ...')
		inputs = tf.placeholder(tf.float32, shape=[batch_size, height, width, channels])

		with slim.arg_scope(net.inception_v4_arg_scope()):
			logits, end_points = net.inception_v4(inputs, is_training = False)
		print('[+] Model contructed!')

		saver = tf.train.Saver()

		self.sess = tf.Session()
		print('[+] Model session initialized!')
		saver.restore(self.sess, checkpoint_file)
		print('[+] Model weights loaded!')
		self.representation_tensor = self.sess.graph.get_tensor_by_name('InceptionV4/Logits/Predictions:0')
		print('[+] Model loaded!')

	def classify(self, images_tensor, k):
		features = self._get_features(images_tensor)
		top_k = self._get_top_k(features, k)
		return top_k

	def _get_features(self, images_tensor):
		print('[o] Model has been fed: {0}'.format(images_tensor.shape))
		features = self.sess.run(self.representation_tensor, {'Placeholder:0': images_tensor})
		print('[o] Model features compute!')
		return features

	def _get_top_k(self, features, k):
		images_labels = []
		for f in features:
			idx = np.flipud(f.argsort()[-k:])
			predictions = [Prediction(f[i], self.names[i]) for i in idx]
			images_labels.append(predictions)
		print('[o] Model top_k compute!')
		return images_labels
			


'''def get_images(img_filenames):
	imgs = []
	for img_filename in img_filenames: 
		img = cv2.imread(img_filename + '.jpg')
		img = cv2.resize(img, (299, 299))
		imgs.append(img)
	imgs = np.array(imgs, dtype=np.float32)
	return ((imgs / 255.0) - 0.5) * 2.0

img_filenames = ['Images/c']

inception = Model()

imgs = get_images(img_filenames)
top_k = inception.classify(imgs, 5)
for k in top_k:
	print('------------------------------------------------')
	for p in k:
		print(p)'''
