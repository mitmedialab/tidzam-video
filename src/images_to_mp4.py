import cv2
import cv2.cv as cv
import numpy as np

def compress(i):
	msg = ''
	if i < 10:
		msg += '0000' + str(i)
	elif i < 100:
		msg += '000' + str(i)
	elif i < 1000:
		msg += '00' + str(i)
	elif i < 10000:
		msg += '0' + str(i)
	elif i < 100000:
		msg += str(i)
	return msg + '.jpg'

path = 'Video/Canadian_Goose/1_5__3_6__1080_720__10/'
files = [compress(i) for i in range(100, 350)]

fourcc = cv.CV_FOURCC(*'MJPG')
video = cv2.VideoWriter(path + 'video.avi', fourcc, 10.0, (1080, 720), True)
for f in files:
	img = cv2.imread(path + f, 3)
	cv2.imshow('', img)
	cv2.waitKey(0)
	video.write(img)
cv2.destroyAllWindows()
video.release()