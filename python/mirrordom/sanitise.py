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

logger = logging.getLogger("mirrordom.sanitise")

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
        diff_doctype = d[1]

        # For SVG XML fragments, we need to retain the element and attribute
        # casing. For HTML, we need to discard casing (everything goes to
        # lowercase)
        retain_case = (diff_doctype == "svg")
        if diff_type == "node":
            # [0] Type [1] Path [2] type [3] outer html ...
            d[3] = sanitise_html(d[3], is_fragment=True,
                    retain_case=retain_case)
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

def sanitise_html(html, return_etree=False, is_fragment=False,
        retain_case=False):
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

    :param retain_case:         Retain element and attr casing. This can be bad for HTML,
                                but is needed for SVG.
    """
    tree = parser.parse_html(html, retain_case=retain_case)
    sanitise_tree(tree)
    if return_etree:
        return tree
    else:
        return lxml.etree.tostring(tree)

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

