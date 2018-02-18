from channels.routing import route
from tidmarsh.consumers import *


channel_routing = [
    route("websocket.receive", ws_message),
    route("websocket.connect", ws_connect),
    route("websocket.disconnect", ws_disconnect),
]
