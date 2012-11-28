"""
Test for the mirrordom server functionality

Note: This short circuits the RPC communication channel, as that's an added
layer of complexity.

That test will be done in another module. Here we'll be reaching into a lot of
javascript and python internal mirrordom functions.
"""

import sys
import os
import json
import time

from selenium import webdriver
import lxml

import util
import test_javascript

try:
    import mirrordom.server
except ImportError:
    sys.path.append(util.get_mirrordom_path())
    import mirrordom.server

from mirrordom.sanitise import sanitise_html, sanitise_diffs
from mirrordom.parser import parse_html

def setupModule():
    util.start_webserver()

def teardownModule():
    util.stop_webserver()

class XMLCompareException(Exception):
    pass

class TestFirefox(util.TestBrowserBase):
    HTML_FILE = "test_mirrordom.html"

    @classmethod
    def _create_webdriver(cls):
        return util.get_debug_firefox_webdriver()

    # --------------------------------------------------------------------------
    # Helpers
    # --------------------------------------------------------------------------
    def html_to_xml(self, html):
        tree = parse_html(html)
        return lxml.etree.tostring(tree)

    def compare_frames(self, sanitise_broadcaster=True, **compare_kwargs):
        broadcaster_html = self.webdriver.execute_script(
                "return get_broadcaster_html()")
        broadcaster_html = broadcaster_html.replace('\r\n', '\n')
        viewer_html = self.webdriver.execute_script("return get_viewer_html()")
        viewer_html = viewer_html.replace('\r\n', '\n')

        if sanitise_broadcaster:
            broadcaster_html = sanitise_html(broadcaster_html)
        else:
            broadcaster_html = self.html_to_xml(broadcaster_html)

        print ""
        print "Broadcaster HTML"            
        print "================"
        print broadcaster_html

        print ""
        print "Viewer HTML"            
        print "================"
        print viewer_html

        viewer_html = self.html_to_xml(viewer_html)
        return self.compare_html(broadcaster_html, viewer_html,
                **compare_kwargs)

    def apply_viewer_html(self, html):
        self.execute_script("""
            var de = viewer.get_document_element();
            viewer.apply_document(de, arguments[0]);
        """, html)

    def apply_viewer_diff(self, diffs):
        self.execute_script("""
            viewer.apply_diffs(null, JSON.parse(arguments[0]));
        """, json.dumps(diffs))

    def get_broadcaster_diff(self):
        result = self.execute_script("return JSON.stringify(broadcaster.get_diff());")
        return json.loads(result)

    # --------------------------------------------------------------------------
    # Tests
    # --------------------------------------------------------------------------
    def test_init_html(self):
        """
        Test 1: Basic HTML transfer

        Note: We don't want to verify the document transmit format in this
        test. It may or may not be a simple string.
        """
        self.init_webdriver()
        init_html = self.execute_script("""
            var data = broadcaster.start_document();
            return data['html'];
        """)
        result_html = sanitise_html(init_html)
        self.apply_viewer_html(result_html)
        assert self.compare_frames()

    def test_diff_transfer(self):
        """
        Test 2: Basic diff transfer
        """
        self.init_webdriver()
        # Replicate the initial test
        self.test_init_html()

        # Now let's go further and modify the document
        self.webdriver.execute_script("""
            broadcaster_iframe.contentWindow.add_div();
        """)
        diff = self.get_broadcaster_diff()
        print "==DIFF=="
        print json.dumps(diff)
        diff = sanitise_diffs(diff)
        self.apply_viewer_diff(diff)
        assert self.compare_frames()

    def test_all_property_transfer(self):
        """
        Test 3: Initial property transfer - make sure the viewer gets stuff set.
        """
        self.init_webdriver()

        # Replicate the initial test
        self.test_init_html()

        # Now let's go further and modify the document
        self.webdriver.execute_script("""
            broadcaster_iframe.contentWindow.change_some_css();
        """)

        # Change text input value property
        new_input_value = "dfkjgopi"
        self.webdriver.switch_to_frame('broadcaster_iframe')
        input = self.webdriver.find_element_by_id('thetextinput')
        input.send_keys(new_input_value)

        self.webdriver.switch_to_default_content()
        diff = self.execute_script("""
            var data = broadcaster.start_document();
            return JSON.stringify(data["props"]);
        """)
        diff = json.loads(diff)

        # Only properties
        assert all(d[0] == "props" for d in diff)
        assert util.diff_contains_changed_property_key(diff, "value")

        # Should be a border in there somewhere (note: IE returns individual
        # border rules for each side, FF retains the single border rule)
        assert util.diff_contains_changed_property_value(diff, "purple")

        diff = sanitise_diffs(diff)

        # We can reuse test 2's diff apply thing
        self.apply_viewer_diff(diff)

        # Verify the diff made it through
        self.webdriver.switch_to_frame('viewer_iframe')
        input = self.webdriver.find_element_by_id('thetextinput')
        input_value = input.get_attribute("value")
        print "Got input value: %s. Expected: <original value>%s" % (input_value, new_input_value)
        assert input_value.endswith(new_input_value)
        table = self.webdriver.find_element_by_id('thetable')
        table_background_colour = input.value_of_css_property("background-color")
        table_background_colour = table_background_colour.replace(" ", "")
        assert table_background_colour in ("purple", "rgba(255,255,255,1)")

    def test_link_stylesheet_transfer(self):
        """
        Test 4: Stylesheets in head element
        """
        self.init_webdriver()

        # Replicate the initial test
        self.test_init_html()

        # Check for stylesheet
        self.webdriver.switch_to_frame('viewer_iframe')

        # Look for test_mirrordom.css
        links = self.webdriver.find_elements_by_xpath('/html/head/link')
        for l in links:
            # When retrieving in IE, href is prefixed with hostname
            if l.get_attribute("href").endswith("test_mirrordom.css"):
                print "Href: %s" % (l.get_attribute("href"))
                link_node = l
                break

        assert link_node is not None
        assert link_node.get_attribute("rel").lower() == "stylesheet"
        assert link_node.get_attribute("type").lower() == "text/css"

        # Count stylesheets
        #num_stylesheets = self.webdriver.execute_script("return document.styleSheets.length;")
        stylesheet_hrefs = self.webdriver.execute_script("""
            var hrefs=[];
            for (var i = 0; i < document.styleSheets.length; i++) {
              if (document.styleSheets[i].href != undefined) {
                hrefs.push(document.styleSheets[i].href);
              }
            }
            return hrefs;
        """)

        assert any(x.endswith("test_mirrordom.css") for x in stylesheet_hrefs)

    def test_diff_transfer_inserted_element(self):
        """
        Test 5: Basic diff transfer, with an element inserted in the middle of
        the DOM.
        """
        self.init_webdriver()

        # Replicate the initial test
        self.test_init_html()

        # Now let's go further and modify the document
        self.webdriver.execute_script("""
            broadcaster_iframe.contentWindow.insert_div();
        """)
        diff = self.get_broadcaster_diff()
        diff = sanitise_diffs(diff)
        self.apply_viewer_diff(diff)
        assert self.compare_frames()

    def test_diff_transfer_inserted_table(self):
        """
        Test 6: More advanced diff transfer, with big table
        """
        self.init_webdriver()
        # Replicate the initial test
        self.test_init_html()
        # Now let's go further and modify the document
        self.webdriver.execute_script("""
            broadcaster_iframe.contentWindow.insert_table();
        """)
        diff = self.get_broadcaster_diff()
        for d in diff:
            if d[0] == "node":
                print "Diff: %s" % (d[3])
        diff = sanitise_diffs(diff)
        self.apply_viewer_diff(diff)
        assert self.compare_frames(ignore_ie_default_attributes=True)

class TestIE(TestFirefox):
    @classmethod
    def _create_webdriver(cls):
        return util.get_debug_ie_webdriver()

class TestChrome(TestFirefox):
    @classmethod
    def _create_webdriver(cls):
        return util.get_debug_chrome_webdriver()
