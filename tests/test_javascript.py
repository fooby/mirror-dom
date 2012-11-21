import json
import re
import os
import time

import nose.plugins.skip
from selenium.common.exceptions import NoSuchElementException

import util

def setupModule():
    util.start_webserver()

def teardownModule():
    util.stop_webserver()

class TestFirefox(util.TestBrowserBase):
    HTML_FILE = "test_javascript.html"

    @classmethod
    def _create_webdriver(cls):
        return util.get_debug_firefox_webdriver()

    def set_iframe_body(self, html):
        """
        Set the iframe body. Note: Body always has ipath [1], being the second
        child of <html>.
        """
        self.execute_script("""
            var iframe = document.getElementById("iframe");
            var body = MirrorDom.get_iframe_document(iframe)
                                .getElementsByTagName("body")[0];
            body.innerHTML = arguments[0];

            window.get_element = function(id) {
                return MirrorDom.get_iframe_document(iframe).getElementById(id);
            };
        """, html)

    def test_text_content(self):
        """ Grab text content inside an element """
        self.init_webdriver()
        self.set_iframe_body("""<span id="here">hello</span>""")
        content = self.execute_script("""
            var span = get_element("here");
            return MirrorDom.get_text_node_content(span.firstChild);
        """)
        assert content == "hello"

    def test_text_content_preceding_child(self):
        """ Grab text content inside an element preceding the first element"""
        self.init_webdriver()
        self.set_iframe_body("""<span id="here">helli<br/>World</span>""")
        content = self.execute_script("""
            var span = get_element("here");
            return MirrorDom.get_text_node_content(span.firstChild);
        """)
        assert content == "helli"

    def test_text_tail(self):
        """ Grab text content after an element """
        self.init_webdriver()
        self.set_iframe_body("""<span id="here">hello</span>blah""")
        content = self.execute_script("""
            var span = get_element("here");
            return MirrorDom.get_text_node_content(span.nextSibling);
        """)
        assert content == "blah"

    def test_text_tail_preceding_sibling(self):
        """ Grab text content after an element """
        self.init_webdriver()
        self.set_iframe_body("""<span id="here">hello</span>bloh<br/>ignore""")
        content = self.execute_script("""
            var span = get_element("here");
            return MirrorDom.get_text_node_content(span.nextSibling);
        """)
        assert content == "bloh"

    def test_text_tail_ignore_elements(self):
        self.init_webdriver()
        self.set_iframe_body("""<span id="here">hello <script>null</script> world!! woo</span>""")
        content = self.execute_script("""
            var span = get_element("here");
            return MirrorDom.get_text_node_content(span.firstChild);
        """)
        # Note: IE is weird with whitespace. We're going to be a little be
        # flexible for IE and use a regex.
        assert re.match("hello\s+world!! woo", content) is not None

class TestIE(TestFirefox):
    @classmethod
    def _create_webdriver(cls):
        return util.get_debug_ie_webdriver()

class TestChrome(TestFirefox):
    @classmethod
    def _create_webdriver(cls):
        return util.get_debug_chrome_webdriver()
