'''
Created on 5 déc. 2017

@author: WIN32GG
'''

from worker import Job

class Failsafejob(Job):
    
    def setup(self, data):
        pass
    
    def loop(self, data):
        raise ValueError("Exception from failsafe test")
    
    def requireData(self):
        return False