from __future__ import absolute_import, unicode_literals

import contextlib
from collections import OrderedDict

import attr
import six
from fluent.syntax import FluentParser, ast

from elm_fluent import codegen, exceptions, html_compiler, types
from elm_fluent.stubs import (
    defaults as dtypes,
    fluent,
    html,
    html_attributes,
    intl_datetimeformat,
    intl_locale,
    intl_numberformat,
    intl_pluralrules,
)
from elm_fluent.stubs.defaults import default_imports

try:
    from functools import singledispatch
except ImportError:
    # Python < 3.4
    from singledispatch import singledispatch

text_type = six.text_type

# Unicode bidi isolation characters.
FSI = "\u2068"
PDI = "\u2069"


# Choose names with final underscores to avoid clashes with message IDs
MESSAGE_ARGS_NAME = "args_"
LOCALE_ARG_NAME = "locale_"
ATTRS_ARG_NAME = "attrs_"
ALL_MESSAGE_FUNCTION_ARGS = [LOCALE_ARG_NAME, MESSAGE_ARGS_NAME, ATTRS_ARG_NAME]


PLURAL_FORM_FOR_NUMBER_NAME = "plural_form_for_number"


CLDR_PLURAL_FORMS = set(["zero", "one", "two", "few", "many", "other"])


@attr.s
class CurrentEnvironment(object):
    # The parts of CompilerEnvironment that we want to mutate (and restore)
    # temporarily for some parts of a call chain.
    message_id = attr.ib(default=None)
    html_context = attr.ib(default=False)


@attr.s
class FtlSource(object):
    expr = attr.ib()
    message_source = attr.ib()
    message_id = attr.ib()


@attr.s
class CompilerEnvironment(object):
    locale = attr.ib()
    use_isolating = attr.ib()
    message_mapping = attr.ib(factory=dict)
    errors = attr.ib(factory=list)
    functions = attr.ib(factory=dict)
    message_ids_to_ast = attr.ib(factory=dict)
    term_ids_to_ast = attr.ib(factory=dict)
    message_source = attr.ib(default=None)
    dynamic_html_attributes = attr.ib(default=True)
    current = attr.ib(factory=CurrentEnvironment)

    def add_current_message_error(self, error, expr):
        error.error_sources.append(
            FtlSource(
                expr=expr,
                message_source=self.message_source,
                message_id=self.current.message_id,
            )
        )
        self.errors.append(error)

    @contextlib.contextmanager
    def modified(self, **replacements):
        """
        Context manager that modifies the 'current' attribute of the
        environment, restoring the old data at the end.
        """
        # CurrentEnvironment only has immutable args at the moment, so the
        # shallow copy returned by attr.evolve is fine.
        old_current = self.current
        self.current = attr.evolve(old_current, **replacements)
        yield self
        self.current = old_current


def parse_ftl(source):
    resource = FluentParser().parse(source)
    messages = OrderedDict()
    junk = []
    for item in resource.body:
        if isinstance(item, ast.Message):
            messages[item.id.name] = item
        elif isinstance(item, ast.Term):
            messages[item.id.name] = item
        elif isinstance(item, ast.Junk):
            junk.append(item)
    return messages, junk


def compile_messages(
    messages_string,
    locale,
    message_source=None,
    module_name=None,
    use_isolating=True,
    dynamic_html_attributes=True,
):
    """
    Compile messages_string to Elm code.

    locale is BCP47 locale (currently unused)

    message_source is a filename that the messages came from

    Returns a tuple:
       (elm_source,
        error_list,
        message_id_to_function_name_mapping
       )

    elm_source is None if error_list is not empty.

    The error list is itself a list of two tuples:
       (message id, exception object)
    """
    # dynamic_html_attributes exists as an option to this function only to
    # simplify the output in tests/test_compiler when we are not interested in
    # this feature, otherwise it is just too noisy.
    messages, junk = parse_ftl(messages_string)
    message_ids_to_ast = OrderedDict(get_message_function_ast(messages))
    term_ids_to_ast = OrderedDict(get_term_ast(messages))

    compiler_env = CompilerEnvironment(
        locale=locale,
        use_isolating=use_isolating,
        functions=FUNCTIONS,
        message_ids_to_ast=message_ids_to_ast,
        term_ids_to_ast=term_ids_to_ast,
        message_source=message_source,
        dynamic_html_attributes=dynamic_html_attributes,
    )
    module_imports = [
        (intl_locale.module, "Locale"),
        (intl_numberformat.module, "NumberFormat"),
        (intl_datetimeformat.module, "DateTimeFormat"),
        (intl_pluralrules.module, "PluralRules"),
        (fluent.module, "Fluent"),
        (html.module, "Html"),
        (html_attributes.module, "Attributes"),
    ]

    module = codegen.Module(name=module_name)
    for mod, name in module_imports:
        module.add_import(mod, name)

    # Reserve names for function arguments, so that we always
    # know the name of these arguments without needing to do
    # lookups etc.
    for arg in list(ALL_MESSAGE_FUNCTION_ARGS):
        module.reserve_function_arg_name(arg)

    # Handle junk
    for junk_item in junk:
        err = exceptions.JunkFound(
            "Junk found: " + "; ".join(a.message for a in junk_item.annotations),
            junk_item.annotations,
        )
        err.error_sources.append(
            FtlSource(
                expr=junk_item,
                message_source=compiler_env.message_source,
                message_id=None,
            )
        )
        compiler_env.errors.append(err)

    # Pass one, find all the names, so that we can populate message_mapping,
    # which is needed for compilation.
    for msg_id, msg in message_ids_to_ast.items():
        function_type = function_type_for_message_id(msg_id)
        function_name = module.reserve_name(
            message_function_name_for_msg_id(msg_id), type=function_type
        )

        compiler_env.message_mapping[msg_id] = function_name

    reverse_message_mapping = {v: k for k, v in compiler_env.message_mapping.items()}

    # == Order of processing ==
    # Processing order is important to get types correct for the case when
    # messages call other messages, and later messages constrain the types of
    # arguments to be non-String.
    # We preserve source order for the sake of readability.
    # These two dicts are: {message id: order number}
    source_order = {msg_id: i for i, msg_id in enumerate(message_ids_to_ast.keys())}
    processing_order = get_processing_order(message_ids_to_ast)
    sorted_message_ids = [
        msg_id
        for msg_id, i in sorted(processing_order.items(), key=lambda pair: pair[1])
    ]

    # Pass 2, actual compilation

    for msg_id in sorted_message_ids:
        msg = message_ids_to_ast[msg_id]
        with compiler_env.modified(
            message_id=msg_id, html_context=is_html_message_id(msg_id)
        ):
            function_name = compiler_env.message_mapping[msg_id]

            # The final function names need to be easily predictable. If we
            # didn't get what we expected, we must have had some clash, and it
            # is best to require that the message IDs change. In reality this
            # would happen very rarely for normal message IDs.
            expected_message_function_name = message_function_name_for_msg_id(msg_id)
            if function_name != expected_message_function_name:
                if expected_message_function_name in codegen.ELM_KEYWORDS:
                    error_msg = (
                        "'{0}' is not allowed as a message ID because it "
                        "clashes with an Elm keyword. "
                        "Please choose another ID.".format(msg_id)
                    )
                elif expected_message_function_name in default_imports.names_in_use():
                    error_msg = (
                        "'{0}' is not allowed as a message ID because it "
                        "clashes with an Elm default import. "
                        "Please choose another ID.".format(msg_id)
                    )
                elif expected_message_function_name in reverse_message_mapping:
                    error_msg = (
                        "'{0}' is not allowed as a message ID because it "
                        "clashes with another message ID - '{1}'. "
                        "Please choose another ID.".format(
                            msg_id,
                            reverse_message_mapping[expected_message_function_name],
                        )
                    )
                else:
                    raise NotImplementedError(
                        "{0} not allowed, need good error message for why".format(
                            expected_message_function_name
                        )
                    )
                compiler_env.add_current_message_error(
                    exceptions.BadMessageId(error_msg), msg
                )
                function = codegen.Function(
                    parent_scope=module,
                    name=function_name,
                    args=function_args_for_func_name(function_name),
                )
                function.body.value = codegen.CompilationError()
            else:
                function = compile_message(
                    msg, msg_id, function_name, module, compiler_env
                )
            if not isinstance(function, codegen.CompilationError):
                module.add_function(
                    function_name, function, source_order=source_order[msg_id]
                )

    module = codegen.simplify(module)
    return (module, compiler_env.errors, compiler_env.message_mapping)


def compile_master(module_name, locales, locale_modules, message_mapping, options):
    """
    Compile the master 'Translations' Elm file. For every message, this has a function
    that despatches to the function from the correct locale.
    """
    func_name_to_message_id = {
        func_name: message_id for message_id, func_name in message_mapping.items()
    }
    errors = []
    warnings = []
    module = codegen.Module(name=module_name)
    module.add_import(intl_locale.module, "Locale")
    module.add_import(fluent.module, "Fluent")
    module.add_import(html.module, "Html")
    locale_module_local_names = {
        locale: module_name_for_locale(locale) for locale in locales
    }

    for locale, locale_module in locale_modules.items():
        if locale_module.exports:
            module.add_import(locale_module, locale_module_local_names[locale])

    sub_module_exports = {
        locale: locale_module.exports
        for locale, locale_module in locale_modules.items()
    }
    for l in locales:
        if l not in sub_module_exports:
            sub_module_exports[l] = []
    all_sub_module_exports = set(
        [e for exports in sub_module_exports.values() for e in exports]
    )

    for func_name in all_sub_module_exports:
        function_type = function_type_for_func_name(func_name)
        function_name = module.reserve_name(func_name, type=function_type)
        assert function_name == func_name, "{0} != {1} unexpectedly".format(
            function_name, func_name
        )
        message_id = func_name_to_message_id[function_name]

        function = codegen.Function(
            parent_scope=module,
            name=function_name,
            args=function_args_for_func_name(function_name),
        )
        locale_tag_expr = function.variables["Locale.toLanguageTag"].apply(
            function.variables[LOCALE_ARG_NAME]
        )
        lower_cased_locale_tag_expr = function.variables["String.toLower"].apply(
            locale_tag_expr
        )
        case_expr = codegen.Case(lower_cased_locale_tag_expr, parent_scope=function)

        def do_call(l):
            try:
                return function.variables[
                    "{0}.{1}".format(locale_module_local_names[l], func_name)
                ].apply(
                    *[
                        function.variables[a]
                        for a in function_args_for_func_name(func_name)
                    ]
                )
            except exceptions.TypeMismatch as e:
                e.message_func_name = function_name
                errors.append(e)
                return codegen.CompilationError()

        for locale in locales:
            locale_to_use_for_message = None
            fallback_locale = options.missing_translation_strategy.get_locale_when_missing(
                locale
            )
            if locale not in locale_modules:
                locale_to_use_for_message = fallback_locale
                options.missing_translation_strategy.missing_message(
                    message_id, locale, errors, warnings
                )
            else:
                mod = locale_modules[locale]
                if func_name not in mod.exports:
                    locale_to_use_for_message = fallback_locale
                    options.missing_translation_strategy.missing_message(
                        message_id, locale, errors, warnings
                    )
                else:
                    locale_to_use_for_message = locale

            branch = case_expr.add_branch(codegen.String(locale.lower()))
            if locale_to_use_for_message is None:
                branch.value = codegen.CompilationError()
            else:
                branch.value = do_call(locale_to_use_for_message)

        if (
            options.default_locale in locale_modules
            and func_name in locale_modules[options.default_locale].exports
        ):
            otherwise_branch = case_expr.add_branch(codegen.Otherwise())
            otherwise_branch.value = do_call(options.default_locale)
            function.body.value = case_expr
            module.add_function(function_name, function)
        else:
            # Can't add the function, the fallback is missing. We have already reported
            # the error.
            pass

    codegen.simplify(module)
    return (module, errors, warnings)


def module_name_for_locale(locale_name):
    return locale_name.replace("-", "").upper()


def is_html_message_id(message_id):
    return is_html_message_func_name(message_function_name_for_msg_id(message_id))


def is_html_message_func_name(func_name):
    return func_name.endswith("Html")


def function_type_for_message_id(message_id):
    return function_type_for_func_name(message_function_name_for_msg_id(message_id))


def function_args_for_func_name(func_name):
    if is_html_message_func_name(func_name):
        return [LOCALE_ARG_NAME, MESSAGE_ARGS_NAME, ATTRS_ARG_NAME]
    else:
        return [LOCALE_ARG_NAME, MESSAGE_ARGS_NAME]


def function_type_for_func_name(func_name):
    if is_html_message_func_name(func_name):
        msg = types.TypeParam("msg")
        return types.Function.for_multiple_inputs(
            [
                intl_locale.Locale,
                types.Record(),
                dtypes.List.specialize(
                    a=types.Tuple(
                        dtypes.String,
                        dtypes.List.specialize(a=html.Attribute.specialize(msg=msg)),
                    )
                ),
            ],
            dtypes.List.specialize(a=html.Html.specialize(msg=msg)),
        )
    else:
        return types.Function.for_multiple_inputs(
            [intl_locale.Locale, types.Record()], dtypes.String
        )


def get_message_function_ast(message_dict):
    for msg_id, msg in message_dict.items():
        if msg.value is None:
            # No body, skip it.
            pass
        elif isinstance(msg, ast.Term):
            pass
        else:
            yield (msg_id, msg)
        for msg_attr in msg.attributes:
            yield (message_id_for_attr(msg_id, msg_attr.id.name), msg_attr)


def get_term_ast(message_dict):
    for term_id, term in message_dict.items():
        if term.value is None:
            # No body, skip it.
            pass
        elif isinstance(term, ast.Message):
            pass
        else:
            yield (term_id, term)
        for term_attr in term.attributes:
            yield (message_id_for_attr(term_id, term_attr.id.name), term_attr)


def message_id_for_attr(parent_msg_id, attr_name):
    return "{0}.{1}".format(parent_msg_id, attr_name)


def message_id_for_attr_expression(attr_expr):
    return message_id_for_attr(attr_expr.ref.id.name, attr_expr.name.name)


def message_function_name_for_msg_id(msg_id):
    # Scope.reserve_name does further sanitising of name, which we don't need to
    # worry about.

    sections = []
    for section in msg_id.split("."):
        # Remove '-' and replace with camelCaps
        parts = section.rstrip("_").rstrip("-").split("-")
        joined = []
        for i, part in enumerate(parts):
            if i > 0:
                part = part.title()
            joined.append(part)

        section_name = "".join(joined)
        sections.append(section_name)
    return "_".join(sections)


def compile_message(msg, msg_id, function_name, module, compiler_env):
    msg_func = codegen.Function(
        parent_scope=module,
        name=function_name,
        args=function_args_for_func_name(function_name),
    )

    if contains_reference_cycle(msg, msg_id, compiler_env):
        error = exceptions.CyclicReferenceError(
            "Cyclic reference in {0}".format(msg_id)
        )
        compiler_env.add_current_message_error(error, msg)
        return codegen.CompilationError()
    else:
        return_expression = compile_expr(msg, msg_func.body, compiler_env)
    msg_func.body.value = return_expression
    codegen.finalize(msg_func)
    return msg_func


def get_processing_order(message_ids_to_ast):
    call_graph = {}

    for msg_id, msg in message_ids_to_ast.items():
        calls = []

        def find_message_calls(node):
            if not isinstance(node, ast.BaseNode):
                return

            if isinstance(node, ast.MessageReference):
                ref = node.id.name
                if ref in message_ids_to_ast:
                    calls.append(ref)
            elif isinstance(node, ast.AttributeExpression):
                ref = message_id_for_attr_expression(node)
                if ref in message_ids_to_ast:
                    calls.append(ref)

        traverse_ast(msg, find_message_calls)
        call_graph[msg_id] = calls

    processed = []
    to_process = list(message_ids_to_ast.keys())
    current_msg_id = None
    current_msg_id_history = []
    while to_process:
        if current_msg_id is None:
            current_msg_id = to_process[0]

        # Cycle detect:
        if (current_msg_id, len(to_process)) in current_msg_id_history:
            # Oops, we've been in the same place before, with the
            # same amount of remaining work ->  cycle. Can't do ordering.
            # Other code will detect this, we just exit here.
            processed.extend(to_process)
            break
        current_msg_id_history.append((current_msg_id, len(to_process)))

        called_msg_ids = call_graph[current_msg_id]
        unprocessed_called_msg_ids = [c for c in called_msg_ids if c in to_process]
        if not unprocessed_called_msg_ids:
            processed.append(current_msg_id)
            to_process.remove(current_msg_id)
            current_msg_id = None
        else:
            current_msg_id = unprocessed_called_msg_ids[0]
    return {k: i for i, k in enumerate(processed)}


STANDARD_TRAVERSE_EXCLUDE_ATTRIBUTES = [
    # Message and Term attributes have already been loaded into the
    # message_ids_to_ast dict, and we get to their contents via
    # AttributeExpression
    (ast.Message, "attributes"),
    (ast.Term, "attributes"),
    # We don't recurse into AttributeExpression.ref, which is a
    # MessageReference, because we have handled the contents of this ref via
    # the parent AttributeExpression, and we don't want it to be handled as
    # a standalone MessageReference which would mean something different.
    (ast.AttributeExpression, "ref"),
    # for speed
    (ast.Message, "comment"),
    (ast.Term, "comment"),
]


def traverse_ast(node, fun, exclude_attributes=STANDARD_TRAVERSE_EXCLUDE_ATTRIBUTES):
    """Postorder-traverse this node and apply `fun` to all child nodes.

    Traverse this node depth-first applying `fun` to subnodes and leaves.
    Children are processed before parents (postorder traversal).

    exclude_attributes is a list of (node type, attribute name) tuples
    that should not be recursed into.
    """

    def visit(value):
        """Call `fun` on `value` and its descendants."""
        if isinstance(value, ast.BaseNode):
            return traverse_ast(value, fun, exclude_attributes=exclude_attributes)
        if isinstance(value, list):
            return fun(list(map(visit, value)))
        else:
            return fun(value)

    # Use all attributes found on the node
    parts = vars(node).items()
    for name, value in parts:
        if exclude_attributes is not None and (type(node), name) in exclude_attributes:
            continue
        visit(value)

    return fun(node)


def contains_reference_cycle(msg, msg_id, compiler_env):
    message_ids_to_ast = compiler_env.message_ids_to_ast
    term_ids_to_ast = compiler_env.term_ids_to_ast

    visited_nodes = set([])
    checks = []

    def checker(node):
        if isinstance(node, ast.BaseNode):
            node_id = id(node)
            if node_id in visited_nodes:
                checks.append(True)
                return
            visited_nodes.add(node_id)
        else:
            return

        # The logic below duplicates the logic that is used for 'jumping' to
        # different nodes (messages via a runtime function call, terms via
        # inlining), including the fallback strategies that are used.
        sub_node = None
        if isinstance(node, ast.MessageReference):
            ref = node.id.name
            if ref in message_ids_to_ast:
                sub_node = message_ids_to_ast[ref]
        elif isinstance(node, ast.TermReference):
            ref = node.id.name
            if ref in term_ids_to_ast:
                sub_node = term_ids_to_ast[ref]
        elif isinstance(node, ast.AttributeExpression):
            ref = message_id_for_attr_expression(node)
            if ref in message_ids_to_ast:
                sub_node = message_ids_to_ast[ref]
            elif ref in term_ids_to_ast:
                sub_node = term_ids_to_ast[ref]

        if sub_node is not None:
            traverse_ast(sub_node, checker)
            if any(checks):
                return

        return

    traverse_ast(msg, checker)
    return any(checks)


@singledispatch
def compile_expr(element, local_scope, compiler_env):
    """
    Compiles a Fluent expression into a Python one, return
    an object of type codegen.Expression.

    This may also add statements into local_scope, which is assumed
    to be a function that returns a message, or a branch of that
    function.
    """
    raise NotImplementedError(
        "Cannot handle object of type {0}".format(type(element).__name__)
    )


@compile_expr.register(ast.Message)
def compile_expr_message(message, local_scope, compiler_env):
    return compile_expr(message.value, local_scope, compiler_env)


@compile_expr.register(ast.Term)
def compile_expr_term(term, local_scope, compiler_env):
    return compile_expr(term.value, local_scope, compiler_env)


@compile_expr.register(ast.Attribute)
def compile_expr_attribute(attribute, local_scope, compiler_env):
    return compile_expr(attribute.value, local_scope, compiler_env)


@compile_expr.register(ast.Pattern)
def compile_expr_pattern(pattern, local_scope, compiler_env):
    parts = []
    subelements = pattern.elements

    use_isolating = compiler_env.use_isolating and len(subelements) > 1

    if compiler_env.current.html_context:
        return html_compiler.compile_pattern(pattern, local_scope, compiler_env)

    for element in pattern.elements:
        wrap_this_with_isolating = use_isolating and not isinstance(
            element, ast.TextElement
        )
        if wrap_this_with_isolating:
            parts.append(codegen.String(FSI))
        parts.append(
            Stringable(
                compile_expr(element, local_scope, compiler_env),
                local_scope,
                from_ftl_source=make_ftl_source(element, compiler_env),
            )
        )
        if wrap_this_with_isolating:
            parts.append(codegen.String(PDI))

    return codegen.StringConcat(parts)


@compile_expr.register(ast.TextElement)
def compile_expr_text(text, local_scope, compiler_env):
    return codegen.String(text.value)


@compile_expr.register(ast.StringLiteral)
def compile_expr_string_expression(expr, local_scope, compiler_env):
    return codegen.String(expr.value)


@compile_expr.register(ast.NumberLiteral)
def compile_expr_number_expression(expr, local_scope, compiler_env):
    return codegen.Number(numeric_to_native(expr.value))


def numeric_to_native(val):
    """
    Given a numeric string (as defined by fluent spec),
    return an int or float
    """
    # val matches this EBNF:
    #  '-'? [0-9]+ ('.' [0-9]+)?
    if "." in val:
        return float(val)
    else:
        return int(val)


@compile_expr.register(ast.Placeable)
def compile_expr_placeable(placeable, local_scope, compiler_env):
    return compile_expr(placeable.expression, local_scope, compiler_env)


@compile_expr.register(ast.MessageReference)
def compile_expr_message_reference(reference, local_scope, compiler_env):
    name = reference.id.name
    try:
        return do_message_call(name, local_scope, reference, compiler_env)
    except exceptions.TypeMismatch as e:
        compiler_env.add_current_message_error(e, reference)
        return codegen.CompilationError()


@compile_expr.register(ast.TermReference)
def compile_expr_term_reference(reference, local_scope, compiler_env):
    name = reference.id.name
    if name in compiler_env.term_ids_to_ast:
        term = compiler_env.term_ids_to_ast[name]
        return compile_expr(term.value, local_scope, compiler_env)
    else:
        error = exceptions.ReferenceError("Unknown term: {0}".format(name))
        compiler_env.add_current_message_error(error, reference)
        return codegen.CompilationError()


def do_message_call(name, local_scope, expr, compiler_env):
    if name in compiler_env.message_mapping:
        msg_func_name = compiler_env.message_mapping[name]
        # If in HTML context, can call either plain or HTML.
        # But plain text context cannot call HTML context
        if not compiler_env.current.html_context:
            if is_html_message_id(name):
                compiler_env.add_current_message_error(
                    exceptions.HtmlTypeMismatch(
                        "Cannot use HTML message {0} from plain text context.".format(
                            name
                        )
                    ),
                    expr,
                )
                return codegen.CompilationError()

        return local_scope.variables[msg_func_name].apply(
            *[
                local_scope.variables[a]
                for a in function_args_for_func_name(msg_func_name)
            ]
        )
    else:
        return unknown_reference(name, local_scope, expr, compiler_env)


def unknown_reference(name, local_scope, expr, compiler_env):
    if name.startswith("-"):
        error = exceptions.ReferenceError("Unknown term: {0}".format(name))
    else:
        error = exceptions.ReferenceError("Unknown message: {0}".format(name))
    compiler_env.add_current_message_error(error, expr)
    return codegen.CompilationError()


@compile_expr.register(ast.AttributeExpression)
def compile_expr_attribute_expression(attribute, local_scope, compiler_env):
    msg_id = message_id_for_attr_expression(attribute)
    # Message attribute
    if msg_id in compiler_env.message_mapping:
        return do_message_call(msg_id, local_scope, attribute, compiler_env)
    # Term attribute
    elif msg_id in compiler_env.term_ids_to_ast:
        term = compiler_env.term_ids_to_ast[msg_id]
        return compile_expr(term, local_scope, compiler_env)
    # Missing
    else:
        return unknown_reference(msg_id, local_scope, attribute, compiler_env)


@compile_expr.register(ast.VariantList)
def compile_expr_variant_list(
    variant_list, local_scope, compiler_env, selected_key=None, term_id=None
):
    default = None
    found = None
    for variant in variant_list.variants:
        if variant.default:
            default = variant
        if selected_key is not None and variant.key.name == selected_key.name:
            found = variant

    if found is None:
        found = default
        if selected_key is not None:
            error = exceptions.ReferenceError(
                "Unknown variant: {0}[{1}]".format(term_id, selected_key.name)
            )
            compiler_env.add_current_message_error(error, selected_key)
            return codegen.CompilationError()
    return compile_expr(found.value, local_scope, compiler_env)


def is_cldr_plural_form_key(key_expr):
    return isinstance(key_expr, ast.VariantName) and key_expr.name in CLDR_PLURAL_FORMS


@compile_expr.register(ast.SelectExpression)
def compile_expr_select_expression(select_expr, local_scope, compiler_env):
    selector_value = compile_expr(select_expr.selector, local_scope, compiler_env)

    numeric_variants = [
        variant
        for variant in select_expr.variants
        if isinstance(variant.key, ast.NumberLiteral)
    ]
    any_numerics = len(numeric_variants) > 0
    all_numerics = len(numeric_variants) == len(select_expr.variants)

    plural_form_variants = [
        variant
        for variant in select_expr.variants
        if is_cldr_plural_form_key(variant.key)
    ]
    all_plural_forms = len(plural_form_variants) == len(select_expr.variants)

    constraining_ftl_expr = None

    if any_numerics:
        numeric_key = True
        constraining_ftl_expr = numeric_variants[0]
    elif all_plural_forms:
        numeric_key = True
        constraining_ftl_expr = plural_form_variants[0]
    else:
        # No numerics, and some of the strings are not plural form categories
        numeric_key = False
        constraining_ftl_expr = [
            variant
            for variant in select_expr.variants
            if variant not in plural_form_variants
        ][0]

    if numeric_key:
        if isinstance(selector_value, codegen.Number):
            inferred_key_type = dtypes.Number
        else:
            inferred_key_type = fluent.FluentNumber
    else:
        inferred_key_type = dtypes.String

    try:
        selector_value.constrain_type(
            inferred_key_type,
            from_ftl_source=make_ftl_source(constraining_ftl_expr, compiler_env),
        )
    except exceptions.TypeMismatch as e:
        compiler_env.add_current_message_error(e, select_expr.selector)
        return codegen.CompilationError()

    def get_plural_form(number_val):
        return local_scope.variables["PluralRules.select"].apply(
            local_scope.variables["PluralRules.fromLocale"].apply(
                local_scope.variables[LOCALE_ARG_NAME]
            ),
            number_val,
        )

    mixed = False
    if numeric_key:
        if selector_value.type == dtypes.Number:
            number_val = selector_value
        elif selector_value.type == fluent.FluentNumber:
            number_val = local_scope.variables["Fluent.numberValue"].apply(
                selector_value
            )
        else:
            raise NotImplementedError(
                "Can't handle numeric of type {0}".format(selector_value.type)
            )

        if all_numerics:
            case_selector_value = number_val
        elif all_plural_forms:
            case_selector_value = get_plural_form(number_val)
        else:
            # mixed numerics and plural categories.
            mixed = True

    else:
        case_selector_value = selector_value

    if mixed:
        number_var = local_scope.add_assignment("val_", number_val)
        plural_form_var = local_scope.add_assignment("pl_", get_plural_form(number_var))

        # series of if/then/else
        default_value = None
        total = len(select_expr.variants)
        retval = codegen.Let(parent_scope=local_scope)
        previous_else_branch = retval
        for i, variant in enumerate(select_expr.variants):
            last = i == total - 1
            branch_value = compile_expr(variant.value, local_scope, compiler_env)
            if variant.default:
                default_value = branch_value
            if last and variant.default:
                # Don't need to add a new if with a condition
                previous_else_branch.value = branch_value
            else:
                key_value = compile_expr(variant.key, local_scope, compiler_env)
                if is_cldr_plural_form_key(variant.key):
                    condition = codegen.Equals(plural_form_var, key_value)
                else:
                    condition = codegen.Equals(number_var, key_value)

                if_expr = codegen.If(condition, parent_scope=previous_else_branch)
                if_expr.true_branch.value = branch_value
                previous_else_branch.value = if_expr
                previous_else_branch = if_expr.false_branch

        if previous_else_branch.value is None:
            previous_else_branch.value = default_value
        return retval
    else:
        case_expr = codegen.Case(case_selector_value, parent_scope=local_scope)
        # Sort so that default is last.
        sorted_variants = sorted(
            select_expr.variants, key=lambda v: 1 if v.default else 0
        )
        for variant in sorted_variants:
            if variant.default:
                key_value = codegen.Otherwise()
            else:
                key_value = compile_expr(variant.key, local_scope, compiler_env)

            # TODO - test for what happens here when there is TypeMismatch
            # e.g. there is a numeric
            key_value.constrain_type(
                case_selector_value.type.constrain(key_value.type),
                from_ftl_source=make_ftl_source(variant, compiler_env),
            )
            branch = case_expr.add_branch(key_value)
            branch.value = compile_expr(variant.value, branch, compiler_env)

        return case_expr


@compile_expr.register(ast.VariantName)
def compile_expr_variant_name(name, local_scope, compiler_env):
    return codegen.String(name.name)


@compile_expr.register(ast.VariantExpression)
def compile_expr_variant_expression(variant_expr, local_scope, compiler_env):
    term_id = variant_expr.ref.id.name
    if term_id in compiler_env.term_ids_to_ast:
        term_val = compiler_env.term_ids_to_ast[term_id].value
        if isinstance(term_val, ast.VariantList):
            return compile_expr_variant_list(
                term_val,
                local_scope,
                compiler_env,
                selected_key=variant_expr.key,
                term_id=term_id,
            )
        else:
            error = exceptions.ReferenceError(
                "Unknown variant: {0}[{1}]".format(term_id, variant_expr.key.name)
            )
            compiler_env.add_current_message_error(error, variant_expr)
            return codegen.CompilationError()
    else:
        error = exceptions.ReferenceError("Unknown term: {0}".format(term_id))
        compiler_env.add_current_message_error(error, variant_expr)
        return codegen.CompilationError()


@compile_expr.register(ast.VariableReference)
def compile_expr_variable_reference(argument, local_scope, compiler_env):
    name = argument.id.name
    # TODO - some kind of sanitising on the argument name
    args_var = local_scope.variables[MESSAGE_ARGS_NAME]
    arg = codegen.AttributeReference(args_var, name)
    return arg


@compile_expr.register(ast.CallExpression)
def compile_expr_call_expression(expr, local_scope, compiler_env):
    function_name = expr.callee.name

    if function_name in compiler_env.functions:
        function_spec = compiler_env.functions[function_name]
        args = [compile_expr(arg, local_scope, compiler_env) for arg in expr.positional]
        kwargs = {
            kwarg.name.name: compile_expr(kwarg.value, local_scope, compiler_env)
            for kwarg in expr.named
        }
        match, error = args_match(function_spec, args, kwargs)
        if match:
            try:
                return function_spec.compile(
                    make_ftl_source(expr, compiler_env), args, kwargs, local_scope
                )
            except exceptions.TypeMismatch as e:
                compiler_env.add_current_message_error(e, expr)
                return codegen.CompilationError()
        else:
            compiler_env.add_current_message_error(error, expr)
            return codegen.CompilationError()

    else:
        error = exceptions.ReferenceError("Unknown function: {0}".format(function_name))
        compiler_env.add_current_message_error(error, expr)
        return codegen.CompilationError()


def make_ftl_source(expr, compiler_env):
    return FtlSource(
        expr=expr,
        message_id=compiler_env.current.message_id,
        message_source=compiler_env.message_source,
    )


def args_match(function_spec, args, kwargs):
    """
    Returns a tuple indicating whether the passed in args tuple and kwargs dict
    match the `function_spec` provided.

    For a match, returns a tuple
       (True, None)

    For a non-match, returns a tuple
       (False, TypeError instance)

    """
    if not all(kw in function_spec.keyword_args for kw in kwargs):
        return (
            False,
            exceptions.FunctionParameterError(
                "{0}() got an unexpected keyword argument '{1}'".format(
                    function_spec.name,
                    six.next(
                        kw for kw in kwargs if kw not in function_spec.keyword_args
                    ),
                )
            ),
        )
    if not function_spec.positional_args == len(args):
        return (
            False,
            exceptions.FunctionParameterError(
                "{0}() takes {1} positional argument(s) but {2} were given".format(
                    function_spec.name, function_spec.positional_args, len(args)
                )
            ),
        )

    return (True, None)


class Stringable(codegen.Expression):
    # A kind of 'flexi' expression for args that will convert itself to
    # NumberFormat.format/DateTimeFormat.format calls when you call finalize(),
    # if the arg turned out to be numeric or a datetime
    def __init__(self, expr, local_scope, from_ftl_source=None):
        super(Stringable, self).__init__(from_ftl_source=from_ftl_source)
        self.expr = expr
        self.local_scope = local_scope
        self._finalized_expr = None
        self._assigned_types = []

    @property
    def type(self):
        return dtypes.String

    def constrain_type(self, type_obj, from_ftl_source=None):
        self._assigned_types.append(type_obj)

    def sub_expressions(self):
        yield self.expr

    def finalize(self):
        if self._finalized_expr is not None:
            return
        assert all(t == dtypes.String for t in self._assigned_types)
        if self.expr.type == dtypes.String:
            # Underlying type is also string, no more to do
            self._finalized_expr = self.expr
        elif isinstance(self.expr.type, types.UnconstrainedType):
            # Constrain in last line
            self._finalized_expr = self.expr
        elif self.expr.type == dtypes.Number:
            self._finalized_expr = self.local_scope.variables[
                "NumberFormat.format"
            ].apply(
                self.local_scope.variables["NumberFormat.fromLocale"].apply(
                    self.local_scope.variables[LOCALE_ARG_NAME]
                ),
                self.expr,
            )
        elif self.expr.type == fluent.FluentNumber:
            self._finalized_expr = self.local_scope.variables[
                "Fluent.formatNumber"
            ].apply(self.local_scope.variables[LOCALE_ARG_NAME], self.expr)
        elif self.expr.type == fluent.FluentDate:
            self._finalized_expr = self.local_scope.variables[
                "Fluent.formatDate"
            ].apply(self.local_scope.variables[LOCALE_ARG_NAME], self.expr)
        else:
            raise NotImplementedError(
                "Don't know how to finalize object {0} of type {1}".format(
                    self.expr, self.expr.type
                )
            )
        self._finalized_expr.constrain_type(
            dtypes.String, from_ftl_source=self.from_ftl_source
        )

    def as_source_code(self):
        assert self._finalized_expr is not None, "Need to call 'finalize' first"
        return self._finalized_expr.as_source_code()

    def simplify(self, changes):
        assert self._finalized_expr is not None, "Need to call 'finalize' first"
        return self._finalized_expr.simplify(changes)


# --- FTL syntax utils ---


def span_to_position(span, source_text):
    start = span.start
    relevant = source_text[0:start]
    row = relevant.count("\n") + 1
    col = len(relevant) - relevant.rfind("\n")
    return row, col


# --- Functions ---


class FluentFunction(object):
    pass


def bool_parameter(name, param_value, local_scope):
    if not isinstance(param_value, codegen.Number):
        # TODO test this branch
        raise exceptions.TypeMismatch(
            "Expecting a number (0 or 1) for {0} parameter, "
            "got {1}".format(name, repr(param_value))
        )
    return dtypes.Bool.False_ if param_value.number == 0 else dtypes.Bool.True_


def maybe_bool_parameter(name, param_value, local_scope):
    return dtypes.Maybe.Just.apply(bool_parameter(name, param_value, local_scope))


def int_parameter(name, param_value, local_scope):
    if not isinstance(param_value, codegen.Number):
        # TODO test this branch.
        raise exceptions.TypeMismatch(
            "Expecting a number for {0} parameter, "
            "got {1}".format(repr(name, param_value))
        )
    return param_value


def maybe_int_parameter(name, param_value, local_scope):
    return dtypes.Maybe.Just.apply(int_parameter(name, param_value, local_scope))


def enum_parameter(enum_type, mapping):
    def parameter_handler(param_name, param_value, local_scope):
        if not isinstance(param_value, codegen.String):
            # TODO test this branch
            raise exceptions.TypeMismatch(
                "Expecting a string for {0} parameter, "
                "got: {1}".format(param_name, repr(param_value))
            )

        val = param_value.string_value

        if val not in mapping:
            # TODO test this branch
            raise exceptions.FunctionParameterError(
                "Invalid value '{0}' for {1} parameter. "
                "(Expecting one of {2}".format(
                    val, param_name, ", ".join(mapping.keys())
                )
            )

        enum_type_module = enum_type.module
        qualifer = local_scope.get_name_qualifier(enum_type_module)
        full_name = "{0}{1}".format(qualifer, mapping[val])
        return local_scope.variables[full_name]

    return parameter_handler


name_style_parameter = enum_parameter(
    intl_datetimeformat.NameStyle,
    {"narrow": "NarrowName", "short": "ShortName", "long": "LongName"},
)


number_style_parameter = enum_parameter(
    intl_datetimeformat.NumberStyle,
    {"numeric": "NumericNumber", "2-digit": "TwoDigitNumber"},
)


month_style_parameter = enum_parameter(
    intl_datetimeformat.MonthStyle,
    {
        "narrow": "NarrowMonth",
        "short": "ShortMonth",
        "long": "LongMonth",
        "numeric": "NumericMonth",
        "2-digit": "TwoDigitMonth",
    },
)


timezone_style_parameter = enum_parameter(
    intl_datetimeformat.TimeZoneStyle,
    {"short": "ShortTimeZone", "long": "LongTimeZone"},
)


currency_display_parameter = enum_parameter(
    intl_numberformat.CurrencyDisplay,
    {"symbol": "CurrencySymbol", "code": "CurrencyCode", "name": "CurrencyName"},
)


class DateTimeFunction(FluentFunction):
    name = "DATETIME"
    positional_args = 1
    keyword_args = {
        "hour12": maybe_bool_parameter,
        "weekday": name_style_parameter,
        "era": name_style_parameter,
        "year": number_style_parameter,
        "month": month_style_parameter,
        "day": number_style_parameter,
        "hour": number_style_parameter,
        "minute": number_style_parameter,
        "second": number_style_parameter,
        "timeZoneName": timezone_style_parameter
        # "dateStyle",  #  elm-intl doesn't support these yet
        # "timeStyle",
    }

    def compile(self, ftl_source, args, kwargs, local_scope):
        assert len(args) == 1
        arg = args[0]
        if not kwargs:
            # Simply make sure it is a FluentDate
            arg.constrain_type(fluent.FluentDate, from_ftl_source=ftl_source)
            # We will do a DateTimeFormat.format later
            return arg
        else:
            options_updates = dict(locale=local_scope.variables[LOCALE_ARG_NAME])

            for kw_name, kw_value in kwargs.items():
                handler = self.keyword_args[kw_name]
                options_updates[kw_name] = handler(kw_name, kw_value, local_scope)

            initial_opts = local_scope.add_assignment(
                "initial_opts_",
                local_scope.variables["Fluent.dateFormattingOptions"].apply(
                    arg, from_ftl_source=ftl_source
                ),
            )
            options = codegen.RecordUpdate(initial_opts, **options_updates)
            fdate = local_scope.add_assignment(
                "fdate_",
                local_scope.variables["Fluent.reformattedDate"].apply(
                    options, arg, from_ftl_source=ftl_source
                ),
            )
            return fdate


class NumberFunction(FluentFunction):
    name = "NUMBER"
    positional_args = 1
    keyword_args = {
        "currencyDisplay": currency_display_parameter,
        "useGrouping": bool_parameter,
        "minimumIntegerDigits": maybe_int_parameter,
        "minimumFractionDigits": maybe_int_parameter,
        "maximumFractionDigits": maybe_int_parameter,
        "minimumSignificantDigits": maybe_int_parameter,
        "maximumSignificantDigits": maybe_int_parameter,
    }

    def compile(self, ftl_source, args, kwargs, local_scope):

        assert len(args) == 1
        arg = args[0]
        if not kwargs:
            # If arg is a literal number, leave it as such, we will deal with it
            # later. This means that hard coded literal numbers don't incur the
            # overhead of creating NumberFormat objects unless necessary
            if isinstance(arg, codegen.Number):
                return arg
            # Otherwise (external arguments) make it a FluentNumber
            arg.constrain_type(fluent.FluentNumber, from_ftl_source=ftl_source)
            # We will do a NumberFormat.format later
            return arg

        else:
            options_updates = dict(locale=local_scope.variables[LOCALE_ARG_NAME])

            for kw_name, kw_value in kwargs.items():
                handler = self.keyword_args[kw_name]
                options_updates[kw_name] = handler(kw_name, kw_value, local_scope)

            if arg.type == dtypes.Number:
                default_opts = local_scope.add_assignment(
                    "defaults_", local_scope.variables["NumberFormat.defaults"]
                )
                options = codegen.RecordUpdate(default_opts, **options_updates)
                fnum = local_scope.add_assignment(
                    "fnum_",
                    local_scope.variables["Fluent.formattedNumber"].apply(
                        options, arg, from_ftl_source=ftl_source
                    ),
                )
            else:
                initial_opts = local_scope.add_assignment(
                    "initial_opts_",
                    local_scope.variables["Fluent.numberFormattingOptions"].apply(
                        arg, from_ftl_source=ftl_source
                    ),
                )
                options = codegen.RecordUpdate(initial_opts, **options_updates)
                fnum = local_scope.add_assignment(
                    "fnum_",
                    local_scope.variables["Fluent.reformattedNumber"].apply(
                        options, arg, from_ftl_source=ftl_source
                    ),
                )
            return fnum


DateTimeFunction = DateTimeFunction()
NumberFunction = NumberFunction()

FUNCTIONS = {f.name: f for f in [DateTimeFunction, NumberFunction]}
