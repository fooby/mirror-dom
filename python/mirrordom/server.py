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

class Changelog(object):
    def __init__(self, init_html, first_change_id):
        self.init_html = init_html
        self.diffs = []
        self.first_change_id = first_change_id
        self.last_updated = time.time()

    def add_diff(self, diff):
        self.diffs.append(diff)
        self.last_updated = time.time()

    @property
    def last_change_id(self):
        return self.first_change_id + len(self.diffs)

    def diff_since_change_id(self, since_change_id):
        """
        return a dict describing the changesets that
        have arrived since since_change_id (inclusive)
        """

        logger.debug("Since change id: %s, First change id: %s",
                since_change_id, self.first_change_id)

        if since_change_id is None or since_change_id <= self.first_change_id:
            logger.debug("returning init_html") 
            return {
                "init_html": self.init_html,
                "diffs": [i for s in self.diffs for i in s], # flatten
                "last_updated": self.last_updated,
                "last_change_id": self.first_change_id + len(self.diffs)
            }
        else:
            logger.debug("getting diffs [%s:] (len is %s)", since_change_id - 
                    self.first_change_id - 1, len(self.diffs))
            diffs = self.diffs[since_change_id - self.first_change_id - 1:]
            return {
                "diffs": [i for s in diffs for i in s], # flatten
                "last_updated": self.last_updated,
                "last_change_id": self.first_change_id + len(self.diffs) 
            }

def _get_html_cleaner():
    cleaner = lxml.html.clean.Cleaner()
    cleaner.frames = False
    cleaner.forms = False
    cleaner.page_structure = False
    #cleaner.style = False
    return cleaner

def sanitise_document(html):
    """
    Strip out nasties such as <meta>, <script> and other useless bits of
    information.
    """
    #html_tree = lxml.html.soupparser.fromstring(html)

    # This converts into a well formed html document 
    parser = lxml.html.html5parser.HTMLParser(namespaceHTMLElements=False)
    html_tree = lxml.html.html5parser.fromstring(html, parser=parser)

    #cleaner(html_tree)

    temp = lxml.html.tostring(html_tree)
    final_html_tree = lxml.html.fromstring(temp)
    cleaner = _get_html_cleaner()
    cleaner(final_html_tree)
    return lxml.etree.tostring(final_html_tree)

def create_storage():
    """
    Create a state storage object. Right now this is just a dictionary but
    this could always change...
    """
    return {}

def handle_new_window(storage, html, url):
    """
    called by the client to create a new sharing session in a new window. we
    individually track each window the client has open in session local storage.

    returns a window id which the window should use for subsequent updates

    :param html:    Yeah, this is no longer a string. It's something weird
                    now!
    """

    #window_id = str(uuid.uuid1())
    #storage["window-%s" % window_id] = Changelog(html, 0)
    #logger.debug("new_window: %s", window_id)

    # Ayup, we're going to clean nasties out of the HTML
    html = sanitise_document(html)
    window_id = "lol"
    storage["window-%s" % window_id] = Changelog(html, 0)
    return window_id

def handle_reset(storage, window_id, html, url):
    """
    called by the client to reset the changelog with a full html snapshot

    this might be because the client navigated to a new page, or because
    the number of changesets accumulated above a certain threshold, after
    which we reset the changelog

    returns the change_id of the new changelog created
    """

    logger.debug("handle_reset: %s", window_id)

    try:
        previous_changelog = storage["window-%s" % window_id]
    except KeyError:
        logger.warn("couldn't find window %s" % window_id)
        # session died - maybe the server restarted
        return None
    
    # continue the sequence of change ids
    first_change_id = previous_changelog.last_change_id + 1
    
    logger.debug("New first change id: %s", first_change_id)

    html = sanitise_document(html)
    # overwrite previous changelog
    storage["window-%s" % window_id] = Changelog(html, first_change_id)

    return first_change_id

def handle_add_diff(storage, window_id, diff):
    """
    called from the client to add a change (i.e. something changed
    in the dom in that window)

    returns the next last_change_id for that window
    """

    logger.debug("add_diff: %s, %s", window_id, pprint.pformat(diff))

    try:
        cl = storage["window-%s" % window_id]
    except KeyError:
        logger.exception("couldn't find window %s" % window_id)
        raise
    
    cl.add_diff(diff)
    return cl.last_change_id
    
def handle_get_update(storage, change_ids):
    """
    called from the viewer to request changes.
    returns a dictionary { window_id -> diffs }
    """
    #change_ids = json.loads(change_ids)

    logger.debug("get_update: %s", change_ids)

    return {
        window_id : cl.diff_since_change_id(change_ids.get(window_id))
        for window_id, cl in storage.items()
    }


