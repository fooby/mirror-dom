import os
import urllib
import urlparse
import SimpleHTTPServer
import SocketServer
import threading
import posixpath
import logging
import re

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
    #ie_log = get_relative_path("logs", "ie.log")
    #log_level = "DEBUG"
    #return webdriver.Ie(log_level=log_level, log_file=ie_log)
    return webdriver.Ie()

def get_debug_chrome_webdriver():
    print "Starting chrome webdriver"
    # Note: chromedriver.log appears in the current directory and there's no
    # way to change this.
    return webdriver.Chrome()

# -----------------------------------------------------------------------------

class CompareException(Exception):
    def __init__(self, msg, elem1_tree=None, elem1=None,
            elem2_tree=None, elem2=None):
        self.msg = msg
        self.elem1_tree = elem1_tree
        self.elem2_tree = elem2_tree
        self.elem1 = elem1
        self.elem2 = elem2

    def get_elem_desc(self, desc, tree, elem):
        if elem is not None:
            return "%s XPath: %s" % (desc, tree.getpath(elem))
        else:
            return "%s is None"

    def __str__(self):
        result = self.msg
        if self.elem1 is not None:
            result += "\n" + self.get_elem_desc("Element 1", self.elem1_tree, self.elem1)
        if self.elem2 is not None:
            result += "\n" + self.get_elem_desc("Element 2", self.elem2_tree, self.elem2)
        return result

class HTMLComparator(object):
    """ Compares two HTML trees

    :param strip_text:
                    Strip surrounding whitespace from text comparison.

    :param ignore_all_whitespace:
                    Get rid of ALL whitespace in text comparison.
                    Used to deal with browser whitespace inconsistencies.
                    This trumps the strip_text option.

    :param ignore_ie_default_attributes:
                    Force default attributes onto various nodes to
                    compensate for IE removing attributes at whim

                    e.g. For each, <input> elements without a "type" attribute
                    we'll force add type="text" attribute forcibly before
                    the compare.

    :param ignore_hrefs:
                    Strip HREFs out

    :param ignore_attr_values:
                    A list of attributes for which we'll ignore comparing the VALUES

    :param strip_localhost_hrefs_for_ie:
                    IE hrefs tend to prefix with the hostname. This messes
                    with our comparison, so strip the hostname prefixs. e.g.

                    <a href="http://127.0.0.1:49602/test_dom_sync_content2.html">
                    will be fixed to
                    <a href="test_dom_sync_content2.html">

    :param ignore_title:
                    IE tends to remove any text inside the <title> element,
                    causing mismatches. We'll just remove it from our
                    compare documents.

    :param strip_style_attributes:
                    IE's style attributes are unworkable for comparison


    """

    # Options
    strip_text=True
    ignore_all_whitespace=False
    ignore_title=True
    ignore_script_content=False
    ignore_ie_default_attributes=True
    ignore_jquery_attributes=True
    ignore_attr_values=[]
    ignore_tags = []
    ignore_attrs = ['webdriver'] # Selenium injects this attribute
    ignore_comments = False
    strip_localhost_hrefs_for_ie = True

    _IE_NODE_DEFAULTS = {
        "input": {"size": "50", "type": "text"},
        "th": {"colspan": "1"},
        "td": {"colspan": "1"}
    }

    _ignore_attr_values = ['style']
    _ignore_attrs = []
    _ignore_tags = []

    def __init__(self, **options):
        self.logger = logging.getLogger("mirrordom.htmlcompare")

        # Set options
        for k, v in options.iteritems():
            if not hasattr(self, k):
                raise Exception("Unexpected HTMLComparator option: %s" % (k))
            setattr(self, k, v)

        self._ignore_tags = self._ignore_tags[:]
        self._ignore_attr_values = self._ignore_attr_values[:]
        self._ignore_attrs = self._ignore_attrs[:]

        if self.ignore_attr_values:
            self._ignore_attr_values.extend(self.ignore_attr_values)

        if self.ignore_attrs:
            self._ignore_attrs.extend(self.ignore_attrs)

        # Ignore tags
        if self.ignore_title:
            self._ignore_tags.append("title")
        if self.ignore_tags:
            self._ignore_tags.extend(self.ignore_tags)

    @staticmethod
    def strip_localhost_href(url):
        """
        """
        parsed = urlparse.urlparse(url)
        if parsed.hostname == "127.0.0.1":

            # HACK: If the URL ends with we assume the original href was simply "#"
            if url.endswith("#"):
                return "#"

            result = "".join(parsed[2:]).lstrip("/")
            return result
        else:
            return url

    def compare_text(self, a, b):
        if a is None:
            a = ""
        if b is None:
            b = ""
        if self.ignore_all_whitespace:
            a = re.sub(r'\s+', '', a)
            b = re.sub(r'\s+', '', b)
        elif self.strip_text:
            a = a.strip()
            b = b.strip()
        return a == b

    def compare_attrs(self, a, b):
        assert a.tag.lower() == b.tag.lower()

        def apply_remove_attr(x):
            a_attrib.pop(x, None)
            b_attrib.pop(x, None)

        def apply_ignore_attr_values(x):
           if x in a_attrib: a_attrib[x] = None
           if x in b_attrib: b_attrib[x] = None

        def apply_setdefault(k, v):
            a_attrib.setdefault(k, v)
            b_attrib.setdefault(k, v)

        def remove_jquery_attributes(attrib):
            remove = [k for k in attrib.keys() if k.startswith('jquery')]
            for k in remove:
                attrib.pop(k)


        a_attrib = dict(a.attrib)
        b_attrib = dict(b.attrib)

        # Perform operations
        if self._ignore_attrs:
            for k in self._ignore_attrs:
                apply_remove_attr(k)

        if self.ignore_ie_default_attributes and a.tag in self._IE_NODE_DEFAULTS:
            default_attrs = self._IE_NODE_DEFAULTS[a.tag]
            for k, v in default_attrs.iteritems():
                apply_setdefault(k, v)

        if self._ignore_attr_values:
            for k in self._ignore_attr_values:
                apply_ignore_attr_values(k)

        if self.strip_localhost_hrefs_for_ie and a.tag == "a":
            if 'href' in a_attrib and a_attrib['href'] is not None:
                a_attrib['href'] = self.strip_localhost_href(a_attrib['href'])
            if 'href' in b_attrib and b_attrib['href'] is not None:
                b_attrib['href'] = self.strip_localhost_href(b_attrib['href'])

        if self.ignore_jquery_attributes:                
            remove_jquery_attributes(a_attrib)
            remove_jquery_attributes(b_attrib)
            
        a_set = set(a_attrib)
        b_set = set(b_attrib)
        added = b_set - a_set
        removed = a_set - b_set

        if added or removed:
            return False, "Added attributes: [%s] Missing attributes: [%s]" % \
                    (", ".join(added), ", ".join(removed))

        assert a_set == b_set                    
        
        changed = [(k, v, b_attrib[k]) for k, v in a_attrib.iteritems() \
                if v != b_attrib[k]]

        if changed:
            diff_strings = ["[%s] %r != %r" % (c) for c in changed]
            return False, "Values differ...%s" % (", ".join(diff_strings))

        assert a_attrib == b_attrib
        return True, None

    def should_ignore_elem(self, elem):
        elem_type = self.get_elem_type(elem)
        if elem_type == "element":
            if elem.tag.lower() in self._ignore_tags:
                return True
        elif elem_type == "comment":
            return self.ignore_comments
        elif elem_type == "pi":
            return True
        return False

    def should_ignore_elem_text(self, elem):
        if self.ignore_script_content and elem.tag.lower() == 'script':
            return True
        return False

    def get_next_elem(self, tree_iter):
        """ Retrieve next element from tree iterator """
        try:
            while True:
                e = tree_iter.next()
                if not self.should_ignore_elem(e):
                    return e
                else:
                    self.logger.debug("Ignoring element: %s",
                            lxml.etree.tostring(e))
        except StopIteration:
            return None

    def compare_elements(self, elem1, elem2, desired_tree, got_tree):        
        if elem1.tag.lower() != elem2.tag.lower():
            raise CompareException(
                    "Tags are not equal: %s != %s" % (elem1.tag, elem2.tag),
                    desired_tree, elem1, got_tree, elem2)

        if not self.compare_text(elem1.tail, elem2.tail):
            raise CompareException(
                    "Different tail text: %r != %r" % (elem1.tail, elem2.tail),
                    desired_tree, elem1, got_tree, elem2)

        if not self.should_ignore_elem_text(elem1):
            if not self.compare_text(elem1.text, elem2.text):
                raise CompareException(
                        "Different child text: %r != %r" % (elem1.text, elem2.text),
                        desired_tree, elem1, got_tree, elem2)

        # Python dictionary key AND value compare
        success, reason = self.compare_attrs(elem1, elem2)
        if not success:
            raise CompareException("Different attributes: %s" % (reason),
                    desired_tree, elem1, got_tree, elem2)

    def get_elem_type(self, elem):
        if isinstance(elem.tag, basestring):
            return "element"
        elif elem.tag is lxml.etree.Comment:
            return "comment"
        elif elem.tag is lxml.etree.ProcessingInstruction:
            return "pi"
        else:
            raise Exception("Unknown element type: %r" % (elem))


    def run(self, desired, got):    
        """ Compare desired HTML to received HTML
        
        :param desired:     Desired HTML string
        :param got:         Received HTML string
        """

        parse = lambda x: lxml.etree.ElementTree(lxml.etree.fromstring(x))
        desired_tree = parse(desired)
        got_tree = parse(got)

        #print "Want Tree: %s" % (lxml.etree.tostring(desired_tree))
        #print "Got Tree: %s" % (lxml.etree.tostring(got_tree))

        t1 = desired_tree.iter()
        t2 = got_tree.iter()

        while True:
            elem1 = self.get_next_elem(t1)
            elem2 = self.get_next_elem(t2)

            if elem1 is None and elem2 is None:
                return True
            elif (elem1 is None) != (elem2 is None):
                raise CompareException("Different tree structures.",
                        desired_tree, elem1, got_tree, elem2)

            elem1_type = self.get_elem_type(elem1)
            elem2_type = self.get_elem_type(elem2)

            if elem1_type != elem2_type:
                raise CompareException("Different element types: %s != %s" % \
                        (elem1_type, elem2_type),
                        desired_tree, elem1, got_tree, elem2)

            elif elem1_type == "element":
                self.compare_elements(elem1, elem2, desired_tree, got_tree)
                    

        raise Exception("shouldn't be hit")

# -----------------------------------------------------------------------------

class TestBase(object):
    def get_html_cleaner(self):
        """
        LXML html cleaner with settings set
        """
        cleaner = lxml.html.clean.Cleaner(
            frames = False,
            forms = False,
            page_structure = False,
        )
        return cleaner

    def compare_html(self, desired, got, **options):
        comparator = HTMLComparator(**options)
        return comparator.run(desired, got)

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
