"""
Test for iframe functionality. Requires some mirrordom.server intervention.

This won't go totally into depth.
"""

import sys
import os
import json
import time

import util
import test_javascript

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException

try:
    import mirrordom.server
except ImportError:
    sys.path.append(util.get_mirrordom_path())
    import mirrordom.server

def setupModule():
    util.start_webserver()

def teardownModule():
    util.stop_webserver()

class XMLCompareException(Exception):
    pass

class TestFirefox(util.TestBrowserBase):
    HTML_FILE = "test_svg.html"

    @classmethod
    def _create_webdriver(cls):
        return util.get_debug_firefox_webdriver()

    # --------------------------------------------------------------------------
    # Helpers
    # --------------------------------------------------------------------------
    def compare_inner_iframes(self, iframe_name):
        # Grab the broadcaster's iframes
        self.webdriver.switch_to_default_content()
        self.webdriver.switch_to_frame('broadcaster_iframe')
        source_iframe_html = self.webdriver.execute_script(
                "return window.document.documentElement.innerHTML")

        # Grab the viewer's iframes
        self.webdriver.switch_to_default_content()
        self.webdriver.switch_to_frame('viewer_iframe')
        dest_iframe_html = self.webdriver.execute_script(
                "return window.document.documentElement.innerHTML")

        return self.compare_html(source_iframe_html, dest_iframe_html, clean=True)

    def get_viewer_html(self, fix_newlines=True):
        viewer_html = self.execute_script("""
            var de = viewer.get_document_element();
            return MirrorDom.outerhtml(de);
        """)
        if fix_newlines:
            viewer_html = viewer_html.replace('\r\n', '\n')
        return viewer_html

    def get_broadcaster_diff(self):
        result = self.execute_script("return JSON.stringify(broadcaster.get_diff());")
        return json.loads(result)
    # --------------------------------------------------------------------------
    # Tests
    # --------------------------------------------------------------------------
    def test_get_svg_document(self):
        """ Test 1: Make sure we detect when iframes are removed """
        self.init_webdriver()
        html = self.webdriver.execute_script("""
          var data = broadcaster.start_document();
          return data["html"];
        """)
        assert "<svg" in html

    TEST_APPLY_SVG_DOCUMENT = """\
           <html>
             <head>
               <title>helo</title>
             </head>
             <body>
               <h1>SVG test</h1>
               <svg id="thesvg" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
                   <rect x="10" y="10" height="100" width="100" style="stroke:#ff0000; fill: #0000ff"/>
               </svg>
             </body>
           </html>"""

    def test_apply_svg_document(self):
        """ Test 2: See if we can apply a document containing an SVG """
        self.init_webdriver()
        desired_html = self.TEST_APPLY_SVG_DOCUMENT
        self.webdriver.execute_script("""
          var doc_elem = viewer.get_document_element();
          viewer.apply_document(doc_elem, arguments[0]);
        """, desired_html)
        # Internet explorer values contain windows line endings
        viewer_html = self.get_viewer_html()
        assert self.compare_html(desired_html, viewer_html, clean=True)

    def test_add_svg_node_diff(self):
        """ Test 3: Modify SVG and get diff """
        self.init_webdriver()
        self.webdriver.execute_script("""
          broadcaster.make_dom_clone();
          var circle = broadcaster_iframe.contentWindow.make_svg("circle", {cx: 100, cy: 50, r:40, stroke: 'black', fill: 'red'});
          broadcaster_iframe.contentWindow.add_svg_node(circle)
          """)
        diffs = self.get_broadcaster_diff()
        assert len(diffs) == 1

        print diffs
        diff_type, node_type, path, svg_xml, tail_text, props = diffs[0]
        assert "<circle" in svg_xml
        assert node_type == "svg"
        assert diff_type == "node"

    def test_apply_add_svg_node_diff(self):
        self.init_webdriver()
        self.webdriver.execute_script("""
            viewer_iframe.src = "test_svg_content.html";
        """)

        # This diffs mangles the entire SVG document, but it gets the circle in there!
        diff = [[u'node', u'svg', [1, 1, 1],
            u'<circle xmlns="http://www.w3.org/2000/svg" fill="green" stroke="yellow" cx="120" cy="30" r="10" />',
            u'tail text', []]]

        print json.dumps(diff)

        self.webdriver.execute_script("""
          apply_viewer_diffs(arguments[0]);
        """, json.dumps(diff));

        # Internet explorer values contain windows line endings
        viewer_html = self.get_viewer_html()
        assert "<circle" in viewer_html

    def test_apply_remove_svg_node_diff(self):
        self.init_webdriver()
        self.webdriver.execute_script("""
            viewer_iframe.src = "test_svg_content.html";
        """)

        # Should delete the <line> element
        diff = [[u'deleted', u'svg', [1, 1, 2]]]
        self.webdriver.execute_script("""
          apply_viewer_diffs(arguments[0]);
        """, json.dumps(diff));

        # Internet explorer values contain windows line endings
        viewer_html = self.get_viewer_html()

        assert "<line" not in viewer_html

    def test_change_svg_text_diff(self):
        self.init_webdriver()

        target_text = "Polar Bear"
        diffs = self.webdriver.execute_script("""
          broadcaster.make_dom_clone();
          broadcaster_iframe.contentWindow.change_svg_text(arguments[0]);
          """, target_text)
        diffs = self.get_broadcaster_diff()
        print diffs

        # Unsure: We may or may not have a "deleted" diff at the start before
        # the "text" diff, this is still up in the air.
        diff_type, node_type, path, tail_text, child_text = diffs[-1]
        assert node_type == "svg"
        assert diff_type == "text"
        assert child_text == target_text

    def test_apply_change_svg_text_diff(self):
        self.init_webdriver()
        self.webdriver.execute_script("""
            viewer_iframe.src = "test_svg_content.html";
        """)

        target_child_text = "Door handle"
        target_tail_text = "Architraves"

        # Should add text inside and after the <text> element
        diff = [[u'text', u'svg', [1, 1, 1], target_child_text, target_tail_text]]
        self.webdriver.execute_script("""
          apply_viewer_diffs(arguments[0]);
        """, json.dumps(diff));

        # Internet explorer values contain windows line endings
        viewer_html = self.get_viewer_html()
        assert target_child_text in viewer_html
        assert target_tail_text in viewer_html

    def test_add_svg_text_node_diff(self):
        self.init_webdriver()

        target_text = "Coffee cup"
        diffs = self.webdriver.execute_script("""
          broadcaster.make_dom_clone();
          var text = broadcaster_iframe.contentWindow.make_svg("text",  {x: "20", y: "140", fill: "purple"});
          text.textContent = arguments[0];
          broadcaster_iframe.contentWindow.add_svg_node(text);
          """, target_text)
        diffs = self.get_broadcaster_diff()
        print diffs

        assert len(diffs) == 1

        diff_type, node_type, path, svg_xml, tail_text, props = diffs[0]
        assert node_type == "svg"
        assert diff_type == "node"
        assert svg_xml.startswith("<text")
        assert target_text in svg_xml

    def test_apply_add_svg_text_node_diff(self):
        self.init_webdriver()
        self.webdriver.execute_script("""
            viewer_iframe.src = "test_svg_content.html";
        """)

        target_text = "Brown Cow"

        # This diffs mangles the entire SVG document, but it gets the circle in there!
        diff = [[u'node', u'svg', [1, 1, 1],
            u'<text xmlns="http://www.w3.org/2000/svg" fill="orange" x="21" y="111">%s</text>' % (target_text),
            u'tail_text',
            []]]

        print json.dumps(diff)

        self.webdriver.execute_script("""
          apply_viewer_diffs(arguments[0]);
        """, json.dumps(diff));

        # Internet explorer values contain windows line endings
        viewer_html = self.get_viewer_html()
        assert target_text in viewer_html

class TestIE(TestFirefox):
    @classmethod
    def _create_webdriver(cls):
        return util.get_debug_ie_webdriver()

class TestChrome(TestFirefox):
    @classmethod
    def _create_webdriver(cls):
        return util.get_debug_chrome_webdriver()
