import time
import logging
import pprint
import uuid

from . import sanitise

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

    def init_html(self, frame_id, html, props, url=None):
        next_id = self.get_next_change_id()
        c = Changelog(html, next_id, url)
        c.add_diff_set(next_id, props)
        self.changelogs[frame_id] = c

    def add_diff(self, frame_id, diffs):
        next_id = self.get_next_change_id()
        # Raises KeyError if frame_id not found
        c = self.changelogs[frame_id]
        c.add_diff_set(next_id, diffs)

    def update_frames(self, frame_paths):
        frame_paths = set(tuple(f) for f in frame_paths)
        removed = set(self.changelogs) - frame_paths
        if removed:
            frame_str = ", ".join('(' + ",".join(str(x)) + ')' for x in removed)
            logger.debug("We've lost frames: %s", frame_str)
        for r in removed:
            del self.changelogs[r]

    def remove_frame_children(self, frame_path):
        """
        TODO: This may no longer be needed now that we're sending a big list of
        iframe paths
        """
        for f in self.changelogs.keys():
            if len(f) <= len(frame_path):
                continue
            if frame_path == f[:len(frame_path)]:
                logger.debug("Removing frame child %s as parent %s was restarted",
                        f, frame_path)
                del self.changelogs[f]


class Changelog(object):
    def __init__(self, init_html, first_change_id, url=None):
        self.init_html = init_html
        self.diffs = []
        self.first_change_id = first_change_id
        self.url = url

    def add_diff_set(self, next_id, diff):
        """
        :param diff:    List of diffs
        """
        self.diffs.append((next_id, diff))
        logger.debug("Adding %s diffs to change id %s", len(diff), next_id)

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
                "url": self.url,
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
                "diffs": [i for (change_id, s) in diffs for i in s], # flatten
                "last_change_id": self.last_change_id,
            }

def create_storage():
    """
    Create a state storage object. Right now this is just a dictionary but
    this could always change...

    This storage corresponds to one session only.
    """
    #return {'changelogs': {},
    #        'iframes':    []}
    return Session()


def handle_send_update(storage, messages, iframes):
    """ Main entry point for handling all update RPC requests

    This RPC call handles and dispatches multiple messages.

    Message format:
        [ <frame path>,
          <update type>,
          <update data>,
        ]

    Frame path: List of path elements:
        - 'm' for main window
        - 'i' for iframe descent
        - integer for node child offset

    Iframes: List of ALL iframes (needed to remove "expired" iframes)
    """
    for frame_path, update_type, update_data in messages:
        frame_id = tuple(frame_path)
        #logger.debug("Got message %s:%s = %s", frame_id, update_type, update_data)
        globals()['handle_send_' + update_type](storage, frame_id, **update_data)

    storage.update_frames(iframes)

def handle_send_new_instance(storage, frame_id, html, props, url=None, iframes=None):
    """
    Handles a new page loading or starting a new session

    :@param html:        HTML dump (unsanitised)
    :@param props:       List of property diffs
    :@param url:         URL of the new page
    :@param iframes:     Paths to child iframes
    """
    html = sanitise.sanitise_html(html)
    storage.init_html(frame_id, html, props, url=url)
    storage.remove_frame_children(frame_id)
    #storage.add_frames(iframes)

def handle_send_new_page(storage, frame_id, html, props, url, iframes):
    """
    Handles a new page loading or starting a new session

    :param html:        HTML dump (unsanitised)
    :param props:       List of property diffs
    :param url:         URL of the new page
    :param iframes:     Paths to child iframes
    """
    html = sanitise.sanitise_html(html)
    storage.init_html(frame_id, html, props, url=url)
    storage.remove_frame_children(frame_id)

def handle_send_diffs(storage, frame_id, diffs):
    """
    called from the client to add a change (i.e. something changed
    in the dom in that window)

    returns the next last_change_id
    """
    logger.debug("add_diff: %s, %s", frame_id, pprint.pformat(diffs))
    diffs = sanitise.sanitise_diffs(diffs)
    try:
        storage.add_diff(frame_id, diffs)
    except KeyError:
        logger.warn("Couldn't find frame %s" % (frame_id))
    return storage.last_change_id

def handle_get_update(storage, change_id=None, init_html_required=False):
    """
    :param init_html_required:      Only return a response if the main frame
                                    has been loaded with a new page
    """
    if change_id:
        change_id = int(change_id)

    # Viewer is in error recovery mode - don't send any new changes unless
    # the main frame has been refreshed.
    if init_html_required:
        has_init_html = False
        try:
            main_changeset = storage.changelogs[('m',)]
        except KeyError:
            pass
        else:
            if main_changeset.first_change_id >= change_id:
                has_init_html = True
        if not has_init_html:
            return {"last_change_id": storage.last_change_id}

    changesets = [(frame_path, c.diffs_since_change_id(change_id)) \
            for frame_path, c in storage.changelogs.iteritems()]

    # Changesets MUST be applied in order of top frames to bottom frames since
    # the top frames need to contain the lower frame elements.  We can sort by
    # frame path length to work this out. We'll sort the changesets and then
    # transmit.
    changesets.sort(key = lambda x: len(x[0]))
    return {"changesets": changesets,
            "last_change_id": storage.last_change_id}

