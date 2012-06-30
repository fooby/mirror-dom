
__version__  = '$Revision: 168945 $'

from xpt.clientaccess import cautil
import time
import logging
import threading
from xpt.session.util import LocalStorage
from xlib.randomiser import getRandomiser
import pprint

logger = logging.getLogger("engage")

changelogs_lock = threading.RLock()

class LocalStorageWithClientId(LocalStorage):
    """
    Overrides LocalStorage so we can access the cache by client id
    from adviser sessions
    """
    def __init__(self, name=None):
        super(LocalStorageWithClientId, self).__init__(name)

        # client_id -> session_id
        self.__client_to_session = {}

    def get(self, session):
        """
        Override LocalStorage
        """
        sessionid = session.getSessionId()

        # going to create? (take that, private!)
        if sessionid not in self._LocalStorage__storage:
            # stash mapping
            castate = cautil.getState()            
            self.__client_to_session[castate.getEntityId()] = sessionid

        return super(LocalStorageWithClientId, self).get(session)

    def get_by_client_id(self, client_id):        
        return self._LocalStorage__storage[self.__client_to_session[client_id]]

# map client_id -> { window_id: Changelog }; uses LocalStorage
# so it'll get cleaned up when the client session terminates
__changelogs = LocalStorageWithClientId()

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

        if since_change_id is None or since_change_id < self.first_change_id:
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


def rpc_new_window(request, html):
    """
    called by the client to create a new sharing session in a new window. we
    individually track each window the client has open in session local storage.

    returns a window id which the window should use for subsequent updates
    """

    castate = cautil.getState()

    lso = __changelogs.get(castate.session)
    window_id = getRandomiser().getHexString(8)
    lso["window-%s" % window_id] = Changelog(html, 0)

    logger.debug("new_window: %s", window_id)

    return window_id
                

def rpc_reset(request, window_id, html):
    """
    called by the client to reset the changelog with a full html snapshot

    this might be because the client navigated to a new page, or because
    the number of changesets accumulated above a certain threshold, after
    which we reset the changelog

    returns the change_id of the new changelog created
    """
    castate = cautil.getState()

    logger.debug("rpc_reset: %s", window_id)

    try:
        previous_changelog = __changelogs.get(
                castate.session)["window-%s" % window_id]
    except KeyError:
        logger.exception("couldn't find window %s" % window_id)
        raise
    
    # continue the sequence of change ids
    first_change_id = previous_changelog.last_change_id + 1

    # overwrite previous changelog
    __changelogs.get(castate.session)["window-%s" % window_id] = \
        Changelog(html, first_change_id)

    return first_change_id


def rpc_add_diff(request, window_id, diff):
    """
    called from the client to add a change (i.e. something changed
    in the dom in that window)

    returns the next last_change_id for that window
    """

    castate = cautil.getState()

    logger.debug("add_diff: %s, %s", window_id, pprint.pformat(diff))

    try:
        cl = __changelogs.get(castate.session)["window-%s" % window_id]
    except KeyError:
        logger.exception("couldn't find window %s" % window_id)
        raise
    
    cl.add_diff(diff)

    return cl.last_change_id

    
def rpc_get_update(request, client_id, at_change_ids):
    """
    called from the viewer to request changes.
    returns a dictionary { window_id -> diffs }
    """
    logger.debug("get_update: %s: %s", client_id, at_change_ids)

    # TODO: visibility rules? caps?

    try:
        lso = __changelogs.get_by_client_id(client_id)
    except KeyError:
        logger.debug("no client session in get_update")
        # no client session
        return None

    result = {}
    for window_id, cl in lso.items():
        result[window_id] = cl.diff_since_change_id(at_change_ids.get(window_id))

    return result
