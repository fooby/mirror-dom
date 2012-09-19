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
    HTML_FILE = "test_iframe.html"

    @classmethod
    def _create_webdriver(cls):
        return util.get_debug_firefox_webdriver()

    def compare_inner_iframes(self, iframe_name):
        # Grab the broadcaster's iframes
        self.webdriver.switch_to_default_content()
        self.webdriver.switch_to_frame('broadcaster_iframe')
        self.webdriver.switch_to_frame(iframe_name)
        source_iframe_html = self.webdriver.execute_script("return window.document.documentElement.innerHTML");

        # Grab the viewer's iframes
        self.webdriver.switch_to_default_content()
        self.webdriver.switch_to_frame('viewer_iframe')
        self.webdriver.switch_to_frame(iframe_name)
        dest_iframe_html = self.webdriver.execute_script("return window.document.documentElement.innerHTML");

        return self.compare_html(source_iframe_html, dest_iframe_html, clean=True)

    #def compare_frames(self):
    #    broadcaster_html = self.webdriver.execute_script("return get_broadcaster_html()")
    #    viewer_html = self.webdriver.execute_script("return get_viewer_html()")

    #    #print "Broadcaster: %s" % (broadcaster_html)
    #    #print "Viewer: %s" % (viewer_html)
    #    return self.compare_html(broadcaster_html, viewer_html, clean=True)

    #def test_init_html(self):
    #    """
    #    Test 1: Basic HTML transfer

    #    Note: We don't want to verify the document transmit format in this
    #    test. It may or may not be a simple string.
    #    """
    #    self.init_webdriver()

    #    init_html_json = self.webdriver.execute_script(
    #            "return test_1_get_broadcaster_document()")
    #    init_html = json.loads(init_html_json)
    #    result_html = mirrordom.server.sanitise_document(init_html)
    #    result_html_json = json.dumps(result_html)
    #    self.webdriver.execute_script("test_1_apply_viewer_document(arguments[0])",
    #            result_html_json)

    #    assert self.compare_frames()

    def test_detect_standard_iframe(self):
        """ Test 1: Make sure we find standard iframe """
        self.init_webdriver()
        self.webdriver.execute_script("test_1_start_broadcaster_document()")
        result = self.webdriver.execute_script("return test_1_fetch_iframe_paths()")
        result = json.loads(result)
        assert len(result) == 1
        assert result[0] == [1,4]

    def test_detect_dynamic_iframe(self):
        """ Test 2: Make sure we find dynamic iframe """
        self.init_webdriver()
        self.webdriver.execute_script("test_2_add_dynamic_iframe()")
        self.webdriver.execute_script("test_1_start_broadcaster_document()")
        result = self.webdriver.execute_script("return test_1_fetch_iframe_paths()")
        result = json.loads(result)
        assert len(result) == 2
        assert [1,1,0] in result

    def test_remove_iframe_and_diff(self):
        """ Test 3: Make sure we detect when iframes are removed """
        self.init_webdriver()
        # Let's start from where test 2 left ovff
        self.test_detect_dynamic_iframe()
        self.webdriver.execute_script("test_3_remove_all_iframes()")
        self.webdriver.execute_script("test_3_get_diff()")
        result = self.webdriver.execute_script("return test_1_fetch_iframe_paths()")
        result = json.loads(result)
        assert result == []

    def test_modify_iframe_path(self):
        """ Test 4: Check if iframe paths are updated after DOM operations """
        self.init_webdriver()
        self.webdriver.execute_script("test_1_start_broadcaster_document()")
        self.webdriver.execute_script("test_4_insert_element_at_start()")
        self.webdriver.execute_script("test_3_get_diff()")
        result = self.webdriver.execute_script("return test_1_fetch_iframe_paths()")
        result = json.loads(result)
        assert len(result) == 1
        assert result[0] == [1,5]

    def test_send_update_messages(self):
        """
        Test 5: Check mirrordom messages contain initial html frame content.
        """
        self.init_webdriver()
        # Let's just throw in the dynamic iframe for good measure
        self.webdriver.execute_script("test_2_add_dynamic_iframe()")
        #self.webdriver.execute_script("test_1_start_broadcaster_document()")
        messages = self.webdriver.execute_script(
                "return test_5_process_and_get_messages()");

        # Dictionary of "messages" and "iframes"
        messages = json.loads(messages)
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
        import time
        time.sleep(5.0)
        self.test_process_send_update_messages()
        # Set from test_process_mirrordom_iframe_messages
        storage = self.storage
        updates = mirrordom.server.handle_get_update(storage)
        print "Updates: %s" % (updates)
        self.webdriver.execute_script("test_7_apply_updates(arguments[0])",
                json.dumps(updates))
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
        self.webdriver.execute_script("test_4_insert_element_at_start()")
        messages = self.webdriver.execute_script(
                "return test_5_process_and_get_messages()");
        messages = json.loads(messages)
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
        self.webdriver.execute_script("test_7_apply_updates(arguments[0])",
                json.dumps(updates))
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

        self.webdriver.execute_script("test_7_apply_updates(arguments[0])",
                json.dumps(updates));

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
