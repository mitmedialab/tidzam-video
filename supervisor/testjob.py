'''
Created on 5 nov. 2017

@author: WIN32GG
'''
import worker
from worker import Job

class testjob(Job):
    
    def setup(self):
        print("Setup")
        
    def loop(self, data):
        print(data)
        
    def requireData(self):
        return True
        
    def destroy(self):
        print("destroy")