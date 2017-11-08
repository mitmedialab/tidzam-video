'''
Created on 7 nov. 2017

@author: WIN32GG
'''

from worker import Job

class printjob(Job):
    
    def requireData(self):
        return True
    
    def loop(self, data):
        print(str(data))