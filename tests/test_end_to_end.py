# -*- coding: utf-8 -*-

from __future__ import absolute_import, unicode_literals

import os
import subprocess
import sys
import time
import unittest

from click.testing import CliRunner
from pyvirtualdisplay import Display
from selenium import webdriver

from elm_fluent import cli

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_PROJECT = os.path.join(THIS_DIR, "test_project")


def noisy_check_call(cmd):
    sys.stdout.write("\n" + " ".join(cmd) + "\n")
    subprocess.check_call(cmd)


@unittest.skipIf(os.environ.get("TEST_FAST_RUN", "0") == "1", "Skipping slow tests")
class TestEndToEnd(unittest.TestCase):

    visible = os.environ.get("TEST_SHOW_BROWSER", "0") == "1"

    @classmethod
    def setUpClass(cls):
        super(TestEndToEnd, cls).setUpClass()
        if not cls.visible:
            display_args = {"visible": False}
            cls.__display = Display(**display_args)
            cls.__display.start()
        cls.browser = webdriver.Firefox()

    @classmethod
    def tearDownClass(cls):
        cls.browser.quit()
        if not cls.visible:
            cls.__display.stop()
        super(TestEndToEnd, cls).tearDownClass()

    def test_everything(self):
        os.chdir(TEST_PROJECT)
        # Run in process, for the sake of coverage testng
        runner = CliRunner()
        result = runner.invoke(
            cli.main,
            ["--when-missing=fallback", "--no-bdi-isolating"],
            catch_exceptions=False,
        )
        self.assertEqual(result.exit_code, 0)

        # Check the script in installed as expected
        noisy_check_call(["ftl2elm", "--when-missing=fallback", "--no-bdi-isolating"])

        noisy_check_call(["elm-install"])
        elm_make_cmd = ["elm-make", "--yes", "Main.elm", "--output=main.js"]
        if "TRAVIS_BUILD_DIR" in os.environ:
            # See https://github.com/elm/compiler/issues/1473#issuecomment-245704142
            elm_make_cmd = [
                os.path.join(
                    os.environ["TRAVIS_BUILD_DIR"], "sysconfcpus", "bin", "sysconfcpus"
                ),
                "-n",
                "2",
            ] + elm_make_cmd

        noisy_check_call(elm_make_cmd)
        self.browser.get("file://{0}/main.html".format(TEST_PROJECT))
        page_source = self.browser.page_source

        # Static tests
        self.assertIn("This is the title", page_source)
        self.assertIn("This is a test page for elm-fluent", page_source)

        # Number
        self.assertIn("There are 12,345 things", page_source)
        self.assertIn("There are 123,456.7 things", page_source)
        self.assertIn("There are 4,567.8 things", page_source)
        self.assertIn("There are 7890 things", page_source)
        self.assertIn("You have 6,543.21 US dollars in your bank.", page_source)

        # Select
        self.assertIn("You've clicked 0 times", page_source)
        e = self.browser.find_element_by_css_selector("button#increment")
        e.click()
        time.sleep(0.1)
        page_source = self.browser.page_source
        self.assertIn("You've clicked once", page_source)
        e.click()
        time.sleep(0.1)
        page_source = self.browser.page_source
        self.assertIn("You've clicked 2 times", page_source)

        # Select with mixed numerics
        self.assertIn("You have no new messages", page_source)
        self.assertIn("You have one new message", page_source)
        self.assertIn("You have 2 new messages", page_source)

        # Dates:
        self.assertIn("January 1, 1970 AD, 01:02:03", page_source)

        # Html:
        self.assertIn("Some text with this &amp; that", page_source)
        self.assertIn(
            "Some <b>bold text</b> and some <b>bold <i>and italic</i></b> text.",
            page_source,
        )
        self.assertIn('Some <span class="foo">highlighted text</span>.', page_source)
        self.assertIn("Hello <b>Mary</b>!", page_source)
        self.assertIn("Hello <b>Maria</b>! You came back", page_source)
        self.assertIn('<b foo="Hello">Some text</b>', page_source)

        # Dynamic HTML:
        self.assertIn("You haven't moved yet", page_source)
        self.assertIn(
            '<a data-left="" class="direction" href="#">left</a>', page_source
        )
        self.assertIn(
            '<a data-right="" class="direction" href="#">right</a>', page_source
        )

        e = self.browser.find_element_by_css_selector("a[data-left]")
        e.click()
        time.sleep(0.1)
        page_source = self.browser.page_source
        self.assertIn("You moved left", page_source)

        e = self.browser.find_element_by_css_selector("a[data-right]")
        e.click()
        time.sleep(0.1)
        page_source = self.browser.page_source
        self.assertIn("You moved right", page_source)
