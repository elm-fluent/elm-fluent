# -*- coding: utf-8 -*-

from __future__ import absolute_import, unicode_literals

import unittest

from elm_fluent import codegen, types
from elm_fluent.stubs import defaults as dtypes


class TestTypes(unittest.TestCase):
    def test_elm_type_str(self):
        self.assertEqual(str(dtypes.String), "String")

    def test_elm_type_signature(self):
        self.assertEqual(dtypes.String.as_signature(codegen.Module()), "String")

    def test_elm_type_eq(self):
        self.assertEqual(dtypes.String, dtypes.String)
        self.assertNotEqual(dtypes.String, dtypes.Number)

    def test_function_signature(self):
        self.assertEqual(
            types.Function(dtypes.String, dtypes.Number).as_signature(codegen.Module()),
            "String -> number",
        )

        self.assertEqual(
            types.Function.for_multiple_inputs(
                [dtypes.String, dtypes.Number], dtypes.Bool
            ).as_signature(codegen.Module()),
            "String -> number -> Bool",
        )

    def test_function_eq(self):
        function1 = types.Function.for_multiple_inputs(
            [dtypes.String, dtypes.Number], dtypes.String
        )
        function2 = types.Function.for_multiple_inputs(
            [dtypes.String, dtypes.Number], dtypes.String
        )
        function3 = types.Function.for_multiple_inputs(
            [dtypes.Bool, dtypes.Number], dtypes.String
        )

        self.assertEqual(function1, function2)
        self.assertNotEqual(function1, function3)

    def test_function_apply_args(self):
        def typed_expr(type_obj):
            class Expr(codegen.Expression):
                type = type_obj

                def constrain_type(self, type_obj, from_ftl_source=None):
                    self.type = type_obj

            return Expr()

        function = types.Function.for_multiple_inputs(
            [dtypes.String, dtypes.Number], dtypes.Bool
        )

        zero_applied = function.apply_args([])
        self.assertEqual(
            zero_applied.as_signature(codegen.Module()), "String -> number -> Bool"
        )
        self.assertEqual(zero_applied, function)

        one_applied = function.apply_args([typed_expr(dtypes.String)])
        self.assertEqual(one_applied.as_signature(codegen.Module()), "number -> Bool")
        self.assertEqual(one_applied, types.Function(dtypes.Number, dtypes.Bool))

        two_applied = function.apply_args(
            [typed_expr(dtypes.String), typed_expr(dtypes.Number)]
        )
        self.assertEqual(two_applied.as_signature(codegen.Module()), "Bool")
        self.assertEqual(two_applied, dtypes.Bool)

    def test_unconstrained_signature(self):
        u = types.UnconstrainedType()
        self.assertEqual(u.as_signature(codegen.Module()), "a")

    def test_function_signature_with_type_variables(self):
        function = types.Function.for_multiple_inputs(
            [types.UnconstrainedType(), types.UnconstrainedType()],
            types.UnconstrainedType(),
        )
        self.assertEqual(function.as_signature(codegen.Module()), "a -> b -> c")

    def test_empty_record_signature(self):
        self.assertEqual(types.Record().as_signature(codegen.Module()), "a")

    def test_empty_record_signature_in_function(self):
        function = types.Function(types.Record(), types.UnconstrainedType())
        self.assertEqual(function.as_signature(codegen.Module()), "a -> b")

    def test_one_field_record_signature(self):
        r = types.Record()
        r.add_field("foo", type_obj=dtypes.String)
        self.assertEqual(r.as_signature(codegen.Module()), "{ a | foo : String }")

    def test_two_field_record_signature(self):
        r = types.Record()
        r.add_field("foo", type_obj=dtypes.String)
        r.add_field("bar")
        self.assertEqual(
            r.as_signature(codegen.Module()), "{ a | bar : b, foo : String }"
        )

    def test_one_field_fixed_record_signature(self):
        r = types.Record(foo=dtypes.String)
        self.assertEqual(r.as_signature(codegen.Module()), "{ foo : String }")

    def test_type_variables_complex(self):
        r1 = types.Record()
        r1.add_field("foo")
        r1.add_field("bar")
        r2 = types.Record()
        r2.add_field("baz")
        function = types.Function.for_multiple_inputs(
            [r1, r2], types.UnconstrainedType()
        )
        self.assertEqual(
            function.as_signature(codegen.Module()),
            "{ a | bar : b, foo : c } -> { d | baz : e } -> f",
        )

    def test_non_builtin_simple_types(self):
        source_module = codegen.Module(name="MyModule")
        mytype = types.Type("MyType", source_module)
        self.assertEqual(mytype.as_signature(source_module), "MyType")

        main_module = codegen.Module()
        main_module.add_import(source_module, "MyAlias")
        self.assertEqual(mytype.as_signature(main_module), "MyAlias.MyType")

    def test_type_parameters_signatures(self):
        source_module = codegen.Module(name="MyModule")
        dict_type = types.Type("Dict k v", source_module)
        self.assertEqual(dict_type.as_signature(source_module), "Dict k v")
        env = types.SignatureEnv(used_type_variables={"k": 1, "v": 2})
        self.assertEqual(dict_type.as_signature(source_module, env=env), "Dict k2 v2")
        dict_type = types.Type("Dict k v", source_module)
        str_to_float_dict = dict_type.specialize(k=dtypes.String, v=dtypes.Float)
        self.assertEqual(
            str_to_float_dict.as_signature(source_module), "Dict String Float"
        )

        container_type = types.Type("Container a", source_module)
        complex_type = container_type.specialize(a=dict_type)
        self.assertEqual(
            complex_type.as_signature(source_module), "Container (Dict k v)"
        )

    def test_type_parameters_constructors(self):
        source_module = codegen.Module(name="MyModule")
        container_type = types.Type(
            "Container a", source_module, constructors=["Empty", ("Single", "a")]
        )
        self.assertEqual(container_type.as_signature(source_module), "Container a")
        Empty = source_module.variables["Empty"]
        Single = source_module.variables["Single"]
        self.assertEqual(Empty.type.as_signature(source_module), "Container a")
        self.assertEqual(Single.type.as_signature(source_module), "a -> Container a")

    def test_function_signature_type_parameters(self):
        param = types.TypeParam("a")
        f = types.Function(param, param)
        self.assertEqual(f.as_signature(codegen.Module()), "a -> a")

        f2 = types.Function(param, dtypes.List.specialize(a=param))
        self.assertEqual(f2.as_signature(codegen.Module()), "a -> List a")

    def test_tuple_signature(self):
        module = codegen.Module(name="MyModule")
        t = types.Tuple(dtypes.String, dtypes.Number)
        self.assertEqual(t.as_signature(module), "(String, number)")

    # This, or something like it, would require a better type system
    #
    # def test_type_parameters_function_application(self):
    #     source_module = codegen.Module(name="MyModule")
    #     container_type = types.Type(
    #         "Container a", source_module, constructors=["Empty", ("Single", "a")]
    #     )
    #     Single = source_module.variables["Single"]

    #     # a -> Container a
    #     function_1 = Single.type
    #     applied_1 = function_1.apply_args([codegen.Number(1)])
    #     self.assertEqual(applied_1, container_type.specialize(a=dtypes.Int))

    #     # Container a -> String -> Container a
    #     function_2 = types.Function.for_multiple_inputs(
    #         [container_type, dtypes.String], container_type
    #     )
    #     applied_2 = function_2.apply_args([codegen.String("")])
    #     self.assertEqual(applied_2, container_type.specialize(a=dtypes.String))

    #     # Container a -> String -> a
    #     function_3 = types.Function.for_multiple_inputs(
    #         [container_type, dtypes.String], container_type.param_dict["a"]
    #     )
    #     applied_3 = function_3.apply_args([codegen.String("")])
    #     self.assertEqual(applied_3, dtypes.String)

    def test_type_parameters_constrain(self):
        source_module = codegen.Module(name="MyModule")
        container_type = types.Type("Container a", source_module)
        specialized = container_type.specialize(a=dtypes.Int)
        specialized2 = container_type.specialize(a=dtypes.Int)
        self.assertEqual(specialized, specialized2)
        self.assertNotEqual(specialized, container_type)
        self.assertEqual(specialized.constrain(container_type), specialized)
