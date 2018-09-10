# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

import unittest

from fluent.syntax import ast

from elm_fluent import exceptions
from elm_fluent.compiler import (
    compile_messages,
    message_function_name_for_msg_id,
    span_to_position,
)
from elm_fluent.stubs import defaults as dtypes, fluent

from .test_codegen import normalize_elm
from .utils import dedent_ftl


def compile_messages_to_elm(
    source,
    locale,
    module_name=None,
    include_module_line=False,
    include_imports=False,
    use_isolating=False,
    dynamic_html_attributes=True,
):
    module, errors, _ = compile_messages(
        dedent_ftl(source),
        locale,
        module_name=module_name,
        use_isolating=use_isolating,
        dynamic_html_attributes=dynamic_html_attributes,
    )
    return (
        module.as_source_code(
            include_module_line=include_module_line, include_imports=include_imports
        ),
        errors,
    )


class TestCompiler(unittest.TestCase):
    locale = "en-US"

    maxDiff = None

    def assertCodeEqual(self, code1, code2):
        self.assertEqual(normalize_elm(code2), normalize_elm(code1))

    def test_message_function_name_for_msg_id(self):
        self.assertEqual(message_function_name_for_msg_id("hello"), "hello")
        self.assertEqual(message_function_name_for_msg_id("hello-there"), "helloThere")
        self.assertEqual(message_function_name_for_msg_id("helloThere"), "helloThere")
        self.assertEqual(message_function_name_for_msg_id("hello.foo"), "hello_foo")
        self.assertEqual(
            message_function_name_for_msg_id("hello-html.foo"), "helloHtml_foo"
        )

    def test_single_string_literal(self):
        code, errs = compile_messages_to_elm(
            """
            foo = Foo ☺
        """,
            self.locale,
        )
        self.assertCodeEqual(
            code,
            """
            foo : Locale.Locale -> a -> String
            foo locale_ args_ =
                "Foo ☺"
        """,
        )
        self.assertEqual(errs, [])

    def test_module_line(self):
        code, errs = compile_messages_to_elm(
            """
            foo = Foo
        """,
            self.locale,
            module_name="Foo.Bar",
            include_module_line=True,
        )
        self.assertCodeEqual(
            code,
            """
            module Foo.Bar exposing (foo)

            foo : Locale.Locale -> a -> String
            foo locale_ args_ =
                "Foo"
        """,
        )
        self.assertEqual(errs, [])

    def test_string_literal_in_placeable(self):
        code, errs = compile_messages_to_elm(
            """
            foo = { "Foo" }
        """,
            self.locale,
        )
        self.assertCodeEqual(
            code,
            """
            foo : Locale.Locale -> a -> String
            foo locale_ args_ =
                "Foo"
        """,
        )
        self.assertEqual(errs, [])

    def test_number_literal(self):
        code, errs = compile_messages_to_elm(
            """
            foo = { 123 }
        """,
            self.locale,
        )
        self.assertCodeEqual(
            code,
            """
            foo : Locale.Locale -> a -> String
            foo locale_ args_ =
                NumberFormat.format (NumberFormat.fromLocale locale_) 123
        """,
        )
        self.assertEqual(errs, [])

    def test_inferred_number(self):
        # From the second instance of $count we know it is numeric,
        # so it must be treated as numeric in the first
        code, errs = compile_messages_to_elm(
            """
            foo = { $count }, { NUMBER($count) }
        """,
            self.locale,
        )
        self.assertCodeEqual(
            code,
            """
            foo : Locale.Locale -> { a | count : Fluent.FluentNumber number } -> String
            foo locale_ args_ =
                String.concat [ Fluent.formatNumber locale_ args_.count
                              , ", "
                              , Fluent.formatNumber locale_ args_.count
                              ]
        """,
        )
        self.assertEqual(errs, [])

    def test_inferred_number_from_select(self):
        code, errs = compile_messages_to_elm(
            """
            foo = { $count ->
               [one]   You have one item
              *[other] You have { $count } items
             }
        """,
            self.locale,
        )
        self.assertCodeEqual(
            code,
            """
            foo : Locale.Locale -> { a | count : Fluent.FluentNumber number } -> String
            foo locale_ args_ =
                case PluralRules.select (PluralRules.fromLocale locale_) (Fluent.numberValue args_.count) of
                    "one" ->
                        "You have one item"
                    _ ->
                        String.concat [ "You have "
                                      , Fluent.formatNumber locale_ args_.count
                                      , " items"
                                      ]
        """,
        )
        self.assertEqual(errs, [])

    def test_literal_number_in_select(self):
        code, errs = compile_messages_to_elm(
            """
            foo = { 123 ->
               [one]   You have one item
              *[other] You have more than one item
             }
        """,
            self.locale,
        )
        self.assertCodeEqual(
            code,
            """
            foo : Locale.Locale -> a -> String
            foo locale_ args_ =
                case PluralRules.select (PluralRules.fromLocale locale_) 123 of
                    "one" ->
                        "You have one item"
                    _ ->
                        "You have more than one item"
        """,
        )
        self.assertEqual(errs, [])

    def test_inferred_number_from_call(self):
        code, errs = compile_messages_to_elm(
            """
           bar = { NUMBER($count) }

           foo = { $count } - { bar }
        """,
            self.locale,
        )
        self.assertCodeEqual(
            code,
            """
            bar : Locale.Locale -> { a | count : Fluent.FluentNumber number } -> String
            bar locale_ args_ =
                Fluent.formatNumber locale_ args_.count

            foo : Locale.Locale -> { a | count : Fluent.FluentNumber number } -> String
            foo locale_ args_ =
                String.concat [ Fluent.formatNumber locale_ args_.count
                              , " - "
                              , bar locale_ args_
                              ]
        """,
        )
        self.assertEqual(errs, [])

    def test_inferred_number_from_call_reversed(self):
        code, errs = compile_messages_to_elm(
            """
            foo = { bar }

            bar = { $count } - { baz }

            baz = { NUMBER($count) }
        """,
            self.locale,
        )
        self.assertCodeEqual(
            code,
            """
            foo : Locale.Locale -> { a | count : Fluent.FluentNumber number } -> String
            foo locale_ args_ =
                bar locale_ args_

            bar : Locale.Locale -> { a | count : Fluent.FluentNumber number } -> String
            bar locale_ args_ =
                String.concat [ Fluent.formatNumber locale_ args_.count
                              , " - "
                              , baz locale_ args_
                              ]

            baz : Locale.Locale -> { a | count : Fluent.FluentNumber number } -> String
            baz locale_ args_ =
                Fluent.formatNumber locale_ args_.count
        """,
        )
        self.assertEqual(errs, [])

    def test_message_reference_plus_string_literal(self):
        code, errs = compile_messages_to_elm(
            """
            foo = Foo
            bar = X { foo }
        """,
            self.locale,
        )
        self.assertCodeEqual(
            code,
            """
            foo : Locale.Locale -> a -> String
            foo locale_ args_ =
                "Foo"

            bar : Locale.Locale -> a -> String
            bar locale_ args_ =
                String.concat [ "X "
                              , foo locale_ args_
                              ]
        """,
        )
        self.assertEqual(errs, [])

    def test_single_message_reference(self):
        code, errs = compile_messages_to_elm(
            """
            foo = Foo
            bar = { foo }
        """,
            self.locale,
        )
        self.assertCodeEqual(
            code,
            """
            foo : Locale.Locale -> a -> String
            foo locale_ args_ =
                "Foo"

            bar : Locale.Locale -> a -> String
            bar locale_ args_ =
                foo locale_ args_
        """,
        )
        self.assertEqual(errs, [])

    def test_message_attr_reference(self):
        code, errs = compile_messages_to_elm(
            """
            foo
               .attr = Foo Attr
            bar = { foo.attr }
        """,
            self.locale,
        )
        self.assertCodeEqual(
            code,
            """
            foo_attr : Locale.Locale -> a -> String
            foo_attr locale_ args_ =
                "Foo Attr"

            bar : Locale.Locale -> a -> String
            bar locale_ args_ =
                foo_attr locale_ args_
        """,
        )
        self.assertEqual(errs, [])

    def test_missing_attr_reference(self):
        code, errs = compile_messages_to_elm(
            """
            foo = Hello
               .attr = Foo Attr
            bar = { foo.baz }
        """,
            self.locale,
        )
        self.assertEqual(errs[0].error_sources[0].message_id, "bar")
        self.assertEqual(errs[0], exceptions.ReferenceError("Unknown message: foo.baz"))

    def test_single_message_reference_reversed_order(self):
        # We should cope with forward references
        code, errs = compile_messages_to_elm(
            """
            bar = { foo }
            foo = Foo
        """,
            self.locale,
        )
        self.assertCodeEqual(
            code,
            """
            bar : Locale.Locale -> a -> String
            bar locale_ args_ =
                foo locale_ args_

            foo : Locale.Locale -> a -> String
            foo locale_ args_ =
                "Foo"
        """,
        )
        self.assertEqual(errs, [])

    def test_single_message_bad_reference(self):
        code, errs = compile_messages_to_elm(
            """
            bar = { foo }
        """,
            self.locale,
        )
        self.assertIn("COMPILATION_ERROR", code)
        self.assertEqual(len(errs), 1)
        self.assertEqual(errs[0].error_sources[0].message_id, "bar")
        self.assertEqual(errs[0], exceptions.ReferenceError("Unknown message: foo"))

    def test_bad_name_keyword(self):
        code, errs = compile_messages_to_elm(
            """
            type = My String
        """,
            self.locale,
        )
        self.assertIn("COMPILATION_ERROR", code)
        self.assertEqual(len(errs), 1)
        self.assertEqual(errs[0].error_sources[0].message_id, "type")
        self.assertEqual(
            errs[0],
            exceptions.BadMessageId(
                "'type' is not allowed as a message ID because it clashes "
                "with an Elm keyword. Please choose another ID."
            ),
        )

    def test_bad_name_default_import(self):
        code, errs = compile_messages_to_elm(
            """
            max = My String
        """,
            self.locale,
        )
        self.assertIn("COMPILATION_ERROR", code)
        self.assertEqual(len(errs), 1)
        self.assertEqual(errs[0].error_sources[0].message_id, "max")
        self.assertEqual(
            errs[0],
            exceptions.BadMessageId(
                "'max' is not allowed as a message ID because it clashes "
                "with an Elm default import. Please choose another ID."
            ),
        )

    def test_bad_name_duplicate(self):
        code, errs = compile_messages_to_elm(
            """
            a-message-id = My Message

            aMessageId = Another Message
        """,
            self.locale,
        )
        self.assertIn("COMPILATION_ERROR", code)
        self.assertEqual(len(errs), 1)
        self.assertEqual(errs[0].error_sources[0].message_id, "aMessageId")
        self.assertEqual(
            errs[0],
            exceptions.BadMessageId(
                "'aMessageId' is not allowed as a message ID because it clashes "
                "with another message ID - 'a-message-id'. "
                "Please choose another ID."
            ),
        )

    def test_message_mapping_used(self):
        # Checking that we actually use message_mapping when looking up the name
        # of the message function to call.
        code, errs = compile_messages_to_elm(
            """
            a-message-id = Foo
        """,
            self.locale,
        )
        self.assertCodeEqual(
            code,
            """
            aMessageId : Locale.Locale -> a -> String
            aMessageId locale_ args_ =
                "Foo"
        """,
        )
        self.assertEqual(errs, [])

    def test_external_argument(self):
        code, errs = compile_messages_to_elm(
            """
            with-arg = Some text { $arg }
        """,
            self.locale,
        )
        self.assertCodeEqual(
            code,
            """
            withArg : Locale.Locale -> { a | arg : String } -> String
            withArg locale_ args_ =
                String.concat [ "Some text "
                              , args_.arg
                              ]
        """,
        )
        self.assertEqual(errs, [])

    def test_lone_external_argument(self):
        code, errs = compile_messages_to_elm(
            """
            with-arg = { $arg }
        """,
            self.locale,
        )
        self.assertCodeEqual(
            code,
            """
            withArg : Locale.Locale -> { a | arg : String } -> String
            withArg locale_ args_ =
                args_.arg
        """,
        )
        self.assertEqual(errs, [])

    def test_function_call(self):
        code, errs = compile_messages_to_elm(
            """
                 foo = { NUMBER(1234) }
        """,
            self.locale,
        )
        self.assertEqual(errs, [])
        self.assertCodeEqual(
            code,
            """
            foo : Locale.Locale -> a -> String
            foo locale_ args_ =
                NumberFormat.format (NumberFormat.fromLocale locale_) 1234
        """,
        )

    def test_function_call_external_arg(self):
        code, errs = compile_messages_to_elm(
            """
            foo = { NUMBER($arg) }
        """,
            self.locale,
        )
        self.assertCodeEqual(
            code,
            """
            foo : Locale.Locale -> { a | arg : Fluent.FluentNumber number } -> String
            foo locale_ args_ =
                Fluent.formatNumber locale_ args_.arg
        """,
        )
        self.assertEqual(errs, [])

    def test_NUMBER_useGrouping(self):
        code, errs = compile_messages_to_elm(
            """
            foo = { NUMBER($arg, useGrouping: 0) }
        """,
            self.locale,
        )
        self.assertCodeEqual(
            code,
            """
            foo : Locale.Locale -> { a | arg : Fluent.FluentNumber number } -> String
            foo locale_ args_ =
                let
                    initial_opts_ = Fluent.numberFormattingOptions args_.arg
                    fnum_ = Fluent.reformattedNumber { initial_opts_ | locale = locale_, useGrouping = False } args_.arg
                in
                    Fluent.formatNumber locale_ fnum_
        """,
        )
        self.assertEqual(errs, [])

    def test_NUMBER_minimumIntegerDigits(self):
        code, errs = compile_messages_to_elm(
            """
            foo = { NUMBER($arg, minimumIntegerDigits: 2) }
        """,
            self.locale,
        )
        self.assertCodeEqual(
            code,
            """
            foo : Locale.Locale -> { a | arg : Fluent.FluentNumber number } -> String
            foo locale_ args_ =
                let
                    initial_opts_ = Fluent.numberFormattingOptions args_.arg
                    fnum_ = Fluent.reformattedNumber { initial_opts_ | locale = locale_, minimumIntegerDigits = Just 2 } args_.arg
                in
                    Fluent.formatNumber locale_ fnum_
        """,
        )
        self.assertEqual(errs, [])

    def test_NUMBER_everything(self):
        code, errs = compile_messages_to_elm(
            """
            foo =
               There are { NUMBER(7890,
                                  useGrouping: 0,
                                  minimumIntegerDigits: 2,
                                  minimumFractionDigits: 3,
                                  maximumFractionDigits: 4,
                                  minimumSignificantDigits: 5,
                                  maximumSignificantDigits: 6 ) } things
        """,
            self.locale,
        )
        self.assertCodeEqual(
            code,
            """
            foo : Locale.Locale -> a -> String
            foo locale_ args_ =
                let
                    defaults_ = NumberFormat.defaults
                    fnum_ = Fluent.formattedNumber { defaults_ | locale = locale_, maximumFractionDigits = Just 4, maximumSignificantDigits = Just 6, minimumFractionDigits = Just 3, minimumIntegerDigits = Just 2, minimumSignificantDigits = Just 5, useGrouping = False } 7890
                in
                    String.concat [ "There are "
                                  , Fluent.formatNumber locale_ fnum_
                                  , " things"
                                  ]
        """,
        )
        self.assertEqual(errs, [])

    def test_inferred_date(self):
        # From the second instance of $date we know it is a date,
        # so it must be treated as a date in the first
        code, errs = compile_messages_to_elm(
            """
            foo = { $startdate }, { DATETIME($startdate) }
        """,
            self.locale,
        )
        self.assertCodeEqual(
            code,
            """
            foo : Locale.Locale -> { a | startdate : Fluent.FluentDate } -> String
            foo locale_ args_ =
                String.concat [ Fluent.formatDate locale_ args_.startdate
                              , ", "
                              , Fluent.formatDate locale_ args_.startdate
                              ]
        """,
        )
        self.assertEqual(errs, [])

    def test_DATETIME_everything(self):
        code, errs = compile_messages_to_elm(
            """
            foo = { DATETIME($startdate,
                             hour12: 0,
                             weekday: "short",
                             era: "long",
                             year: "numeric",
                             month: "numeric",
                             day: "numeric",
                             hour: "2-digit",
                             minute: "2-digit",
                             second: "2-digit",
                             timeZoneName: "short") }
        """,
            self.locale,
        )
        self.assertCodeEqual(
            code,
            """
            foo : Locale.Locale -> { a | startdate : Fluent.FluentDate } -> String
            foo locale_ args_ =
                let
                    initial_opts_ = Fluent.dateFormattingOptions args_.startdate
                    fdate_ = Fluent.reformattedDate { initial_opts_ | day = DateTimeFormat.NumericNumber, era = DateTimeFormat.LongName, hour = DateTimeFormat.TwoDigitNumber, hour12 = Just False, locale = locale_, minute = DateTimeFormat.TwoDigitNumber, month = DateTimeFormat.NumericMonth, second = DateTimeFormat.TwoDigitNumber, timeZoneName = DateTimeFormat.ShortTimeZone, weekday = DateTimeFormat.ShortName, year = DateTimeFormat.NumericNumber } args_.startdate
                in
                    Fluent.formatDate locale_ fdate_
        """,
        )
        self.assertEqual(errs, [])

    def test_missing_function_call(self):
        code, errs = compile_messages_to_elm(
            """
            foo = { MISSING(123) }
        """,
            self.locale,
        )
        self.assertEqual(errs[0].error_sources[0].message_id, "foo")
        self.assertEqual(
            errs[0], exceptions.ReferenceError("Unknown function: MISSING")
        )

    def test_function_call_with_bad_keyword_arg(self):
        code, errs = compile_messages_to_elm(
            """
            foo = { NUMBER(123, foo: 1) }
        """,
            self.locale,
        )
        self.assertEqual(len(errs), 1)
        self.assertEqual(errs[0].error_sources[0].message_id, "foo")
        self.assertEqual(
            errs[0],
            exceptions.FunctionParameterError(
                "NUMBER() got an unexpected keyword argument 'foo'"
            ),
        )

    def test_function_call_with_bad_positional_arg(self):
        code, errs = compile_messages_to_elm(
            """
            foo = { NUMBER(123, 456) }
        """,
            self.locale,
        )
        self.assertEqual(len(errs), 1)
        self.assertEqual(errs[0].error_sources[0].message_id, "foo")
        self.assertEqual(
            errs[0],
            exceptions.FunctionParameterError(
                "NUMBER() takes 1 positional argument(s) but 2 were given"
            ),
        )
        self.assertEqual(type(errs[0].error_sources[0].expr), ast.CallExpression)

    def test_message_arg_type_mismatch(self):
        # Should return error gracefully
        src = dedent_ftl(
            """
            foo = { NUMBER($arg) } { DATETIME($arg) }
        """
        )
        code, errs = compile_messages_to_elm(src, self.locale)
        self.assertEqual(len(errs), 1)
        err = errs[0]
        self.assertEqual(span_to_position(err.error_sources[0].expr.span, src), (1, 26))

        self.assertEqual(type(err), exceptions.RecordTypeMismatch)
        self.assertEqual(err.field_name, "arg")
        type_sources = err.record_type.field_type_ftl_sources["arg"]
        self.assertEqual(len(type_sources), 2)

        self.assertEqual(
            span_to_position(type_sources[0].ftl_source.expr.span, src), (1, 9)
        )
        self.assertEqual(type_sources[0].type_obj, fluent.FluentNumber)

        self.assertEqual(
            span_to_position(type_sources[1].ftl_source.expr.span, src), (1, 26)
        )
        self.assertEqual(type_sources[1].type_obj, fluent.FluentDate)

    def test_message_arg_type_mismatch_across_messsages(self):
        # Should return error gracefully, including info about where the
        # different types were inferred from
        src = dedent_ftl(
            """
            foo = { bar } { baz }

            bar = { NUMBER($arg) }

            baz = { DATETIME($arg) }
        """
        )
        code, errs = compile_messages_to_elm(src, self.locale)
        self.assertEqual(len(errs), 1)
        err = errs[0]
        self.assertEqual(span_to_position(err.error_sources[0].expr.span, src), (1, 17))

        self.assertEqual(type(err), exceptions.RecordTypeMismatch)
        self.assertEqual(err.field_name, "arg")
        type_sources = err.record_type.field_type_ftl_sources["arg"]
        self.assertEqual(len(type_sources), 2)
        self.assertEqual(
            span_to_position(type_sources[0].ftl_source.expr.span, src), (3, 9)
        )
        self.assertEqual(
            span_to_position(type_sources[1].ftl_source.expr.span, src), (5, 9)
        )

    def test_message_arg_type_mismatch_with_args(self):
        # Should return error gracefully
        code, errs = compile_messages_to_elm(
            """
            foo = { NUMBER($arg, useGrouping:0) } { DATETIME($arg, era:"long") }
        """,
            self.locale,
        )
        self.assertEqual(len(errs), 1)

    def test_message_arg_type_mismatch_with_string(self):
        src = dedent_ftl(
            """
            foo = { bar } { baz }

            bar = { $arg }

            baz = { NUMBER($arg) }
        """
        )
        code, errs = compile_messages_to_elm(src, self.locale)
        self.assertEqual(len(errs), 1)
        err = errs[0]
        self.assertEqual(span_to_position(err.error_sources[0].expr.span, src), (1, 17))

        self.assertEqual(type(err), exceptions.RecordTypeMismatch)
        self.assertEqual(err.field_name, "arg")
        type_sources = err.record_type.field_type_ftl_sources["arg"]
        self.assertEqual(len(type_sources), 2)
        self.assertEqual(
            span_to_position(type_sources[0].ftl_source.expr.span, src), (3, 7)
        )
        self.assertEqual(
            span_to_position(type_sources[1].ftl_source.expr.span, src), (5, 9)
        )

    def test_function_arg_type_mismatch(self):
        code, errs = compile_messages_to_elm(
            """
            foo = { NUMBER($arg, era: 123) }
        """,
            self.locale,
        )
        self.assertEqual(len(errs), 1)
        self.assertEqual(type(errs[0].error_sources[0].expr), ast.CallExpression)

    def test_message_with_attrs(self):
        code, errs = compile_messages_to_elm(
            """
            foo = Foo
               .attr-1 = Attr 1
               .attr-2 = Attr 2
        """,
            self.locale,
        )
        self.assertCodeEqual(
            code,
            """
            foo : Locale.Locale -> a -> String
            foo locale_ args_ =
                "Foo"

            foo_attr1 : Locale.Locale -> a -> String
            foo_attr1 locale_ args_ =
                "Attr 1"

            foo_attr2 : Locale.Locale -> a -> String
            foo_attr2 locale_ args_ =
                "Attr 2"
        """,
        )
        self.assertEqual(errs, [])

    def test_term_inline(self):
        code, errs = compile_messages_to_elm(
            """
           -term = Term
           message = Message { -term }
        """,
            self.locale,
        )
        self.assertCodeEqual(
            code,
            """
            message : Locale.Locale -> a -> String
            message locale_ args_ =
                "Message Term"
        """,
        )

    def test_variant_select_inline(self):
        code, errs = compile_messages_to_elm(
            """
            -my-term = {
                [a] A
               *[b] B
              }
            foo = Before { -my-term[a] } After
        """,
            self.locale,
        )
        self.assertCodeEqual(
            code,
            """
            foo : Locale.Locale -> a -> String
            foo locale_ args_ =
                "Before A After"
        """,
        )
        self.assertEqual(errs, [])

    def test_variant_select_default(self):
        code, errs = compile_messages_to_elm(
            """
            -my-term = {
                [a] A
               *[b] B
              }
            foo = { -my-term }
        """,
            self.locale,
        )
        self.assertCodeEqual(
            code,
            """
            foo : Locale.Locale -> a -> String
            foo locale_ args_ =
                "B"
        """,
        )
        self.assertEqual(errs, [])

    def test_variant_select_missing_variant(self):
        # We don't use the default, it is more useful to give a compilation error
        code, errs = compile_messages_to_elm(
            """
            -my-term = {
                [a] A
               *[b] B
              }
            foo = { -my-term[c] }
        """,
            self.locale,
        )
        self.assertEqual(errs[0].error_sources[0].message_id, "foo")
        self.assertEqual(
            errs[0], exceptions.ReferenceError("Unknown variant: -my-term[c]")
        )

    def test_variant_select_missing_term(self):
        code, errs = compile_messages_to_elm(
            """
            foo = { -my-term[a] }
        """,
            self.locale,
        )
        self.assertEqual(errs[0].error_sources[0].message_id, "foo")
        self.assertEqual(errs[0], exceptions.ReferenceError("Unknown term: -my-term"))

    def test_variant_select_from_non_variant(self):
        code, errs = compile_messages_to_elm(
            """
            -my-term = Term
            foo = { -my-term[a] }
        """,
            self.locale,
        )
        self.assertEqual(errs[0].error_sources[0].message_id, "foo")
        self.assertEqual(
            errs[0], exceptions.ReferenceError("Unknown variant: -my-term[a]")
        )
        self.assertEqual(len(errs), 1)

    def test_select_string(self):
        code, errs = compile_messages_to_elm(
            """
            foo = { $stringArg ->
                [a] A
               *[b] B
             }
        """,
            self.locale,
        )
        self.assertCodeEqual(
            code,
            """
            foo : Locale.Locale -> { a | stringArg : String } -> String
            foo locale_ args_ =
                case args_.stringArg of
                    "a" ->
                        "A"
                    _ ->
                        "B"
        """,
        )
        self.assertEqual(errs, [])

    def test_select_number(self):
        code, errs = compile_messages_to_elm(
            """
            foo = { $numberArg ->
                [1] One
               *[2] { 2 }
             }
        """,
            self.locale,
        )
        # We should not get number formatting calls in the select expression or
        # or the key comparisons, but we should get them for the select value
        # for { 2 }.
        # We should also get $numberArg inferred to be numeric
        self.assertCodeEqual(
            code,
            """
            foo : Locale.Locale -> { a | numberArg : Fluent.FluentNumber number } -> String
            foo locale_ args_ =
                case Fluent.numberValue args_.numberArg of
                    1 ->
                        "One"
                    _ ->
                        NumberFormat.format (NumberFormat.fromLocale locale_) 2
        """,
        )
        self.assertEqual(errs, [])

    def test_select_plural_categories(self):
        code, errs = compile_messages_to_elm(
            """
            foo = { $count ->
                [one] You have one thing
               *[other] You have some things
             }
        """,
            self.locale,
        )
        self.assertCodeEqual(
            code,
            """
            foo : Locale.Locale -> { a | count : Fluent.FluentNumber number } -> String
            foo locale_ args_ =
                case PluralRules.select (PluralRules.fromLocale locale_) (Fluent.numberValue args_.count) of
                    "one" ->
                        "You have one thing"
                    _ ->
                        "You have some things"
        """,
        )

    def test_select_mixed_numeric(self):
        code, errs = compile_messages_to_elm(
            """
            foo = { $count ->
                [0] You have nothing
                [one] You have a thing
               *[other] You have some things
             }
        """,
            self.locale,
        )
        self.assertCodeEqual(
            code,
            """
            foo : Locale.Locale -> { a | count : Fluent.FluentNumber number } -> String
            foo locale_ args_ =
                let
                    val_ = Fluent.numberValue args_.count
                    pl_ = PluralRules.select (PluralRules.fromLocale locale_) val_
                in
                    if (val_ == 0) then
                        "You have nothing"
                    else
                        if (pl_ == "one") then
                            "You have a thing"
                        else
                            "You have some things"
        """,
        )

    def test_select_mismtatch(self):
        src = dedent_ftl(
            """
            foo = { 1 ->
                [x]   X
               *[y]   Y
             }
        """
        )

        code, errs = compile_messages_to_elm(src, self.locale)
        self.assertEqual(len(errs), 1)
        err = errs[0]
        self.assertEqual(type(err), exceptions.TypeMismatch)
        self.assertEqual(span_to_position(err.error_sources[0].expr.span, src), (1, 9))
        # TODO - it would be nice to capture the other places that are causing
        # the type mismatch (e.g. the [x] key), but we don't have the
        # infrastructure for that and it is low priority.

    def test_select_mismtatch_with_arg(self):
        src = dedent_ftl(
            """
            foo = { NUMBER($count) ->
                [x]   X
               *[y]   Y
             }
        """
        )

        code, errs = compile_messages_to_elm(src, self.locale)
        self.assertEqual(len(errs), 1)
        err = errs[0]
        self.assertEqual(span_to_position(err.error_sources[0].expr.span, src), (1, 9))

        self.assertEqual(type(err), exceptions.RecordTypeMismatch)
        self.assertEqual(err.field_name, "count")
        type_sources = err.record_type.field_type_ftl_sources["count"]
        self.assertEqual(len(type_sources), 2)

        self.assertEqual(
            span_to_position(type_sources[0].ftl_source.expr.span, src), (1, 9)
        )
        self.assertEqual(type_sources[0].type_obj, fluent.FluentNumber)

        self.assertEqual(
            span_to_position(type_sources[1].ftl_source.expr.span, src), (2, 5)
        )
        self.assertEqual(type_sources[1].type_obj, dtypes.String)

    def test_select_mixed_numeric_last_not_default(self):
        code, errs = compile_messages_to_elm(
            """
            foo = { $count ->
                [0]     You have nothing
               *[other] You have some things
                [one]   You have a thing
             }
        """,
            self.locale,
        )
        self.assertCodeEqual(
            code,
            """
            foo : Locale.Locale -> { a | count : Fluent.FluentNumber number } -> String
            foo locale_ args_ =
                let
                    val_ = Fluent.numberValue args_.count
                    pl_ = PluralRules.select (PluralRules.fromLocale locale_) val_
                in
                    if (val_ == 0) then
                        "You have nothing"
                    else
                        if (pl_ == "other") then
                            "You have some things"
                        else
                            if (pl_ == "one") then
                                "You have a thing"
                            else
                                "You have some things"
        """,
        )

    def test_combine_strings(self):
        code, errs = compile_messages_to_elm(
            """
            foo = Start { "Middle" } End
        """,
            self.locale,
        )
        self.assertCodeEqual(
            code,
            """
            foo : Locale.Locale -> a -> String
            foo locale_ args_ =
                "Start Middle End"
        """,
        )
        self.assertEqual(errs, [])

    def test_single_string_literal_isolating(self):
        code, errs = compile_messages_to_elm(
            """
            foo = Foo
        """,
            self.locale,
            use_isolating=True,
        )
        # No isolating chars, because we have no placeables.
        self.assertCodeEqual(
            code,
            """
            foo : Locale.Locale -> a -> String
            foo locale_ args_ =
                "Foo"
        """,
        )
        self.assertEqual(errs, [])

    def test_interpolation_isolating(self):
        code, errs = compile_messages_to_elm(
            """
            foo = Foo { $arg } Bar
        """,
            self.locale,
            use_isolating=True,
        )
        self.assertCodeEqual(
            code,
            """
            foo : Locale.Locale -> { a | arg : String } -> String
            foo locale_ args_ =
                String.concat [ "Foo \u2068"
                              , args_.arg
                              , "\u2069 Bar"
                              ]
        """,
        )
        self.assertEqual(errs, [])

    def test_cycle_detection(self):
        code, errs = compile_messages_to_elm(
            """
            foo = { foo }
        """,
            self.locale,
        )
        self.assertEqual(errs[0].error_sources[0].message_id, "foo")
        self.assertEqual(
            errs[0], exceptions.CyclicReferenceError("Cyclic reference in foo")
        )

    def test_cycle_detection_with_attrs(self):
        code, errs = compile_messages_to_elm(
            """
            foo
               .attr1 = { bar.attr2 }

            bar
               .attr2 = { foo.attr1 }
        """,
            self.locale,
        )
        self.assertEqual(errs[0].error_sources[0].message_id, "foo.attr1")
        self.assertEqual(
            errs[0], exceptions.CyclicReferenceError("Cyclic reference in foo.attr1")
        )
        self.assertEqual(errs[1].error_sources[0].message_id, "bar.attr2")
        self.assertEqual(
            errs[1], exceptions.CyclicReferenceError("Cyclic reference in bar.attr2")
        )

    def test_term_cycle_detection(self):
        code, errs = compile_messages_to_elm(
            """
            -cyclic-term = { -cyclic-term }
            cyclic-term-message = { -cyclic-term }
        """,
            self.locale,
        )
        self.assertEqual(errs[0].error_sources[0].message_id, "cyclic-term-message")
        self.assertEqual(
            errs[0],
            exceptions.CyclicReferenceError("Cyclic reference in cyclic-term-message"),
        )

    def test_multiline_text(self):
        code, errs = compile_messages_to_elm(
            """
            test = Some text
                   that spans multiple lines
            """,
            self.locale,
        )
        self.assertCodeEqual(
            code,
            """
            test : Locale.Locale -> a -> String
            test locale_ args_ =
                "Some text\\nthat spans multiple lines"
            """,
        )

    def test_imports_eliminated(self):
        code, errs = compile_messages_to_elm(
            """
            test = Some text
            """,
            self.locale,
            include_imports=True,
        )
        self.assertCodeEqual(
            code,
            """
            import Intl.Locale as Locale

            test : Locale.Locale -> a -> String
            test locale_ args_ =
                "Some text"
            """,
        )


class TestHtml(unittest.TestCase):
    locale = "en-US"

    maxDiff = None

    def assertCodeEqual(self, code1, code2):
        self.assertEqual(normalize_elm(code2), normalize_elm(code1))

    def test_text(self):
        code, errs = compile_messages_to_elm(
            """
            text-html = Me &amp; my friends ☺
            """,
            self.locale,
        )
        self.assertCodeEqual(
            code,
            """
            textHtml : Locale.Locale -> a -> List (String, List (Html.Attribute msg)) -> List (Html.Html msg)
            textHtml locale_ args_ attrs_ =
                [ Html.text "Me & my friends ☺"
                ]
            """,
        )
        self.assertEqual(errs, [])

    def test_tags(self):
        code, errs = compile_messages_to_elm(
            """
            tags-html = Some <b>bold text</b> and some <b>bold and <i>nested italic ☺</i></b> text
            """,
            self.locale,
            dynamic_html_attributes=False,
        )
        self.assertCodeEqual(
            code,
            """
            tagsHtml : Locale.Locale -> a -> List (String, List (Html.Attribute msg)) -> List (Html.Html msg)
            tagsHtml locale_ args_ attrs_ =
                [ Html.text "Some "
                , Html.b [] [ Html.text "bold text"
                            ]
                , Html.text " and some "
                , Html.b [] [ Html.text "bold and "
                            , Html.i [] [ Html.text "nested italic ☺"
                                        ]
                            ]
                , Html.text " text"
                ]
            """,
        )
        self.assertEqual(errs, [])

    def test_tags_not_builtin(self):
        code, errs = compile_messages_to_elm(
            """
            new-tag-html = <html5000newelement></html5000newelement>
            """,
            self.locale,
            dynamic_html_attributes=False,
        )
        self.assertCodeEqual(
            code,
            """
            newTagHtml : Locale.Locale -> a -> List (String, List (Html.Attribute msg)) -> List (Html.Html msg)
            newTagHtml locale_ args_ attrs_ =
                [ Html.node "html5000newelement" [] []
                ]
            """,
        )
        self.assertEqual(errs, [])

    def test_static_attributes(self):
        code, errs = compile_messages_to_elm(
            """
            tag-html = <b id="myid" data-foo data-bar="baz">text</b>
            """,
            self.locale,
            dynamic_html_attributes=False,
        )
        self.assertCodeEqual(
            code,
            """
            tagHtml : Locale.Locale -> a -> List (String, List (Html.Attribute msg)) -> List (Html.Html msg)
            tagHtml locale_ args_ attrs_ =
                [ Html.b [ Attributes.attribute "data-bar" "baz"
                         , Attributes.attribute "data-foo" ""
                         , Attributes.id "myid"
                         ] [ Html.text "text"
                           ]
                ]
            """,
        )
        self.assertEqual(errs, [])

    def test_class_attributes(self):
        # Check we work around bs4 'helpfulness'
        code, errs = compile_messages_to_elm(
            """
            new-tag-html = <b class="foo">text</b>
            """,
            self.locale,
            dynamic_html_attributes=False,
        )
        self.assertCodeEqual(
            code,
            """
            newTagHtml : Locale.Locale -> a -> List (String, List (Html.Attribute msg)) -> List (Html.Html msg)
            newTagHtml locale_ args_ attrs_ =
                [ Html.b [ Attributes.class "foo"
                         ] [ Html.text "text"
                           ]
                ]
            """,
        )
        self.assertEqual(errs, [])

    def test_dynamic_attributes(self):
        code, errs = compile_messages_to_elm(
            """
            attributes-html = <b class="foo" data-foo>text</b>
            """,
            self.locale,
        )
        self.assertCodeEqual(
            code,
            """
            attributesHtml : Locale.Locale -> a -> List (String, List (Html.Attribute msg)) -> List (Html.Html msg)
            attributesHtml locale_ args_ attrs_ =
                [ Html.b (List.concat [ [ Attributes.class "foo"
                                        , Attributes.attribute "data-foo" ""
                                        ]
                                      , Fluent.selectAttributes attrs_ [ "b"
                                                                       , ".foo"
                                                                       , "b.foo"
                                                                       , "[data-foo]"
                                                                       , "b[data-foo]"
                                                                       , "[data-foo=\\"\\"]"
                                                                       , "b[data-foo=\\"\\"]"
                                                                       ]
                                      ]) [ Html.text "text"
                                         ]
                ]
            """,
        )
        self.assertEqual(errs, [])

    def test_dynamic_attributes_2(self):
        code, errs = compile_messages_to_elm(
            """
            attributes-html = <b>text</b>
            """,
            self.locale,
        )
        self.assertCodeEqual(
            code,
            """
            attributesHtml : Locale.Locale -> a -> List (String, List (Html.Attribute msg)) -> List (Html.Html msg)
            attributesHtml locale_ args_ attrs_ =
                [ Html.b (Fluent.selectAttributes attrs_ [ "b"
                                                         ]) [ Html.text "text"
                                                            ]
                ]
            """,
        )
        self.assertEqual(errs, [])

    def test_attribute_substitution(self):
        # If we have any non-static text in attributes, we can't use them for attribute selectors
        code, errs = compile_messages_to_elm(
            """
            attributes-html = <b class="foo{ bar }" data-foo="{ $arg }" id="{ baz.id }">text</b>
            bar = Bar
            baz = baz
                .id = bazid
            """,
            self.locale,
        )
        self.assertCodeEqual(
            code,
            """
            attributesHtml : Locale.Locale -> { a | arg : String } -> List (String, List (Html.Attribute msg)) -> List (Html.Html msg)
            attributesHtml locale_ args_ attrs_ =
                [ Html.b (List.concat [ [ Attributes.class (String.concat [ "foo"
                                                                          , bar locale_ args_
                                                                          ])
                                        , Attributes.attribute "data-foo" args_.arg
                                        , Attributes.id (baz_id locale_ args_)
                                        ]
                                      , Fluent.selectAttributes attrs_ [ "b"
                                                                       , "[data-foo]"
                                                                       , "b[data-foo]"
                                                                       ]
                                      ]) [ Html.text "text"
                                         ]
                ]

            bar : Locale.Locale -> a -> String
            bar locale_ args_ =
                "Bar"

            baz : Locale.Locale -> a -> String
            baz locale_ args_ =
                "baz"

            baz_id : Locale.Locale -> a -> String
            baz_id locale_ args_ =
                "bazid"
            """,
        )
        self.assertEqual(errs, [])

    def test_non_string_args_in_attributes(self):
        code, errs = compile_messages_to_elm(
            """
            number-attribute-html = <b data-foo="{ NUMBER($arg) }">text</b>
            """,
            self.locale,
        )
        self.assertCodeEqual(
            code,
            """
            numberAttributeHtml : Locale.Locale -> { a | arg : Fluent.FluentNumber number } -> List (String, List (Html.Attribute msg)) -> List (Html.Html msg)
            numberAttributeHtml locale_ args_ attrs_ =
                [ Html.b (List.concat [ [ Attributes.attribute "data-foo" (Fluent.formatNumber locale_ args_.arg)
                                        ]
                                      , Fluent.selectAttributes attrs_ [ "b"
                                                                       , "[data-foo]"
                                                                       , "b[data-foo]"
                                                                       ]
                                      ]) [ Html.text "text"
                                         ]
                ]
            """,
        )
        self.assertEqual(errs, [])

    def test_argument(self):
        code, errs = compile_messages_to_elm(
            """
            hello-html = Hello <b>{ $username }</b>!
            """,
            self.locale,
            dynamic_html_attributes=False,
        )
        self.assertCodeEqual(
            code,
            """
            helloHtml : Locale.Locale -> { a | username : String } -> List (String, List (Html.Attribute msg)) -> List (Html.Html msg)
            helloHtml locale_ args_ attrs_ =
                [ Html.text "Hello "
                , Html.b [] [ Html.text args_.username
                            ]
                , Html.text "!"
                ]
             """,
        )
        self.assertEqual(errs, [])

    def test_non_string_args_in_text(self):
        code, errs = compile_messages_to_elm(
            """
            foo-html = <b>Text { $arg } { DATETIME($arg) }</b>
            """,
            self.locale,
            dynamic_html_attributes=False,
        )
        self.assertCodeEqual(
            code,
            """
            fooHtml : Locale.Locale -> { a | arg : Fluent.FluentDate } -> List (String, List (Html.Attribute msg)) -> List (Html.Html msg)
            fooHtml locale_ args_ attrs_ =
                [ Html.b [] [ Html.text (String.concat [ "Text "
                                                       , Fluent.formatDate locale_ args_.arg
                                                       , " "
                                                       , Fluent.formatDate locale_ args_.arg
                                                       ])
                            ]
                ]
             """,
        )
        self.assertEqual(errs, [])

    def test_text_message_call(self):
        code, errs = compile_messages_to_elm(
            """
            welcome-back = Welcome back!
            hello-html = Hello, friend! <b>{ welcome-back }</b>
            """,
            self.locale,
            dynamic_html_attributes=False,
        )
        self.assertCodeEqual(
            code,
            """
            welcomeBack : Locale.Locale -> a -> String
            welcomeBack locale_ args_ =
                "Welcome back!"

            helloHtml : Locale.Locale -> a -> List (String, List (Html.Attribute msg)) -> List (Html.Html msg)
            helloHtml locale_ args_ attrs_ =
                [ Html.text "Hello, friend! "
                , Html.b [] [ Html.text (welcomeBack locale_ args_)
                            ]
                ]
             """,
        )
        self.assertEqual(errs, [])

    def test_html_message_call(self):
        code, errs = compile_messages_to_elm(
            """
            welcome-html = Welcome to <b>Awesome site!</b>
            hello-html = Hello! { welcome-html }
            """,
            self.locale,
            dynamic_html_attributes=False,
        )
        self.assertCodeEqual(
            code,
            """
            welcomeHtml : Locale.Locale -> a -> List (String, List (Html.Attribute msg)) -> List (Html.Html msg)
            welcomeHtml locale_ args_ attrs_ =
                [ Html.text "Welcome to "
                , Html.b [] [ Html.text "Awesome site!"
                            ]
                ]

            helloHtml : Locale.Locale -> a -> List (String, List (Html.Attribute msg)) -> List (Html.Html msg)
            helloHtml locale_ args_ attrs_ =
                List.concat [ [ Html.text "Hello! "
                              ]
                            , welcomeHtml locale_ args_ attrs_
                            ]
             """,
        )
        self.assertEqual(errs, [])

    def test_text_message_call_attribute(self):
        code, errs = compile_messages_to_elm(
            """
            hello-html = Hello <b data-foo="&lt;stuff&gt; { hello-html.foo }">friend</b>
                      .foo = <xxx>
            """,
            self.locale,
            dynamic_html_attributes=False,
        )
        self.assertCodeEqual(
            code,
            """
            helloHtml : Locale.Locale -> a -> List (String, List (Html.Attribute msg)) -> List (Html.Html msg)
            helloHtml locale_ args_ attrs_ =
                [ Html.text "Hello "
                , Html.b [ Attributes.attribute "data-foo" (String.concat [ "<stuff> "
                                                                          , helloHtml_foo locale_ args_
                                                                          ])
                         ] [ Html.text "friend"
                           ]
                ]

            helloHtml_foo : Locale.Locale -> a -> String
            helloHtml_foo locale_ args_ =
                "<xxx>"
            """,
        )
        self.assertEqual(errs, [])

    def test_html_message_call_attribute(self):
        code, errs = compile_messages_to_elm(
            """
            hello-html = Hello <b class="{ foo-html }">friend</b>
            foo-html = Foo
            """,
            self.locale,
        )
        self.assertEqual(len(errs), 1)
        self.assertEqual(
            errs[0].args[0], "Cannot use HTML message foo-html from plain text context."
        )

    def test_html_message_call_from_plain_test(self):
        code, errs = compile_messages_to_elm(
            """
            hello = Hello { foo-html }
            foo-html = Foo
            """,
            self.locale,
        )
        self.assertEqual(len(errs), 1)
        self.assertEqual(
            errs[0].args[0], "Cannot use HTML message foo-html from plain text context."
        )

    def test_select_expression_1(self):
        # Test we get HTML handling of the pattern inside the select express
        # i.e HTML context propagates
        code, errs = compile_messages_to_elm(
            """
            hello-html = Hello { $gender ->
               [male]    <b>Mr. { $surname }</b>, nice to see you
               [female]  <b>Ms. { $surname }</b>, nice to see you
              *[other]   <b>{ $surname }</b>, nice to see you
             }
            """,
            self.locale,
            dynamic_html_attributes=False,
        )
        self.assertCodeEqual(
            code,
            """
            helloHtml : Locale.Locale -> { a | gender : String, surname : String } -> List (String, List (Html.Attribute msg)) -> List (Html.Html msg)
            helloHtml locale_ args_ attrs_ =
                List.concat [ [ Html.text "Hello "
                              ]
                            , case args_.gender of
                                  "male" ->
                                      [ Html.b [] [ Html.text (String.concat [ "Mr. "
                                                                             , args_.surname
                                                                             ])
                                                  ]
                                      , Html.text ", nice to see you"
                                      ]
                                  "female" ->
                                      [ Html.b [] [ Html.text (String.concat [ "Ms. "
                                                                             , args_.surname
                                                                             ])
                                                  ]
                                      , Html.text ", nice to see you"
                                      ]
                                  _ ->
                                      [ Html.b [] [ Html.text args_.surname
                                                  ]
                                      , Html.text ", nice to see you"
                                      ]

                            ]
             """,
        )
        self.assertEqual(errs, [])

    def test_html_term_inline(self):
        code, errs = compile_messages_to_elm(
            """
            welcome-html = Welcome to { -brand-html }
            -brand-html = Awesomeness<sup>2</sup>
            """,
            self.locale,
            dynamic_html_attributes=False,
        )
        self.assertCodeEqual(
            code,
            """
            welcomeHtml : Locale.Locale -> a -> List (String, List (Html.Attribute msg)) -> List (Html.Html msg)
            welcomeHtml locale_ args_ attrs_ =
                [ Html.text "Welcome to Awesomeness"
                , Html.sup [] [ Html.text "2"
                              ]
                ]
            """,
        )
        self.assertEqual(errs, [])

    def test_plain_term_inline(self):
        code, errs = compile_messages_to_elm(
            """
            welcome-html = Welcome to <b>{ -brand }</b>
            -brand = Awesomeness2
            """,
            self.locale,
            dynamic_html_attributes=False,
        )
        self.assertCodeEqual(
            code,
            """
            welcomeHtml : Locale.Locale -> a -> List (String, List (Html.Attribute msg)) -> List (Html.Html msg)
            welcomeHtml locale_ args_ attrs_ =
                [ Html.text "Welcome to "
                , Html.b [] [ Html.text "Awesomeness2"
                            ]
                ]
            """,
        )
        self.assertEqual(errs, [])
