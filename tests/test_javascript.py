"""
Tests
"""

import json
import os

import util

def setupModule():
    TestJavascript.start_webdriver()

def teardownModule():
    TestJavascript.kill_webdriver()

class TestJavascript(util.TestBrowserBase):

    HTML_FILE = "test_javascript.html"

    # The file INSIDE the broadcaster iframe
    HTML_CONTENT_FILE = "test_javascript_content.html"

    def test_fetch_document(self):
        """ Test 1: Just make sure fetching works """

        # Right now, browser_html should be the raw inner html
        browser_html = self.driver.execute_script("return test_1_get_broadcaster_document()")

        # Compare it to the actual HTML file
        html_path = util.get_html_path(self.HTML_CONTENT_FILE)
        actual_html = open(html_path, 'r').read()

        assert self.compare_html(actual_html, browser_html)


    # Note that I've deliberately omitted <tbody> from the table element, as I
    # want to see what sort of complications ensue
    TEST_APPLY_DOCUMENT = """\
    <html>
      <head>
        <meta content="text/html; charset=utf-8" http-equiv="Content-Type"></meta>
        <script src="https://ajax.googleapis.com/ajax/libs/jquery/1.7.2/jquery.min.js" type="text/javascript"></script>
        <script type="text/javascript"></script>
        <style type="text/css">table { border-collapse: collapse; }
        table,th,td { border: 1px solid black; }</style>
      </head>
      <body>
        <h3>Hallow world!</h3>
        <div>
        ohay
          <table id="thetable" style="border: 1px solid pink;">
          <tr>
            <th>1</th>
            <th>2</th>
          </tr>
          <tr>
            <td>a</td>
            <td>b</td>
          </tr>
          <tr>
            <td>c</td>
            <td>d</td>
          </tr>
          </table>
        </div>
        <div>
          <input id="text_input" length="50" type="text" value="hello"></input>
        </div>
        <a href="test_dom_sync_content2.html">Page 2</a>
      </body>
    </html>"""

    def test_apply_document(self):
        """ Test 2: Put the document back in """
        desired_html = self.TEST_APPLY_DOCUMENT
        self.driver.execute_script("test_2_apply_document(arguments[0])", desired_html)
        viewer_html = self.driver.execute_script("return get_viewer_html()")
        assert self.compare_html(desired_html, viewer_html, clean=True)

    def test_get_diff(self):
        # This triggers clone_dom() in the broadcaster js object, so that diffing works
        self.driver.execute_script("test_1_get_broadcaster_document()")
        self.driver.execute_script("test_2_modify_broadcaster_document()")
        result = self.driver.execute_script("return test_2_get_broadcaster_diff()")
        result = json.loads(result)

