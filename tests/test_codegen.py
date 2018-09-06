# -*- coding: utf-8 -*-

from __future__ import absolute_import, unicode_literals

import textwrap
import unittest

from elm_fluent import codegen, types
from elm_fluent.stubs import defaults as dtypes


def normalize_elm(text):
    return textwrap.dedent(text.rstrip()).strip()


class TestCodeGen(unittest.TestCase):
    def assertCodeEqual(self, code1, code2):
        self.assertEqual(normalize_elm(code2), normalize_elm(code1))

    def test_module_builtins(self):
        module = codegen.Module()
        self.assertIn("min", module.all_reserved_names())

    def test_module_keywords(self):
        module = codegen.Module()
        self.assertIn("import", module.all_reserved_names())

    def test_reserve_name(self):
        scope = codegen.Scope()
        name1 = scope.reserve_name("name")
        name2 = scope.reserve_name("name")
        self.assertEqual(name1, "name")
        self.assertNotEqual(name1, name2)
        self.assertEqual(name2, "name2")

    def test_variables(self):
        scope = codegen.Scope()
        name = scope.reserve_name("name")
        var = scope.variables[name]
        self.assertEqual(type(var), codegen.VariableReference)
        self.assertEqual(var.name, name)

    def test_reserve_name_function_arg_disallowed(self):
        scope = codegen.Scope()
        scope.reserve_name("name")
        self.assertRaises(AssertionError, scope.reserve_name, "name", function_arg=True)

    def test_reserve_name_function_arg(self):
        scope = codegen.Scope()
        scope.reserve_function_arg_name("arg_name")
        scope.reserve_name("myfunc")
        func = codegen.Function("myfunc", args=["arg_name"], parent_scope=scope)
        self.assertNotIn("arg_name2", func.all_reserved_names())

    def test_reserve_name_nested(self):
        parent = codegen.Scope()
        parent_name = parent.reserve_name("name")
        self.assertEqual(parent_name, "name")

        child1 = codegen.Scope(parent_scope=parent)
        child2 = codegen.Scope(parent_scope=parent)

        child1_name = child1.reserve_name("name")
        self.assertNotEqual(child1_name, parent_name)

        child2_name = child2.reserve_name("name")
        self.assertNotEqual(child2_name, parent_name)

        # But children can have same names, they don't shadow each other.
        # To be deterministic, we expect the same name
        self.assertEqual(child1_name, child2_name)

    def test_reserve_name_after_reserve_function_arg(self):
        scope = codegen.Scope()
        scope.reserve_function_arg_name("my_arg")
        name = scope.reserve_name("my_arg")
        self.assertEqual(name, "my_arg2")

    def test_reserve_function_arg_after_reserve_name(self):
        scope = codegen.Scope()
        scope.reserve_name("my_arg")
        self.assertRaises(AssertionError, scope.reserve_function_arg_name, "my_arg")

    def test_get_type(self):
        scope = codegen.Scope()
        scope.reserve_name("name", type=dtypes.Bool)
        self.assertEqual(scope.get_type("name"), dtypes.Bool)

    def test_function(self):
        module = codegen.Module()
        func = codegen.Function(
            "myfunc", args=["myarg1", "myarg2"], parent_scope=module
        )
        func.body.value = codegen.String("hello")
        func = codegen.simplify(func)
        self.assertCodeEqual(
            func.as_source_code(),
            """
            myfunc myarg1 myarg2 =
                "hello"
        """,
        )

    def test_function_typed(self):
        module = codegen.Module()
        function_type = types.Function.for_multiple_inputs(
            [dtypes.String, dtypes.Number], dtypes.String
        )
        module.reserve_name("myfunc", type=function_type)
        func = codegen.Function(
            "myfunc", args=["myarg1", "myarg2"], parent_scope=module
        )
        func.body.value = codegen.String("hello")
        func = codegen.simplify(func)
        self.assertCodeEqual(
            func.as_source_code(),
            """
            myfunc : String -> number -> String
            myfunc myarg1 myarg2 =
                "hello"
        """,
        )
        self.assertEqual(func.variables["myarg2"].type, dtypes.Number)

    def test_attribute_reference_in_function(self):
        module = codegen.Module()
        record_type = types.Record()
        function_type = types.Function(record_type, dtypes.String)
        module.reserve_name("myfunc", type=function_type)
        func = codegen.Function("myfunc", args=["myarg"], parent_scope=module)
        func.body.value = codegen.AttributeReference(func.variables["myarg"], "myattr")
        func.finalize()
        codegen.simplify(func)
        self.assertCodeEqual(
            func.as_source_code(),
            """
            myfunc : { a | myattr : String } -> String
            myfunc myarg =
                myarg.myattr
        """,
        )

    def test_let_no_assignments(self):
        module = codegen.Module()
        func = codegen.Function("myfunc", parent_scope=module)
        func.body.value = codegen.String("Hello")
        func = codegen.simplify(func)
        self.assertCodeEqual(
            func.as_source_code(),
            """
            myfunc =
                "Hello"
        """,
        )

    def test_let_one_assignment(self):
        module = codegen.Module()
        func = codegen.Function("myfunc", parent_scope=module)
        let = func.body
        x = let.add_assignment("x", codegen.String("Hello"))
        self.assertEqual(x.name, "x")
        self.assertEqual(x.type, dtypes.String)
        let.value = x
        func = codegen.simplify(func)
        self.assertCodeEqual(
            func.as_source_code(),
            """
            myfunc =
                "Hello"
        """,
        )

    def test_let_two_assignments(self):
        module = codegen.Module()
        func = codegen.Function("myfunc", parent_scope=module)
        let = func.body
        x = let.add_assignment("x", codegen.Number(1))
        y = let.add_assignment("y", codegen.Number(2))
        let.value = codegen.Add(x, y)
        func = codegen.simplify(func)
        # TODO SOMEDAY - remove unnecessary parenthesis in final expression
        self.assertCodeEqual(
            func.as_source_code(),
            """
            myfunc =
                let
                    x = 1
                    y = 2
                in
                    (x + y)
            """,
        )

    def test_add_function(self):
        module = codegen.Module(name="Main")
        func_name = module.reserve_name("myfunc")
        func = codegen.Function(func_name, parent_scope=module)
        func.body.value = codegen.String("hi")
        module.add_function(func_name, func)
        func = codegen.simplify(func)
        self.assertCodeEqual(
            module.as_source_code(),
            """
            module Main exposing (myfunc)

            myfunc =
                "hi"
        """,
        )

    def test_variable_reference(self):
        module = codegen.Module()
        name = module.reserve_name("name")
        ref = codegen.VariableReference(name, module)
        self.assertEqual(ref.as_source_code(), "name")

    def test_variable_reference_check(self):
        module = codegen.Module()
        self.assertRaises(AssertionError, codegen.VariableReference, "name", module)

    def test_variable_reference_function_arg_check(self):
        module = codegen.Module()
        func_name = module.reserve_name("myfunc")
        func = codegen.Function(func_name, args=["my_arg"], parent_scope=module)
        # Can't use undefined 'some_name'
        self.assertRaises(AssertionError, lambda: func.variables["some_name"])
        # But can use function argument 'my_arg'
        ref = func.variables["my_arg"]
        self.assertCodeEqual(ref.as_source_code(), "my_arg")

    def test_function_args_name_check(self):
        module = codegen.Module()
        module.reserve_name("my_arg")
        func_name = module.reserve_name("myfunc")
        self.assertRaises(
            AssertionError,
            codegen.Function,
            func_name,
            args=["my_arg"],
            parent_scope=module,
        )

    def test_function_args_name_reserved_check(self):
        module = codegen.Module()
        module.reserve_function_arg_name("myarg")
        func_name = module.reserve_name("myfunc")
        func = codegen.Function(func_name, args=["myarg"], parent_scope=module)
        func.body.value = func.variables["myarg"]
        func = codegen.simplify(func)
        self.assertCodeEqual(
            func.as_source_code(),
            """
           myfunc myarg =
               myarg
        """,
        )

    def test_add_assignment_reserved(self):
        scope = codegen.Scope()
        let = codegen.Let(parent_scope=scope)
        name = let.add_assignment("x", codegen.String("a string"))
        self.assertEqual(name.name, "x")
        let.value = codegen.String("other")
        self.assertCodeEqual(
            let.as_source_code(),
            """
            let
                x = "a string"
            in
                "other"
        """,
        )

    def test_function_call_args(self):
        scope = codegen.Scope()
        scope.reserve_name(
            "aFunction", type=types.Function(dtypes.Number, dtypes.String)
        )
        func_call = codegen.FunctionCall(
            scope.variables["aFunction"], [codegen.Number(123)]
        )
        self.assertCodeEqual(func_call.as_source_code(), "aFunction 123")

    def test_function_call_using_apply(self):
        scope = codegen.Scope()
        scope.reserve_name(
            "aFunction", type=types.Function(dtypes.Number, dtypes.String)
        )
        func_call = scope.variables["aFunction"].apply(codegen.Number(123))
        self.assertCodeEqual(func_call.as_source_code(), "aFunction 123")

    def test_function_call_nested(self):
        scope = codegen.Scope()
        scope.reserve_name(
            "aFunction", type=types.Function(dtypes.Number, dtypes.String)
        )
        scope.reserve_name(
            "aFunction2", type=types.Function(dtypes.String, dtypes.Number)
        )
        func_call_1 = scope.variables["aFunction"].apply(codegen.Number(123))
        func_call_2 = scope.variables["aFunction2"].apply(func_call_1)
        self.assertCodeEqual(func_call_2.as_source_code(), "aFunction2 (aFunction 123)")

    def test_if(self):
        scope = codegen.Scope()
        if_expr = codegen.If(parent_scope=scope)
        if_expr.condition = codegen.Equals(codegen.Number(1), codegen.Number(2))
        if_expr.true_branch.value = codegen.Number(3)
        if_expr.false_branch.value = codegen.Number(4)
        if_expr = codegen.simplify(if_expr)
        self.assertCodeEqual(
            if_expr.as_source_code(),
            """
            if (1 == 2) then
                3
            else
                4
        """,
        )

    def test_string_join_empty(self):
        join = codegen.StringConcat([])
        join = codegen.simplify(join)
        self.assertCodeEqual(join.as_source_code(), '""')

    def test_string_join_one(self):
        join = codegen.StringConcat([codegen.String("hello")])
        join = codegen.simplify(join)
        self.assertCodeEqual(join.as_source_code(), '"hello"')

    def test_string_join_two(self):
        scope = codegen.Scope()
        scope.reserve_name("tmp", type=dtypes.String)
        var = scope.variables["tmp"]
        join = codegen.StringConcat([codegen.String("hello "), var])
        self.assertCodeEqual(
            join.as_source_code(),
            """
            String.concat [ "hello "
                          , tmp
                          ]
        """,
        )

    def test_string_join_collapse_strings(self):
        scope = codegen.Scope()
        scope.reserve_name("tmp", type=dtypes.String)
        var = scope.variables["tmp"]
        join1 = codegen.StringConcat(
            [
                codegen.String("hello "),
                codegen.String("there "),
                var,
                codegen.String(" how"),
                codegen.String(" are you?"),
            ]
        )
        join1 = codegen.simplify(join1)
        self.assertCodeEqual(
            join1.as_source_code(),
            """
            String.concat [ "hello there "
                          , tmp
                          , " how are you?"
                          ]
            """,
        )

    def test_cleanup_name(self):
        for n, c in [
            ("abc-def()[]ghi,.<>¡!?¿", "abcdefghi"),  # illegal chars
            ("1abc", "n1abc"),  # leading digit not allowed
            ("-", "n"),  # aboid being empty after removing illegals
            ("_abc", "n_abc"),  # leading underscore not allowed
            ("abc_def", "abc_def"),  # underscore in middle is allowed
        ]:
            self.assertEqual(codegen.cleanup_name(n), c)

    def test_case(self):
        scope = codegen.Scope()
        tmp = scope.reserve_name("tmp")
        case = codegen.Case(scope.variables[tmp])
        branch1 = case.add_branch(codegen.String("x"))
        branch1.value = codegen.Number(1)
        branch2 = case.add_branch(codegen.String("y"))
        branch2.value = codegen.Number(2)
        branch3 = case.add_branch(codegen.Otherwise())
        branch3.value = codegen.Number(3)

        case = codegen.simplify(case)
        self.assertCodeEqual(
            case.as_source_code(),
            """
            case tmp of
                "x" ->
                    1
                "y" ->
                    2
                _ ->
                    3
        """,
        )

    def test_record_update(self):
        rec = types.Record()
        rec.add_field("name", dtypes.String)
        rec.add_field("age", dtypes.Number)
        rec.add_field("height", dtypes.Number)
        scope = codegen.Scope()
        tmp = scope.reserve_name("tmp", type=rec)
        var = scope.variables[tmp]
        update = codegen.RecordUpdate(
            var, name=codegen.String("Fred"), age=codegen.Number(34)
        )
        self.assertCodeEqual(
            update.as_source_code(),
            """
            { tmp | age = 34, name = "Fred" }
        """,
        )

    def test_multiple_indent(self):
        scope = codegen.Scope()
        scope.reserve_name(
            "aFunction",
            type=types.Function.for_multiple_inputs(
                [dtypes.Number, dtypes.Number], dtypes.String
            ),
        )
        let1 = codegen.Let()
        name1 = let1.add_assignment("x", codegen.Number(1))
        name2 = let1.add_assignment("y", codegen.Number(2))
        let1.value = codegen.Add(name1, name2)

        case1 = codegen.Case(codegen.Add(codegen.Number(7), codegen.Number(8)))
        branch1 = case1.add_branch(codegen.Number(15))
        branch1.value = codegen.Number(16)
        branch2 = case1.add_branch(codegen.Otherwise())
        branch2.value = codegen.Number(17)

        let2 = codegen.Let()
        name3 = let2.add_assignment("a", codegen.Number(3))
        name4 = let2.add_assignment("b", case1)
        let2.add_assignment("c", codegen.Number(4))
        let2.value = codegen.Add(name3, name4)

        func_call = scope.variables["aFunction"].apply(let1, let2)
        func_call = codegen.simplify(func_call)
        self.assertCodeEqual(
            func_call.as_source_code(),
            """
        aFunction (let
                       x = 1
                       y = 2
                   in
                       (x + y)) (let
                                     a = 3
                                     b = case (7 + 8) of
                                             15 ->
                                                 16
                                             _ ->
                                                 17

                                     c = 4
                                 in
                                     (a + b))
        """,
        )
