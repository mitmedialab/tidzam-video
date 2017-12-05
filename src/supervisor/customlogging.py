'''

@author: WIN32GG
'''

import sys

"""
    DEBUG OUTPUT HANDLING
"""
#debug level 0,1,2,3 the higher, the depper debug
_DEBUG_LEVEL = 2
_DEBUG_DICT  = {0:"Minimum", 1: "Warden info", 2: "Workers status", 3: "Everything"}
def debug(msg, level = 1, err= False):
    stream = sys.stderr if err else sys.stdout
    msg    = "[ERROR] "+msg if err else "[INFO] "+msg
    if(level <= _DEBUG_LEVEL):
        stream.write(msg+"\n")
        stream.flush()