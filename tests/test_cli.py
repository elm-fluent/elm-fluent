#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `elm_fluent` package."""


import unittest

import mock
from click.testing import CliRunner
from fs.memoryfs import MemoryFS

from elm_fluent import cli

from .utils import dedent_ftl


class TestHelp(unittest.TestCase):
    def test_help(self):
        runner = CliRunner()
        help_result = runner.invoke(cli.main, ["--help"])
        assert help_result.exit_code == 0
        assert "Show this message and exit." in help_result.output


class StandardLayoutMixin(object):
    locales = ["en"]

    def setUp(self):
        super(StandardLayoutMixin, self).setUp()
        self.runner = CliRunner()
        self.locales_fs = MemoryFS()
        self.output_fs = MemoryFS()

        def get_locales_fs(path):
            return self.locales_fs.opendir(path)

        def get_output_fs(path):
            return self.output_fs.opendir(path)

        self.locales_fs_patcher = mock.patch('elm_fluent.cli.get_locales_fs',
                                             new=get_locales_fs)
        self.locales_fs_patcher.start()

        self.output_fs_patcher = mock.patch('elm_fluent.cli.get_output_fs',
                                            new=get_output_fs)
        self.output_fs_patcher.start()

        self.setup_fs()

    def tearDown(self):
        self.locales_fs_patcher.stop()
        super(StandardLayoutMixin, self).tearDown()

    def setup_fs(self):
        sub = self.locales_fs.makedir("locales")
        for l in self.locales:
            sub.makedir(l)

    def write_ftl_file(self, path, contents):
        self.locales_fs.writetext(path, dedent_ftl(contents))

    def run_main(self, args=None):
        return self.runner.invoke(cli.main,
                                  args=[] if args is None else args)


class TestErrors(StandardLayoutMixin, unittest.TestCase):

    def test_type_error_conflicting_functions(self):
        self.write_ftl_file("locales/en/foo.ftl", """
            foo =
                 line 1 has { NUMBER($arg) }
                 but line 2 has { DATETIME($arg) }
        """)
        result = self.run_main()
        self.assertEqual(result.output.strip(), """
Errors:

locales/en/foo.ftl:3:23: In message 'foo': FluentDate is not compatible with FluentNumber number
  Explanation: incompatible types were detected for message argument '$arg'
  Compare the following:
    locales/en/foo.ftl:2:19: Inferred type: FluentNumber number
    locales/en/foo.ftl:3:23: Inferred type: FluentDate
Aborted!
""".strip())
