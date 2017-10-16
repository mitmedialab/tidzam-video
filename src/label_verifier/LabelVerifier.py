# Dependencies
from utils import *
import os

# Print Header
print('===========================================')
print('===========                   =============')
print('===========   LabelVerifier   =============')
print('===========                   =============')
print('=============================  V 0.5  =====')
print('===========================================\n')

# Image infos
# image_url = "https://farm5.staticflickr.com/4478/37337347542_00aa66509a.jpg"
# image_name = "man_4478_37337347542"
image_path = "Temp/temp.jpeg"

# Load the inception model 
model = load_inception()

# Main
exit = False

while not exit:
	# Debug infos
	infos()
	
	# Get the image url
	image_url = input('[Input] Enter the image url: ')

	try:
		# Download the image
		download_image(image_url, image_path)

		# Get the top 10 labels
		possible_labels = classify(model, image_path)
		print_labels(possible_labels)

		# Validate the lables
		validation_labels = validate_labels(possible_labels)
		print('[Ouput] Validation labels: ')
		for v in validation_labels:
			print('            ' + v)
		if(len(validation_labels) > 0):
			print('[Output] The image has been ACCEPTED !')
		else:
			print('[Output] The image has been REFUSED !')


		# Delete the temporary file holding the image
		os.remove(image_path)
	except:
		print('[Error] Failed to classify this image (Format, url, ...) ...')

	exit_resp = input('[Input] Do you want to quit ? y/Y or n/N: ')
	exit = (exit_resp == 'y' or exit_resp == 'Y')
	print('\n')
	print('===========================================\n')
	if exit:
		quit()
