'''
Created on 5 nov. 2017

@author: WIN32GG
'''
import worker
from worker import Job

from tensorflow.python.client import device_lib

def get_available_gpus():
    local_device_protos = device_lib.list_local_devices()
    return [x.name for x in local_device_protos if x.device_type == 'GPU']

class testjob(Job):
    
    def setup(self):
        print("Setup")
        
    def loop(self, data):
        print(data)
        print(get_available_gpus())
        
    def requireData(self):
        return True
        
    def destroy(self):
        print("destroy")