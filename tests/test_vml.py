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

class TestIE(util.TestBrowserBase):
    HTML_FILE = "test_vml.html"

    @classmethod
    def _create_webdriver(cls):
        return util.get_debug_ie_webdriver()

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

    def test_get_vml_document(self):
        """ Test 1: Get VML stuff """
        self.init_webdriver()
        html = self.execute_script("""
          var data = broadcaster.start_full_document();
          return data["html"];
        """)
        assert "<line" in html or "<v:line" in html

    TEST_APPLY_VML_DOCUMENT = """\
           <html>
             <head>
               <title>helo</title>
             </head>
             <body>
               <h1>VML test</h1>
               <div style="position: relative;">
                 <oval xmlns="urn:schemas-microsoft-com:vml" style="behavior:url(#default#VML); left: 20px; top: 10px; width:100px; height:100px; position: absolute;" fillcolor="green"></oval>
               </div>
             </body>
           </html>"""

    def test_apply_vml_document(self):
        """ Test 2: See if we can apply a document containing a VML """
        self.init_webdriver()
        desired_html = self.TEST_APPLY_VML_DOCUMENT
        self.webdriver.execute_script("""
          var doc_elem = viewer.get_document_element();
          viewer.apply_document(doc_elem, arguments[0]);
        """, desired_html)
        # Internet explorer values contain windows line endings
        viewer_html = self.webdriver.execute_script("""
            return MDTestUtil.get_html(viewer_iframe);
        """).replace('\r\n', '\n')
        assert self.compare_html(desired_html, viewer_html, clean=True)

    def test_create_vml_element(self):
        """ Test 3: Create a VML element...just create it """
        self.init_webdriver()
        result = self.execute_script("""
            try {
                var circle = broadcaster_iframe.contentWindow.make_vml("oval", {'left': '100px', 'top': '30px', 'width':'40px', 'height': '40px'}, {'fillcolor': 'yellow'});
                return [true, ""]
            } catch(e) {
                return [false, e.toString()]
            }
        """)

        success, message = result
        if not success:
            print "Create element failed with error: %s" % (message)
        assert success

    def test_add_vml_node_diff(self):
        """ Test 4: Modify VML and get diff """
        self.init_webdriver()
        diffs = self.execute_script("""
          broadcaster.make_dom_clone();
          var circle = broadcaster_iframe.contentWindow.make_vml("oval", {'left': '100px', 'top': '30px', 'width':'40px', 'height': '40px'}, {'fillcolor': 'yellow'});
          var div = broadcaster_iframe.contentWindow.document.getElementById('thevml');
          div.appendChild(circle);
          return JSON.stringify(broadcaster.get_diff());""")
        diffs = json.loads(diffs)
        assert len(diffs) == 1

        print diffs
        diff_type, node_type, path, svg_xml, props = diffs[0]
        assert "oval" in svg_xml
        assert node_type == "vml"
        assert diff_type == "node"

    def test_apply_add_vml_node_diff(self):
        """ Test 5: Try to apply a diff to the document """
        self.init_webdriver()
        self.webdriver.execute_script("""
            viewer_iframe.src = "test_vml_content.html";
        """)

        # This diffs mangles the entire VML document, but it gets the circle in there!
        diff = [[u'node', u'vml', [1, 1, 0],
            u'<oval style="POSITION: absolute; WIDTH: 90; HEIGHT: 90; BEHAVIOR: url(#default#VML); TOP: 11px; LEFT: 12px" xmlns="urn:schemas-microsoft-com:vml" coordsize = "21600,21600" fillcolor = "yellow"></oval>', [[u'vml', [], {u'runtimeStyle.cssText': u'WIDTH: 31.5pt; HEIGHT: 31.5pt; TOP: 29px; LEFT: 99px', u'style.cssText': u'POSITION: absolute; WIDTH: 40px; HEIGHT: 40px; BEHAVIOR: url(#default#VML); TOP: 30px; LEFT: 100px'}]]]]

        self.execute_script("""
          apply_viewer_diffs(arguments[0]);
        """, json.dumps(diff));

        # Internet explorer values contain windows line endings
        viewer_html = self.execute_script("""
            return MDTestUtil.get_html(viewer_iframe);
        """).replace('\r\n', '\n')

        print viewer_html

        assert "oval" in viewer_html

    def test_apply_remove_vml_node_diff(self):
        """
        Test 6: Try to remove a VML node from the document
        """
        self.init_webdriver()
        self.execute_script("""
            viewer_iframe.src = "test_vml_content.html";
        """)

        # Should delete the <oval id="deletemeoval"> element
        diff = [[u'deleted', u'vml', [1, 2, 0]]]
        self.execute_script("""
          apply_viewer_diffs(arguments[0]);
        """, json.dumps(diff));

        # Internet explorer values contain windows line endings
        viewer_html = self.execute_script("""
            return MDTestUtil.get_html(viewer_iframe);
        """).replace('\r\n', '\n')

        assert "deletemeoval" not in viewer_html

    def test_get_shape_path_diff(self):
        """
        Test 7: Try to update a shape path and get the resulting diff
        """
        self.init_webdriver()
        new_shape_path = "wr2018,408,4493,2883,2213,978,3255,408 at3255,1645,3255,1645,3255,1645,3255,1645 x e"
        diffs = self.execute_script("""
          broadcaster.make_dom_clone();
          var shape = broadcaster_iframe.contentWindow.document.getElementById('theshape');
          if (shape == null) {
              throw new Error("Couldn't find shape!");
          }
          shape.path.v = arguments[0];
          return JSON.stringify(broadcaster.get_diff());""", new_shape_path)
        diffs = json.loads(diffs)
        assert len(diffs) == 1
        print diffs
        diff_type, node_type, path, vml_xml, props = diffs[0]
        assert util.diff_contains_changed_property_key(diffs, 'path.v')
        assert node_type == "vml"

    def test_apply_shape_path_diff(self):
        """
        Test 8: Try to update a shape path
        """
        self.init_webdriver()
        self.execute_script("""
            viewer_iframe.src = "test_vml_content.html";
        """)

        new_path = "m 1,1 l 1,161, 200,200, 200,1 x e"
        diff = [[u'props', u'vml', [1, 1, 3], {u'path.v': new_path}, []]]
        self.execute_script("""
            apply_viewer_diffs(arguments[0]);
        """, json.dumps(diff));

        # Yeah, it's kinda hard to verify
        result_path = self.execute_script("""
            var shape = viewer_iframe.contentWindow.document.getElementById('theshape');
            return shape.path.v;
        """)

        # Yup, because we have 161 in our new path
        print result_path
        assert "161" in result_path
