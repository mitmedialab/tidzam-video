import datetime,json
from websocket import create_connection
from supervisor.utils.custom_logging import debug,error,warning,ok, _DEBUG_LEVEL

today   = datetime.datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
start   = round(( today- datetime.timedelta(1)).timestamp()*1000)
end     = round(today.timestamp() * 1000)
req = {
    "name":"",
    "unify":"https://tidmarsh.link:7443",
    "apiKey":"tOPvRsuHCAU74ymg",
    "startTime":start,
    "endTime":end,
    "locked":False
}

ws = create_connection("ws://localhost:4652")
debug("Sending unify request ",0)
debug(str(req),0)

ws.send(json.dumps(req))
result =  ws.recv()
debug("Response:",0)
debug(str(result),0)
debug("==============",0)
ws.close()
