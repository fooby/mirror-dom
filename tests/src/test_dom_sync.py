"""
Tests
"""
import os
import difflib

from selenium import webdriver
from nose.plugins.attrib import attr

import util

_driver = None
def setupModule(self):
    global _driver
    _driver = webdriver.Firefox()

def teardownModule(self):
    global driver
    _driver.quit()

class TestDomSync(object):

    HTML_FILE = "test_diff.html"

    def setUp(self):
        # Refresh the test page for a fresh start
        self.driver = self._get_webdriver()
        url = util.get_html_url(self.HTML_FILE)
        self.driver.get(url)

    def _get_webdriver(self):
        #driver = webdriver.Firefox()
        assert _driver
        return _driver

    def _compare_iframes(self):
        """
        :param iframe1:     Javascript reference to source iframe
        :param iframe2:     Javascript reference to dest iframe
        """
        src = self.driver.execute_script("return get_src_html()");
        dest = self.driver.execute_script("return get_dest_html()");
        #print "Html 1: %s" % (src)
        #print "Html 2: %s" % (dest)

        diff = difflib.context_diff(src, dest)
        print "\n".join(diff)

        return src == dest

    def test_html_works(self):
        """
        Pre test
        """
        src = self.driver.execute_script("return get_src_html()")
        assert len(src) > 0

    def test_init_html(self):
        self.driver.execute_script("window.test_initial_tree()")
        assert self._compare_iframes()

    def test_add_table_row(self):
        self.driver.execute_script("window.test_initial_tree()")
        self.driver.execute_script("window.test_add_table_row()")
        assert self._compare_iframes()

    def test_remove_table_row(self):
        self.driver.execute_script("window.test_initial_tree()")
        self.driver.execute_script("window.test_remove_table_row()")
        assert self._compare_iframes()

    def test_change_text(self):
        self.driver.execute_script("window.test_initial_tree()")
        self.driver.execute_script("window.test_change_text_input()")
        assert self._compare_iframes()

    def test_change_styles(self):
        self.driver.execute_script("window.test_initial_tree()")
        self.driver.execute_script("window.test_change_styles()")
        assert self._compare_iframes()
