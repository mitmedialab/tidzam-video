'''

@author: WIN32GG
'''

from worker import Job
import matplotlib.pyplot as plt

class Showjob(Job):
    
    def setup(self, data):
        plt.ion()
        
    
    def loop(self, data):
        img = data.img
        plt.pause(0.001)
        plt.imshow(img)
        plt.show()
        
        
    def requireData(self):
        return True
    
    