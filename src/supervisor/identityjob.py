'''

@author: WIN32GG
'''

from worker import Job

class Identityjob(Job):
    def setup(self, data):
        pass
    
    def loop(self, data):
        print(str(data))
        return data
    
    def requireData(self):
        return True