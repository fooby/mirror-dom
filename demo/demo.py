"""
Basic demo of mirrordom using the Bottle web framework.

Steps:
1) Run demo.py
2) Open up the http://localhost:8080/broadcaster in one (and ONLY one) browser window
    (OR use http://localhost:8080/broadcaster_iframe)

3) Open up the http://localhost:8080/viewer in one or more browser windows
"""

import os
import wsgiref
import logging
import json

import pprint
from external_libs import bottle

app = bottle.Bottle()

# Setup demo paths
MIRRORDOM_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
DEMO_ROOT = os.path.dirname(__file__)

STATIC_PATH = os.path.join(DEMO_ROOT, 'static')

# Use the JS and Python files outside of the demo directory tree
MIRRORDOM_JS_PATH = os.path.join(MIRRORDOM_ROOT, 'js')
MIRRORDOM_PYTHON_PATH = os.path.join(MIRRORDOM_ROOT, 'python')

import sys
sys.path.append(MIRRORDOM_PYTHON_PATH)
import mirrordom
import mirrordom.server


# Global storage for mirrordom diffs - this means we only have one global
# mirrordom session for the demo.
mirrordom_storage = mirrordom.server.create_storage()

logger = logging.getLogger("mirrordom")
logger.setLevel(logging.DEBUG)
h = logging.StreamHandler(sys.stdout)
logger.addHandler(h)


def get_mirrordom_uri(page="mirrordom", environ=None):
    if environ is None:
        environ = bottle.request.environ
    uri = wsgiref.util.application_uri(environ) + page
    return uri

@app.route('/blank')
def blank():
    return "<html><head></head><body></body></html>"

@app.route('/viewer')
def viewer():
    """ Serve the viewer page """
    return bottle.template('viewer', mirrordom_uri=get_mirrordom_uri(),
            blank_page=get_mirrordom_uri("blank"))

@app.route('/broadcaster')
def broadcaster():
    """ Serve the broadcaster page (make sure not to run multiple instances of
    this page) """
    return bottle.template('broadcaster', mirrordom_uri=get_mirrordom_uri())

@app.route('/mirrordom/<name>', method='ANY')
def handle_mirrordom(name):
    """
    Core mirrordom server functionality
    """
    global mirrordom_storage
    query = bottle.request.params
    parsed_query = dict((k, json.loads(v)) for k,v in query.iteritems())
    result = getattr(mirrordom.server, "handle_" + name)(mirrordom_storage, **parsed_query)
    return result

@app.route('/debug_storage')
def debug_storage():
    """ Static mirrordom js files """
    global mirrordom_storage
    from xml.sax.saxutils import escape
    storage_str = pprint.pformat(mirrordom_storage)
    storage_str = escape(storage_str)
    return "<html><body><pre>%s</pre></body></html>"  % (storage_str)

#@app.route('/mirrordom/<name>', method='ANY')
#def handle_mirrordom(name):
#    """
#    Core mirrordom server functionality
#    """
#    global mirrordom_storage
#    query = bottle.request.params
#    bottle.response.set_header("Content-Type", "application/json")
#
#    #TODO: Tidy up this mess
#    if name == "add_diff":
#        # have to de-jsonise diff argument
#        result = mirrordom.server.handle_add_diff(mirrordom_storage,
#                window_id=query["window_id"],
#                diff=json.loads(query["diff"]))
#    elif name == "get_update":
#        result = mirrordom.server.handle_get_update(mirrordom_storage,
#                change_ids=json.loads(query["change_ids"]))
#    elif name == "new_window":
#        prop_diffs = json.loads(query["props"])
#        result = mirrordom.server.handle_new_window(mirrordom_storage,
#                query["html"], prop_diffs, query["url"])
#    elif name == "reset":
#        prop_diffs = json.loads(query["props"])
#        result = mirrordom.server.handle_reset(mirrordom_storage,
#                query["window_id"], query["html"], prop_diffs, query["url"])
#
#    else:
#        result = getattr(mirrordom.server, "handle_" + name)(mirrordom_storage, **query)
#    print result
#    return json.dumps(result)

@app.route('/static/mirrordom/<filepath:path>')
def js_static(filepath):
    """ Static mirrordom js files """
    return bottle.static_file(filepath, root=MIRRORDOM_JS_PATH)

@app.route('/static/<filepath:path>')
def static(filepath):
    """ Static files """
    return bottle.static_file(filepath, root=STATIC_PATH)

bottle.run(app, host='localhost', port=8079, debug=True)
