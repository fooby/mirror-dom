"""
Testing the javascript functionality of the mirrordom library
"""

import json
import os
import time

import nose.plugins.skip
from selenium.common.exceptions import NoSuchElementException

import util

def setupModule():
    util.start_webserver()

def teardownModule():
    util.stop_webserver()

class TestFirefox(util.TestBrowserBase):

    HTML_FILE = "test_javascript.html"

    @classmethod
    def _create_webdriver(cls):
        return util.get_debug_firefox_webdriver()

    def test_webdriver_works(self):
        """ Test 0: Sometimes this is the real problem """
        self.init_webdriver()
        value = self.webdriver.execute_script("return 1")

class TestIE(TestFirefox):
    @classmethod
    def _create_webdriver(cls):
        return util.get_debug_ie_webdriver()

class TestChrome(TestFirefox):
    @classmethod
    def _create_webdriver(cls):
        return util.get_debug_chrome_webdriver()
