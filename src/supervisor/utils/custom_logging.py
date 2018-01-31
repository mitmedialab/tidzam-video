'''

@author: WIN32GG
'''

import sys

"""
    DEBUG OUTPUT HANDLING
"""
#debug level 0,1,2,3 the higher, the depper debug
_DEBUG_LEVEL = 3 #FIXME not sensible to change
_DEBUG_DICT  = {0:"Minimum", 1: "Supervisor info", 2: "Workers status", 3: "Everything (debug)"}

def debug(msg, level = 1, err= False):
    stream = sys.stderr if err else sys.stdout
    sts = "[INFO] [LV "+str(level)+"] " if level < 3 else "[DEBUG] "
    msg    = "[ERROR] "+msg if err else sts + msg
    
    if(level <= _DEBUG_LEVEL):
        stream.write(msg+"\n")
        stream.flush()