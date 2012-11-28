"""
Test parsing of innerHTML constructs
"""

import sys
import lxml.etree

from nose.tools import nottest

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

class TestParseDirect(util.TestBase):
    """ Test parsing of various innerHTML constructs """

    # -----------------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------------
    def parse_and_compare(self, raw, desired=None, is_fragment=False,
            **compare_args):
        """
        :param raw:         Unsanitised HTML, the type you would expect to see
                            from a browser's innerHTML. This well be parsed
                            with mirrordom's parsing routine.

        :param desired:     What the HTML should look like. MUST be well formed XML.
                            Will be parsed with a strict XML parser.
        """
        global compare_html
        desired = raw if desired is None else desired
        raw = raw.strip()
        desired = desired.strip()
        parsed_tree = parse_html(raw)
        parsed_html = lxml.etree.tostring(parsed_tree)
        return self.compare_html(parsed_html, desired, **compare_args)

    # -----------------------------------------------------------------------------
    # Tests
    # -----------------------------------------------------------------------------
    def test_simple_doc(self):
        """
        Test simple document.
        In HTML, there's no slash to indicate self closing. (called a "void" tag)
        """
        doc = """<html><head><title>RemoveMe</title></head><body>hello</body></html>"""
        assert self.parse_and_compare(doc)

    def test_meta_in_doc(self):
        """
        Test parsing of meta self-closing tag in a document.
        In HTML, there's no slash to indicate self closing. (called a "void" tag)
        """
        raw = """<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"><title>RemoveMe</title></head><body></body></html>"""
        well_formed = """<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"/><title>RemoveMe</title></head><body></body></html>"""
        assert self.parse_and_compare(raw, well_formed)

    def test_link_in_doc(self):
        """
        Test parsing of link self-closing tag in a document.
        In HTML, there's no slash to indicate self closing. (called a "void" tag)
        """
        raw = """<html><head><link rel="stylesheet" type="text/css" media="print" href="/styles/print.css"><title>RemoveMe</title></head><body></body></html>"""
        well_formed = """<html><head><link rel="stylesheet" type="text/css" media="print" href="/styles/print.css"/><title>RemoveMe</title></head><body></body></html>"""
        assert self.parse_and_compare(raw, well_formed)

    def test_input_in_doc(self):
        """
        Test parsing of input self-closing tag in a document.
        In HTML, there's no slash to indicate self closing. (called a "void" tag)
        """
        raw = """<html><head><title>RemoveMe</title></head><body><input type="text" value="hello"></body></html>"""
        well_formed = """<html><head><title>RemoveMe</title></head><body><input type="text" value="hello"/></body></html>"""
        assert self.parse_and_compare(raw, well_formed)

    def test_input_in_doc(self):
        """
        Test parsing of <script> tag
        """
        raw = """<html><head><title>RemoveMe</title></head><body><script type="text/javascript">
            var x = "<div>hello</div>";
        </script></body></html>"""

        well_formed = """<html><head><title>RemoveMe</title></head><body><script type="text/javascript"><![CDATA[
            var x = "<div>hello</div>";
        ]]></script></body></html>"""
        assert self.parse_and_compare(raw, well_formed)

class TestFirefox(util.TestBrowserBase):
    """
    Test applying HTML fragments to the browser, reading them back, sanitising
    them and comparing to the original.

    Should help identify browser behavioural anomalies.
    """
    HTML_FILE = "test_parse_or_sanitise.html"

    @classmethod
    def _create_webdriver(cls):
        return util.get_debug_firefox_webdriver()

    # -----------------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------------
    def to_browser_html(self, html):
        """ Set the body and get the resulting innerHTML.  """
        browser_html = self.execute_script("""
            var element = $(arguments[0]);
            $('body').append(element);
            return MirrorDom.outerhtml(element[0]);
        """, html)
        return browser_html

    def apply_and_compare(self, html, desired_html=None,
            **compare_kwargs):
        browser_html = self.to_browser_html(html)
        print "Browser html: %s" % (browser_html)
        desired_html = html if desired_html is None else desired_html
        parsed_tree = parse_html(browser_html)
        parsed_html = lxml.etree.tostring(parsed_tree)
        return self.compare_html(desired_html, parsed_html, **compare_kwargs)

    # -----------------------------------------------------------------------------
    # Tests
    # -----------------------------------------------------------------------------
    def test_simple_html(self):
        """ Test fetching simple innerHTML """
        self.init_webdriver()
        html = """<div class="hello">Hello<p>World</p><span>Dog</span></div>"""
        assert self.apply_and_compare(html)

    def test_input(self):
        """ Test fetching innerHTML with input """
        self.init_webdriver()
        html = """<div><input type="text"/>Hello<span>Blah</span></div>"""
        assert self.apply_and_compare(html, ignore_ie_default_attributes=True)

    def test_dodgy_self_closing_tag(self):
        """
        Test browser automatically fixing up dodgy self closing input tag.
        
        Note: IE doesn't actually fix it up, it leaves it as:

        <SPAN><INPUT>I shouldn't be here</INPUT>hello</SPAN>
        
        But our HTML parser finishes the job of fixing it. Go our HTML parser!
        """
        self.init_webdriver()
        html = """<span><input type="text">I shouldn't be here</input>hello</span>"""
        desired_html = """<span><input type="text"/>I shouldn't be herehello</span>"""
        assert self.apply_and_compare(html, desired_html)

    def test_table(self):
        """ Test fetching td innerHTML """
        self.init_webdriver()
        html = "<table><tbody><tr><td>HELO</td></tr></tbody></table>"
        assert self.apply_and_compare(html)

    def test_table_in_a(self):
        """ Test table inside anchor element (from CKEditor) """
        self.init_webdriver()
        html = """\
        <a class="cke_colorauto" _cke_focus="1" hidefocus="true"
            title="Automatic"
            onclick="CKEDITOR.tools.callFunction(118,null,'back');return false;"
            href="javascript:void('Automatic')" role="option" aria-posinset="1"
            aria-setsize="41">
          <table role="presentation" cellspacing="0" cellpadding="0" width="100%">
            <tbody>
              <tr>
                <td>
                  <span class="cke_colorbox" id="cke_4_colorBox"
                        style="background-color: rgba(0, 0, 0, 0);">
                  </span>
                </td>
                <td colspan="7" align="center">Automatic</td>
              </tr>
            </tbody>
          </table>
        </a>"""
        assert self.apply_and_compare(html, ignore_attr_values=["hidefocus"])

    def test_html_entity(self):
        self.init_webdriver()
        html = """<span>Hello World &#169; nobody</span>"""
        assert self.apply_and_compare(html)

    def test_comment(self):
        self.init_webdriver()
        html = """<span>oh,<!-- hello world--><br/></span>"""
        assert self.apply_and_compare(html)

    def test_bad_attribute(self):        
        self.init_webdriver()
        html = """<div><span class="world"">World</span>Blah<a href="hello"" target="_top">Hello</a></div>"""
        desired_html = """<div><span class="world">World</span>Blah<a href="hello" target="_top">Hello</a></div>"""
        assert self.apply_and_compare(html, desired_html)

    def test_para_autoclose(self):        
        self.init_webdriver()
        html = """<div><p>hello<div>world</div></div>"""
        desired_html = """<div><p>hello</p><div>world</div></div>"""
        assert self.apply_and_compare(html, desired_html)

    def test_table_autoclose_on_open(self):
        self.init_webdriver()
        html = """<table><colgroup><col width="100%"><tbody><tr><td>hello</td><tr><td>world</td></tbody></table>"""
        desired_html = """<table><colgroup><col width="100%"/></colgroup><tbody><tr><td>hello</td></tr><tr><td>world</td></tr></tbody></table>"""
        assert self.apply_and_compare(html, desired_html)

    def test_table_autoclose_on_close(self):
        """ Test inserting autoclosing HTML

        Note: Browsers automatically insert close tags, so we don't have to
        handle this scenario in our parser.
        """

        self.init_webdriver()
        html = """<table><tbody><tr><td>hello</td></table>"""
        desired_html = """<table><tbody><tr><td>hello</td></tr></tbody></table>"""
        assert self.apply_and_compare(html, desired_html)

class TestIE(TestFirefox):
    @classmethod
    def _create_webdriver(cls):
        return util.get_debug_ie_webdriver()

class TestChrome(TestFirefox):
    @classmethod
    def _create_webdriver(cls):
        return util.get_debug_chrome_webdriver()

class TestIE(TestFirefox):
    @classmethod
    def _create_webdriver(cls):
        return util.get_debug_ie_webdriver()

class TestChrome(TestFirefox):
    @classmethod
    def _create_webdriver(cls):
        return util.get_debug_chrome_webdriver()
