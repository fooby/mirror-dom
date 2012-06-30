"""
web.py server running miror-dom
"""

import web
from mirrordom import server
import json
import sys

urls = (
    "/client", "Client",
    "/viewer", "Viewer",
    "/(.+)", "MirrorDomHandler"
)

storage = {}

class Client(object):
    def GET(self):
        return open("demo_client.html").read()

class Viewer(object):
    def GET(self):
        return open("demo_viewer.html").read()

class MirrorDomHandler(object):
    def POST(self, name):
        global storage
        i = web.input()
        web.header("Content-Type", "application/json")
        return json.dumps(getattr(server, "handle_" + name)(storage, **i))

    def GET(self, name):
        global storage
        i = web.input()
        web.header("Content-Type", "application/json")
        return json.dumps(getattr(server, "handle_" + name)(storage, **i))

if __name__ == "__main__": 
    import logging
    logger = logging.getLogger("mirrordom")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler(sys.stderr))
    logging.getLogger().setLevel(logging.DEBUG)
    app = web.application(urls, globals())
    app.run() 
