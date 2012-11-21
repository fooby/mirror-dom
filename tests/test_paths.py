import json
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
    HTML_FILE = "test_paths.html"

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
        """, html)


    def find_targets(self):
        found_ipaths = self.execute_script("""
            var iframe = document.getElementById("iframe");
            var de = MirrorDom.get_iframe_document(iframe).documentElement;
            var dom_iterator = new MirrorDom.DomIterator(de);
            var found = [];
            var handler = function(node, ipath_base, ipath, data) {
                if (node.id == "target") {
                    data.push(ipath);
                }
            };
            dom_iterator.add_handler(handler, found);
            dom_iterator.run();
            return found;
        """)
        return found_ipaths

    def test_get_simple_path(self):
        """ Test simple path"""
        self.init_webdriver()
        self.set_iframe_body("""<div id="target">here</div>""")
        found_ipaths = self.find_targets()
        assert found_ipaths == [[1, 0]]

    def test_get_path_around_text(self):
        """ Test path with text."""
        self.init_webdriver()
        self.set_iframe_body("""
                <span>lsjfls</span>jdfl
                <div id="target">asdgds</div>sdgds
                &x160;<div>gsdg
                  <div id="target">helo</div>
                </div>""")
        found_ipaths = self.find_targets()
        assert found_ipaths == [[1, 1], [1, 2, 0]]

    def test_get_path_ignore_nodes(self):
        """ Test path with ignoring elements """
        self.init_webdriver()
        self.set_iframe_body("""
            <div>
              <script type="text/javascript">null</script>
              <br/>
              <script type="text/javascript">null</script>
              <span id="target">hello</span>
            </div>
        """)
        found_ipaths = self.find_targets()
        assert found_ipaths == [[1, 0, 1]]

class TestIE(TestFirefox):
    @classmethod
    def _create_webdriver(cls):
        return util.get_debug_ie_webdriver()

class TestChrome(TestFirefox):
    @classmethod
    def _create_webdriver(cls):
        return util.get_debug_chrome_webdriver()
