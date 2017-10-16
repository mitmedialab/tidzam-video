# Dependencies
import urllib.request
import numpy as np
import tensorflow as tf
import os
import inception

# Download the image
def download_image(url, path):
	try:
		urllib.request.urlretrieve(url, path)
	except:
		print('[Error] Failed to download the image ...')

# Load the inception model
def load_inception():
	inception.maybe_download()
	model = inception.Inception()
	return model

# Classify an image
def classify(model, image_path):
	pred = model.classify(image_path=image_path)
	possible_labels = model.print_scores(pred=pred, k=10, only_first_name=True)
	return possible_labels

# Print the labels
def print_labels(possible_labels):
	print('[Ouput] Top 10 labels: ')
	for l in possible_labels:
		print('            ' + l['label'] + ': ' + str(l['score']))

# Labels
BlueHeron = ['little blue heron', 'American egret']
CanadianGoose = ['goose']
BlackGrouse = ['black groose']
BeeEater = ['bee eater']
WillowPtarmigan = ['ptarmigan']
Cuckoo = ['water ouzel']
Woodpecker = ['magpie']
Swift = ['kite']
Quail = ['quail']
Pheasant = ['cock']
Chicken = ['cock', 'hen']
Human = ['jersey', 'jean', 'miniskirt', 'sweatshirt', 'sunglass', 'suit', 'bow tie', 'cloack', 'abay', 'diaper', 'cardigan', 'sock', 'cowboy boot', 'lab coat', 'medecine chest', 'swimming trunks', 'bikini', 'maillot', 'brassiere', 'running shoe', 'lipstick', 'face powder', 'loupe', 'mask', 'wool', 'lotion', 'band aid', 'knee pad', 'sock', 'sandal']

Labels = [{'label': 'Blue Heron', 'set': BlueHeron}, {'label': 'Canadian Goose', 'set': CanadianGoose}, {'label': 'Black Grouse', 'set': BlackGrouse}, {'label': 'Bee Eater', 'set': BeeEater}, {'label': 'Willow Ptarmigan', 'set': WillowPtarmigan}, {'label': 'Cuckoo', 'set': Cuckoo}, {'label': 'Woodpecker', 'set': Woodpecker}, {'label': 'Swift', 'set': Swift}, {'label': 'Quail', 'set': Quail}, {'label': 'Pheasant', 'set': Pheasant}, {'label': 'Chicken', 'set': Chicken}, {'label': 'Human', 'set': Human}]

# Validate the labels
def validate_labels(possible_labels):
	validation_set = []
	for label in possible_labels:
		for label_set in Labels:
			if(label['label'] in label_set['set'] and not label_set['label'] in validation_set):
				validation_set.append(label_set['label'])
	return validation_set

# Print infos
def infos():
	print('===========================================\n')

	print('[Infos] This tool will be able to deal with: ')
	for l in Labels:
		print('            ' + l['label'])

	print('===========================================\n')
