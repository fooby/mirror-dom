"""
Test for the mirrordom server
"""

import sys
import os
import json

import util
import test_javascript

from selenium import webdriver

try:
    import mirrordom.server
except ImportError:
    sys.path.append(util.get_mirrordom_path())
    import mirrordom.server

def setupModule():
    TestMirrorDOM.start_webdriver()

def teardownModule():
    TestMirrorDOM.kill_webdriver()

class XMLCompareException(Exception):
    pass

class TestMirrorDOM(util.TestBrowserBase):

    HTML_FILE = "test_mirrordom.html"

    def compare_frames(self):
        broadcaster_html = self.driver.execute_script("return get_broadcaster_html()")
        viewer_html = self.driver.execute_script("return get_viewer_html()")
        return self.compare_html(broadcaster_html, viewer_html, clean=True)

    UNSANITARY_HTML = """\
<html>
  <head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <script type="text/javascript" src="https://ajax.googleapis.com/ajax/libs/jquery/1.7.2/jquery.min.js"></script>
    <style type="text/css">
      table { border-collapse: collapse; }
      table,th,td { border: 1px solid black; }
    </style>
  </head>
  <body>
    <h1>Hello world!</h1>
    <div>
      <input id="text_input" type="text" size="50" value="hello"></input>
    </div>
    <a href="test_dom_sync_content2.html">Page 2</a>
    <script type="text/javascript">alert("helo");</script>
  </body>
</html>
"""

    SANITARY_HTML = """\
<html>
  <head>
    <style type="text/css">
      table { border-collapse: collapse; }
      table,th,td { border: 1px solid black; }
    </style>
  </head>
  <body>
    <h1>Hello world!</h1>
    <div>
      <input id="text_input" type="text" size="50" value="hello"></input>
    </div>
    <a href="test_dom_sync_content2.html">Page 2</a>
  </body>
</html>
"""

    def test_sanitise_document(self):
        """
        Strip tags from submitted HTML
        """
        from_html = self.UNSANITARY_HTML
        to_html = self.SANITARY_HTML
        result_html = mirrordom.server.sanitise_document(from_html)
        assert self.compare_html(result_html, to_html, clean=False)

    def test_init_html(self):
        """
        Test basic HTML transfer

        Note: We don't want to verify the document transmit format in this
        test. It may or may not be a simple string.
        """
        init_html_json = self.driver.execute_script(
                "return test_1_get_broadcaster_document()")
        init_html = json.loads(init_html_json)
        result_html = mirrordom.server.sanitise_document(init_html)
        result_html_json = json.dumps(result_html)
        self.driver.execute_script("test_1_apply_viewer_document(arguments[0])",
                result_html_json)

        assert self.compare_frames()

    def test_diff_transfer(self):

        # Replicate the initial test
        self.test_init_html()

        # Now let's go further and modify the document
        self.driver.execute_script("test_2_modify_broadcaster_document()")

        diff = self.driver.execute_script("return test_2_get_broadcaster_diff()")
        diff = json.loads(diff)

        print diff

        # TODO: Sanitise diff in mirrordom.server?

        result = json.dumps(diff)
        self.driver.execute_script("test_2_apply_viewer_diff(arguments[0])", result)

        assert self.compare_frames()
