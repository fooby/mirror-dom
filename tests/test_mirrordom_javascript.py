"""
Testing the javascript functionality of the mirrordom library
"""

import json
import os
import re
import time
import sys

import lxml
import nose.plugins.skip
from selenium.common.exceptions import NoSuchElementException

import util

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

class TestFirefox(util.TestBrowserBase):

    HTML_FILE = "test_mirrordom_javascript.html"

    # The file INSIDE the broadcaster iframe
    HTML_CONTENT_FILE = "test_mirrordom_javascript_content.html"

    @classmethod
    def _create_webdriver(cls):
        return util.get_debug_firefox_webdriver()

    # --------------------------------------------------------------------------
    # Helpers
    # --------------------------------------------------------------------------

    def setup_viewer_iframe_document(self,
            src="test_mirrordom_javascript_content_sanitised.html"):
        self.execute_script("viewer_iframe.src = arguments[0];", src)

    def get_viewer_html(self, fix_newlines=True):
        viewer_html = self.execute_script("""
            var de = viewer.get_document_element();
            return MirrorDom.outerhtml(de);
        """)
        if fix_newlines:
            viewer_html = viewer_html.replace('\r\n', '\n')
        return viewer_html

    def init_broadcaster_state(self):
        self.execute_script("broadcaster.make_dom_clone();")

    def get_broadcaster_diff(self):
        result = self.execute_script("return JSON.stringify(broadcaster.get_diff());")
        return json.loads(result)

    def apply_viewer_diff(self, diffs):
        self.execute_script("""
            viewer.apply_diffs(null, JSON.parse(arguments[0]));
        """, json.dumps(diffs))

    def apply_viewer_html(self, html):
        self.execute_script("""
            var de = viewer.get_document_element();
            viewer.apply_document(de, arguments[0]);
        """, html)

    #def compare_html(self, ):
    #    util.TestBrowserBase.compare_html(desired_html, got_html, **compare_kwargs)

    # --------------------------------------------------------------------------
    # Tests
    # --------------------------------------------------------------------------
    def test_webdriver_works(self):
        """ Test 0: Sometimes this is the real problem """
        self.init_webdriver()
        value = self.execute_script("return 1")

    def test_fetch_document(self):
        """ Test 1: Just make sure fetching works """
        self.init_webdriver()

        # Right now, browser_html should be the raw inner html
        browser_html = self.execute_script("""
            var data = broadcaster.start_document();
            return data['html'];
        """)

        # Internet explorer values contain windows line endings
        browser_html = browser_html.replace('\r\n', '\n')
        print "Browser HTML: %s" % (browser_html)
        browser_tree = parse_html(browser_html)
        browser_xml = lxml.etree.tostring(browser_tree)

        # Compare it to the actual HTML file
        html_path = util.get_html_path(self.HTML_CONTENT_FILE)
        actual_html = open(html_path, 'r').read()

        # Semi hack: We expect all browsers to insert tbody, so we'll manually
        # insert tbodies into our "expected" html too
        #import lxml.html
        #actual_tree = lxml.html.fromstring(actual_html)
        #util.force_insert_tbody(actual_tree)

        #browser_tree = lxml.html.fromstring(browser_html)

        assert self.compare_html(actual_html, browser_xml, ignore_script_content=True)

    # Note that I've deliberately omitted <tbody> from the table element, as I
    # want to see what sort of complications ensue
    TEST_APPLY_DOCUMENT = """\
    <html>
      <head>
        <title>Blah</title>
        <meta content="text/html; charset=utf-8" http-equiv="Content-Type"></meta>
        <script src="https://ajax.googleapis.com/ajax/libs/jquery/1.7.2/jquery.min.js" type="text/javascript"></script>
        <script type="text/javascript"></script>
        <!-- Style element can't be modified in IE8, this is now in a separate test -->
        <!--style type="text/css">table { border-collapse: collapse; }
        table,th,td { border: 1px solid black; }</style-->
      </head>
      <body>
        <h3>Hallow world!</h3>
        <div>
          ohay
          <table id="thetable" style="border: 1px solid pink;">
            <tbody>
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
            </tbody>
          </table>
        </div>
        <div>
          <input id="thetextinput" length="50" type="text" value="hello"></input>
        </div>
        <a href="test_dom_sync_content2.html">Page 2</a>
      </body>
    </html>"""

    def test_apply_document(self):
        """ Test 2: Apply document to viewer """
        self.init_webdriver()
        desired_html = self.TEST_APPLY_DOCUMENT
        self.execute_script("""
            var de = viewer.get_document_element();
            viewer.apply_document(de, arguments[0]);
        """, desired_html)


        # Parse the viewer html. We need to parse it with our own custom HTML
        # parser and then dump it back out as well-formed XML, to allow the
        # comparison to proceed.
        viewer_html = self.get_viewer_html()
        viewer_tree = parse_html(viewer_html)
        viewer_xml = lxml.etree.tostring(viewer_tree)
        assert self.compare_html(desired_html, viewer_xml, strip_localhost_hrefs_for_ie=True)

    def test_get_diff_add_node(self):
        """ Test 3: Diff of adding a node """
        self.init_webdriver()
        self.init_broadcaster_state()
        self.execute_script("""
            broadcaster_iframe.contentWindow.add_div(); // Defined in test_mirrordom_javascript_content.html
        """)
        diffs = self.get_broadcaster_diff()

        print "Diff: %s" % (diffs)

        # Expected result should be identical to:
        # [[u'node', [1,5], u'<div title="title goes here" onclick="alert('hi')">Hello everybody</div>',
        #       [[u'props', [], {u'style.cssText': u'background-color: blue;'}, None]]]]

        # Diff should be similar to:
        #[[u'node', u'html', [1, 7], u'<div onclick="alert(\'hi\')" title="title goes here" style="background-color: blue;">Hello everybody</div>',
        #       u'', [[u'html', [], {u'style.cssText': u'background-color: blue;'}]]]]
        EXPECTED_NODE_HTML = """<div title="title goes here" onclick="alert('hi')">Hello everybody</div>"""

        assert len(diffs) == 1
        html = diffs[0][3]
        tail_text = diffs[0][4]
        props = diffs[0][5]

        print "Expected: %s" % (EXPECTED_NODE_HTML)
        print "Html: %s" % (html)

        # Warning: innerHTML works different between different browsers
        # (i.e. IE will mangle innerHTML with dynamic property updates we can't
        # do a direct string comparison)
        assert self.compare_html(EXPECTED_NODE_HTML, html, ignore_attrs=['style'])

        # test_3_modify_broadcaster_document_with_add_node adds
        # background-color style which should reflect in the node properties
        assert len(props) == 1

        # Prop should be: [], {u'style.cssText': u'background-color: red;'}
        node_type, prop_path, changed_props = props[0]
        assert "style.cssText" in changed_props
        # The path should be empty as the style applies directly to the node
        assert prop_path == []

    def test_apply_add_node_diff(self):
        """ Test 4: Apply a simple add node diff """
        self.init_webdriver()
        self.setup_viewer_iframe_document()
        div_id = "LASDFSDKLFJLSDK"
        tail_text = "SHIL:SDHGLSDG"
        diff = [[u'node', 'html', [1, 4],
                 u'<div id="%s" style="background-color: red">Hello There</div>' % (div_id),
                 tail_text, []]]
        self.apply_viewer_diff(diff)

        self.webdriver.switch_to_frame('viewer_iframe')
        div = self.webdriver.find_element_by_id(div_id)
        assert div is not None
        # Slightly dodgy, can't really verify that it's after the div
        div_parent = div.find_element_by_xpath("..")
        assert tail_text in div_parent.text

    def test_get_initial_property_diff(self):
        """ Test 5: Retrieve initial property diff """
        self.init_webdriver()
        result = self.execute_script("""
            var data = broadcaster.start_document();
            return JSON.stringify(data["props"]);
        """)
        result = json.loads(result)
        print result

        # CSS rules only
        assert all(d[0] == "props" for d in result)

        # Should be a border in there somewhere (note: IE returns individual
        # border rules for each side, FF retains the single border rule)
        assert util.diff_contains_changed_property_value(result, "border")

        # Make sure there's no crud making it through
        assert not util.diff_contains_empty_attr_prop_values(result)

        # One inline style has been defined against the table, there should be
        # a "value" property against the input element as well
        assert len(result) >= 1

    def test_get_diff_styles(self):
        """ Test 6: Retrieve document with dynamically modified styles """
        self.init_webdriver()
        self.init_broadcaster_state()
        self.execute_script("""
            broadcaster_iframe.contentWindow.change_some_css();
        """)
        result = self.get_broadcaster_diff()
        print result

        # Extra class added, plus css background-color
        assert len(result) >= 2

    def test_get_diff_attributes(self):
        """ Test 7: Diff of attributes """
        self.init_webdriver()
        self.init_broadcaster_state()
        self.execute_script("""
            broadcaster_iframe.contentWindow.change_some_attribute();
        """)
        result = self.get_broadcaster_diff()
        print result
        assert len(result) > 0

    def test_get_diff_properties(self):
        """ Test 8: Diff of properties """
        self.init_webdriver()
        self.init_broadcaster_state()

        new_value = "-ae9ij"

        # Change text input value
        self.webdriver.switch_to_frame('broadcaster_iframe')
        input = self.webdriver.find_element_by_id('thetextinput')
        input.send_keys(new_value)
        #self.execute_script("test_8_modify_broadcaster_document_with_property()")

        # Get the diff
        self.webdriver.switch_to_default_content()
        result = self.get_broadcaster_diff()
        print result

        # Should be there
        assert util.diff_contains_changed_property_value(result, new_value)

    def test_get_diff_delete_node(self):
        """ Test 9: Diff of deleting nodes """
        self.init_webdriver()
        self.init_broadcaster_state()
        self.execute_script("""
            broadcaster_iframe.contentWindow.delete_div();
        """)
        result = self.get_broadcaster_diff()
        print result
        assert len(result) > 0

    def test_apply_property_diff(self):
        """ Test 10: Apply a property diff """
        self.init_webdriver()
        new_value = "gSE_AU*)EHGSIODNGO"
        # Assuming that the <input id="thetextinput">  element is at position
        # [1,2,0] in test_mirrordom_javascript_content_sanitised.html
        diff = [[u'props', 'html', [1, 2, 0], {u'value': new_value}, None]]
        self.setup_viewer_iframe_document()

        # Value should be default to "hello"
        self.webdriver.switch_to_frame('viewer_iframe')
        input = self.webdriver.find_element_by_id('thetextinput')
        input_value = input.get_attribute("value")
        assert input_value == "hello"
        print "Initial value: %s" % (input_value)

        # Ok, change the property
        self.webdriver.switch_to_default_content()
        self.apply_viewer_diff(diff)

        # Now let's check it out
        self.webdriver.switch_to_frame('viewer_iframe')
        input = self.webdriver.find_element_by_id('thetextinput')
        input_value = input.get_attribute("value")
        print "Got: %s" % (input_value)
        assert input_value == new_value

    def test_apply_attribute_diff(self):
        """ Test 11: Apply an attribute diff """
        self.init_webdriver()
        new_value = "4"
        # Assuming that the <table id="thetable">  element is at position
        # [1,1,1] in test_mirrordom_javascript_content_sanitised.html. This should
        # change cellSpacing to 4
        diff = [[u'attribs', 'html', [1, 1, 0], {u'cellSpacing': new_value}, []]]
        self.setup_viewer_iframe_document()

        # Cellspacing shouldn't be set yet
        self.webdriver.switch_to_frame('viewer_iframe')
        table = self.webdriver.find_element_by_id('thetable')
        table_cellspacing = table.get_attribute("cellspacing")
        print "Cellspacing before: %s" % (table_cellspacing)
        assert table_cellspacing == None

        # Ok, change the attrib
        self.webdriver.switch_to_default_content()
        self.apply_viewer_diff(diff)

        # Now let's check it out
        self.webdriver.switch_to_frame('viewer_iframe')
        table = self.webdriver.find_element_by_id('thetable')
        table_cellspacing = table.get_attribute("cellspacing")
        print "Cellspacing after: %s" % (table_cellspacing)
        assert table_cellspacing == new_value

    def test_apply_delete_node_diff(self):
        """ Test 12: Apply a delete diff

        WARNING: This test is brittle if you're modifying the test HTML
        Try to make sure <div id="thelastelement"> is always the last element
        in the <body>.
        """
        self.init_webdriver()

        # This should delete the <a id="textinput"> at the end of the page
        diff = [[u'deleted', 'html', [1, 4]]]
        self.setup_viewer_iframe_document()

        # Just make sure it's there first
        self.webdriver.switch_to_frame('viewer_iframe')
        div = self.webdriver.find_element_by_id('thelastelement')
        assert div != None

        self.webdriver.switch_to_default_content()
        self.apply_viewer_diff(diff)

        # Shouldn't be there now
        self.webdriver.switch_to_frame('viewer_iframe')
        try:
            div = self.webdriver.find_element_by_id('thelastelement')
        except NoSuchElementException:
            div_exists = False
        else:
            div_exists = True

        assert not div_exists

    def test_get_and_apply_initial_property_diff(self):
        """
        Test 13: Get and set initial property diff

        This is mainly testing that the ipaths in the get_property_diffs value
        are correct.

        WARNING: Assumes that diffs are untouched in mirrordom
        """
        new_value = "sdfgsdfogj"

        self.init_webdriver()
        self.setup_viewer_iframe_document()

        # Value should be default to "hello"
        self.webdriver.switch_to_frame('broadcaster_iframe')
        input = self.webdriver.find_element_by_id('thetextinput')
        initial_value = input.get_attribute("value")
        input.send_keys(new_value)
        test_value = input.get_attribute("value")
        assert test_value == initial_value + new_value
        print "Test value: %s" % (test_value)

        # Ok, change the property
        self.webdriver.switch_to_default_content()
        prop_diffs = self.execute_script("""
            var data = broadcaster.start_document();
            return data["props"];
        """)
        print "Diff: %s" % (prop_diffs)
        self.apply_viewer_diff(prop_diffs)

        # Now let's check it out
        self.webdriver.switch_to_frame('viewer_iframe')
        input = self.webdriver.find_element_by_id('thetextinput')
        input_value = input.get_attribute("value")
        print "Got: %s" % (input_value)
        assert input_value == test_value

    def test_jquery_dialog_open(self):
        """ Test 14: Open jquery dialog, get diff """
        self.init_webdriver()
        self.init_broadcaster_state()
        self.execute_script("""
            broadcaster_iframe.contentWindow.make_and_show_dialog();
        """)
        result = self.get_broadcaster_diff()
        print result

    def test_jquery_dialog_close(self):
        """ Test 15: Open jquery dialog, get diff """
        self.test_jquery_dialog_open()
        self.execute_script("""
            broadcaster_iframe.contentWindow.close_dialog();
        """)
        result = self.get_broadcaster_diff()
        print result

    def test_multiple_text_nodes(self):
        """ Test 16: Test multiple consecutive text nodes """
        self.init_webdriver()
        text_nodes = ["multiple ", " text ", "nodes"]
        add_to_node = [1,1] # <div id="thediv">Blaurgh

        # Before we start...confirm existing text

        # Existing text
        before, after = self.execute_script("""
            var doc_elem = broadcaster.get_document_element();
            var text_items = arguments[0];
            var node = MirrorDom.node_at_path(doc_elem, arguments[1]);
            var existing_text = MirrorDom.get_text_node_content(node.firstChild);
            var doc = node.ownerDocument;
            var insert_before = node.firstChild;
            for (var i = 0; i < text_items.length; i++) {
                node.insertBefore(doc.createTextNode(text_items[i]), insert_before);
            }
            var updated_text = MirrorDom.get_text_node_content(node.firstChild);
            return [existing_text, updated_text];
            """, text_nodes, add_to_node)
        after = after.replace('\n', '')
        print "Before: %r\nAfter: %r" % (before, after)
        assume_before_text = "Blaurgh" # Previous knowledge from our path
        assert before.strip() == assume_before_text
        re_pattern = "%s\s*%s" % ("".join(text_nodes), assume_before_text)
        assert re.search(re_pattern, after.replace('\n', '')) is not None

    # Note that I've deliberately omitted <tbody> from the table element, as I
    # want to see what sort of complications ensue
    TEST_APPLY_DOCUMENT_WITH_STYLE_ELEMENT = """\
    <html>
      <head>
        <title>Blah</title>
        <style type="text/css"> body { color: red; } </style>
      </head>
      <body>
        helo
      </body>
    </html>"""

    def test_apply_document_with_style_element(self):
        """ Test 17: Some browsers don't like dynamically created <style>
        elements (i.e. IE8) """
        self.init_webdriver()
        # Firefox doesn't like it when we go too fast
        time.sleep(0.1)
        desired_html = self.TEST_APPLY_DOCUMENT_WITH_STYLE_ELEMENT
        self.apply_viewer_html(desired_html)
        viewer_html = self.get_viewer_html()
        assert self.compare_html(desired_html, viewer_html)

class TestIE(TestFirefox):

    @classmethod
    def _create_webdriver(cls):
        return util.get_debug_ie_webdriver()

    def test_apply_document_with_style_element(self):
        # I want to run the test, but ignore failure because we're expecting it
        try:
            return super(TestIE, self).test_apply_document_with_style_element(self)
        except:
            # Hmm...
            raise nose.plugins.skip.SkipTest("IE can't modify style elements")

class TestChrome(TestFirefox):
    @classmethod
    def _create_webdriver(cls):
        return util.get_debug_chrome_webdriver()
