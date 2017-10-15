import imageio
from PIL import Image

def slice_mp4(filename,timestamp,image_rate):
	vid = imageio.get_reader(filename,"ffmpeg")
	max_time = len(vid) / image_rate
	image_index = [int(time * image_rate) for time in range(0,int(max_time),timestamp)]
	#for i in image_index:
		#Image.fromarray(vid.get_data(i)).show()
		#time_sec = i / (image_rate)
		#print (str(time_sec / 60.0).split(".")[0] + ":" + str(int(time_sec) % 60))
	return [vid.get_data(i) for i in image_index]


if __name__ == "__main__":
	imgs = slice_mp4("mario.mp4",int(36*60 / 5),30)
	for img in imgs:
		Image.fromarray(img).show()