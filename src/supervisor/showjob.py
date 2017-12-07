'''

@author: WIN32GG
'''

from worker import Job
import numpy as np
import PIL

class Showjob(Job):
    
    
    
    def loop(self, data):
        img = data.img
        PIL.Image.fromarray(np.uint8(img)).show()
        
    def requireData(self):
        return True
    
    