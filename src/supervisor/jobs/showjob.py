'''

@author: WIN32GG
'''

from worker import Job
import numpy as np
from matplotlib import pyplot as plt

class Showjob(Job):
    
    def setup(self, data):
        plt.ion()
    
    def loop(self, data):
        plt.imshow(data.img)
        plt.pause(0.0001)
        
    def requireData(self):
        return True
    
    