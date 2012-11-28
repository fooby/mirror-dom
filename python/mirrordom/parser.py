"""
InnerHTML parser.

We probably want to feed the output to a DOM library for further operations.
We'll try using lxml.html.Elements.
"""

import re
import logging
from HTMLParser import HTMLParser, HTMLParseError, tagfind

from lxml.html import Element
import lxml.html

logger = logging.getLogger("mirrordom.parser")

class OuterHTMLParser(HTMLParser):
    """
    Parse outerHTML attribute from the browser (which uses innerHTML-esque output).

    This means we can make the following assumptions:

    - The innerHTML is well-formed HTML, given that the browser has
      performed the parse of the source HTML and performed any recovery of
      broken HTML.
    - HTML "self-closing" tags are NOT terminated with the trailing XML-esque
      slash (e.g. <div><input type="text"></div>
    - Internet Explorer may omit the double quotes around attributes (when
      there are no spaces in the attribute)
    - HTML has a single root

    The critical assumption here is that the innerHTML is well formed. This
    means our parser does not perform any recovery whatsoever.
    """

    VOID_TAGS = set(['area', 'base', 'br', 'col', 'command', 'embed', 'hr',
        'img', 'input', 'keygen', 'link', 'meta', 'param', 'source', 'track',
        'wbr'])

    TABLE_ELEMS = set(['tbody', 'thead', 'tfoot', 'colgroup'])

    # From HTML5 specs
    AUTOCLOSE_ON_OPEN = {
        "p":    set(["address", "article", "aside", "blockquote", "dir", "div",
            "dl", "fieldset", "footer", "form", "h1", "h2", "h3", "h4", "h5",
            "h6", "header", "hr", "menu", "nav", "ol", "p", "pre", "section",
            "table", "ul"]),

        "tbody":    TABLE_ELEMS,
        "thead":    TABLE_ELEMS,
        "tfoot":    TABLE_ELEMS,
        "colgroup": TABLE_ELEMS,
        "tr":       set(["tr"]),
        "td":       set(["td", "th"]),
        "th":       set(["td", "th"]),
        "dt":       set(["dt", "dd"]),
        "dd":       set(["dt", "dd"]),
        "li":       set(["li"]),
        "option":   set(["option"]),
    }

    #AUTOCLOSE_ON_CLOSE = {
    #    "tbody":    set(["table"]),
    #    "thead":    set(["table"]),
    #    "tfoot":    set(["table"]),
    #    "col":      set(["col"]),
    #}

    AUTOCLOSE_ON_PARENT_CLOSE = set([
        "col", "tbody", "thead", "tfoot", "colgroup",
    ])

    # Override standard CDATA handling
    CDATA_CONTENT_ELEMENTS = ()
    CDATA_CONTENT_ELEMENTS_V2 = set(['script', 'style'])

    def __init__(self):
        self.stack = []
        self.root = None
        HTMLParser.__init__(self)

    def find_autoclose_on_open(self, tag):
        pos = len(self.stack) - 1
        while pos >= 0:
            elem = self.stack[pos]
            try:
                autoclose_tags = self.AUTOCLOSE_ON_OPEN[elem.tag]
            except KeyError:
                break
            if tag not in autoclose_tags:
                break
            elif pos == 0:
                return 0
            pos -=1
        autoclose_count = len(self.stack) - pos
        return autoclose_count - 1

    def check_autoclose_on_open(self, tag):
        num_to_close = self.find_autoclose_on_open(tag)
        for i in range(num_to_close):
            #logger.debug("Autoclosing: %s due to %s", self.stack[-1].tag, tag)
            self.close_tag(tag, force=True)

    # None of our browsers rely on autoclosing...thankfully, they all
    # insert close tags.
    #
    #def check_autoclose_on_close(self, tag):
    #    if not self.stack:
    #        return
    #    pos = len(self.stack) - 1
    #    while pos >= 0:
    #        elem = self.stack[pos]
    #        if elem.tag == tag:
    #            # Success
    #            break
    #        elif elem.tag not in AUTOCLOSE_ON_PARENT_CLOSE:
    #            # Failed at locating a tag
    #            return 0
    #        elif pos == 0:
    #            # Failed at locating a tag
    #            return 0
    #        pos -=1
    #    autoclose_count = len(self.stack) - pos
    #    return autoclose_count

    def open_tag(self, tag, attrs):
        """
        Handle a new tag. Performs autoclose checks.
        """
        new = Element(tag)
        attrs = ((k, v or "") for k, v in attrs)
        new.attrib.update(attrs)

        if self.root is None:
            self.root = new
        else:
            if not self.stack:
                raise HTMLParseError("Unexpected open tag: %s" % (tag))
            self.check_autoclose_on_open(tag)
            parent = self.stack[-1]
            parent.append(new)
        self.stack.append(new)

    def close_tag(self, tag, check_autoclose=False, force=False):
        """
        Close a new tag. Performs autoclose checks.

        :param check_autoclose:     Scans up through the stack to find out how
                                    far to autoclose. UNUSED
        :param force:               Force close the topmost element on the stack
                                    Not compatible with check_autoclose
        """
        # Removing autoclose checking as our browsers automatically close
        # elements.
        #
        #assert not (check_autoclose and force)
        #if check_autoclose:
        #    num_to_close = self.check_autoclose_on_close(tag)
        #    if num_to_close == 0:
        #        raise HTMLParseError("Unexpected close tag: %s. Expected: %s" \
        #                % (tag, elem.tag))
        #else:
        #    if not self.stack:
        #        raise HTMLParseError("Unexpected close tag at top of tree: %s" % \
        #                tag)
        #    elem = self.stack[-1]
        #    if not force and elem.tag != tag:
        #        raise HTMLParseError("Unexpected close tag: %s. Expected: %s" \
        #                % (tag, elem.tag))
        #    num_to_close = 1

        #for i in range(num_to_close):
        #    self.stack.pop()

        if not self.stack:
            raise HTMLParseError("Unexpected close tag at top of tree: %s" % (tag))
        elem = self.stack[-1]
        if not force and elem.tag != tag:
            #import rpdb2
            #rpdb2.start_embedded_debugger("hello")
            raise HTMLParseError("Unexpected close tag: %s. Expected: %s" % \
                    (tag, elem.tag))
        self.stack.pop()

    # -------------------------------------------------------------------------
    # HTMLParser methods
    # -------------------------------------------------------------------------

    def set_specific_cdata_mode(self, tag):
        self.interesting = re.compile(r'<(/%s|\Z)' % (tag), re.IGNORECASE)

    def handle_starttag(self, tag, attrs):
        self.open_tag(tag, attrs)
        if tag in self.VOID_TAGS:
            self.close_tag(tag)

        if tag in self.CDATA_CONTENT_ELEMENTS_V2:
            self.set_specific_cdata_mode(tag)

    def handle_endtag(self, tag):
        if tag in self.VOID_TAGS:
            return
        #self.close_tag(tag, check_autoclose=True)
        self.close_tag(tag)

    def handle_startendtag(self, tag, attrs):
        self.open_tag(tag, attrs)
        self.close_tag(tag)

    def handle_data(self, data):
        # Ignore data outside the root, usually trailing whitespace
        if not self.stack:
            return
        elem = self.stack[-1]
        if len(elem):
            elem[-1].tail = (elem[-1].tail or "") + data
        else:
            elem.text = (elem.text or "") + data

    def handle_comment(self, data):
        elem = self.stack[-1]
        comment = lxml.etree.Comment(data)
        elem.append(comment)

    # -------------------------------------------------------------------------
    # HACK check_for_whole_start_tag to tolerate bad attributes (sigh)
    # -------------------------------------------------------------------------


    LOCATESTARTTAGEND = re.compile(r"""
      <[a-zA-Z][-.a-zA-Z0-9:_]*          # tag name
      (?:\s+                             # whitespace before attribute name
        (?:[a-zA-Z_][-.:a-zA-Z0-9_]*     # attribute name
          (?:\s*=\s*                     # value indicator
            (?:'[^']*'                   # LITA-enclosed value
              |\"[^\"]*\"                # LIT-enclosed value
              |[^'\">\s]+                # bare value
             )
           )?
              | (\?)                     # IE Hack (single question mark)
              | (\"=\"\")                # Chrome Hack ( "="" )
         )
       )*
      \s*                                # trailing whitespace
    """, re.VERBOSE)

    # Internal -- check to see if we have a complete starttag; return end
    # or -1 if incomplete.
    def check_for_whole_start_tag(self, i):
        rawdata = self.rawdata
        m = self.LOCATESTARTTAGEND.match(rawdata, i)          # Hacked line
        if m:
            j = m.end()
            next = rawdata[j:j+1]
            if next == ">":
                return j + 1
            if next == "/":
                if rawdata.startswith("/>", j):
                    return j + 2
                if rawdata.startswith("/", j):
                    # buffer boundary
                    return -1
                # else bogus input
                self.updatepos(i, j + 1)
                self.error("malformed empty start tag")
            if next == "":
                # end of input
                return -1
            # HACK GOES HERE: Adding ? and " characters.
            # IE tends to add a single question mark e.g. <a href="hello""> becomes <a href="hello" ?>
            # Chrome tends to add a weird thing e.g. <a href="hello""> becomes <a href="hello" "="">
            if next in ("abcdefghijklmnopqrstuvwxyz=/"
                        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
                # end of input in or before attribute value, or we have the
                # '/' from a '/>' ending
                return -1
            self.updatepos(i, j)
            self.error("malformed start tag")
        raise AssertionError("we should not get here!")

    # Hacks: Search for solo question marks (IE) OR "="" (Chrome) e.g.
    #   IE:     <a href="hello""> becomes <a href="hello" ?>
    #   Chrome: <a href="hello""> becomes <a href="hello" "="">
    ATTRFIND = re.compile(                                      # Hacked line
        r'\s*([a-zA-Z_][-.:a-zA-Z_0-9]*|\?|\")(\s*=\s*'          # Hacked line
        r'(\'[^\']*\'|"[^"]*"|[^\s"\'=<>`]*))?')                # Hacked line

    # Internal -- handle starttag, return end or -1 if not terminated
    def parse_starttag(self, i):
        #import rpdb2
        #rpdb2.start_embedded_debugger("hello"
        self._HTMLParser__starttag_text = None
        endpos = self.check_for_whole_start_tag(i)
        if endpos < 0:
            return endpos
        rawdata = self.rawdata
        self._HTMLParser__starttag_text = rawdata[i:endpos]

        # Now parse the data between i+1 and j into a tag and attrs
        attrs = []
        match = tagfind.match(rawdata, i+1)
        assert match, 'unexpected call to parse_starttag()'
        k = match.end()
        self.lasttag = tag = rawdata[i+1:k].lower()

        while k < endpos:
            m = self.ATTRFIND.match(rawdata, k)                 # Hacked line
            if not m:
                break
            attrname, rest, attrvalue = m.group(1, 2, 3)
            # IE and Chrome hack                                # Hacked line
            if attrname == "?" or attrname == '"':              # Hacked line
                k = m.end()                                     # Hacked line
                continue                                        # Hacked line
            elif not rest:
                attrvalue = None
            elif attrvalue[:1] == '\'' == attrvalue[-1:] or \
                 attrvalue[:1] == '"' == attrvalue[-1:]:
                attrvalue = attrvalue[1:-1]
                attrvalue = self.unescape(attrvalue)
            attrs.append((attrname.lower(), attrvalue))
            k = m.end()

        end = rawdata[k:endpos].strip()
        if end not in (">", "/>"):
            lineno, offset = self.getpos()
            if "\n" in self._HTMLParser__starttag_text:
                lineno = lineno + self._HTMLParser__starttag_text.count("\n")
                offset = len(self._HTMLParser__starttag_text) \
                         - self._HTMLParser__starttag_text.rfind("\n")
            else:
                offset = offset + len(self._HTMLParser__starttag_text)
            self.error("junk characters in start tag: %r"
                       % (rawdata[k:endpos][:20],))
        if end.endswith('/>'):
            # XHTML-style empty tag: <span attr="value" />
            self.handle_startendtag(tag, attrs)
        else:
            self.handle_starttag(tag, attrs)
            if tag in self.CDATA_CONTENT_ELEMENTS:
                self.set_cdata_mode()
        return endpos

def parse_html(html, is_fragment=False):
    """ See docstring for OuterHTMLParser.
    Returns None if no HTML detected.

    :param is_fragment:     Unused, but may come into play later with fallback parsers.
    """
    parser = OuterHTMLParser()
    try:
        parser.feed(html)
    except HTMLParseError, e:
        logger.debug("Couldn't parse HTML: %s", html)
        raise
    return parser.root

if __name__ == "__main__":
    TEST_HTML = """<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"><title>RemoveMe</title></head><body><span>hello</span>world!</body></html>"""
    parser = InnerHTMLParser()
    parser.feed(TEST_HTML)
    print lxml.html.tostring(parser.root)

    TEST_HTML2 = """\
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

    print "-----"
    parser = InnerHTMLParser()
    parser.feed(TEST_HTML2)
    print lxml.html.tostring(parser.root)
