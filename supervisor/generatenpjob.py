'''
Created on 7 nov. 2017

@author: WIN32GG
'''

from worker import Job
import numpy as np

class generatenpjob(Job):
    
    
    def loop(self, data):
        return np.random.randint(0, 255, size = (1280, 1080, 3))
    
    def requireData(self):
        return False