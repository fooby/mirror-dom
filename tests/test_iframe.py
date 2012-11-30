"""
Test for iframe functionality. Requires some mirrordom.server intervention.

This won't go totally into depth.
"""

import sys
import os
import json
import time
import pprint
import lxml

import util
import test_javascript

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException

try:
    import mirrordom.server
except ImportError:
    sys.path.append(util.get_mirrordom_path())
    import mirrordom.server

from mirrordom.parser import parse_html

def setupModule():
    util.start_webserver()

def teardownModule():
    util.stop_webserver()

class XMLCompareException(Exception):
    pass

class TestFirefox(util.TestBrowserBase):
    HTML_FILE = "test_iframe.html"

    @classmethod
    def _create_webdriver(cls):
        return util.get_debug_firefox_webdriver()

    # --------------------------------------------------------------------------
    # Helpers
    # --------------------------------------------------------------------------
    def html_to_xml(self, html):
        tree = parse_html(html)
        return lxml.etree.tostring(tree)

    def compare_inner_iframes(self, iframe_name, **compare_args):
        # Grab the broadcaster's iframes
        self.webdriver.switch_to_default_content()
        self.webdriver.switch_to_frame('broadcaster_iframe')
        self.webdriver.switch_to_frame(iframe_name)
        source_iframe_html = self.webdriver.execute_script("""return (
            "<html>" + window.document.documentElement.innerHTML + "</html>");
        """);
        source_iframe_html = source_iframe_html.replace('\r\n', '\n')
        source_iframe_xml = self.html_to_xml(source_iframe_html)

        # Grab the viewer's iframes
        self.webdriver.switch_to_default_content()
        self.webdriver.switch_to_frame('viewer_iframe')
        self.webdriver.switch_to_frame(iframe_name)
        dest_iframe_html = self.webdriver.execute_script("""return (
            "<html>" + window.document.documentElement.innerHTML + "</html>");
        """);
        dest_iframe_html = dest_iframe_html.replace('\r\n', '\n')
        dest_iframe_xml = self.html_to_xml(dest_iframe_html)

        print "Source: %s" % (source_iframe_html)
        print "Dest: %s" % (dest_iframe_html)

        # Options here need to reflect the sanitising process. Maybe I could
        # just sanitise the source_iframe_html?
        compare_args.setdefault("ignore_tags", ["meta", "script"])
        compare_args.setdefault("ignore_comments", True)

        return self.compare_html(source_iframe_xml, dest_iframe_xml, **compare_args)

    def init_broadcaster_state(self):
        self.execute_script("broadcaster.start_document();")

    def fetch_iframe_paths(self):
        paths = self.execute_script("""
            var iframe_paths = [];
            for (key in broadcaster.child_iframes) {
                iframe_paths.push(broadcaster.child_iframes[key]["ipath"]);
            }
            return iframe_paths;
        """)
        return paths

    def get_broadcaster_diff(self):
        result = self.execute_script("return JSON.stringify(broadcaster.get_diff());")
        return json.loads(result)

    def process_and_get_broadcaster_messages(self):
        result = self.execute_script("""
           var messages = [];
           broadcaster.process_and_get_messages(messages);
           // Iframe listings are now a necessary part of every update
           var iframes = broadcaster.get_all_iframe_paths();
           return JSON.stringify({"messages": messages, "iframes": iframes});
        """)
        return json.loads(result)

    def apply_viewer_updates(self, updates):
        self.execute_script("""
            var updates = JSON.parse(arguments[0]);
            viewer.receive_updates(updates);
        """, json.dumps(updates))

    # --------------------------------------------------------------------------
    # Tests
    # --------------------------------------------------------------------------
    def test_detect_standard_iframe(self):
        """ Test 1: Make sure we find standard iframe """
        self.init_webdriver()
        self.init_broadcaster_state()
        result = self.fetch_iframe_paths()
        assert len(result) == 1
        assert result[0] == [1,4]

    def test_detect_dynamic_iframe(self):
        """ Test 2: Make sure we find dynamic iframe """
        self.init_webdriver()
        self.execute_script("""
            broadcaster_iframe.contentWindow.add_dynamic_iframe();
        """)
        self.init_broadcaster_state()
        result = self.fetch_iframe_paths()
        assert len(result) == 2
        assert [1,1,0] in result

    def test_remove_iframe_and_diff(self):
        """ Test 3: Make sure we detect when iframes are removed """
        self.init_webdriver()
        # Let's start from where test 2 left ovff
        self.test_detect_dynamic_iframe()
        self.webdriver.execute_script("""
            broadcaster_iframe.contentWindow.remove_all_iframes();
        """)
        diffs = self.get_broadcaster_diff()
        result = self.fetch_iframe_paths()
        assert result == []

    def test_modify_iframe_path(self):
        """ Test 4: Check if iframe paths are updated after DOM operations """
        self.init_webdriver()
        self.init_broadcaster_state()
        self.webdriver.execute_script("""
            broadcaster_iframe.contentWindow.add_div_at_start();
        """)
        diffs = self.get_broadcaster_diff()
        result = self.fetch_iframe_paths()
        assert len(result) == 1
        assert result[0] == [1,5]

    def test_send_update_messages(self):
        """
        Test 5: Check mirrordom messages contain initial html frame content.
        """
        self.init_webdriver()
        #time.sleep(10.0)

        # Let's just throw in the dynamic iframe for good measure
        self.execute_script("""
            broadcaster_iframe.contentWindow.add_dynamic_iframe();
        """)

        messages = self.process_and_get_broadcaster_messages()
        # Dictionary of "messages" and "iframes"
        print messages["iframes"]

        # These are the frames that we expect from the broadcaster
        expected_frames = set([('m',), ('m',1,1,0,'i'), ('m',1,4,'i')])
        message_paths = set(tuple(f[0]) for f in messages["messages"])
        iframe_paths = set(tuple(f) for f in messages["iframes"])

        assert message_paths == expected_frames
        assert iframe_paths == expected_frames

        # Pass values onto subsequent tests
        return expected_frames, messages

    def test_process_send_update_messages(self):
        """
        Test 6: Apply the messages to our python mirrordom library and ensure
        that the changesets are properly constructed for iframes
        """
        # Put the frames into our mirrordom changeset storage
        expected_frames, messages = self.test_send_update_messages()

        print messages

        storage = mirrordom.server.create_storage()
        mirrordom.server.handle_send_update(storage, messages["messages"],
                messages["iframes"])
        storage_frames = set(storage.changelogs.keys())
        assert storage_frames == expected_frames

        # Store mirrordom storage for test reuse
        self.storage = storage

    def test_apply_init_update(self):
        """
        Test 7: Apply processed messages to the viewer to reconstruct iframes

        Moment of truth!
        """
        self.test_process_send_update_messages()
        # Set from test_process_mirrordom_iframe_messages
        storage = self.storage
        updates = mirrordom.server.handle_get_update(storage)
        print "Updates: %s" % (updates)
        self.apply_viewer_updates(updates)

        assert self.compare_inner_iframes('theiframe')
        assert self.compare_inner_iframes('thedynamiciframe')

    def test_send_update_messages2(self):
        """
        Test 8: Get DOM modification update messages
        """
        self.test_process_send_update_messages()
        # Set from test_process_mirrordom_iframe_messages
        storage = self.storage
        self.webdriver.switch_to_default_content()
        self.webdriver.execute_script("""
            broadcaster_iframe.contentWindow.add_div_at_start();
        """)
        messages = self.process_and_get_broadcaster_messages()
        print "===Messages 2:===\n\n"
        print pprint.pformat(messages)
        mirrordom.server.handle_send_update(storage, messages["messages"],
                messages["iframes"])

        expected_frames = set([('m',), ('m',1,2,0,'i'), ('m',1,5,'i')])
        storage_frames = set(storage.changelogs.keys())

        print "Storage frames: %s" % (storage_frames)
        print "Expected frames: %s" % (expected_frames)
        assert expected_frames == storage_frames

    def test_apply_modify_update(self):
        """
        Test 9: Apply modification update messages
        """
        self.test_send_update_messages2()
        storage = self.storage
        updates = mirrordom.server.handle_get_update(storage)
        self.apply_viewer_updates(updates)
        # Yep, have to wait a bit
        time.sleep(0.5)
        assert self.compare_inner_iframes('theiframe')
        assert self.compare_inner_iframes('thedynamiciframe')

    def test_iframe_css(self):
        """
        Test 10: Test iframe CSS application
        """
        self.init_webdriver()

        # This test involves fabricating diff messages, so it's going to be
        # pretty brittle if the diff changes
        top_document = """
        <html>
          <head></head>
          <!-- iframe at position [1,0] -->
          <body><iframe frameborder="0" name="test_css_iframe" id="test_css_iframe"></iframe></body>
        </html>
        """

        iframe_document = """
        <html>
          <head>
            <link rel="stylesheet" type="text/css" href="test_iframe2.css"/>
          </head>
          <body>test</body>
        </html>
        """

        changesets = [
             [['m'],     {'init_html': top_document}],
             [['m',1,0], {'init_html': iframe_document}],
        ]

        updates = {
            "changesets": changesets,
            "last_change_id": 12345,
        }

        self.apply_viewer_updates(updates)

        self.webdriver.switch_to_default_content()
        self.webdriver.switch_to_frame('viewer_iframe')
        self.webdriver.switch_to_frame('test_css_iframe')

        # Look for test_mirrordom.css
        links = self.webdriver.find_elements_by_xpath('/html/head/link')
        link_hrefs = [l.get_attribute("href") for l in links]
        print "Link hrefs: %s" % link_hrefs
        assert any(x.endswith("test_iframe2.css") for x in link_hrefs if x)


        # This is the important part: make sure the document has acknowledged
        # the stylesheet.
        stylesheet_hrefs = self.webdriver.execute_script("""
            var hrefs=[];
            for (var i = 0; i < document.styleSheets.length; i++) {
              if (document.styleSheets[i].href != undefined) {
                hrefs.push(document.styleSheets[i].href);
              }
            }
            return hrefs;
        """)

        assert any(x.endswith("test_iframe2.css") for x in stylesheet_hrefs)

class TestIE(TestFirefox):
    @classmethod
    def _create_webdriver(cls):
        return util.get_debug_ie_webdriver()

class TestChrome(TestFirefox):
    @classmethod
    def _create_webdriver(cls):
        return util.get_debug_chrome_webdriver()
