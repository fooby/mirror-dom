"""
HTML Parsing and sanitising
"""

import logging
import re
from cStringIO import StringIO

import lxml
import lxml.etree
import lxml.html
import lxml.html.clean

from . import parser

logger = logging.getLogger("mirrordom")

# List of void tags obtained from HTML5 specs. These are tags for which there
# may not be a closing tag.
VOID_TAGS = set(['area', 'base', 'br', 'col', 'command', 'embed', 'hr', 'img',
                'input', 'keygen', 'link', 'meta', 'param', 'source', 'track',
                'wbr'])

VOID_TAGS_RE = re.compile("<(%s).*?>" % ('|'.join(VOID_TAGS)), re.IGNORECASE)
TAG_END_RE = re.compile(".*?</\s*(\w+)\s*>")

def _get_html_cleaner():
    cleaner = lxml.html.clean.Cleaner(
        frames = False,
        links = False,
        forms = False,
        style = False,
        page_structure = False,
        scripts = True,
        embedded = False,
        safe_attrs_only = False,

        # Setting title elements have some issues in IE
        kill_tags = ['title'],

        # Hmm...we want to keep SVG and VML tags
        remove_unknown_tags = False,

        # If True, the cleaner will wipe out <link> elements. We do want to clean
        # javascript but we can't use the cleaner's handling, so we'll have to do
        # our own javascript cleaning later on.
        javascript = False,
    )

    cleaner.remove_unknown_tags = False

    return cleaner

def sanitise_diffs(diffs):
    # For now, we'll just sanitise in place
    for d in diffs:
        diff_type = d[0]
        if diff_type == "node":
            # [0] Type [1] Path [2] type [3] outer html ...
            d[3] = sanitise_html(d[3], is_fragment=True)
    return diffs

def force_insert_tbody(html_tree):
    """
    We want to force insert <tbody> elements between tables and trs to simulate
    the automatic <tbody> insertion that most browsers do internally in their
    DOM structure. It's probably not safe to assume that the innerHTML values
    will always include the <tbody> insertion, so we'll just do it ourselves
    here too.
    """
    tables = html_tree.iter('table')
    for table in tables:
        tbody = None
        children = list(table)
        for c in children:
            if not isinstance(c.tag, basestring):
                continue
            elif c.tag.lower() == "colgroup":
                continue
            elif c.tag.lower() in ("tbody", "tfoot", "thead"):
                tbody = None
            else:
                if tbody is None:
                    tbody = lxml.html.Element('tbody')
                    c.addprevious(tbody)
                tbody.append(c)
    return html_tree

def sanitise_html(html, return_etree=False, is_fragment=False):
    """
    Strip out nasties such as <meta>, <script> and other useless bits of
    information.

    NOTE: The sanitising process needs to work in agreement with the javascript function
    MirrorDom.Util.should_ignore_node

    :param return_etree:        If True, return an etree object (instead of a string)

    :param is_fragment:         Whether we're doing a fragment of the HTML document.
                                The current HTML parsing using a subclassed
                                python HTMLParser doesn't care whether it's a
                                fragment or not, but other alternative HTML parsers do.
    """
    #tree = parse_html(html, is_fragment=is_fragment)
    tree = parser.parse_html(html)
    sanitise_tree(tree)
    if return_etree:
        return tree
    else:
        return lxml.etree.tostring(tree)

#def correct_html(html, fix_void_tags=True):
#    result = StringIO()
#    pos = 0
#    while True:
#        m = VOID_TAGS_RE.search(html, pos)
#        if m is not None:
#            # Establish if it's an "open" void tag
#            full_tag = m.group()
#            tagname = m.group(1)
#            need_to_fix = True
#            end_pos = m.end()
#            if full_tag[-2] == "/":
#                need_to_fix = False
#            else:
#                end_match = TAG_END_RE.match(html, end_pos)
#                if end_match is not None and end_match.group(1) == tagname:
#                    need_to_fix = False
#            if need_to_fix:
#                # We'll manually close this tag
#                result.write(html[pos:m.start()])
#                full_tag = full_tag[:-1] + "/>"
#                result.write(full_tag)
#                new_pos = m.end()
#            else:
#                # Self closing tag
#                new_pos = m.end()
#                result.write(html[pos:new_pos])
#            pos = new_pos
#        else:
#            # Write the rest of the string
#            result.write(html[pos:])
#            break
#    return result.getvalue()
#
#def parse_html(html, is_fragment=False):
#    """
#    Parses HTML and return lxml.etree.ElementTree instance
#    """
#    #if is_fragment:
#    #    try:
#    #        return lxml.html.fragment_fromstring(html)
#    #    except lxml.etree.ParserError:
#    #        return lxml.html.fromstring(html)
#    #else:
#    #    return lxml.html.fromstring(html)
#
#
#    html = correct_html(html, fix_void_tags=True)
#    return lxml.etree.fromstring(html)

def sanitise_tree(tree):
    """
    :param tree:    lxml.etree.ElementTree instance
    """
    cleaner = _get_html_cleaner()
    cleaner(tree)

    force_insert_tbody(tree)

    # Find iframes and strip src
    for iframe in tree.iter('iframe'):
        try:
            iframe.attrib.pop("src")
        except KeyError:
            pass

    # Find anchors and strip hrefs        
    for anchor in tree.iter('a'):
        if "href" in anchor.attrib:
            anchor.attrib["href"] = "#"

    # Strip javascript (copied from lxml.html.clean.Cleaner code, but that does
    # more than we want)
    # safe_attrs handles events attributes itself
    for el in tree.iter():
        attrib = el.attrib
        for aname in attrib.keys():
            if aname.startswith('on'):
                del attrib[aname]

