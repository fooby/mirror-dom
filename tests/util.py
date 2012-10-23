import os
import urllib
import urlparse
import SimpleHTTPServer
import SocketServer
import threading
import posixpath
import logging

import lxml
import lxml.doctestcompare
import lxml.html
import lxml.html.clean
import lxml.etree
from selenium import webdriver

from doctest import Example

def get_relative_path(*dirs):
    return os.path.normpath(os.path.join(os.path.dirname(__file__), *dirs))

def get_html_path(f):
    """
    :param f:   Name of HTML test file in the tests\html directory (e.g. "test_diff.html")
    :returns    Absolute path of html test file
    """
    path = os.path.join(get_relative_path("html"), f)
    assert os.path.isfile(path)
    return path

#def get_html_url(f):
#    path = get_html_path(f)
#    uri = "file:" + urllib.pathname2url(path)
#    return uri

def get_mirrordom_path():
    return get_relative_path("..", "python")

# -----------------------------------------------------------------------------
# Basic HTTP file server (because IE doesn't like file:/// files for automated
# scripting).
#
# It maps static files in the "html" subdirectory and also the "js" directory
# where the core MirrorDom files are.
# -----------------------------------------------------------------------------

class SimpleTestHTTPRequestHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        """Translate a /-separated PATH to the local filename syntax.

        Components that mean special things to the local file system
        (e.g. drive or directory names) are ignored.  (XXX They should
        probably be diagnosed.)

        """
        # abandon query parameters
        path = path.split('?',1)[0]
        path = path.split('#',1)[0]
        path = posixpath.normpath(urllib.unquote(path))
        words = path.split('/')
        words = filter(None, words)
        #path = os.getcwd()

        paths_to_try = [get_relative_path("html")]

        if (words[0] == "js"):
            words = words[1:]
            paths_to_try.append(get_relative_path("../js"))

        for p in paths_to_try:
            for word in words:
                drive, word = os.path.splitdrive(word)
                head, word = os.path.split(word)
                #if word in (os.curdir, os.pardir): continue
                path = os.path.join(p, word)

            if os.path.isfile(path):
                break


        self.log_message("Getting path for %s: %s", words, path)
        return path

    def log_message(self, format, *args):
        logging.getLogger("mirrordom.test_httpd").info(format, *args)


def get_simple_http_server():
    handler = SimpleTestHTTPRequestHandler
    httpd = SocketServer.TCPServer(("localhost", 0), handler)
    return httpd

class HttpServerThread(threading.Thread):
    def __init__(self, httpd):
        threading.Thread.__init__(self)
        self.httpd = httpd

    def get_address(self):
        return self.httpd.server_address

    def run(self):
        print "Starting HTTP server!"
        self.httpd.serve_forever()

    def stop_server(self):
        print "Stopping HTTP server!"
        self.httpd.shutdown()
        self.join()

HTTP_SERVER_THREAD = None
HTTP_SERVER_ADDRESS = None

def start_webserver():
    global HTTP_SERVER_THREAD, HTTP_SERVER_ADDRESS
    httpd = get_simple_http_server()
    HTTP_SERVER_ADDRESS = httpd.server_address
    HTTP_SERVER_THREAD = HttpServerThread(httpd)
    HTTP_SERVER_THREAD.start()

def stop_webserver():
    if HTTP_SERVER_THREAD is not None:
        HTTP_SERVER_THREAD.stop_server()

def get_webserver_address():
    return HTTP_SERVER_ADDRESS

# -----------------------------------------------------------------------------
# Testing helpers
# -----------------------------------------------------------------------------

def get_debug_firefox_webdriver():
    """
    Get Firefox webdriver with firebug enabled and some logging output
    """
    print "Starting firefox webdriver"
    profile = webdriver.FirefoxProfile()
    firebug = get_relative_path("stuff", "firebug-1.10.2-fx.xpi")
    profile.set_preference("extensions.firebug.currentVersion", "1.10.2")

    ff_log = get_relative_path("logs", "firefox.log")
    js_log = get_relative_path("logs", "firefox_js.log")
    profile.set_preference("webdriver.log.file", js_log)
    profile.set_preference("webdriver.firefox.logfile", ff_log)
    profile.set_preference("extensions.firebug.allPagesActivation", "on")

    profile.set_preference("extensions.firebug.console.enableSites", "true")
    profile.set_preference("extensions.firebug.script.enableSites", "true")
    profile.set_preference("extensions.firebug.net.enableSites", "true")

    profile.add_extension(firebug)
    return webdriver.Firefox(profile)

def get_debug_ie_webdriver():
    print "Starting IE webdriver"
    ie_log = get_relative_path("logs", "ie.log")
    log_level = "DEBUG"
    return webdriver.Ie(log_level=log_level, log_file=ie_log)

def get_debug_chrome_webdriver():
    print "Starting chrome webdriver"
    # Note: chromedriver.log appears in the current directory and there's no
    # way to change this.
    return webdriver.Chrome()

# -----------------------------------------------------------------------------
# HTML parsing fixes

class LHTMLOutputChecker(lxml.doctestcompare.LHTMLOutputChecker):
    """ The standard LHTML output checker doesn't use the lxml.html.fromstring
    parser """

    def get_parser(self, want, got, optionflags):
        """ LHTMLOutputChecker """
        return lxml.html.fromstring

def force_insert_tbody(html_tree):
    """
    Force insert tbody elements between tables and trs
    """
    tables = html_tree.iter('table')
    for table in tables:
        tbody = None
        children = list(table)
        for c in children:
            if not isinstance(c.tag, basestring):
                continue
            elif c.tag.lower() == "colgroup":
                continue
            elif c.tag.lower() == "tbody":
                tbody = None
            else:
                if tbody is None:
                    tbody = lxml.html.Element('tbody')
                    c.addprevious(tbody)
                tbody.append(c)
    return html_tree

# -----------------------------------------------------------------------------

# Internet Explorer HTML comparison hacks

NODE_DEFAULTS = {
    "input": {"size": "50", "type": "text"},
    "th": {"colspan": "1"},
    "td": {"colspan": "1"}
}

def augment_single_node_defaults_for_ie(node):
    """ IE stuffs up our InnerHTML by omitting "default" attributes on certain
    elements
    
    e.g. <input type="text" size="50"/>, both the "type" and "size"
    attributes are default values and gets stripped out.
    
    We'll just shove these default values in EVERY eleent where we can to
    ensure it passes the comparison.


    """
    logger = logging.getLogger("mirrordom.ie_default_hack")
    try:
        defaults = NODE_DEFAULTS[node.tag]
    except KeyError:
        return

    for attribute, value in defaults.iteritems():
        if attribute not in node.attrib:
            logger.info("Shoving %s=%s into %s!", attribute, value, node.tag)
            node.attrib[attribute] = value
            
def augment_tree_defaults_for_ie(root):
    """ In place tree modification """
    for element in root.iter():
        augment_single_node_defaults_for_ie(element)

def strip_hrefs(doc):
    doc.rewrite_links(lambda url: "")

def strip_localhost_hrefs_for_ie(doc):
    # rewrite_links only defined on HtmlElement
    assert isinstance(doc, lxml.html.HtmlElement)

    def strip_hostname(url):
        parsed = urlparse.urlparse(url)
        if parsed.hostname == "127.0.0.1":
            result = "".join(parsed[2:]).lstrip("/")
            #print "Got %s, return %s" % (url, result)
            return result
        else:
            #print "Got %s, not doing anything" % (url)
            return url
    doc.rewrite_links(strip_hostname)

def remove_title_for_ie(doc):
    head = doc.find('head/title')
    if head is not None:
        head.getparent().remove(head)

# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------

class TestBase(object):
    def get_html_cleaner(self):
        """
        LXML html cleaner with settings set
        """
        cleaner = lxml.html.clean.Cleaner()
        cleaner.frames = False
        cleaner.forms = False
        cleaner.page_structure = False
        #cleaner.style = False
        return cleaner


    def compare_html(self, want, got,
            should_augment_defaults_for_ie=True,
            should_strip_localhost_hrefs_for_ie=True,
            should_remove_title_for_ie=True,
            strip_style_attributes=True,
            ignore_hrefs=True,
            clean=False):
        """
        Yep, compare two target documents together

        :param want:    The "template" HTML we're matching against (either a string or a etree document)
        :param got:     The output HTML we got from our test (string or etree)
        :param should_augment_defaults_for_ie:
                        Force default attributes onto various nodes to
                        compensate for IE removing attributes at whim

                        e.g. All <input> elements without a "type" attribute
                        will get a type="text" attribute forcibly added before
                        the compare

        :param should_strip_localhost_hrefs_for_ie:
                        IE hrefs tend to prefix with the hostname. This messes
                        with our comparison, so strip the hostname prefixs. e.g.

                        <a href="http://127.0.0.1:49602/test_dom_sync_content2.html">
                        will be fixed to
                        <a href="test_dom_sync_content2.html">

        :param should_remove_title_for_ie:
                        IE tends to remove any text inside the <title> element,
                        causing mismatches. We'll just remove it from our
                        compare documents.

        :param strip_style_attributes:
                        IE's style attributes are unworkable for comparison

        :param ignore_hrefs:
                        Strip HREFs out

        :param clean:   Try to perform some extra cleaning using the lxml html
                        Cleaner class to make the comparison less brittle.
        """
        want_doc = lxml.html.fromstring(want) if isinstance(want, basestring) else want
        got_doc = lxml.html.fromstring(got) if isinstance(got, basestring) else got

        compare = LHTMLOutputChecker()

        if should_augment_defaults_for_ie:
            augment_tree_defaults_for_ie(want_doc)
            augment_tree_defaults_for_ie(got_doc)

        if ignore_hrefs:
            strip_hrefs(want_doc)
            strip_hrefs(got_doc)
        elif should_strip_localhost_hrefs_for_ie:
            strip_localhost_hrefs_for_ie(want_doc)
            strip_localhost_hrefs_for_ie(got_doc)

        if should_remove_title_for_ie:
            remove_title_for_ie(want_doc)
            remove_title_for_ie(got_doc)

        if strip_style_attributes:
            lxml.etree.strip_attributes(want_doc, "style")
            lxml.etree.strip_attributes(got_doc, "style")


        if clean:
            cleaner = self.get_html_cleaner()
            cleaner(want_doc)
            cleaner(got_doc)

        result = compare.compare_docs(want_doc, got_doc)

        if not result:
            got_doc_string = lxml.html.tostring(got_doc)
            want_doc_string = lxml.html.tostring(want_doc)
            print compare.output_difference(Example("", want_doc_string),
                    got_doc_string, 0)
        return result

class JavascriptFailed(Exception):
    pass

class TestBrowserBase(TestBase):

    # File to initialise the browser with
    HTML_FILE = None
    _webdriver = None

    # -----------------------------------------------------------------------------
    # Class level testing setup/teardown
    #
    # Note: If overriding teardownClass/setupClass check if you need to call
    # the corresponding superclass method 

    @classmethod
    def teardownClass(cls):
        cls._kill_webdriver()

    # -----------------------------------------------------------------------------
    # WEBDRIVER MODULE LEVEL HACK (it's actually managed at the module level,
    # but I'm just storing the webdriver reference against the class to avoid
    # module level variables). This might have to be rewritten

    @classmethod
    def _create_webdriver(cls):
        #return get_debug_firefox_webdriver()
        #return get_debug_ie_webdriver()
        raise Exception("Must override this method")

    @classmethod
    def _kill_webdriver(cls):
        if cls._webdriver:
            if os.environ.get("KEEP_WEBDRIVER_ALIVE") == "1":
                print "Keeping webdriver %s alive!" % (cls._webdriver)
            else:
                print "Killing webdriver %s!" % (cls._webdriver)
                cls._webdriver.quit()

            # Set to None to prevent multiple instances of this class to be run
            # sequentially
            cls._webdriver = None

    @classmethod
    def _get_webdriver(cls):
        if cls._webdriver is None:
            cls._webdriver = cls._create_webdriver()
        assert cls._webdriver
        print "Using webdriver %s!" % (cls._webdriver)
        return cls._webdriver


    def init_webdriver(self):
        """ Refresh the test page for a fresh start.  """
        self.webdriver = self._get_webdriver()
        url = self.get_html_url(self.HTML_FILE)
        self.webdriver.get(url)

    def execute_script(self, script, *args):
        """
        This seems to be working to get some non-nonsensical error feedback.

        TODO: Move tests to use this instead of self.webdriver.execute_script
        """
        wrapped_script = """\
            function _wrappa_() {
                %s
            };
            var result;
            try {
                result = _wrappa_.apply(this, arguments);
                result = [true, result];
            } catch (e) {
                result = [false, e.message];
            }
            return result;
        """ % (script)
        result = self.webdriver.execute_script(wrapped_script, *args)
        success, value = result
        if not success:
            raise JavascriptFailed(value)
        else:
            return value

    def get_html_url(self, f):
        # Assumes file is in html/ directory 
        hostname, port = get_webserver_address()
        url = "http://%s:%s/%s" % (hostname, port, f)
        return url

# -----------------------------------------------------------------------------
# Diff comparison utilities
# -----------------------------------------------------------------------------

def attr_prop_diff_extract(diff):
    """
    Extract property/attr diffs (not for use on on deleted, added diffs)
    """
    if len(diff) == 4:
        diff_type, node_type, path, added = diff
        return type, path, added, None
    elif len(diff) == 5:
        diff_type, node_type, path, added, removed = diff
        return type, path, added, removed

def diff_contains_changed_property_key(diffs, s):
    """
    Check if a certain property was changed, but ignore the value.

    e.g. If you changed a "disabled" property and want to check if the diff
    made it in, look here.
    """
    prop_diffs = [x for x in diffs if x[0] == "props"]
    def dict_key_contains(dct, value):
        return any(value in v.lower() for v in dct.iterkeys())
    def list_contains(lst, value):
        if not lst:
            return False
        return any(value in v.lower() for v in lst)
    return any(dict_key_contains(added, s) or list_contains(removed, s) \
            for _, _, added, removed in map(attr_prop_diff_extract, prop_diffs))


def diff_contains_changed_property_value(diffs, s):
    """
    Check if a prop diff changed value contains a string

    e.g. If you set some background color to "purple", and you just want to
    check for "purple", use this

    Note: Doesn't account for removed properties
    """
    prop_diffs = [x for x in diffs if x[0] == "props"]
    def dict_value_contains(dct, value):
        return any(value in v.lower() for v in dct.itervalues() \
                if isinstance(v, basestring))
    return any(dict_value_contains(added, s) \
            for _, _, added, removed in map(attr_prop_diff_extract, prop_diffs))


def diff_contains_changed_attribute(diffs, s):
    """
    Check if a certain attribute was changed.

    e.g. If you changed a "cellspacing" property and want to check if the diff
    made it in, look here.
    """
    attr_diffs = [x for x in diffs if x[0] == "attrib"]
    def dict_key_contains(dct, value):
        return any(value in v.lower() for v in dct.iterkeys())

    def list_contains(lst, value):
        if not lst:
            return False
        return any(value in v.lower() for v in lst)

    return any(dict_key_contains(added, s) or list_contains(removed, s) \
            for _, _, added, removed in map(attr_prop_diff_extract, attr_diffs))

def diff_contains_empty_attr_prop_values(diffs):
    """
    Check if any empty values made it through (we might be picking up some
    unnecessary items)
    """
    attr_prop_diffs = [x for x in diffs if x[0] in ("attrib", "props")]
    def dict_value_empty(dct):
        return any(not v for v in dct.itervalues())
    return any(dict_value_empty(added) \
            for _, _, added, removed in map(attr_prop_diff_extract, attr_prop_diffs))
