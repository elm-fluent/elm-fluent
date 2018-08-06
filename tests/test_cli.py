#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `elm_fluent` package."""


import unittest

from click.testing import CliRunner

from elm_fluent import cli


class TestCli(unittest.TestCase):
    def test_help(self):
        runner = CliRunner()
        help_result = runner.invoke(cli.main, ["--help"])
        assert help_result.exit_code == 0
        assert "Show this message and exit." in help_result.output
