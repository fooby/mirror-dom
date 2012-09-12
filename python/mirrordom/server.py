import time
import logging
import pprint
import uuid
import lxml
import lxml.etree
import lxml.html
import lxml.html.clean
import lxml.html.html5parser

#import json

logger = logging.getLogger("mirrordom")

class Session(object):
    """
    Track changelogs for each frame individually, but keep a common id counting
    system for the diffs.
    """

    def __init__(self):
        self.changelogs = {}
        self.last_change_id = -1

    def __repr__(self):
        return pprint.pformat(vars(self))

    def clear(self):
        self.changelogs = {}

    def get_next_change_id(self):
        self.last_change_id += 1
        x = self.last_change_id
        return x

    def init_html(self, frame_id, html, props):
        next_id = self.get_next_change_id()
        c = Changelog(html, next_id)
        c.add_diff_set(next_id, props)
        self.changelogs[frame_id] = c

    def add_diff(self, frame_id, diffs):
        """

        """
        next_id = self.get_next_change_id()
        # Raises KeyError if frame_id not found
        c = self.changelogs[frame_id]
        c.add_diff_set(next_id, diffs)

    def remove_frame_children(self, frame_path):
        for f in self.changelogs.keys():
            if len(f) <= len(frame_path):
                continue
            if frame_path == f[:len(frame_path)]:
                logger.debug("Removing frame child %s as parent %s was restarted",
                        f, frame_path)
                del self.changelogs[f]


class Changelog(object):
    def __init__(self, init_html, first_change_id):
        self.init_html = init_html
        self.diffs = []
        self.first_change_id = first_change_id

    def add_diff_set(self, next_id, diff):
        """
        :param diff:    List of diffs
        """
        self.diffs.append((next_id, diff))

    def __repr__(self):
        return pprint.pformat(vars(self))

    @property
    def last_change_id(self):
        return self.diffs[-1][0] if self.diffs else self.first_change_id

    def diffs_since_change_id(self, since_change_id):
        """
        return a dict describing the changesets that
        have arrived since since_change_id (inclusive)
        """
        if since_change_id > self.last_change_id:
            return { "last_change_id": self.last_change_id, }

        logger.debug("Since change id: %r, First change id: %r, Last change id: %r",
                since_change_id, self.first_change_id, self.last_change_id)


        if since_change_id is None or since_change_id <= self.first_change_id:
            logger.debug("returning init_html") 
            return {
                "init_html": self.init_html,
                "diffs": [i for (change_id, s) in self.diffs for i in s], # flatten
                "last_change_id": self.last_change_id,
            }
        else:
            # Find the starting position of the changesets to return
            for pos, (change_id, d) in enumerate(self.diffs):
                if change_id >= since_change_id:
                    break
            diffs = self.diffs[pos:]
            logger.debug("getting diffs since [%s:] (len is %s)",
                    since_change_id, len(diffs))
            return {
                "diffs": [i for (change_id, s) in self.diffs for i in s], # flatten
                "last_change_id": self.last_change_id,
            }

def _get_html_cleaner():
    cleaner = lxml.html.clean.Cleaner()
    cleaner.frames = False
    cleaner.links = False
    cleaner.forms = False
    cleaner.style = False
    cleaner.page_structure = False
    cleaner.scripts = True
    cleaner.embedded = False
    cleaner.safe_attrs_only = False

    # If True, the cleaner will wipe out <link> elements
    cleaner.javascript = False
    return cleaner

def sanitise_document(html):
    """
    Strip out nasties such as <meta>, <script> and other useless bits of
    information.

    NOTE: The sanitising process needs to work in agreement with the javascript function
    MirrorDom.Util.should_ignore_node
    """
    #html_tree = lxml.html.soupparser.fromstring(html)

    # This converts into a well formed html document 
    parser = lxml.html.html5parser.HTMLParser(namespaceHTMLElements=False)
    html_tree = lxml.html.html5parser.fromstring(html, parser=parser)

    #cleaner(html_tree)

    temp = lxml.html.tostring(html_tree)
    final_html_tree = lxml.html.fromstring(temp)
    cleaner = _get_html_cleaner()
    #import rpdb2
    #rpdb2.start_embedded_debugger("hello")
    cleaner(final_html_tree)

    # Find iframes and strip src
    for iframe in final_html_tree.iter('iframe'):
        try:
            iframe.attrib.pop("src")
        except KeyError:
            pass

    return lxml.etree.tostring(final_html_tree)

def create_storage():
    """
    Create a state storage object. Right now this is just a dictionary but
    this could always change...

    This storage corresponds to one session only.
    """
    #return {'changelogs': {},
    #        'iframes':    []}
    return Session()


def handle_send_update(storage, messages):
    """ Main entry point for handling all RPC requests

    Message format:
        [ <frame name>,
          <update type>,
          <update data>,
        ]

    Frame name: 'm' for main window, otherwise comma separated path for iframes
    """
    for frame_path, update_type, update_data in messages:
        frame_id = tuple(frame_path)
        #logger.debug("Got message %s:%s = %s", frame_id, update_type, update_data)
        globals()['handle_send_' + update_type](storage, frame_id, **update_data)

def handle_send_new_instance(storage, frame_id, html, props, url=None, iframes=None):
    """
    Handles a new page loading or starting a new session

    @param html         HTML dump (unsanitised)
    @param props        List of property diffs
    @param url          URL of the new page
    @param iframes      Paths to child iframes
    """
    html = sanitise_document(html)
    storage.init_html(frame_id, html, props)
    storage.remove_frame_children(frame_id)
    #storage.add_frames(iframes)

def handle_send_new_page(storage, frame_id, html, props, url, iframes):
    """
    Handles a new page loading or starting a new session

    @param html         HTML dump (unsanitised)
    @param props        List of property diffs
    @param url          URL of the new page
    @param iframes      Paths to child iframes
    """
    html = sanitise_document(html)
    storage.init_html(frame_id, html, props)
    storage.remove_frame_children(frame_id)

def handle_send_diffs(storage, frame_id, diffs):
    """
    called from the client to add a change (i.e. something changed
    in the dom in that window)

    returns the next last_change_id
    """
    logger.debug("add_diff: %s, %s", frame_id, pprint.pformat(diffs))
    try:
        storage.add_diff(frame_id, diffs)
    except KeyError:
        logger.warn("Couldn't find frame %s" % (frame_id))
    return storage.last_change_id

def handle_get_update(storage, change_id=None):
    if change_id:
        change_id = int(change_id)
    changesets = [(frame_path, c.diffs_since_change_id(change_id)) \
            for frame_path, c in storage.changelogs.iteritems()]

    # Changesets MUST be applied in order of top frames to bottom frames since
    # the top frames need to contain the lower frame elements.  We can sort by
    # frame path length to work this out. We'll sort the changesets and then
    # transmit.
    changesets.sort(key = lambda x: len(x[0]))
    return {"changesets": changesets,
            "last_change_id": storage.last_change_id}

