# -*- coding: utf-8 -*-

from __future__ import absolute_import, unicode_literals

import textwrap
import unittest

from elm_fluent import codegen


def normalize_elm(text):
    return textwrap.dedent(text.rstrip()).strip()


class TestCodeGen(unittest.TestCase):

    def assertCodeEqual(self, code1, code2):
        self.assertEqual(normalize_elm(code1),
                         normalize_elm(code2))

    def test_module_builtins(self):
        module = codegen.Module()
        self.assertIn('min', module.all_reserved_names())

    def test_module_keywords(self):
        module = codegen.Module()
        self.assertIn('import', module.all_reserved_names())

    def test_reserve_name(self):
        scope = codegen.Scope()
        name1 = scope.reserve_name('name')
        name2 = scope.reserve_name('name')
        self.assertEqual(name1, 'name')
        self.assertNotEqual(name1, name2)
        self.assertEqual(name2, 'name2')

    def test_reserve_name_function_arg_disallowed(self):
        scope = codegen.Scope()
        scope.reserve_name('name')
        self.assertRaises(AssertionError,
                          scope.reserve_name,
                          'name',
                          function_arg=True)

    def test_reserve_name_function_arg(self):
        scope = codegen.Scope()
        scope.reserve_function_arg_name('arg_name')
        scope.reserve_name('myfunc')
        func = codegen.Function('myfunc',
                                args=['arg_name'],
                                parent_scope=scope)
        self.assertNotIn('arg_name2', func.all_reserved_names())

    def test_reserve_name_nested(self):
        parent = codegen.Scope()
        parent_name = parent.reserve_name('name')
        self.assertEqual(parent_name, 'name')

        child1 = codegen.Scope(parent_scope=parent)
        child2 = codegen.Scope(parent_scope=parent)

        child1_name = child1.reserve_name('name')
        self.assertNotEqual(child1_name, parent_name)

        child2_name = child2.reserve_name('name')
        self.assertNotEqual(child2_name, parent_name)

        # But children can have same names, they don't shadow each other.
        # To be deterministic, we expect the same name
        self.assertEqual(child1_name, child2_name)

    def test_reserve_name_after_reserve_function_arg(self):
        scope = codegen.Scope()
        scope.reserve_function_arg_name('my_arg')
        name = scope.reserve_name('my_arg')
        self.assertEqual(name, 'my_arg2')

    def test_reserve_function_arg_after_reserve_name(self):
        scope = codegen.Scope()
        scope.reserve_name('my_arg')
        self.assertRaises(AssertionError,
                          scope.reserve_function_arg_name,
                          'my_arg')

    def test_name_properties(self):
        scope = codegen.Scope()
        scope.reserve_name('name', properties={'FOO': True})
        self.assertEqual(scope.get_name_properties('name'),
                         {'FOO': True})

    def test_function(self):
        module = codegen.Module()
        func = codegen.Function('myfunc', args=['myarg1', 'myarg2'],
                                parent_scope=module,
                                body=codegen.String("hello"))
        self.assertCodeEqual(func.as_source_code(), """
            myfunc myarg1 myarg2 =
                "hello"
        """)

    def test_let_no_assignments(self):
        module = codegen.Module()
        func = codegen.Function('myfunc',
                                parent_scope=module)
        func.body.value = codegen.String("Hello")
        func = codegen.simplify(func)
        self.assertCodeEqual(func.as_source_code(), """
            myfunc =
                "Hello"
        """)

    def test_let_one_assignment(self):
        module = codegen.Module()
        func = codegen.Function('myfunc',
                                parent_scope=module)
        let = func.body
        let.reserve_name('x')
        let.add_assignment('x', codegen.String("Hello"))
        let.value = codegen.VariableReference('x', let)
        func = codegen.simplify(func)
        self.assertCodeEqual(func.as_source_code(), """
            myfunc =
                "Hello"
        """)

    def test_let_two_assignments(self):
        module = codegen.Module()
        func = codegen.Function('myfunc',
                                parent_scope=module)
        let = func.body
        let.reserve_name('x')
        let.reserve_name('y')
        let.add_assignment('x', codegen.Number(1))
        let.add_assignment('y', codegen.Number(2))
        let.value = codegen.Add(codegen.VariableReference('x', let),
                                codegen.VariableReference('y', let))
        func = codegen.simplify(func)
        # TODO - remove unnecessary parenthesis in final expression
        self.assertCodeEqual(func.as_source_code(), """
            myfunc =
                let
                    x = 1
                    y = 2
                in
                    (x + y)
        """)

    def test_add_function(self):
        module = codegen.Module()
        func_name = module.reserve_name('myfunc')
        func = codegen.Function(func_name,
                                parent_scope=module,
                                body=codegen.String("hi"))
        module.add_function(func_name, func)
        self.assertCodeEqual(module.as_source_code(), """
            myfunc =
                "hi"
        """)

    def test_variable_reference(self):
        module = codegen.Module()
        name = module.reserve_name('name')
        ref = codegen.VariableReference(name, module)
        self.assertEqual(ref.as_source_code(), 'name')

    def test_variable_reference_check(self):
        module = codegen.Module()
        self.assertRaises(AssertionError,
                          codegen.VariableReference,
                          'name',
                          module)

    def test_variable_reference_function_arg_check(self):
        module = codegen.Module()
        func_name = module.reserve_name('myfunc')
        func = codegen.Function(func_name, args=['my_arg'],
                                parent_scope=module)
        # Can't use undefined 'some_name'
        self.assertRaises(AssertionError,
                          codegen.VariableReference,
                          'some_name',
                          func)
        # But can use function argument 'my_arg'
        ref = codegen.VariableReference('my_arg', func)
        self.assertCodeEqual(ref.as_source_code(), 'my_arg')

    def test_function_args_name_check(self):
        module = codegen.Module()
        module.reserve_name('my_arg')
        func_name = module.reserve_name('myfunc')
        self.assertRaises(AssertionError,
                          codegen.Function,
                          func_name, args=['my_arg'],
                          parent_scope=module)

    def test_function_args_name_reserved_check(self):
        module = codegen.Module()
        module.reserve_function_arg_name('myarg')
        func_name = module.reserve_name('myfunc')
        func = codegen.Function(func_name, args=['myarg'],
                                parent_scope=module)
        func.body.value = codegen.VariableReference('myarg', func)
        func = codegen.simplify(func)
        self.assertCodeEqual(func.as_source_code(), """
           myfunc myarg =
               myarg
        """)

    def test_add_assignment_unreserved(self):
        scope = codegen.Scope()
        let = codegen.Let(parent_scope=scope)
        self.assertRaises(AssertionError,
                          let.add_assignment,
                          'x',
                          codegen.String('a string'))

    def test_add_assignment_reserved(self):
        scope = codegen.Scope()
        let = codegen.Let(parent_scope=scope)
        name = let.reserve_name('x')
        let.add_assignment(name, codegen.String('a string'))
        let.value = codegen.String('other')
        self.assertCodeEqual(let.as_source_code(), """
            let
                x = "a string"
            in
                "other"
        """)

    def test_add_assignment_multi(self):
        scope = codegen.Scope()
        let = codegen.Let()
        name1 = let.reserve_name('x')
        name2 = let.reserve_name('y')
        let.add_assignment((name1, name2), codegen.Tuple(codegen.String('a string'), codegen.String('another')))
        let.value = codegen.String("other")
        self.assertCodeEqual(let.as_source_code(), """
            let
                (x, y) = ("a string", "another")
            in
                "other"
        """)

    def test_function_call_unknown(self):
        scope = codegen.Scope()
        self.assertRaises(AssertionError,
                          codegen.FunctionCall,
                          'a_function',
                          [],
                          scope)

    def test_function_call_known(self):
        scope = codegen.Scope()
        scope.reserve_name('aFunction')
        func_call = codegen.FunctionCall('aFunction', [], scope)
        self.assertCodeEqual(func_call.as_source_code(), "aFunction")

    def test_function_call_args(self):
        scope = codegen.Scope()
        scope.reserve_name('aFunction')
        func_call = codegen.FunctionCall('aFunction', [codegen.Number(123)], scope)
        self.assertCodeEqual(func_call.as_source_code(), "aFunction 123")

    def test_if(self):
        scope = codegen.Scope()
        if_expr = codegen.If(parent_scope=scope)
        if_expr.condition = codegen.Equals(codegen.Number(1),
                                           codegen.Number(2))
        if_expr.true_branch.value = codegen.Number(3)
        if_expr.false_branch.value = codegen.Number(4)
        if_expr = codegen.simplify(if_expr)
        self.assertCodeEqual(if_expr.as_source_code(), """
            if (1 == 2) then
                3
            else
                4
        """)

    def test_string_join_empty(self):
        join = codegen.Concat([])
        join = codegen.simplify(join)
        self.assertCodeEqual(join.as_source_code(), '""')

    def test_string_join_one(self):
        join = codegen.Concat([codegen.String('hello')])
        join = codegen.simplify(join)
        self.assertCodeEqual(join.as_source_code(), '"hello"')

    def test_string_join_two(self):
        scope = codegen.Scope()
        scope.reserve_name('tmp')
        var = codegen.VariableReference('tmp', scope)
        join = codegen.Concat([codegen.String('hello '), var])
        self.assertCodeEqual(join.as_source_code(), 'String.concat ["hello ", tmp]')

    def test_string_join_collapse_strings(self):
        scope = codegen.Scope()
        scope.reserve_name('tmp')
        var = codegen.VariableReference('tmp', scope)
        join1 = codegen.Concat([codegen.String('hello '),
                                codegen.String('there '),
                                var,
                                codegen.String(' how'),
                                codegen.String(' are you?'),
                                ])
        join1 = codegen.simplify(join1)
        self.assertCodeEqual(join1.as_source_code(), 'String.concat ["hello there ", tmp, " how are you?"]')

    def test_cleanup_name(self):
        for n, c in [('abc-def()[]ghi,.<>¡!?¿', 'abcdefghi'),  # illegal chars
                     ('1abc', 'n1abc'),  # leading digit not allowed
                     ('-', 'n'),  # aboid being empty after removing illegals
                     ('_abc', 'n_abc'),  # leading underscore not allowed
                     ('abc_def', 'abc_def'),  # underscore in middle is allowed
                     ]:
            self.assertEqual(codegen.cleanup_name(n), c)
