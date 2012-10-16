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

import util
import test_javascript

from selenium import webdriver

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

class TestServer(util.TestBase):
    UNSANITARY_HTML = """\
<html>
  <head>
    <!-- Random comment -->
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <script type="text/javascript" src="https://ajax.googleapis.com/ajax/libs/jquery/1.7.2/jquery.min.js"></script>
    <link rel="StyleSheet" type="text/css" href="/trunkdevel/css/slidemenu.css?v=073c3303" />
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
    <iframe name="theiframe" id="theiframe" src="blah.html"> </iframe>
    <script type="text/javascript">alert("helo");</script>
  </body>
</html>
"""

    SANITARY_HTML = """\
<html>
  <head>
    <link rel="StyleSheet" type="text/css" href="/trunkdevel/css/slidemenu.css?v=073c3303"/>
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
    <a href="#">Page 2</a>
    <iframe name="theiframe" id="theiframe"> </iframe>
  </body>
</html>
"""
    @classmethod
    def _create_webdriver(cls):
        return None

    def test_sanitise_document(self):
        """
        Test 1: Strip tags from submitted HTML.

        No browser required
        """
        from_html = self.UNSANITARY_HTML
        to_html = self.SANITARY_HTML
        #import rpdb2
        #rpdb2.start_embedded_debugger("hello")
        result_html = mirrordom.server.sanitise_document(from_html)
        assert self.compare_html(to_html, result_html, clean=False)


    UNSANITARY_HTML_FRAGMENT = """
    <div>
      <!-- Random comment -->
      hello world
      <div id="blah">
        <iframe src="http://removeme"> </iframe>
      </div>
      hlerhre
      <script type="text/javascript">nope</script>
      bye world
    </div>
    """

    SANITARY_HTML_FRAGMENT = """
    <div>
      hello world
      <div id="blah">
          <iframe> </iframe>
      </div>
      hlerhre
      bye world
    </div>
    """
    def test_sanitise_html_fragment(self):
        """
        Test 2: Strip tags from node html fragment (used for node diffs)
        """
        from_html = self.UNSANITARY_HTML_FRAGMENT
        to_html = self.SANITARY_HTML_FRAGMENT
        result_html = mirrordom.server.sanitise_html_fragment(from_html)
        assert self.compare_html(to_html, result_html, clean=False)

    UNSANITARY_HTML_FRAGMENT2 = """
    <tbody>
        <tr>
            <th class="heloworld">Blah</th>
            <th class="heloworld2">Blah2</th>
        </tr>
        <tr>
            <td style="background-color: blue;">SDF</td>
            <td style="color: green;">axg</td>
        </tr>
    </tbody>
    """

    SANITARY_HTML_FRAGMENT2 = """
    <tbody>
        <tr>
            <th class="heloworld">Blah</th>
            <th class="heloworld2">Blah2</th>
        </tr>
        <tr>
            <td style="background-color: blue;">SDF</td>
            <td style="color: green;">axg</td>
        </tr>
    </tbody>
    """
    def test_sanitise_html_fragment2(self):
        """ Test 3: Strip tags from complex inner html """
        from_html = self.UNSANITARY_HTML_FRAGMENT2
        to_html = self.SANITARY_HTML_FRAGMENT2
        result_html = mirrordom.server.sanitise_html_fragment(from_html)
        # html5parser mangles the input too much, disable it
        assert self.compare_html(to_html, result_html, clean=False)

    UNSANITARY_HTML_FRAGMENT3 = """<td style="background-color: blue;">SDF</td>"""
    SANITARY_HTML_FRAGMENT3 = """<td style="background-color: blue;">SDF</td>"""
    def test_sanitise_html_fragment3(self):
        """ Test 3: Strip tags from complex inner html """
        from_html = self.UNSANITARY_HTML_FRAGMENT3
        to_html = self.SANITARY_HTML_FRAGMENT3
        result_html = mirrordom.server.sanitise_html_fragment(from_html)
        # html5parser mangles the input too much, disable it
        assert self.compare_html(to_html, result_html, clean=False)

    UNSANITARY_HTML_FRAGMENT_TBODY = """
    <table>
        <colgroup span="1"></colgroup>
        <!-- Random comment -->
        <thead>
          <tr><td>Header</td></tr>
        </thead>
        <tfoot>
          <tr><td>Footer</td></tr>
        </tfoot>
        <tr><td>Blah1</td></tr>
        <tbody>
            <tr><td>Blah2</td></tr>
        </tbody>
        <tr><td>Blah3</td></tr>
        <tbody>
          <tr><td>Blah4</td></tr>
          <tr><td>Blah5</td></tr>
        </tbody>
        <tr><td>Blah6</td></tr>
        <tr><td>Blah7</td></tr>
    </table>
    """

    SANITARY_HTML_FRAGMENT_TBODY = """
    <table>
        <colgroup span="1"></colgroup>
        <thead>
          <tr><td>Header</td></tr>
        </thead>
        <tfoot>
          <tr><td>Footer</td></tr>
        </tfoot>
        <tbody>
          <tr><td>Blah1</td></tr>
        </tbody>
        <tbody>
          <tr><td>Blah2</td></tr>
        </tbody>
        <tbody>
          <tr><td>Blah3</td></tr>
        </tbody>
        <tbody>
          <tr><td>Blah4</td></tr>
          <tr><td>Blah5</td></tr>
        </tbody>
        <tbody>
          <tr><td>Blah6</td></tr>
          <tr><td>Blah7</td></tr>
        </tbody>
    </table>
    """

    def test_sanitise_html_fragment_tbody(self):
        """ Test 3: Strip tags from complex inner html """
        from_html = self.UNSANITARY_HTML_FRAGMENT_TBODY
        to_html = self.SANITARY_HTML_FRAGMENT_TBODY
        result_html = mirrordom.server.sanitise_document(from_html)
        # html5parser mangles the input too much, disable it
        assert self.compare_html(to_html, result_html, clean=False)

    UNSANITARY_HTML_FRAGMENT_BAD_FORM_IN_TABLE = """
    <html>
      <body>
        <table>
          <form name="badform">
            <tr><td>Blah2</td></tr>
          </form>
        </table>
      </body>
    </html>
    """

    SANITARY_HTML_FRAGMENT_BAD_FORM_IN_TABLE = """
    <html>
      <body>
        <table>
          <tbody>
          <form name="badform">
            <tr><td>Blah2</td></tr>
          </form>
          </tbody>
        </table>
      </body>
    </html>
    """
    def test_sanitise_html_fragment_bad_form_in_table(self):
        from_html = self.UNSANITARY_HTML_FRAGMENT_BAD_FORM_IN_TABLE
        to_html = self.SANITARY_HTML_FRAGMENT_BAD_FORM_IN_TABLE
        result_html = mirrordom.server.sanitise_document(from_html)
        # html5parser mangles the input too much, disable it
        assert self.compare_html(to_html, result_html, clean=False)

    UNSANITARY_HTML_FRAGMENT_LINK = """
        <div>
            <a href="www.google.com.au">Google</a>
            <a href="/blah">Blah</a>
            <a href="#" onclick="do_something_evil();">Evil</a>
        </div>"""

    SANITARY_HTML_FRAGMENT_LINK = """
        <div>
            <a href="#">Google</a>
            <a href="#">Blah</a>
            <a href="#">Evil</a>
        </div>"""

    def test_sanitise_links(self):
        from_html = self.UNSANITARY_HTML_FRAGMENT_LINK
        to_html = self.SANITARY_HTML_FRAGMENT_LINK
        result_html = mirrordom.server.sanitise_document(from_html)
        assert self.compare_html(to_html, result_html, ignore_hrefs=False, clean=False)


class TestFirefox(util.TestBrowserBase):
    HTML_FILE = "test_mirrordom.html"

    @classmethod
    def _create_webdriver(cls):
        return util.get_debug_firefox_webdriver()

    def compare_frames(self):
        broadcaster_html = self.webdriver.execute_script("return get_broadcaster_html()")
        viewer_html = self.webdriver.execute_script("return get_viewer_html()")

        #print "Broadcaster: %s" % (broadcaster_html)
        #print "Viewer: %s" % (viewer_html)

        # html5parser mangles the input too much, disable it
        return self.compare_html(broadcaster_html, viewer_html, clean=True)

    def test_init_html(self):
        """
        Test 1: Basic HTML transfer

        Note: We don't want to verify the document transmit format in this
        test. It may or may not be a simple string.
        """
        self.init_webdriver()
        init_html = self.webdriver.execute_script(
                "return test_1_get_broadcaster_document()")
        init_html = json.loads(init_html)
        result_html = mirrordom.server.sanitise_document(init_html)
        print "==RESULT HTML=="
        print json.dumps(result_html)
        self.webdriver.execute_script("test_1_apply_viewer_document(arguments[0])",
                result_html)

        assert self.compare_frames()

    def test_diff_transfer(self):
        """
        Test 2: Basic diff transfer
        """
        self.init_webdriver()
        # Replicate the initial test
        self.test_init_html()

        # Now let's go further and modify the document
        self.webdriver.execute_script("test_2_modify_broadcaster_document()")
        diff = self.webdriver.execute_script("return test_2_get_broadcaster_diff()")
        diff = json.loads(diff)
        print "==DIFF=="
        print json.dumps(diff)
        diff = mirrordom.server.sanitise_diffs(diff)
        self.webdriver.execute_script("test_2_apply_viewer_diff(arguments[0])", json.dumps(diff))

        assert self.compare_frames()

    def test_all_property_transfer(self):
        """
        Test 3: Initial property transfer - make sure the viewer gets stuff set.
        """
        self.init_webdriver()

        # Replicate the initial test
        self.test_init_html()

        # Now let's go further and modify the document
        self.webdriver.execute_script("test_3_modify_broadcaster_document_with_css()")
        #self.webdriver.execute_script("test_3_modify_broadcaster_document_with_property()")

        # Change text input value property
        new_input_value = "dfkjgopi"
        self.webdriver.switch_to_frame('broadcaster_iframe')
        input = self.webdriver.find_element_by_id('thetextinput')
        input.send_keys(new_input_value)

        self.webdriver.switch_to_default_content()
        diff = self.webdriver.execute_script("return test_3_get_broadcaster_all_property_diffs()")
        diff = json.loads(diff)

        # Only properties
        assert all(d[0] == "props" for d in diff)
        assert util.diff_contains_changed_property_key(diff, "value")

        # Should be a border in there somewhere (note: IE returns individual
        # border rules for each side, FF retains the single border rule)
        assert util.diff_contains_changed_property_value(diff, "purple")

        diff = mirrordom.server.sanitise_diffs(diff)

        # We can reuse test 2's diff apply thing
        self.webdriver.execute_script("test_2_apply_viewer_diff(arguments[0])", json.dumps(diff))

        # Verify the diff made it through
        self.webdriver.switch_to_frame('viewer_iframe')
        input = self.webdriver.find_element_by_id('thetextinput')
        input_value = input.get_attribute("value")
        print "Got input value: %s. Expected: <original value>%s" % (input_value, new_input_value)
        assert input_value.endswith(new_input_value)
        table = self.webdriver.find_element_by_id('thetable')
        table_background_colour = input.value_of_css_property("background-color")
        assert table_background_colour in ("purple", "rgba(255, 255, 255, 1)")

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
        self.webdriver.execute_script("test_5_modify_broadcaster_document_insert_element()")
        diff = self.webdriver.execute_script("return test_2_get_broadcaster_diff()")
        diff = json.loads(diff)
        print diff
        diff = mirrordom.server.sanitise_diffs(diff)
        self.webdriver.execute_script("test_2_apply_viewer_diff(arguments[0])", json.dumps(diff))
        assert self.compare_frames()

    def test_diff_transfer_inserted_table(self):
        """
        Test 6: More advanced diff transfer, with big table
        """
        self.init_webdriver()
        # Replicate the initial test
        self.test_init_html()
        # Now let's go further and modify the document
        self.webdriver.execute_script("test_6_modify_broadcaster_document_insert_table()")
        diff = self.webdriver.execute_script("return test_2_get_broadcaster_diff()")
        diff = json.loads(diff)
        diff = mirrordom.server.sanitise_diffs(diff)
        self.webdriver.execute_script("test_2_apply_viewer_diff(arguments[0])", json.dumps(diff))
        assert self.compare_frames()

class TestIE(TestFirefox):
    @classmethod
    def _create_webdriver(cls):
        return util.get_debug_ie_webdriver()

class TestChrome(TestFirefox):
    @classmethod
    def _create_webdriver(cls):
        return util.get_debug_chrome_webdriver()
