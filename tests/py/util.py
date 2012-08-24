import os
import urllib

# HTML files
HTML_DIRECTORY = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "html"))

def get_html_path(f):
    """
    :param f:   Name of HTML test file in the tests\html directory (e.g. "test_diff.html")
    :returns    Absolute path of html test file
    """
    path = os.path.join(HTML_DIRECTORY, f)
    assert os.path.isfile(path)
    return path

def get_html_url(f):
    path = get_html_path(f)
    uri = "file:" + urllib.pathname2url(path)
    return uri
