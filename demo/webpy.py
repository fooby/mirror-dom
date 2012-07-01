"""
web.py server running miror-dom
"""

import web
from mirrordom import server
import json
import sys

urls = (
    "/favicon.ico", None,
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
    def handle(self, name):
        global storage
        inputs = web.input()
        web.header("Content-Type", "application/json")

        if name == "add_diff":
            # have to de-jsonise diff argument
            result = server.handle_add_diff(storage, 
                    window_id=inputs["window_id"],
                    diff=json.loads(inputs["diff"]))
        else:
            result = getattr(server, "handle_" + name)(storage, **inputs)

        return json.dumps(result)

    def POST(self, name):
        return self.handle(name)

    def GET(self, name):
        return self.handle(name)

if __name__ == "__main__": 
    import logging
    logger = logging.getLogger("mirrordom")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler(sys.stderr))
    logging.getLogger().setLevel(logging.DEBUG)
    app = web.application(urls, globals())
    app.run() 
