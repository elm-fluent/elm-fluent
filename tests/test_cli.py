#!/usr/bin/env python
# -*- coding: utf-8 -*-
import unittest

import mock
from click.testing import CliRunner
from fs.memoryfs import MemoryFS

from elm_fluent import cli

from .utils import dedent_ftl

dedent_source = dedent_ftl


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

    def get_all_files(self, fs):
        return {p: fs.readtext(p) for p in fs.walk.files()}

    def assertFileSystemEquals(self, fs, files):
        all_files = self.get_all_files(fs)
        self.assertEqual({p: c.rstrip() for p, c in all_files.items()},
                         {p: c.rstrip() for p, c in files.items()})

    def run_main(self, args=None):
        return self.runner.invoke(cli.main,
                                  args=[] if args is None else args)


class TestCreate(StandardLayoutMixin, unittest.TestCase):
    maxDiff = None

    def test_simple(self):
        self.write_ftl_file("locales/en/foo.ftl", """
            foo = Foo
        """)
        result = self.run_main()
        self.assertEqual(result.output.strip(), "")
        self.assertFileSystemEquals(self.output_fs, {
            '/Ftl/EN/Foo.elm': dedent_source('''
            module Ftl.EN.Foo exposing (foo)

            import Intl.Locale as Locale

            foo : Locale.Locale -> a -> String
            foo locale_ args_ =
                "Foo"
            '''),
            '/Ftl/Translations/Foo.elm': dedent_source('''
            module Ftl.Translations.Foo exposing (foo)

            import Ftl.EN.Foo as EN
            import Intl.Locale as Locale

            foo : Locale.Locale -> a -> String
            foo locale_ args_ =
                case String.toLower (Locale.toLanguageTag locale_) of
                    "en" ->
                        EN.foo locale_ args_
                    _ ->
                        EN.foo locale_ args_
            '''),
        })


class TestErrors(StandardLayoutMixin, unittest.TestCase):

    locales = ["en", "tr"]
    maxDiff = None

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
        self.assertFileSystemEquals(self.output_fs, {})

    def test_incompatible_types_between_messages(self):
        # Inferred type of $items is for `you-have` is string, but number for `we-have`
        self.write_ftl_file("locales/en/foo.ftl", """
        you-have = you have { $items }

        we-have = I have { NUMBER($items) } and { you-have }
        """)
        result = self.run_main()
        assert result.output.strip() == """
Errors:

locales/en/foo.ftl:3:43: In message 'we-have': String is not compatible with FluentNumber number
  Explanation: incompatible types were detected for message argument '$items'
  Compare the following:
    locales/en/foo.ftl:3:20: Inferred type: FluentNumber number
    locales/en/foo.ftl:1:21: Inferred type: String

  Hint: You may need to use NUMBER() or DATETIME() builtins to force the correct type
Aborted!
""".strip()

    def test_number_inference_from_selector(self):
        # Really here to check that we are getting accurate line/column numbers
        # for this case.
        self.write_ftl_file("locales/en/foo.ftl", """
        foo = You have { $count ->
             [0]     zero items
            *[other] some items
          }, on { DATETIME($count) }
        """)
        result = self.run_main()
        assert result.output.strip() == """
Errors:

locales/en/foo.ftl:4:11: In message 'foo': FluentDate is not compatible with FluentNumber number
  Explanation: incompatible types were detected for message argument '$count'
  Compare the following:
    locales/en/foo.ftl:2:6: Inferred type: FluentNumber number
    locales/en/foo.ftl:4:11: Inferred type: FluentDate
Aborted!
""".strip()

    def test_type_errors_conflicting_across_files(self):
        self.write_ftl_file("locales/en/foo.ftl", """
            foo = message with number { NUMBER($arg) }
        """)
        self.write_ftl_file("locales/tr/foo.ftl", """
            foo = message with date { DATETIME($arg) }
        """)
        result = self.run_main()
        self.assertEqual(result.output.strip(), """
Errors:

While trying to compile master 'foo' function:
  FluentDate is not compatible with FluentNumber number
  Explanation: incompatible types were detected for message argument '$arg'
  Compare the following:
    locales/en/foo.ftl:1:29: Inferred type: FluentNumber number
    locales/tr/foo.ftl:1:27: Inferred type: FluentDate
Aborted!
        """.strip())

    def test_multiple_type_errors_different_files(self):
        self.write_ftl_file("locales/en/foo.ftl", """
            foo = message with number { NUMBER($arg) }
        """)
        self.write_ftl_file("locales/tr/foo.ftl", """
            foo = message with date { DATETIME($arg) }
        """)
        self.write_ftl_file("locales/en/bar.ftl", """
            valid = Valid
            bar = message with { syntax error
        """)
        self.write_ftl_file("locales/tr/bar.ftl", """
            bar = message with internal conflict { DATETIME($arg) } { NUMBER($arg) }
        """)
        result = self.run_main()
        self.assertEqual(result.output.strip(), """
Errors:

locales/en/bar.ftl:2:1: Junk found: Expected token: "}"
locales/tr/bar.ftl:1:59: In message 'bar': FluentNumber number is not compatible with FluentDate
  Explanation: incompatible types were detected for message argument '$arg'
  Compare the following:
    locales/tr/bar.ftl:1:40: Inferred type: FluentDate
    locales/tr/bar.ftl:1:59: Inferred type: FluentNumber number
Locale 'en' - Message 'bar' missing
Locale 'tr' - Message 'valid' missing
While trying to compile master 'foo' function:
  FluentDate is not compatible with FluentNumber number
  Explanation: incompatible types were detected for message argument '$arg'
  Compare the following:
    locales/en/foo.ftl:1:29: Inferred type: FluentNumber number
    locales/tr/foo.ftl:1:27: Inferred type: FluentDate
Aborted!
        """.strip())


class TestFileSelection(StandardLayoutMixin, unittest.TestCase):

    def setUp(self):
        super(TestFileSelection, self).setUp()
        self.write_ftl_file("locales/en/foo.ftl", """
            foo = Foo
        """)
        self.write_ftl_file("locales/en/error.ftl", """
            error =  { -not-a-term }
        """)

    def test_include_default(self):
        """
        Test that by default all files get included
        """
        result = self.run_main()
        self.assertEqual(result.exit_code, 1)
        self.assertFileSystemEquals(self.output_fs, {})
        self.assertIn('Unknown term: -not-a-term', result.output)

    def test_include_glob(self):
        result = self.run_main(['--include', '**/foo.ftl'])
        self.assertEqual(result.output.strip(), '')
        self.assertEqual(sorted(self.get_all_files(self.output_fs).keys()),
                         ['/Ftl/EN/Foo.elm',
                          '/Ftl/Translations/Foo.elm'
                          ])
        self.assertEqual(result.exit_code, 0)
