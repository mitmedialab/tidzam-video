'''
Created on 30 nov. 2017

@author: win32gg
'''
import json
import traceback

from .custom_logging import debug

def checkMasterConfigSanity(cfg):
    return checkConfigSanity(cfg, ["units"], ["workers","action","refreshinterval", "supervisorport"])

def checkWorkerConfigSanity(cfg):
    return checkConfigSanity(cfg,  ["port", "jobname", "workername"], ["jobreplacemethod", "outputmethod", "debuglevel", "output", "jobdata", "action"])

def checkConfigSanity(cfg, MANDATORY, OPTIONAL):
        TOTAL = MANDATORY + OPTIONAL

        try:
            j = json.loads(cfg)

            for k in j.keys():
                if(not k in TOTAL):
                    raise ValueError("Unknown parameter: "+str(k))

            for k in MANDATORY:
                if(not k in j.keys()):
                    raise ValueError("Missing mandatory parameter: "+str(k))

        except ValueError as ve:
            error("Error in configuration: "+str(ve), 0)
            return False
        except json.JSONDecodeError:
            error("Error in configuration: The provided configuration is not valid", 0)
            return False
        except:
            error("Error when checking config sanity", 0)
            traceback.print_exc()
            return False

        return True
