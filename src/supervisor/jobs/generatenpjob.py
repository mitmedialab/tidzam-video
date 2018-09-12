'''

@author: WIN32GG
'''

from worker import Job
import numpy as np

class Generatenpjob(Job):
    
    def setup(self, data):
        self.a = 0
    
    def loop(self, data):
        self.a += 1
        
        if(self.a > 200):
            self.shouldStop = True
            return None
        
        return np.random.randint(0, 255, size = (1920, 1080, 3), dtype="uint8")
    
    def requireData(self):
        return False