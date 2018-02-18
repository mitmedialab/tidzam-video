from django.http import HttpResponse
from channels.handler import AsgiHandler
import numpy as np
from channels import Group
# test
#def hello(message):
#	#Make standard HTTP response - access ASGI path attribute directly
#	response = HttpResponse("Hello !")
	#Encode that response into message format (ASGI)
#	for chunk in AsgiHandler.encode_response(response):
#		message.reply_channel.send(chunk)
#
# def ws_connect(message):
# 	Group('users').add(message.reply_channel)
#
# def ws_disconnect(message):
# 	Group('users').discard(message.reply_channel)
#
# def ws_add(message):
# 	#ASGI WebSocket packet-received and send-packet message types
# 	#both have a "text" key for their textual data
# 	response = HttpRequest(np.zeros((1980,1080)))
# 	for chunk in AsgiHandler.encode_response(response):
# 		message.reply_channel.send(chunk)
# 	#message.reply_channel.send({
# 	#	"np": message.content[response],
# 	#	})
#

AUTH_KEY = "5edb6a02bc2c1a6ecd1e2c7f30b80d6f"

from hashlib import sha1
from PIL import Image
import numpy as np
import io
import json
import hashlib

def get_image(pck, binary):
	inBytes = io.BytesIO()
	inBytes.write(binary)
	inBytes.seek(0)

	img = np.load(inBytes)['arr_0']

	#print(hashlib.sha1(img).hexdigest()+" "+pck["checksum"])
	chk = hashlib.sha1(img).hexdigest()
	if(chk != pck["checksum"]):
	    raise ValueError("Error in transmission: checksums do not match")

	return img.reshape(pck["shape"])

def raw_to_encoded(img, format = "JPEG"):
	pil_raw = Image.fromarray(img)
	imgByteArr = io.BytesIO()
	pil_raw.save(imgByteArr, format)
	return imgByteArr.getvalue()


def check(s):
	m = sha1()
	m.update(s)
	return m.hexdigest()

def ws_connect(message):
	message.reply_channel.send({"accept": True})
	if(message['path'] == '/camera/'):
		print("New user connection")
		Group('all-cameras').add(message.reply_channel)

def ws_disconnect(message):
    Group("all-cameras").discard(message.reply_channel)

pck = None

def ws_message(message):
	global pck

	if(message['path'] == '/push/'):
		if('text' in message.content):
			pck = json.loads(message.content['text'])
			print("Got image info")

		else:
			raw_message = message.content['bytes']

			print("got "+str(len(raw_message)) +" bytes")
			#tag_len = int.from_bytes(rawmessage[:HEADER_LEN], byteorder='little')
			#tags =
			#print(str(raw_message[:20])) #log
			img = get_image(pck, raw_message)
			encoded = raw_to_encoded(img)
			print("encoded is "+str(len(encoded))+" bytes")

			print(str(check(raw_message)))
			Group('all-cameras').send({
				"bytes": encoded
			})

			#print("test: "+str(message.content.keys()))

			# message.reply_channel.send({
		    #     "text": message.content['text'],
		    # })
