from __future__ import absolute_import, unicode_literals

from collections import OrderedDict, defaultdict
from functools import wraps

import attr
import six

from elm_fluent import exceptions

# This module is the heart of the type tracking the compiler does. Types are
# associated with node objects in the codegen.py. It is currently rather adhoc
# and incomplete, but suffices for our purposes.
#
# There are 4 main purposes of this type tracking:
#
# 1. To prevent (or provide early feedback) for many type errors in the development
#    of the compiler, so that generated code has a much better chance of at least
#    being type correct.
#
# 2. To catch many type errors the users (i.e. FTL authors) might make, for example
#    if a message has both `DATETIME($arg)` and `NUMBER($arg)` it is a clear type error
#
# 3. For tracing the types we need to work out what conversions need to be done
#    at which stage e.g. numbers need to be run through NumberFormat.format
#    eventually if they need to be converted to strings, but not eagerly because
#    select expressions need to handle them as numbers.
#
# 4. For determining the correct types of the passed in record argument, so that we can
#    generate correct type signatures for the generated functions.
#
# However, for item 1, while the current code worked OK initially, after the
# addition of type parameters there are now many bugs e.g. an expression like
# `Maybe.Just.apply(codegen.Number(1))` should have a type of 'Maybe Int', but
# actually returns 'Maybe a', all TypeParams are considered equal to each other
# etc.
#
# These do not currently affect the correctness of output. To fix these issues,
# and others marked as TODO in this module, it would probably be best to start
# over with this whole type system, using proper Hindler-Milney type inference
# perhaps. See
# https://github.com/rob-smallshire/hindley-milner-python/blob/master/inference.py


def with_auto_env(meth):
    @wraps(meth)
    def wrapper(self, from_module, env=None):
        if env is None:
            env = SignatureEnv()
        return meth(self, from_module, env=env)

    return wrapper


@attr.s
class SignatureEnv(object):
    """
    Environment object for creating type/function signatures
    """

    used_type_variables = attr.ib(factory=dict)


class ElmType(object):
    def constrain(self, other):
        """
        Constrain the other type to be compatible with (equal to or more specific
        than) self May return a new object, other unchanged, or other mutated.
        (TODO - would be cleaner if it never mutated, only returned new
        objects).

        """
        raise NotImplementedError(
            "{0} needs to implement 'constrain'".format(self.__class__)
        )

    def apply_args(self, args):
        if len(args) > 0:
            raise AssertionError(
                "{0} is not a function, cannot apply arguments to it".format(self)
            )
        return self

    def signature_sub_types(self):
        """
        Returns all the type objects that would appear in a signature
        """
        raise NotImplementedError(
            "{0} needs to implement signature_sub_types".format(self.__class__)
        )


class UnconstrainedType(ElmType):
    def constrain(self, other):
        return other

    @with_auto_env
    def as_signature(self, from_module, env=None):
        # This fails if we reach 'z', which is unlikely
        if not env.used_type_variables:
            retval = "a"
        else:
            retval = six.unichr(max(map(ord, env.used_type_variables)) + 1)
        env.used_type_variables[retval] = self
        return retval

    def signature_sub_types(self):
        return []


class TypeParam(UnconstrainedType):
    def __init__(self, preferred_name):
        self.preferred_name = preferred_name

    def constrain(self, other):
        if isinstance(other, UnconstrainedType):
            return self
        else:
            return other

    @with_auto_env
    def as_signature(self, from_module, env=None):
        for v, t in env.used_type_variables.items():
            if t is self:
                return v
        c = 1
        candidate = self.preferred_name
        while candidate in env.used_type_variables:
            c = c + 1
            candidate = "{0}{1}".format(self.preferred_name, c)
        env.used_type_variables[candidate] = self
        return candidate

    def __eq__(self, other):
        # This is a really weak check, but deliberately relaxes things enough
        # so we can easily get signatures to work the way we need
        return isinstance(other, TypeParam)


class Type(ElmType):
    def __init__(
        self, full_name, module, params=None, constructors=None, reserve_names=True
    ):
        """
        Construct a union type.
        constructors is a list of constructors, where each constructor is a:
           string - for nullary constructors
           tuple of (string, types...) - for constructors with type parameters
        """

        from . import codegen

        if " " in full_name:
            assert (
                params is None
            ), "Either pass params, or auto created using spaces in name"
            parts = full_name.split(" ")
            name, param_names = parts[0], tuple(parts[1:])
            params = [TypeParam(p) for p in param_names]
        else:
            name = full_name
            if params is None:
                params = []
        self.name = name
        param_dict = OrderedDict()
        for p in params:
            param_dict[p.preferred_name] = p
        self.param_dict = param_dict
        self.module = module
        if constructors is None:
            constructors = []

        for c in constructors:
            if isinstance(c, six.text_type):
                name = c
                params = ()
                constructor_type = self
            else:
                name, params = c[0], tuple(c[1:])
                params = [
                    self.param_dict[p] if isinstance(p, six.text_type) else p
                    for p in params
                ]
                constructor_type = Function.for_multiple_inputs(params, self)

            if reserve_names:
                reserved_name = module.reserve_name(name, type=constructor_type)
                assert reserved_name == name, "Expected {0} == {1}".format(
                    reserved_name, name
                )

            if module.is_default_imports:
                # For builtins, we attach a name to self for easy access.
                attr_name = name
                # For 'True', 'False' etc, we have to avoid a clash with Python keywords.
                # Could use module 'keyword.kwlist', but this is different on Python 2.
                if attr_name in ["True", "False"]:
                    attr_name += "_"

                setattr(self, attr_name, codegen.VariableReference(name, module))

    def __eq__(self, other):
        return self._is_compatible(other) and (self.param_dict == other.param_dict)

    def _is_compatible(self, other):
        return (
            isinstance(other, Type)
            and (self.module == other.module)
            and (self.name == other.name)
        )

    def __str__(self):
        return self.as_signature(dummy_module)

    def __repr__(self):
        return "<ElmType: {0}>".format(str(self))

    @with_auto_env
    def as_signature(self, from_module, env=None):
        return "{0}{1}".format(
            from_module.get_name_qualifier(self.module), self.name
        ) + "".join(
            " " + type_paren_wrap(t.as_signature(from_module, env=env))
            for n, t in self.param_dict.items()
        )

    def signature_sub_types(self):
        return self.param_dict.values()

    def constrain(self, other):
        if isinstance(other, UnconstrainedType):
            return self
        if not self._is_compatible(other):
            raise exceptions.TypeMismatch(
                "{0} is not compatible with {1}".format(self, other)
            )
        diff_params = {
            n: p
            for n, p in self.param_dict.items()
            if other.param_dict[n] != self.param_dict[n]
        }
        if diff_params:
            retval = other.specialize(**diff_params)
        else:
            retval = self
        return retval

    def specialize(self, **params):
        retval = self.clone()
        for name, type_obj in params.items():
            if name not in retval.param_dict:
                raise LookupError(
                    "{0} is not a parameter of type {1}".format(name, self)
                )
            retval.param_dict[name] = type_obj.constrain(self.param_dict[name])
        return retval

    def clone(self):
        retval = self.__class__(
            self.name, self.module, params=None, constructors=None, reserve_names=False
        )
        retval.param_dict.update(self.param_dict)
        return retval


class Tuple(Type):
    def __init__(self, *param_types):
        type_params = [
            TypeParam(six.unichr(ord("a") + i)) for i in range(len(param_types))
        ]
        super(Tuple, self).__init__(
            "Tuple", None, params=type_params, reserve_names=False
        )
        for type_param, param_type in zip(type_params, param_types):
            self.param_dict[type_param.preferred_name] = param_type

    def clone(self):
        retval = self.__class__(self.name)
        retval.param_dict.update(self.param_dict)
        return retval

    @with_auto_env
    def as_signature(self, from_module, env=None):
        return "({0})".format(
            ", ".join(
                t.as_signature(from_module, env=env) for n, t in self.param_dict.items()
            )
        )


def type_paren_wrap(sig):
    if " " in sig and not (sig.startswith("(") and sig.endswith(")")):
        return "({0})".format(sig)
    else:
        return sig


@attr.s
class TypeSource(object):
    ftl_source = attr.ib()
    type_obj = attr.ib()


class Record(ElmType):
    def __init__(self, **fields):
        """
        Pass fields as keyword args to create a fixed record type,
        or no parameters to create one that is extensible
        """
        self.fields = {}  # Dict from name to type
        self.fixed = False
        for name, type_obj in fields.items():
            self.add_field(name, type_obj)
        self.fixed = bool(fields)
        if not self.fixed:
            self.field_type_ftl_sources = defaultdict(list)

    def add_field(self, name, type_obj=None, from_ftl_source=None):
        """
        Add a field, or set the type for an existing field.
        """
        if type_obj is None:
            type_obj = UnconstrainedType()
        if name in self.fields:
            if self.fixed:
                assert type_obj.constrain(self.fields[name])
            else:
                if from_ftl_source is not None and type_obj != self.fields[name]:
                    self.field_type_ftl_sources[name].append(
                        TypeSource(from_ftl_source, type_obj)
                    )
                try:
                    new_type = type_obj.constrain(self.fields[name])
                except exceptions.TypeMismatch as e:
                    raise exceptions.RecordTypeMismatch(
                        *e.args, record_type=self, field_name=name
                    )
                self.fields[name] = new_type
        else:
            if self.fixed:
                raise AssertionError(
                    "Cannot add field {0} to a fixed record type, only {1} available".format(
                        name, ", ".join(self.fields.keys())
                    )
                )
            self.fields[name] = type_obj
            if from_ftl_source is not None:
                self.field_type_ftl_sources[name].append(
                    TypeSource(from_ftl_source, type_obj)
                )

    def constrain(self, other):
        if isinstance(other, UnconstrainedType):
            return self

        if not isinstance(other, Record):
            raise exceptions.TypeMismatch(
                "Expected type {0} is not compatible with a record type".format(other)
            )

        if other.fixed:
            for n in self.fields:
                if n not in other.fields:
                    raise exceptions.TypeMismatch(
                        "Unexpected field {0}, only {1} available".format(
                            n, ", ".join(self.other.keys())
                        )
                    )
        else:
            # TODO - it would be cleaner if we were returning a clone here,
            # but it gets really tricky to re-associate the new object as part
            # of the type of the codegen.Function objects create.
            for n, t in self.fields.items():
                other.field_type_ftl_sources[n].extend(self.field_type_ftl_sources[n])
                other.add_field(n, t)

        return other

    @with_auto_env
    def as_signature(self, from_module, env=None):
        def fields_signature():
            return ", ".join(
                "{0} : {1}".format(name, type_obj.as_signature(from_module, env=env))
                for name, type_obj in sorted(self.fields.items())
            )

        if self.fixed:
            return "{ %s }" % fields_signature()
        else:
            base = UnconstrainedType().as_signature(from_module, env=env)
            if not self.fields:
                return base
            else:
                return "{ %s | %s }" % (base, fields_signature())

    def signature_sub_types(self):
        return self.fields.values()


class Function(ElmType):
    def __init__(self, input_type, output_type):
        # In Elm, functions always have a single input, and a single output. We
        # have conveniences for 'multiple input' functions later.
        self.input_type = input_type
        self.output_type = output_type

    def __repr__(self):
        return "<Function: {0}>".format(self.as_signature(dummy_module))

    def __eq__(self, other):
        return (
            isinstance(other, Function)
            and (self.input_type == other.input_type)
            and (self.output_type == other.output_type)
        )

    def constrain(self, other):
        assert isinstance(other, Function), "Expecting {0} to be a Function".format(
            other
        )
        return Function(
            other.input_type.constrain(self.input_type),
            other.output_type.constrain(self.output_type),
        )

    @staticmethod
    def for_multiple_inputs(input_types, output_type):
        if len(input_types) == 0:
            return output_type
        if len(input_types) == 1:
            return Function(input_types[0], output_type)
        else:
            return Function(
                input_types[0],
                Function.for_multiple_inputs(input_types[1:], output_type),
            )

    @with_auto_env
    def as_signature(self, from_module, env=None):
        return "{0} -> {1}".format(
            self.input_type.as_signature(from_module, env=env),
            self.output_type.as_signature(from_module, env=env),
        )

    def signature_sub_types(self):
        return [self.input_type, self.output_type]

    def apply_args(self, args, from_ftl_source=None):
        """
        Returns that type that would remain after the supplied arguments
        (which are expression objects) are applied.

        Also applies type constraints to the args.
        """
        if len(args) == 0:
            return self
        arg, remainder = args[0], args[1:]

        # 1. Suppose we have a function
        #  { a | foo : String } -> String
        # and an empty record type {}.
        # When we apply the function to the type,
        # the record type ought to gain a 'foo : String' field

        # 2. Suppose we have a function
        #  List a -> a
        # and an input
        #  List String
        #
        # When we apply the function to the type,
        # the output type should end up as String.
        #
        # TODO fix this second case somehow???

        arg.constrain_type(self.input_type, from_ftl_source=from_ftl_source)
        return self.output_type.apply_args(remainder)


class DummyModule(object):
    def get_name_qualifier(self, module):
        return ""


dummy_module = DummyModule()


def signature_traverse(type_obj):
    sub_parts = type_obj.signature_sub_types()
    for part in sub_parts:
        for t in signature_traverse(part):
            yield t
    yield type_obj
