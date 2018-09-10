"""
Utilities for doing Python code generation
"""
from __future__ import absolute_import, unicode_literals

import contextlib
import re

import six

from elm_fluent import types

# This module provides simple utilities for building up Elm source code. It
# implements only what is really needed by compiler.py, with a number of aims
# and constraints:
#
# 1. Performance.
#
#    The resulting Elm code should do as little as possible, especially for
#    simple cases (which are by far the most common for .ftl files)
#
# 2. Correctness (obviously)
#
#    In particular, we should try to make it hard to generate incorrect code,
#    esepcially incorrect code that is syntactically correct and therefore
#    compiles but doesn't work. In particular, we try to make it hard to
#    generate accidental name clashes, or use variables that are not defined.
#
# 3. Simplicity
#
#    The resulting Elm code should be easy to read and understand.
#
# 4. Predictability
#
#    Since we want to test the resulting source code, we have made some design
#    decisions that aim to ensure things like function argument names are
#    consistent and so can predicted easily.


class ElmAst(object):
    def __init__(self, from_ftl_source=None):
        self.from_ftl_source = from_ftl_source

    def simplify(self, changes):
        """
        Simplify the statement/expression, returning either a modified
        self, or a new object.

        This method should call .simplify(changes) on any contained subexpressions
        or statements.

        If changes were made, a True value must be appended to the passed in changes list.
        """
        return self

    def sub_expressions(self):
        """
        Returns an iterable of all syntax nodes contained in this node
        """
        raise NotImplementedError(
            "{0} needs to implement sub_expressions".format(self.__class__)
        )

    def finalize(self):
        pass

    def as_source_code(self):
        builder = SourceCodeBuilder()
        self.build_source(builder)
        return builder.render()


class Variables(object):
    def __init__(self, scope):
        self.scope = scope

    def __getitem__(self, item):
        return VariableReference(item, self.scope)


class Scope(ElmAst):
    is_default_imports = False

    def __init__(self, parent_scope=None):
        super(Scope, self).__init__()
        self.parent_scope = parent_scope
        self.names = set()
        self._function_arg_reserved_names = set()
        self._types = {}
        self.variables = Variables(self)

    def names_in_use(self):
        names = self.names
        if self.parent_scope is not None:
            names = names | self.parent_scope.names_in_use()
        return names

    def function_arg_reserved_names(self):
        names = self._function_arg_reserved_names
        if self.parent_scope is not None:
            names = names | self.parent_scope.function_arg_reserved_names()
        return names

    def all_reserved_names(self):
        return self.names_in_use() | self.function_arg_reserved_names()

    def reserve_name(self, requested, function_arg=False, type=None):
        """
        Reserve a name as being in use in a scope.

        Pass function_arg=True if this is a function argument.
        'properties' is an optional dict of additional properties
        (e.g. the type associated with a name)
        """

        def _add(final):
            self.names.add(final)
            if type is not None:
                self._types[final] = type
            return final

        if function_arg:
            if requested in self.function_arg_reserved_names():
                assert requested not in self.names_in_use()
                return _add(requested)
            else:
                if requested in self.all_reserved_names():
                    raise AssertionError(
                        "Cannot use '{0}' as argument name as it is already in use".format(
                            requested
                        )
                    )

        cleaned = cleanup_name(requested)

        attempt = cleaned
        count = 2  # instance without suffix is regarded as 1
        # To avoid shadowing of global names in local scope, we
        # take into account parent scope when assigning names.

        used = self.all_reserved_names()
        while attempt in used:
            attempt = cleaned + str(count)
            count += 1
        return _add(attempt)

    def reserve_function_arg_name(self, name):
        """
        Reserve a name for *later* use as a function argument. This does not result
        in that name being considered 'in use' in the current scope, but will
        avoid the name being assigned for any use other than as a function argument.
        """
        # To keep things simple, and the generated code predictable, we reserve
        # names for all function arguments in a separate scope, and insist on
        # the exact names
        if name in self.all_reserved_names():
            raise AssertionError(
                "Can't reserve '{0}' as function arg name as it is already reserved".format(
                    name
                )
            )
        self._function_arg_reserved_names.add(name)

    def get_type(self, name):
        """
        Gets a dictionary of properties for the name.
        Raises exception if the name is not reserved in this scope or parent
        """
        if name in self._types:
            return self._types[name]
        else:
            if self.parent_scope is None:
                raise KeyError(name)
            return self.parent_scope.get_type(name)

    def set_type(self, name, type):
        """
        Sets the type for the name.
        Raises exception if the name is not reserved in this scope or parent.
        """
        scope = self
        while True:
            if name in scope._types:
                scope._types[name] = type
                break
            else:
                scope = scope.parent_scope

    def get_imported_module(self, name):
        # Chain back until we find a 'Module', which has an implementation
        # for this.
        return self.parent_scope.get_imported_module(name)

    def get_name_qualifier(self, module):
        """
        For a given module, find the local name of that module in this scope
        """
        # Chain back until we a find a 'Module', which has an implementation for this
        return self.parent_scope.get_name_qualifier(module)


_IDENTIFIER_SANITIZER_RE = re.compile("[^a-zA-Z0-9_]")
_IDENTIFIER_START_RE = re.compile("^[a-zA-Z]")


def cleanup_name(name):
    # Choose safe subset of known allowed chars
    name = _IDENTIFIER_SANITIZER_RE.sub("", name)
    if not _IDENTIFIER_START_RE.match(name):
        name = "n" + name
    return name


# Keywords: see
# https://github.com/elm/compiler/blob/master/compiler/src/Parse/Primitives/Keyword.hs#L57
# However, some seem to be accepted fine as function names, they are only
# keywords in some positions it seems. These are commented out.
ELM_KEYWORDS = set(
    [
        "type",
        # "alias",
        "port",
        "if",
        "then",
        "else",
        "case",
        "of",
        "let",
        "in",
        "infix",
        # "left",
        # "right",
        # "non",
        "module",
        "import",
        "exposing",
        "as",
        "where",
        # "effect",
        # "command",
        # "subscription",
        # "true",
        # "false",
        # "null",
    ]
)


class Module(Scope):
    def __init__(self, name=None):
        from .stubs.defaults import default_imports

        super(Module, self).__init__(parent_scope=default_imports)
        self.statements = {}  # Dict from statement number to statement
        self.exports = []
        self.import_dict = {}  # Map from local name to module
        self.name = name

    def __repr__(self):
        return "<Module {0}>".format(self.name)

    def all_reserved_names(self):
        return super(Module, self).all_reserved_names() | ELM_KEYWORDS

    def get_imported_module(self, import_name):
        # Here to avoid circular imports. TODO CLEANUP - more generic mechanism for
        # default imports, while still avoid circular import problem.
        if import_name == "String":
            from .stubs.string import module as string_module

            return string_module
        return self.import_dict[import_name]

    def get_name_qualifier(self, module):
        """
        For a given module, find the qualifer that must be used for that module in this module
        """
        if module is self:
            return ""

        if module.is_default_imports:
            # defaults need no qualifiers
            return ""
        for name, mod in self.import_dict.items():
            if mod == module:
                return name + "."
        raise LookupError(
            "module {0} not found in {1}. Missing 'add_import'?".format(module, self)
        )

    def add_function(self, func_name, func, expose=True, source_order=None):
        assert func.func_name == func_name
        self.exports.append(func_name)

        if source_order is None:
            if not self.statements:
                source_order = 0
            else:
                source_order = max(self.statements.keys()) + 1
        self.statements[source_order] = func

    def add_import(self, module, name):
        self.import_dict[name] = module

    def as_source_code(self, include_module_line=True, include_imports=True):
        lines = []
        if include_module_line:
            assert self.name is not None
            lines.append(
                "module {0} exposing ({1})\n".format(self.name, ", ".join(self.exports))
            )
            lines.append("\n")
        if include_imports and self.import_dict:
            for name, module in sorted(
                self.import_dict.items(), key=lambda pair: pair[1].name
            ):
                if self.import_is_used(name, module):
                    # We only support 'as' imports, to avoid name conflicts
                    # with functions defined in the module
                    lines.append("import {0} as {1}\n".format(module.name, name))
            lines.append("\n")

        for s in self.sorted_statements():
            lines.append(s.as_source_code())
            # blank line
            lines.append("\n\n")
        return "".join(lines)

    def sorted_statements(self):
        return [s for i, s in sorted(self.statements.items(), key=lambda pair: pair[0])]

    def import_is_used(self, local_name, module):
        for node in traverse(self):
            # Check for variable references
            if isinstance(node, VariableReference):
                if node.module_name == local_name:
                    return True

            # Check function signatures
            if isinstance(node, Function):
                function_type = node.type
                if function_type is not None:
                    for t in types.signature_traverse(function_type):
                        if getattr(t, "module", None) == module:
                            return True

        return False

    def simplify(self, changes):
        self.statements = {i: s.simplify(changes) for i, s in self.statements.items()}
        return self

    def sub_expressions(self):
        return self.sorted_statements()


class Statement(ElmAst):
    pass


class _Assignment(Statement):
    def __init__(self, name, value):
        self.name = name
        self.value = value

    # def format_names(self):
    #     if len(self.names) == 1:
    #         return self.names[0]
    #     else:
    #         return "({0})".format(", ".join(n for n in self.names))

    def build_source(self, builder):
        builder.add_part(self.name)
        builder.add_part(" = ")
        self.value.build_source(builder)

    def simplify(self, changes):
        self.value = self.value.simplify(changes)
        return self

    def sub_expressions(self):
        yield self.value


class Function(Scope, Statement):
    def __init__(self, name, args=None, parent_scope=None):
        super(Function, self).__init__(parent_scope=parent_scope)
        self.func_name = name
        self.body = Let(parent_scope=self)
        if args is None:
            args = ()
        self.args = args

        # Get the types of the arguments from the registered function type
        remaining_function_type = self.type
        for arg in args:
            if arg in parent_scope.names_in_use():
                raise AssertionError(
                    "Can't use '{0}' as function argument name because it shadows other names".format(
                        arg
                    )
                )
            if remaining_function_type is not None:
                arg_type = remaining_function_type.input_type
                remaining_function_type = remaining_function_type.output_type
            else:
                arg_type = None
            self.reserve_name(arg, function_arg=True, type=arg_type)

    @property
    def type(self):
        try:
            return self.parent_scope.get_type(self.func_name)
        except KeyError:
            return None

    @type.setter
    def type(self, type_obj):
        self.parent_scope.set_type(self.func_name, type_obj.constrain(self.type))

    def sub_expressions(self):
        yield self.body

    def finalize(self):
        t = self.type
        if t is not None:
            args = self.args
            output_type = t
            for a in args:
                output_type = output_type.output_type
            self.body.constrain_type(output_type)

    def build_source(self, builder):
        if self.parent_scope is None:
            signature = ""
        else:
            function_type = self.type
            if function_type is None:
                signature = ""
            else:
                signature = "{name} : {signature}\n".format(
                    signature=function_type.as_signature(self.parent_scope),
                    name=self.func_name,
                )

        builder.add_part(signature)
        builder.add_part(self.func_name)
        for arg in self.args:
            builder.add_part(" " + arg)

        builder.add_part(" =\n")
        with builder.indented():
            self.body.build_source(builder)

    def simplify(self, changes):
        self.body = self.body.simplify(changes)
        return self


def resolve_type(type_object_or_name):
    # To avoid circular imports, we accept a string to represent types
    # in dtypes
    from .stubs import defaults as dtypes

    if isinstance(type_object_or_name, six.text_type):
        return getattr(dtypes, type_object_or_name)
    else:
        return type_object_or_name


def fixed_type(type_object_or_name):
    class FixedType(object):
        _type_object_or_name = type_object_or_name

        @property
        def type(self):
            return resolve_type(self._type_object_or_name)

    return FixedType


class SourceCodeBuilder(object):
    BLOCK_INDENT_SIZE = 4

    def __init__(self):
        self.parts = []
        self.indent_level = 0
        self.current_line = ""

    def add_part(self, part):
        if self.current_line == "":
            # Add indentation:
            indent = " " * self.indent_level
            self.parts.append(indent)
            self.current_line += indent
        if "\n" in part and part.find("\n") != len(part) - 1:
            raise ValueError(
                "If you pass '\n' to add_part, it must be at the end of string value. Received {0}".format(
                    repr(part)
                )
            )
        self.current_line += part
        if self.current_line.endswith("\n"):
            self.current_line = ""
        self.parts.append(part)

    def render(self):
        return "".join(self.parts)

    @contextlib.contextmanager
    def aligned_block(self):
        old_indent_level = self.indent_level
        if self.current_line == "":
            alignment_level = self.indent_level
        else:
            alignment_level = len(self.current_line)
        self.indent_level = alignment_level
        yield
        self.indent_level = old_indent_level

    @contextlib.contextmanager
    def indented(self):
        self.indent_level += self.BLOCK_INDENT_SIZE
        yield self
        self.indent_level -= self.BLOCK_INDENT_SIZE

    @contextlib.contextmanager
    def parens_if_needed(self, expr):
        # TODO - may need a better way to determine when we need parentheses, that
        # respects operator precedence etc. At the moment the following suffices.
        # Operators do wrapping always to be safe.
        wrapping = not isinstance(
            expr, (Literal, Bracketing, VariableReference, AttributeReference)
        )
        if wrapping:
            self.add_part("(")

        yield self

        if wrapping:
            self.add_part(")")


class Expression(ElmAst):
    # type represents the Elm type this expression will produce,
    # if we know it (UnconstrainedType otherwise).
    @property
    def type(self):
        return types.UnconstrainedType()

    def constrain_type(self, type_obj, from_ftl_source=None):
        raise NotImplementedError(
            "Object {0} of type {1} does not implement constrain_type".format(
                self, type(self)
            )
        )

    # Python 2.7 compatible kwarg syntax
    def apply(self, *args, **kwargs):
        """
        Function application
        """
        from_ftl_source = kwargs.pop("from_ftl_source", None)
        assert not kwargs, "Unexpected keyword args {0}".format(
            ", ".join(kwargs.keys())
        )
        return FunctionCall(self, args, from_ftl_source=from_ftl_source)


class Let(Expression, Scope):
    def __init__(self, parent_scope=None):
        Scope.__init__(self, parent_scope=parent_scope)
        self.value = None
        self.assignments = []

    @property
    def type(self):
        assert self.value is not None
        return self.value.type

    def constrain_type(self, type_obj, from_ftl_source=None):
        return self.value.constrain_type(type_obj.constrain(self.value.type))

    def add_assignment(self, name, value):
        """
        Adds an assigment of the form:

           x = value

        """
        # If needed, we might have to add assignment from tuples here
        assigned_name = self.reserve_name(name, type=value.type)
        self.assignments.append(_Assignment(assigned_name, value))
        return self.variables[name]

    def simplify(self, changes):
        self.value = self.value.simplify(changes)
        for assignment in self.assignments:
            assignment.simplify(changes)
        if len(self.assignments) == 0:
            changes.append(True)
            return self.value
        if len(self.assignments) == 1:
            if isinstance(self.value, VariableReference):
                if self.value.name == self.assignments[0].name:
                    changes.append(True)
                    return self.assignments[0].value
        return self

    def sub_expressions(self):
        return self.assignments + [self.value]

    def build_source(self, builder):
        with builder.aligned_block():
            builder.add_part("let\n")
            with builder.indented():
                for a in self.assignments:
                    a.build_source(builder)
                    builder.add_part("\n")
            builder.add_part("in\n")
            with builder.indented():
                self.value.build_source(builder)


class If(Expression):
    def __init__(
        self, condition=None, true_branch=None, false_branch=None, parent_scope=None
    ):
        self.condition = condition
        self.true_branch = true_branch or Let(parent_scope=parent_scope)
        self.false_branch = false_branch or Let(parent_scope=parent_scope)

    @property
    def type(self):
        # TODO - can we do better than just returning the true branch
        # Does it matter?
        return self.true_branch.type

    def constrain_type(self, type_obj, from_ftl_source=None):
        self.true_branch.constrain_type(
            type_obj.constrain(self.true_branch.type), from_ftl_source=from_ftl_source
        )
        self.false_branch.constrain_type(
            type_obj.constrain(self.false_branch.type), from_ftl_source=from_ftl_source
        )

    def build_source(self, builder):
        with builder.aligned_block():
            builder.add_part("if ")
            self.condition.build_source(builder)
            builder.add_part(" then\n")
            with builder.indented():
                self.true_branch.build_source(builder)
                builder.add_part("\n")
            builder.add_part("else\n")
            with builder.indented():
                self.false_branch.build_source(builder)

    def sub_expressions(self):
        yield self.condition
        yield self.true_branch
        yield self.false_branch

    def simplify(self, changes):
        self.condition = self.condition.simplify(changes)
        self.true_branch = self.true_branch.simplify(changes)
        self.false_branch = self.false_branch.simplify(changes)
        return self


class Case(Expression):
    def __init__(self, selector=None, parent_scope=None):
        self.parent_scope = parent_scope
        self.selector = selector
        self.branches = []

    def add_branch(self, matcher):
        value = Let(self.parent_scope)
        self.branches.append((matcher, value))
        return value

    def build_source(self, builder):
        with builder.aligned_block():
            builder.add_part("case ")
            self.selector.build_source(builder)
            builder.add_part(" of\n")
            with builder.indented():
                for matcher, value in self.branches:
                    matcher.build_source(builder)
                    builder.add_part(" ->\n")
                    with builder.indented():
                        value.build_source(builder)
                        builder.add_part("\n")

    @property
    def type(self):
        assert len(self.branches) > 0
        # TODO - can we do better than just returning the first one?
        # Does it matter?
        return self.branches[0][1].type

    def constrain_type(self, type_obj, from_ftl_source=None):
        for m, val in self.branches:
            val.constrain_type(
                type_obj.constrain(val.type), from_ftl_source=from_ftl_source
            )

    def sub_expressions(self):
        yield self.selector
        for matcher, value in self.branches:
            yield matcher
            yield value

    def simplify(self, changes):
        self.selector = self.selector.simplify(changes)
        self.branches = [
            (matcher.simplify(changes), value.simplify(changes))
            for matcher, value in self.branches
        ]
        return self


class Literal(Expression):
    def sub_expressions(self):
        return []

    def constrain_type(self, type_obj, from_ftl_source=None):
        t = type_obj.constrain(self.type)
        assert t is self.type, "Expected {0} is {1}".format(t, self.type)


class Bracketing(object):
    """
    Sentinel class to indicate expression that do their own bracketing
    so don't need extra parenthesis
    """

    pass


class String(fixed_type("String"), Literal):
    def __init__(self, string_value):
        self.string_value = string_value

    def __repr__(self):
        return "<String {0}>".format(repr(self.string_value))

    def build_source(self, builder):
        # TODO - escapes for other chars?
        builder.add_part(
            '"{0}"'.format(self.string_value.replace('"', '\\"').replace("\n", "\\n"))
        )


class Number(fixed_type("Number"), Literal):
    def __init__(self, number):
        self.number = number

    def build_source(self, builder):
        # TODO - Are there cases where this won't work?
        builder.add_part(repr(self.number))


class List(Bracketing, Expression):
    def __init__(self, items):
        self.items = items

    @property
    def type(self):
        # TODO - can we do better than just using the first one?
        # Does it matter?
        from .stubs import defaults as dtypes

        if self.items:
            return dtypes.List.specialize(a=self.items[0].type)
        else:
            return dtypes.List

    def constrain_type(self, type_obj, from_ftl_source=None):
        list_type = type_obj.constrain(self.type)
        val_type = list_type.param_dict["a"]
        for val in self.items:
            val.constrain_type(
                val_type.constrain(val.type), from_ftl_source=from_ftl_source
            )

    def build_source(self, builder):
        if len(self.items) == 0:
            builder.add_part("[]")
        else:
            with builder.aligned_block():
                for i, item in enumerate(self.items):
                    if i == 0:
                        builder.add_part("[ ")
                    else:
                        builder.add_part(", ")
                    item.build_source(builder)
                    builder.add_part("\n")
                builder.add_part("]")

    def sub_expressions(self):
        return self.items

    def simplify(self, changes):
        self.items = [item.simplify(changes) for item in self.items]
        return self


class Concat(Expression):
    def __init__(self, parts, from_ftl_source=None):
        super(Concat, self).__init__(from_ftl_source=from_ftl_source)
        self.parts = parts

    def __repr__(self):
        return "<Concat {0}>".format(repr(self.parts))

    def sub_expressions(self):
        return self.parts

    def constrain_type(self, type_obj, from_ftl_source=None):
        for part in self.parts:
            part.constrain_type(
                type_obj.constrain(part.type), from_ftl_source=from_ftl_source
            )

    def build_source(self, builder):
        builder.add_part(self.function_call + " ")
        List(self.parts).build_source(builder)

    def simplify(self, changes):
        # Simplify sub parts
        self.parts = [part.simplify(changes) for part in self.parts]

        # Merge adjacent List(like) objects.
        new_parts = []
        for part in self.parts:
            if (
                len(new_parts) > 0
                and isinstance(new_parts[-1], self.literal)
                and isinstance(part, self.literal)
            ):
                new_parts[-1] = self.merge_two(new_parts[-1], part)
            else:
                if not self.is_empty(part):
                    new_parts.append(part)
        if len(new_parts) < len(self.parts):
            changes.append(True)
        self.parts = new_parts

        # See if we can eliminate the Concat altogether
        if len(self.parts) == 0:
            changes.append(True)
            return self.empty()
        elif len(self.parts) == 1:
            changes.append(True)
            return self.parts[0]
        else:
            return self


class StringConcat(fixed_type("String"), Concat):
    literal = String
    function_call = "String.concat"

    def is_empty(self, part):
        return isinstance(part, String) and part.string_value == ""

    def empty(self):
        return self.literal("")

    def merge_two(self, part1, part2):
        return self.literal(part1.string_value + part2.string_value)


class ListConcat(Concat):
    def __init__(self, parts, type_obj):
        self.parts = parts
        self._type = type_obj

    @property
    def type(self):
        return self._type

    def constrain_type(self, type_obj, from_ftl_source=None):
        assert type_obj == self._type, "Expected {0} == {1}".format(
            type_obj, self._type
        )
        for p in self.parts:
            p.constrain_type(type_obj, from_ftl_source=from_ftl_source)

    literal = List
    function_call = "List.concat"

    def is_empty(self, part):
        return isinstance(part, List) and len(part.items) == 0

    def empty(self):
        return self.literal([])

    def merge_two(self, part1, part2):
        return self.literal(part1.items + part2.items)


class VariableReference(Expression):
    # Instead of using this directly, normally use
    # scope.variables[qualified_name] for convenience and readability
    def __init__(self, qualified_name, scope):
        super(VariableReference, self).__init__()
        if "." in qualified_name:
            module_name, name = qualified_name.split(".")
        else:
            module_name = None
            name = qualified_name
        if module_name is not None:
            definition_scope = scope.get_imported_module(module_name)
        else:
            definition_scope = scope
        if name not in definition_scope.names_in_use():
            raise AssertionError("Cannot refer to undefined name '{0}'".format(name))

        self._definition_scope = definition_scope
        self.module_name = module_name
        self.name = name

    @property
    def type(self):
        return self._definition_scope.get_type(self.name)

    def constrain_type(self, type_obj, from_ftl_source=None):
        self._definition_scope.set_type(self.name, type_obj.constrain(self.type))

    def build_source(self, builder):
        builder.add_part(
            ((self.module_name + ".") if self.module_name is not None else "")
            + self.name
        )

    def sub_expressions(self):
        return []

    def __repr__(self):
        return "<VariableReference {0}>".format(self.as_source_code())


class AttributeReference(Expression):
    def __init__(self, variable, attribute_name):
        self.variable = variable
        self.attribute_name = attribute_name
        assert isinstance(variable.type, types.Record)
        variable.type.add_field(attribute_name)

    @property
    def type(self):
        return self.variable.type.fields[self.attribute_name]

    def constrain_type(self, type_obj, from_ftl_source=None):
        self.variable.type.add_field(
            self.attribute_name, type_obj, from_ftl_source=from_ftl_source
        )

    def __repr__(self):
        return "<AttributeReference {0}.{1}>".format(
            repr(self.variable), self.attribute_name
        )

    def build_source(self, builder):
        self.variable.build_source(builder)
        builder.add_part(".")
        builder.add_part(self.attribute_name)

    def sub_expressions(self):
        yield self.variable


class FunctionCall(Expression):
    # Instead of using this directly, normally use expr.apply()
    def __init__(self, expr, args, from_ftl_source=None):
        super(FunctionCall, self).__init__(from_ftl_source=from_ftl_source)
        self.expr = expr
        self.args = args
        self._type = self.expr.type.apply_args(
            self.args, from_ftl_source=from_ftl_source
        )

    @property
    def type(self):
        return self._type

    def constrain_type(self, type_obj, from_ftl_source=None):
        # Currently all our functions have fully concrete return types,
        # so we don't need anything beyond this:
        assert self.type == type_obj, "Expected {0} == {1}".format(self.type, type_obj)

    def __repr__(self):
        return "<FunctionCall {0} {1}>".format(
            self.expr.as_source_code(), " ".join(repr(a) for a in self.args)
        )

    def build_source(self, builder):
        self.expr.build_source(builder)
        for arg in self.args:
            builder.add_part(" ")
            with builder.parens_if_needed(arg):
                arg.build_source(builder)

    def sub_expressions(self):
        return [self.expr] + list(self.args)

    def simplify(self, changes):
        self.args = [arg.simplify(changes) for arg in self.args]
        return self


class Otherwise(Expression):
    def __init__(self):
        self._type = types.UnconstrainedType()

    @property
    def type(self):
        return self._type

    def constrain_type(self, type_obj, from_ftl_source=None):
        self._type = type_obj.constrain(self._type)

    def sub_expressions(self):
        return []

    def build_source(self, builder):
        builder.add_part("_")


class CompilationError(Expression):
    def __init__(self, type_obj=None):
        if type_obj is None:
            type_obj = types.UnconstrainedType()
        self._type = type_obj

    @property
    def type(self):
        return self._type

    def constrain_type(self, type_obj, from_ftl_source=None):
        # Just assign without complaining
        self._type = type_obj

    def build_source(self, builder):
        # Return something that will definitely cause the Elm code to fail to
        # compile. Normally the value is not written out anywhere. It exists as
        # an Expression to allow compilation to continue, so that as many error
        # messages as possible can be collected instead of quitting early.
        builder.add_part("!!!COMPILATION_ERROR!!!")

    def sub_expressions(self):
        return []


def infix_operator(operator, return_type, operand_type):
    class Op(fixed_type(return_type), Bracketing, Expression):
        def __init__(self, left, right):
            self.left = left
            self.right = right

        def build_source(self, builder):
            builder.add_part("(")
            self.left.build_source(builder)
            builder.add_part(" " + operator + " ")
            self.right.build_source(builder)
            builder.add_part(")")

        def simplify(self, changes):
            self.left = self.left.simplify(changes)
            self.right = self.right.simplify(changes)
            return self

        def sub_expressions(self):
            yield self.left
            yield self.right

        def constrain_type(self, type_obj, from_ftl_source=None):
            self.left.constrain_type(type_obj.constrain(resolve_type(operand_type)))
            self.right.constrain_type(type_obj.constrain(resolve_type(operand_type)))

    return Op


Equals = infix_operator("==", "Bool", types.UnconstrainedType())
Add = infix_operator("+", "Number", "Number")


class RecordUpdate(Bracketing, Expression):
    def __init__(self, var, **updates):
        assert isinstance(
            var.type, types.Record
        ), "isinstance({0}, types.Record)".format(var.type)
        assert isinstance(
            var, VariableReference
        ), "isinstance({0}, VariableReference)".format(var)
        assert (
            var.module_name is None
        ), "Record update syntax does not allow qualified name like {0}.{1}".format(
            var.module_name, var.name
        )
        self.var = var
        self.updates = updates
        for name, val in updates.items():
            var.type.add_field(name, val.type)

    @property
    def type(self):
        return self.var.type

    def constrain_type(self, type_obj, from_ftl_source=None):
        self.var.constrain_type(
            type_obj.constrain(self.var.type), from_ftl_source=from_ftl_source
        )

    def sub_expressions(self):
        for name, val in self.updates.items():
            yield val

    def build_source(self, builder):
        builder.add_part("{ ")
        self.var.build_source(builder)
        builder.add_part(" | ")
        for i, (name, val) in enumerate(sorted(self.updates.items())):
            builder.add_part(name)
            builder.add_part(" = ")
            val.build_source(builder)
            if i < len(self.updates) - 1:
                builder.add_part(", ")
        builder.add_part(" }")


def simplify(source_code):
    # Can't use 'traverse' for simplify because of the way it needs to change
    # the actual tree itself.
    finalize(source_code)

    changes = [True]
    while any(changes):
        changes = []
        source_code = source_code.simplify(changes)
    return source_code


def traverse(node):
    sub_parts = node.sub_expressions()
    for part in sub_parts:
        for t in traverse(part):
            yield t
    yield node


def finalize(source_code):
    for node in traverse(source_code):
        node.finalize()
