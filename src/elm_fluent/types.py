from __future__ import annotations

import dataclasses
from collections import OrderedDict
from dataclasses import dataclass
from functools import wraps

# This module provides help with basic type checking/tracking for the
# codegen.ElmAst objects, plus the ability to generate type signatures.


def with_auto_env(meth):
    @wraps(meth)
    def wrapper(self, from_module, env: SignatureEnv | None = None):
        if env is None:
            env = SignatureEnv()
        return meth(self, from_module, env=env)

    return wrapper


@dataclass
class SignatureEnv:
    """
    Environment object for creating type/function signatures
    """

    used_type_variables: dict[str, ElmType] = dataclasses.field(default_factory=dict)


class ElmType:
    def apply_args(self, args):
        if len(args) > 0:
            raise AssertionError(f"{self} is not a function, cannot apply arguments to it")
        return self

    def signature_sub_types(self):
        """
        Returns all the type objects that would appear in a signature
        """
        raise NotImplementedError(f"{self.__class__} needs to implement signature_sub_types")


class UnconstrainedType(ElmType):
    @with_auto_env
    def as_signature(self, from_module, env: SignatureEnv) -> str:
        # This fails if we reach 'z', which is unlikely
        if not env.used_type_variables:
            retval = "a"
        else:
            retval = chr(max(map(ord, env.used_type_variables)) + 1)
        env.used_type_variables[retval] = self
        return retval

    def signature_sub_types(self):
        return []


class TypeParam(UnconstrainedType):
    def __init__(self, preferred_name):
        self.preferred_name = preferred_name

    @with_auto_env
    def as_signature(self, from_module, env: SignatureEnv):
        for v, t in env.used_type_variables.items():
            if t is self:
                return v
        c = 1
        candidate = self.preferred_name
        while candidate in env.used_type_variables:
            c = c + 1
            candidate = f"{self.preferred_name}{c}"
        env.used_type_variables[candidate] = self
        return candidate

    def __eq__(self, other):
        # This is a really weak check, but deliberately relaxes things enough
        # so we can easily get signatures to work the way we need
        return isinstance(other, TypeParam)


class Type(ElmType):
    def __init__(self, full_name, module, params=None, constructors=None, reserve_names=True):
        """
        Construct a union type.
        constructors is a list of constructors, where each constructor is a:
           string - for nullary constructors
           tuple of (string, types...) - for constructors with type parameters
        """

        if " " in full_name:
            assert params is None, "Either pass params, or auto created using spaces in name"
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
            if isinstance(c, str):
                name = c
                params = ()
                constructor_type = self
            else:
                name, params = c[0], tuple(c[1:])
                params = [self.param_dict[p] if isinstance(p, str) else p for p in params]
                constructor_type = Function.for_multiple_inputs(params, self)

            if reserve_names:
                reserved_name = module.reserve_name(name, type=constructor_type)
                assert reserved_name == name, f"Expected {reserved_name} == {name}"

            if module.is_default_imports:
                from . import codegen

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
        return isinstance(other, Type) and (self.module == other.module) and (self.name == other.name)

    def __str__(self):
        return self.as_signature(dummy_module)

    def __repr__(self):
        return f"<ElmType: {str(self)}>"

    @with_auto_env
    def as_signature(self, from_module, env=None):
        return f"{from_module.get_name_qualifier(self.module)}{self.name}" + "".join(
            " " + type_paren_wrap(t.as_signature(from_module, env=env)) for n, t in self.param_dict.items()
        )

    def signature_sub_types(self):
        return self.param_dict.values()

    def specialize(self, **params):
        retval = self.clone()
        for name, type_obj in params.items():
            if name not in retval.param_dict:
                raise LookupError(f"{name} is not a parameter of type {self}")
            retval.param_dict[name] = type_obj
        return retval

    def clone(self):
        retval = self.__class__(self.name, self.module, params=None, constructors=None, reserve_names=False)
        retval.param_dict.update(self.param_dict)
        return retval


class Tuple(Type):
    def __init__(self, *param_types):
        type_params = [TypeParam(chr(ord("a") + i)) for i in range(len(param_types))]
        super().__init__("Tuple", None, params=type_params, reserve_names=False)
        for type_param, param_type in zip(type_params, param_types):
            self.param_dict[type_param.preferred_name] = param_type

    @with_auto_env
    def as_signature(self, from_module, env=None):
        return f"({', '.join(t.as_signature(from_module, env=env) for n, t in self.param_dict.items())})"


def type_paren_wrap(sig):
    if " " in sig and not (sig.startswith("(") and sig.endswith(")")):
        return f"({sig})"
    else:
        return sig


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

    def add_field(self, name, type_obj=None, ftl_sources=None):
        """
        Add a field, or set the type for an existing field.
        """
        if type_obj is None:
            type_obj = UnconstrainedType()
        if name in self.fields:
            # Ideally would assert that types match here, but we don't
            # have a complete enough model of Elm type system
            return
        if self.fixed:
            raise AssertionError(
                f"Cannot add field {name} to a fixed record type, only {', '.join(self.fields.keys())} available"
            )
        self.fields[name] = type_obj

    @with_auto_env
    def as_signature(self, from_module, env: SignatureEnv):
        def fields_signature() -> str:
            return ", ".join(
                f"{name} : {type_obj.as_signature(from_module, env=env)}"
                for name, type_obj in sorted(self.fields.items())
            )

        if self.fixed:
            return "{ " + fields_signature() + " }"
        else:
            base = UnconstrainedType().as_signature(from_module, env=env)
            if not self.fields:
                return base
            else:
                return "{ " + base + " | " + fields_signature() + " }"

    def signature_sub_types(self):
        return self.fields.values()


class Function(ElmType):
    def __init__(self, input_type, output_type):
        # In Elm, functions always have a single input, and a single output. We
        # have conveniences for 'multiple input' functions later.
        self.input_type = input_type
        self.output_type = output_type

    def __repr__(self):
        return f"<Function: {self.as_signature(dummy_module)}>"

    def __eq__(self, other):
        return (
            isinstance(other, Function)
            and (self.input_type == other.input_type)
            and (self.output_type == other.output_type)
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
        return f"{self.input_type.as_signature(from_module, env=env)} -> {self.output_type.as_signature(from_module, env=env)}"

    def signature_sub_types(self):
        return [self.input_type, self.output_type]

    def apply_args(self, args, ftl_source=None):
        """
        Returns that type that would remain after the supplied arguments
        (which are expression objects) are applied.
        """
        if len(args) == 0:
            return self
        _, remainder = args[0], args[1:]
        return self.output_type.apply_args(remainder)


class DummyModule:
    def get_name_qualifier(self, module):
        return ""


dummy_module = DummyModule()


def signature_traverse(type_obj):
    sub_parts = type_obj.signature_sub_types()
    for part in sub_parts:
        yield from signature_traverse(part)
    yield type_obj


class ConflictType(Type):
    @with_auto_env
    def as_signature(self, from_module, env=None):
        return "COMPILATION ERROR"


Conflict = ConflictType("(conflicted-type)", dummy_module)  # Sentinel value
