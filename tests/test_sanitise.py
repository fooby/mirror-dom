import sys
import lxml

from nose.tools import nottest

import util

try:
    import mirrordom.server
except ImportError:
    sys.path.append(util.get_mirrordom_path())
    import mirrordom.server

from mirrordom.sanitise import sanitise_html

def setupModule():
    util.start_webserver()

def teardownModule():
    util.stop_webserver()

class TestSanitiseDirect(util.TestBase):
    """ Test document sanitising which can't easily be tested through the
    browser """

    # -----------------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------------
    def sanitise_and_compare(self, raw, desired=None, is_fragment=False,
            **compare_args):
        """
        :param raw:     Unsanitised HTML, the type you would expect to see
                        from a browser's innerHTML.
        :param desired: What the HTML should look like
        """
        global compare_html
        desired = raw if desired is None else desired
        raw = raw.strip()
        desired = desired.strip()
        sanitised = sanitise_html(raw, is_fragment=is_fragment)
        return self.compare_html(desired, sanitised, **compare_args)

    # -----------------------------------------------------------------------------
    # Tests
    # -----------------------------------------------------------------------------
    def test_document(self):
        """ General tag strip test """
        raw = """\
            <html>
              <head>
                <title>RemoveMe</title>
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

        sanitised = """\
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

        assert self.sanitise_and_compare(raw, sanitised)

    def test_remove_head_title_and_scripts(self):
        """ Remove title and script tags """
        raw = """
            <html>
              <head>
                <title>Blah</title>
                <script type="text/javascript" src="https://ajax.googleapis.com/ajax/libs/jquery/1.7.2/jquery.min.js"></script>
                <script type="text/javascript">alert("hello");</script>
              </head>
              <body>
                <script type="text/javascript">alert("bye");</script>
                <div>hi</div>
              </body>
            </html>
            """
        sanitised = """
            <html>
              <head>
              </head>
              <body>
                <div>hi</div>
              </body>
            </html>
            """

        assert self.sanitise_and_compare(raw, sanitised)

    def test_preserve_tbody_fragment(self):
        """
        Ensure that sanitising doesn't introduce unexpected tags.

        Apparently libxml apparently likes to wrap <html> tags.
        """
        html = """
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
        assert self.sanitise_and_compare(html, is_fragment=True)

    def test_preserve_td_fragment(self):
        html = """<td style="background-color: blue;">SDF</td>"""
        assert self.sanitise_and_compare(html, is_fragment=True)

    def test_inject_tbody(self):
        raw = """
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
        sanitised = """
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
        assert self.sanitise_and_compare(raw, sanitised, is_fragment=True)

    def test_sanitise_html_fragment_bad_form_in_table(self):
        raw = """
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
        sanitised = """
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
        assert self.sanitise_and_compare(raw, sanitised)

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

    def apply_and_compare(self, html, desired_html=None, sanitise=True,
            **compare_kwargs):
        browser_html = self.to_browser_html(html)
        desired_html = html if desired_html is None else desired_html
        print "Browser HTML: %s" %(browser_html)
        if sanitise:
            browser_html = sanitise_html(browser_html, is_fragment=True)
            print "Sanitised Browser HTML: %s" % (browser_html)
        return self.compare_html(desired_html, browser_html, **compare_kwargs)

    # -----------------------------------------------------------------------------
    # Tests
    # -----------------------------------------------------------------------------
    def test_simple_html(self):
        """ Test fetching simple innerHTML """
        self.init_webdriver()
        html = """<div>Hello<p>World</p><span>Dog</span></div>"""
        assert self.apply_and_compare(html)

    def test_href(self):
        """ Test removing href """
        self.init_webdriver()
        html = """<div><a href="hello world">Blah</a></div>"""
        desired_html = """<div><a href="#">Blah</a></div>"""
        assert self.apply_and_compare(html, desired_html)

    def test_onclick(self):
        """ Test removing onclick"""
        self.init_webdriver()
        html = """<div onclick="do_something_evil();">Click me</div>"""
        desired_html = """<div>Click me</div>"""
        assert self.apply_and_compare(html, desired_html)

    def test_input(self):
        """ Test fetching innerHTML with input """
        self.init_webdriver()
        html = """<div><input type="text"/>Hello<span>Blah</span></div>"""
        assert self.apply_and_compare(html, ignore_ie_default_attributes=True)

    def test_table(self):
        """ Test fetching td innerHTML with input """
        self.init_webdriver()
        html = "<table><tr><td>HELO</td></tr></table>"
        desired_html = "<table><tbody><tr><td>HELO</td></tr></tbody></table>"
        assert self.apply_and_compare(html, desired_html)

    @nottest
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
        assert self.apply_and_compare(html)

    def test_iframe_src(self):
        """ Strip iframe src """
        self.init_webdriver()
        html = '<iframe src="http://removeme"></iframe>'
        desired_html = '<iframe></iframe>'
        assert self.apply_and_compare(html, desired_html)

    def test_script_tag(self):
        """ Remove script tag """
        self.init_webdriver()
        html = '<div>hello <script type="text/javascript">null</script> world</div>'
        desired_html = '<div>hello  world</div>'

        # Internet Explorer loses a whitespace somewhere, darn it.
        assert self.apply_and_compare(html, desired_html, ignore_all_whitespace=True)

    def test_script_in_table(self):
        """ Test script tags where they shouldn't be in a table """
        self.init_webdriver()
        html = """\
        <table>
           <script type="text/javascript">null;</script>
           <script type="text/javascript">null;</script>
           <tr><td>hello</td></tr>
           <script type="text/javascript">null;</script>
        </table>
        """
        desired_html = """\
        <table>
            <tbody>
              <tr><td>hello</td></tr>
            </tbody>
        </table>
        """
        assert self.apply_and_compare(html, desired_html)

class TestSanitiseOnly(TestFirefox):
    """ Don't test browser HTML mangling, ONLY test sanitising """
    def init_webdriver(self):
        pass

    def to_browser_html(self, html):
        return html

class TestIE(TestFirefox):
    @classmethod
    def _create_webdriver(cls):
        return util.get_debug_ie_webdriver()

class TestChrome(TestFirefox):
    @classmethod
    def _create_webdriver(cls):
        return util.get_debug_chrome_webdriver()
