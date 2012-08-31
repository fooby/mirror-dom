import os
import urllib
import html5lib
import lxml
import lxml.doctestcompare
import lxml.html
import lxml.html.clean
#import lxml.html.soupparser
import lxml.html.html5parser
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

def get_html_url(f):
    path = get_html_path(f)
    uri = "file:" + urllib.pathname2url(path)
    return uri

def get_mirrordom_path():
    return get_relative_path("..", "python")


# -----------------------------------------------------------------------------
# Testing helpers
# -----------------------------------------------------------------------------

def get_debug_firefox_webdriver():
    """
    Get Firefox webdriver with firebug enabled and some logging output
    """
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

class XMLCompareException(Exception):
    pass

def parse_html_string(s):
    parser = lxml.html.html5parser.HTMLParser(namespaceHTMLElements=False)
    return lxml.html.html5parser.fromstring(s, parser=parser)

class LHTML5OutputChecker(lxml.doctestcompare.LHTMLOutputChecker):
    def get_parser(self, want, got, optionflags):
        return parse_html_string

class TestBrowserBase(object):

    # File to initialise the browser with
    HTML_FILE = None

    _webdriver = None

    @classmethod
    def start_webdriver(cls):
        cls._webdriver = get_debug_firefox_webdriver()

    @classmethod
    def kill_webdriver(cls):
        #cls._webdriver.quit()
        pass

    def get_cleaner(self):
        cleaner = lxml.html.clean.Cleaner()
        cleaner.frames = False
        cleaner.forms = False
        cleaner.page_structure = False
        #cleaner.style = False
        return cleaner

    def setUp(self):
        # Refresh the test page for a fresh start
        self.driver = self._get_webdriver()
        url = get_html_url(self.HTML_FILE)
        self.driver.get(url)

    def _get_webdriver(self):
        assert self._webdriver
        return self._webdriver

    def compare_html(self, orig, test, clean=False):
        compare = LHTML5OutputChecker()
        #result = compare.compare_docs(orig, test)
        #result = compare.check_output(orig, test, 0)

        orig_doc = parse_html_string(orig)
        test_doc = parse_html_string(test)

        if clean:
            # Oh man...as a result of html5parser.fromstring, we have
            # lxml.etree._Element instances. We want lxml.html.ELement instances.
            # Dump to string and re-parse!
            #
            # Note: html5lib.fromstring performs crucial operations such as
            # injecting <tbody>s between <tables> and <trs>, hence this
            # "useless" operation.
            cleaner = self.get_cleaner()
            orig_doc = lxml.html.fromstring(lxml.html.tostring(orig_doc))
            test_doc = lxml.html.fromstring(lxml.html.tostring(orig_doc))
            cleaner(orig_doc)
            cleaner(test_doc)

        result = compare.compare_docs(orig_doc, test_doc)

        if not result:
        #if True:
            test_doc_string = lxml.html.tostring(test_doc)
            orig_doc_string = lxml.html.tostring(orig_doc)
            print compare.output_difference(Example("", orig_doc_string),
                    test_doc_string, 0)
        return result
