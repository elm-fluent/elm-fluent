import contextlib
import dataclasses
from dataclasses import dataclass
from functools import singledispatch

from fluent.syntax import ast

from elm_fluent.types import ConflictType

from .utils import FtlSource, get_ast_nodes, is_cldr_plural_form_key, reference_to_id


@dataclass(frozen=True)
class Type:
    name: str


String = Type("String")
Number = Type("Number")
DateTime = Type("DateTime")


@dataclass
class InferredType:
    type: Type
    evidences: list[FtlSource] = dataclasses.field(default_factory=list)


@dataclass
class Conflict:
    types: list[InferredType]
    # FtlSource instance for Message
    # message_source can be None when compiling master function
    message_source: FtlSource | None = None


@dataclass
class CurrentEnvironment:
    message_id: str | None = None


@dataclass
class InferenceEnvironment:
    source_filename: str
    messages_string: str
    known_arg_types: dict
    current: CurrentEnvironment = dataclasses.field(default_factory=CurrentEnvironment)

    @contextlib.contextmanager
    def modified(self, **replacements):
        """
        Context manager that modifies the 'current' attribute of the
        environment, restoring the old data at the end.
        """
        old_current = self.current
        self.current = dataclasses.replace(old_current, **replacements)
        yield self
        self.current = old_current

    def ftl_source_for_expr(self, expr):
        return FtlSource(
            expr=expr,
            message_id=self.current.message_id,
            source_filename=self.source_filename,
            messages_string=self.messages_string,
        )


def infer_arg_types(message_dict, sorted_message_ids, source_filename, messages_string):
    """
    For a input of {message_id: Message} and a list of message_ids giving
    the order in which to process them, returns a dictionary
    {message_id: arg_types}, where arg_types is a dictionary from
    {arg_name: arg_type}, where arg_type is InferredType or Conflict
    """
    output = {}
    env = InferenceEnvironment(
        source_filename=source_filename,
        messages_string=messages_string,
        known_arg_types=output,
    )
    for message_id in sorted_message_ids:
        msg = message_dict[message_id]
        inferred_types = []  # (name, InferredType or None)
        with env.modified(message_id=message_id):
            for expr in get_ast_nodes(msg):
                inferred_types.extend(infer(expr, env))
            output[message_id] = combine_inferred_types(inferred_types, env.ftl_source_for_expr(msg))

    return output


@singledispatch
def infer(expr, env):
    """
    Handles FTL AST `expr`, return a list of (name, type, expr) tuples
    if it can determine a type for arg `name`. `type` may be `None`
    """
    return []


@infer.register(ast.VariableReference)
def infer_variable_reference(expr, env):
    # Use `None` here - the variable was used, but more than that we don't know.
    return [(expr.id.name, InferredType(None, [env.ftl_source_for_expr(expr)]))]


@infer.register(ast.FunctionReference)
def infer_function_reference(expr, env):
    if expr.id.name == "NUMBER":
        posargs = expr.arguments.positional
        if len(posargs) > 0:
            if isinstance(posargs[0], ast.VariableReference):
                return [(posargs[0].id.name, InferredType(Number, [env.ftl_source_for_expr(expr)]))]
    if expr.id.name == "DATETIME":
        posargs = expr.arguments.positional
        if len(posargs) > 0:
            if isinstance(posargs[0], ast.VariableReference):
                return [(posargs[0].id.name, InferredType(DateTime, [env.ftl_source_for_expr(expr)]))]
    return []


@infer.register(ast.MessageReference)
def infer_message_reference(expr, env):
    reference_id = reference_to_id(expr)
    if reference_id not in env.known_arg_types:
        # We know that messages are processed in the correct order
        # so we ought to have done type inference for reference_id already.
        # If it's missing, this is a compilation error that will be picked
        # up by other code.
        return []
    arg_types = env.known_arg_types[reference_id]
    return [
        # Copy over all params from the message we are calling.
        (
            name,
            InferredType(
                t.type,
                # Combine evidence from called message with the fact
                # that we are calling that message.
                [env.ftl_source_for_expr(expr)] + t.evidences,
            ),
        )
        for name, t in arg_types.items()
    ]


@infer.register(ast.SelectExpression)
def infer_select_expression(select_expr, env):
    if not isinstance(select_expr.selector, ast.VariableReference):
        return []
    retval = []

    name = select_expr.selector.id.name
    numeric_variants = [variant for variant in select_expr.variants if isinstance(variant.key, ast.NumberLiteral)]
    plural_form_variants = [variant for variant in select_expr.variants if is_cldr_plural_form_key(variant.key)]
    other_variants = list(set(select_expr.variants) - set(numeric_variants) - set(plural_form_variants))

    if numeric_variants:
        retval.append(
            (name, InferredType(Number, [env.ftl_source_for_expr(variant.key) for variant in numeric_variants]))
        )

    if not other_variants:
        # We've only got numbers and plural form categories
        # Treat everything that looks like a plural form as evidence for numeric
        retval.append(
            (name, InferredType(Number, [env.ftl_source_for_expr(variant.key) for variant in plural_form_variants]))
        )
    else:
        # We got non-plural form strings, and potentially plural form strings.
        # Treat plural form (and others) as evidence for string.
        string_variants = [
            variant for variant in select_expr.variants if variant in plural_form_variants or variant in other_variants
        ]
        retval.append(
            (name, InferredType(String, [env.ftl_source_for_expr(variant.key) for variant in string_variants]))
        )

    return retval


def combine_inferred_types(inferred_types, message_source) -> dict[str, InferredType | ConflictType]:
    """
    Given list [(name, InferredType or None)],
    returns a dictionary {name: InferredType or Conflict}
    with evidences combined. 'message_source' can be
    None, will be passed to any Conflict instances created.
    """
    # inferred_types may contain lots of distinct evidence for
    # different types.
    output: dict[str, InferredType | ConflictType] = {}
    found_names = set()

    real_inferred_types = []
    for name, inferred_type in inferred_types:
        if inferred_type.type is None:
            found_names.add(name)
            continue
        else:
            real_inferred_types.append((name, inferred_type))
    for name, inferred_type in real_inferred_types:
        if name in output:
            existing = output[name]
            if isinstance(existing, Conflict):
                existing.types.append(inferred_types)
            else:
                if existing.type == inferred_type.type:
                    existing.evidences.extend(inferred_type.evidences)
                else:
                    replacement = Conflict(
                        types=[existing, inferred_type],
                        message_source=message_source,
                    )
                    output[name] = replacement
        else:
            output[name] = inferred_type

    for name in found_names:
        if name not in output:
            # We have an arg name that was referred to (e.g. in a placeable),
            # but no evidence what it was beyond that. We default to String.
            output[name] = InferredType(
                type=String,
                evidences=[
                    e
                    for evidences in [t.evidences for n, t in inferred_types if n == name and t.type is None]
                    for e in evidences
                ],
            )

    return output
