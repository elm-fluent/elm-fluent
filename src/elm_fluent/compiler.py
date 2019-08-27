import contextlib
from collections import OrderedDict, defaultdict

import attr
from fluent.syntax import FluentParser, ast

from . import codegen, error_types, html_compiler, inference, types
from .stubs import (
    defaults as dtypes,
    fluent,
    html,
    html_attributes,
    intl_datetimeformat,
    intl_locale,
    intl_numberformat,
    intl_pluralrules,
)
from .stubs.defaults import default_imports
from .utils import (
    FtlSource,
    ast_to_id,
    attribute_ast_to_id,
    get_ast_nodes,
    get_term_used_variables,
    is_cldr_plural_form_key,
    reference_to_id,
    traverse_ast,
)

try:
    from functools import singledispatch
except ImportError:
    # Python < 3.4
    from singledispatch import singledispatch

# Unicode bidi isolation characters.
FSI = "\u2068"
PDI = "\u2069"


# Choose names with final underscores to avoid clashes with message IDs
MESSAGE_ARGS_NAME = "args_"
LOCALE_ARG_NAME = "locale_"
ATTRS_ARG_NAME = "attrs_"
ALL_MESSAGE_FUNCTION_ARGS = [LOCALE_ARG_NAME, MESSAGE_ARGS_NAME, ATTRS_ARG_NAME]

PLURAL_FORM_FOR_NUMBER_NAME = "plural_form_for_number"


@attr.s
class CurrentEnvironment(object):
    # The parts of CompilerEnvironment that we want to mutate (and restore)
    # temporarily for some parts of a call chain.
    message_id = attr.ib(default=None)
    term_args = attr.ib(default=None)
    html_context = attr.ib(default=False)


@attr.s
class CompilerEnvironment(object):
    locale = attr.ib()
    use_isolating = attr.ib()
    message_mapping = attr.ib(factory=dict)
    errors = attr.ib(factory=list)
    functions = attr.ib(factory=dict)
    message_ids_to_ast = attr.ib(factory=dict)
    term_ids_to_ast = attr.ib(factory=dict)
    source_filename = attr.ib(default=None)
    messages_string = attr.ib(default=None)
    message_arg_types = attr.ib(default=None)
    dynamic_html_attributes = attr.ib(default=True)
    current = attr.ib(factory=CurrentEnvironment)

    def add_current_message_error(self, error, exprs):
        for expr in exprs:
            error.error_sources.append(self.make_ftl_source(expr))
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

    def modified_for_term_reference(self, term_args=None):
        return self.modified(term_args=term_args if term_args is not None else {})

    def make_ftl_source(self, expr):
        return FtlSource(
            expr=expr,
            message_id=self.current.message_id,
            source_filename=self.source_filename,
            messages_string=self.messages_string,
        )


def parse_ftl(source):
    resource = FluentParser().parse(source)
    messages = OrderedDict()
    junk = []
    for item in resource.body:
        if isinstance(item, ast.Message):
            messages[ast_to_id(item)] = item
        elif isinstance(item, ast.Term):
            messages[ast_to_id(item)] = item
        elif isinstance(item, ast.Junk):
            junk.append(item)
    return messages, junk


def compile_messages(
    messages_string,
    locale,
    source_filename=None,
    module_name=None,
    use_isolating=True,
    dynamic_html_attributes=True,
):
    """
    Compile messages_string to Elm code.

    locale is BCP47 locale (currently unused)

    source_filename is a filename that the messages came from

    Returns a tuple:
       (elm_source,
        error_list,
        message_id_to_function_name_mapping,
        arg_types,
       )

    elm_source will not be valid Elm source if error_list is not empty.

    The error list is itself a list of two tuples:
       (message id, exception object)

    arg_types is from inference.infer_arg_types
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
        source_filename=source_filename,
        messages_string=messages_string,
        dynamic_html_attributes=dynamic_html_attributes,
        message_arg_types=None,  # later
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
        err = error_types.JunkFound(
            "Junk found: " + "; ".join(a.message for a in junk_item.annotations),
            junk_item.annotations,
        )
        err.error_sources.append(
            FtlSource(
                expr=junk_item,
                source_filename=compiler_env.source_filename,
                message_id=None,
                messages_string=compiler_env.messages_string,
            )
        )
        compiler_env.errors.append(err)

    # Pass one, find all the names, so that we can populate message_mapping,
    # which is needed for compilation.
    for msg_id, msg in message_ids_to_ast.items():
        function_name = module.reserve_name(
            message_function_name_for_msg_id(msg_id)
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
    # Pass 2, type inference of message args
    message_arg_types = inference.infer_arg_types(message_ids_to_ast, sorted_message_ids, source_filename,
                                                  messages_string)
    compiler_env.message_arg_types = message_arg_types

    # Pass 3, actual compilation
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
                    error_types.BadMessageId(error_msg), [msg]
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
    return (module, compiler_env.errors, compiler_env.message_mapping, message_arg_types)


def compile_master(module_name, locales, locale_modules, message_mapping, locale_message_arg_types, options):
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
    locale_module_local_names = OrderedDict([
        (locale, module_name_for_locale(locale)) for locale in locales
    ])

    for locale, locale_module in locale_modules.items():
        if locale_module.exports:
            module.add_import(locale_module, locale_module_local_names[locale])

    sub_module_exports = {
        locale: locale_module.exports
        for locale, locale_module in locale_modules.items()
    }
    for locale in locales:
        if locale not in sub_module_exports:
            sub_module_exports[locale] = []
    all_sub_module_exports = set(
        [e for exports in sub_module_exports.values() for e in exports]
    )

    for func_name in sorted(all_sub_module_exports):
        function_name = module.reserve_name(func_name)
        assert function_name == func_name, "{0} != {1} unexpectedly".format(
            function_name, func_name
        )
        message_id = func_name_to_message_id[function_name]
        combined_arg_types, arg_type_errors = combine_arg_types_master(locale_message_arg_types, message_id)
        errors.extend(arg_type_errors)
        function_type = function_type_for_func_name(func_name, combined_arg_types)

        function = codegen.Function(
            parent_scope=module,
            name=function_name,
            args=function_args_for_func_name(function_name),
            function_type=function_type,
        )
        locale_tag_expr = function.variables["Locale.toLanguageTag"].apply(
            function.variables[LOCALE_ARG_NAME]
        )
        lower_cased_locale_tag_expr = function.variables["String.toLower"].apply(
            locale_tag_expr
        )
        case_expr = codegen.Case(lower_cased_locale_tag_expr, parent_scope=function)

        def do_call(l):
            return function.variables[
                "{0}.{1}".format(locale_module_local_names[l], func_name)
            ].apply(
                *[
                    function.variables[a]
                    for a in function_args_for_func_name(func_name)
                ]
            )

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


def function_args_for_func_name(func_name):
    if is_html_message_func_name(func_name):
        return [LOCALE_ARG_NAME, MESSAGE_ARGS_NAME, ATTRS_ARG_NAME]
    else:
        return [LOCALE_ARG_NAME, MESSAGE_ARGS_NAME]


def record_type_for_arg_types(external_arg_types):
    args_type = types.Record()
    for name, inferred_type in external_arg_types.items():
        elm_type, ftl_sources = inferred_type_to_elm_type(inferred_type)
        args_type.add_field(name, elm_type, ftl_sources=ftl_sources)
    return args_type


def combine_arg_types_master(locale_message_arg_types, message_id):
    """
    Given a dictionary {locale: arg_types} where arg_types
    is return value of inference.infer_arg_types, and a message_id,
    returns (combined arg_types, list of errors)
    """
    errors = []
    combined = defaultdict(list)
    for locale, messages_arg_types in locale_message_arg_types.items():
        if message_id not in messages_arg_types:
            continue
        arg_types = messages_arg_types[message_id]  # {arg_name: arg_type}
        for arg_name, arg_type in arg_types.items():
            combined[arg_name].append(arg_type)

    # Now detect conflicts
    retval = {}
    for arg_name, arg_type_list in combined.items():
        # We ignore Conflicts, because they'll be reported elsewhere
        # and we don't want cascading errors
        non_conflict_types = [arg_type for arg_type in arg_type_list
                              if not isinstance(arg_type, inference.Conflict)]
        different_types = set([arg_type.type for arg_type in non_conflict_types])
        if len(different_types) > 1:
            # combine_inferred_types is guaranteed to return a Conflict instance
            # for us:
            conflict = inference.combine_inferred_types(
                [(arg_name, inferred_type)
                 for inferred_type in non_conflict_types],
                None)[arg_name]
            errors.append(error_types.ArgumentConflictError(
                message_id=message_id,
                arg_name=arg_name,
                conflict=conflict,
                master=True,
            ))

        retval[arg_name] = non_conflict_types[0] if non_conflict_types else arg_type_list[0]
    return retval, errors


def function_type_for_func_name(func_name, external_arg_types):
    args_type = record_type_for_arg_types(external_arg_types)
    if is_html_message_func_name(func_name):
        msg = types.TypeParam("msg")
        return types.Function.for_multiple_inputs(
            [
                intl_locale.Locale,
                args_type,
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
            [intl_locale.Locale, args_type], dtypes.String
        )


def inferred_type_to_elm_type(inferred_type):
    """
    Given an InferredType (or Conflict), returns an Elm Type
    and a list of FtlSource
    """
    if isinstance(inferred_type, inference.Conflict):
        # We will report the error elsewhere
        return types.Conflict, []
    return {
        inference.String: dtypes.String,
        inference.Number: fluent.FluentNumber,
        inference.DateTime: fluent.FluentDate,
    }[inferred_type.type], inferred_type.evidences


def get_message_function_ast(message_dict):
    for msg_id, msg in message_dict.items():
        if isinstance(msg, ast.Term):
            continue
        if msg.value is not None:  # has a body
            yield (msg_id, msg)
        for attribute in msg.attributes:
            yield (attribute_ast_to_id(attribute, msg), attribute)


def get_term_ast(message_dict):
    for term_id, term in message_dict.items():
        if isinstance(term, ast.Message):
            pass
        if term.value is not None:  # has a body
            yield (term_id, term)
        for attribute in term.attributes:
            yield (attribute_ast_to_id(attribute, term), attribute)


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
    arg_types = compiler_env.message_arg_types[msg_id]
    for arg_name, arg_type in arg_types.items():
        if isinstance(arg_type, inference.Conflict):
            compiler_env.errors.append(error_types.ArgumentConflictError(
                message_id=msg_id,
                arg_name=arg_name,
                conflict=arg_type,
            ))

    function_type = function_type_for_func_name(function_name, arg_types)
    module.set_type(function_name, function_type)
    msg_func = codegen.Function(
        parent_scope=module,
        name=function_name,
        args=function_args_for_func_name(function_name),
        function_type=function_type,
    )

    if contains_reference_cycle(msg, compiler_env):
        error = error_types.CyclicReferenceError(
            "Cyclic reference in {0}".format(msg_id)
        )
        compiler_env.add_current_message_error(error, [msg])
        return codegen.CompilationError()
    else:
        return_expression = compile_expr(msg, msg_func.body, compiler_env)
    msg_func.body.value = return_expression
    return msg_func


def get_processing_order(message_ids_to_ast):
    """
    Given a dictionary of {message_id: Message},
    returns a dictionary {message_id: processing order}
    """
    call_graph = {}

    for msg_id, msg in message_ids_to_ast.items():
        calls = []

        for node in get_ast_nodes(msg):
            if not isinstance(node, ast.BaseNode):
                continue

            if isinstance(node, ast.MessageReference):
                ref = reference_to_id(node)
                if ref in message_ids_to_ast:
                    calls.append(ref)

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


def contains_reference_cycle(msg, compiler_env):
    """
    Returns True if the message 'msg' contains a cyclic reference,
    in the context of the other messages provided in compiler_env
    """
    # We traverse the AST starting from message, jumping to other messages and
    # terms as necessary, and seeing if a path through the AST loops back to
    # previously visited nodes at any point.

    # This algorithm has some bugs compared to the runtime method in resolver.py
    # For example, a pair of conditionally mutually recursive messages:

    # foo = Foo { $arg ->
    #      [left]    { bar }
    #     *[right]   End
    #  }

    # bar = Bar { $arg ->
    #     *[left]    End
    #      [right]   { foo }
    #  }

    # These messages are rejected as containing cycles by this checker, when in
    # fact they cannot go into an infinite loop, and the resolver correctly
    # executes them.

    # It is pretty difficult to come up with a compelling use case
    # for this kind of thing though... so we are not too worried
    # about fixing this bug, since we are erring on the conservative side.

    message_ids_to_ast = compiler_env.message_ids_to_ast
    term_ids_to_ast = compiler_env.term_ids_to_ast

    # We need to keep track of visited nodes. If we use just a single set for
    # each top level message, then things like this would be rejected:
    #
    #     message = { -term } { -term }
    #
    # because we would visit the term twice.
    #
    # So we have a stack of sets:
    visited_node_stack = [set([])]
    # The top of this stack represents the set of nodes in the current path of
    # visited nodes. We push a copy of the top set onto the stack when we
    # traverse into a sub-node, and pop it off when we come back.

    checks = []

    def checker(node):
        if isinstance(node, ast.BaseNode):
            node_id = id(node)
            if node_id in visited_node_stack[-1]:
                checks.append(True)
                return
            visited_node_stack[-1].add(node_id)
        else:
            return

        # The logic below duplicates the logic that is used for 'jumping' to
        # different nodes (messages via a runtime function call, terms via
        # inlining), including the fallback strategies that are used.
        sub_node = None
        if isinstance(node, (ast.MessageReference, ast.TermReference)):
            ref_id = reference_to_id(node)
            if ref_id in message_ids_to_ast:
                sub_node = message_ids_to_ast[ref_id]
            elif ref_id in term_ids_to_ast:
                sub_node = term_ids_to_ast[ref_id]

        if sub_node is not None:
            visited_node_stack.append(visited_node_stack[-1].copy())
            traverse_ast(sub_node, checker)
            if any(checks):
                return
            visited_node_stack.pop()

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
        parts.append(render_to_string(compile_expr(element, local_scope, compiler_env), local_scope, compiler_env))
        if wrap_this_with_isolating:
            parts.append(codegen.String(PDI))

    return codegen.StringConcat(parts)


@compile_expr.register(ast.TextElement)
def compile_expr_text(text, local_scope, compiler_env):
    return codegen.String(text.value, ftl_source=compiler_env.make_ftl_source(text))


@compile_expr.register(ast.StringLiteral)
def compile_expr_string_expression(expr, local_scope, compiler_env):
    return codegen.String(expr.parse()['value'], ftl_source=compiler_env.make_ftl_source(expr))


@compile_expr.register(ast.NumberLiteral)
def compile_expr_number_expression(expr, local_scope, compiler_env):
    return codegen.Number(numeric_to_native(expr.value), ftl_source=compiler_env.make_ftl_source(expr))


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
    name = reference_to_id(reference)
    if compiler_env.current.term_args is not None:
        compiler_env.add_current_message_error(
            error_types.ReferenceError(
                "Message '{0}' called from within a term".format(name)
            ),
            [reference],
        )
    return do_message_call(name, local_scope, reference, compiler_env)


@compile_expr.register(ast.TermReference)
def compile_expr_term_reference(reference, local_scope, compiler_env):
    term_id = reference_to_id(reference)
    if term_id in compiler_env.term_ids_to_ast:
        term = compiler_env.term_ids_to_ast[term_id]

        if reference.arguments:
            args = [compile_expr(arg, local_scope, compiler_env) for arg in reference.arguments.positional]
            kwargs = {
                kwarg.name.name: compile_expr(kwarg.value, local_scope, compiler_env)
                for kwarg in reference.arguments.named
            }
        else:
            args = []
            kwargs = {}

        if args:
            compiler_env.add_current_message_error(
                error_types.TermParameterError(
                    "Positional arguments passed to term '{0}'".format(
                        reference_to_id(reference)
                    )
                ),
                [reference],
            )
            return codegen.CompilationError()

        used_variables = get_term_used_variables(term, compiler_env)
        bad_kwarg = False
        for kwarg_name in kwargs:
            if kwarg_name not in used_variables:
                bad_kwarg = True
                if len(used_variables) > 0:
                    compiler_env.add_current_message_error(
                        error_types.TermParameterError(
                            "Parameter '{0}' was passed to term '{1}' which does not take this parameter. Did you mean: {2}?".format(
                                kwarg_name,
                                term_id,
                                ", ".join(sorted(used_variables)),
                            )
                        ),
                        [reference],
                    )
                else:
                    compiler_env.add_current_message_error(
                        error_types.TermParameterError(
                            "Parameter '{0}' was passed to term '{1}' which does not take parameters.".format(
                                kwarg_name, term_id
                            )
                        ),
                        [reference],
                    )
        if bad_kwarg:
            return codegen.CompilationError()

        return compile_term(term, local_scope, compiler_env, term_args=kwargs)
    else:
        return unknown_reference(term_id, local_scope, reference, compiler_env)


def compile_term(term, local_scope, compiler_env, term_args=None):
    with compiler_env.modified_for_term_reference(term_args=term_args):
        return compile_expr(term.value, local_scope, compiler_env)


def do_message_call(name, local_scope, expr, compiler_env):
    if name in compiler_env.message_mapping:
        msg_func_name = compiler_env.message_mapping[name]
        # If in HTML context, can call either plain or HTML.
        # But plain text context cannot call HTML context
        if not compiler_env.current.html_context:
            if is_html_message_id(name):
                compiler_env.add_current_message_error(
                    error_types.HtmlTypeMismatch(
                        "Cannot use HTML message {0} from plain text context.".format(
                            name
                        )
                    ),
                    [expr],
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
        error = error_types.ReferenceError("Unknown term: {0}".format(name))
    else:
        error = error_types.ReferenceError("Unknown message: {0}".format(name))
    compiler_env.add_current_message_error(error, [expr])
    return codegen.CompilationError()


@compile_expr.register(ast.SelectExpression)
def compile_expr_select_expression(select_expr, local_scope, compiler_env):
    selector_value = compile_expr(select_expr.selector, local_scope, compiler_env)

    static_retval = resolve_select_expression_statically(
        select_expr, selector_value, local_scope, compiler_env
    )
    if static_retval is not None:
        return static_retval

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

    if any_numerics:
        numeric_key = True
    elif all_plural_forms:
        numeric_key = True
    else:
        # No numerics, and some of the strings are not plural form categories
        numeric_key = False

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
        elif selector_value.type == types.Conflict:
            number_val = codegen.Number(0)  # to allow compilation to continue
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
            key_value = compile_expr(variant.key, local_scope, compiler_env)
            if key_value.type != case_selector_value.type and case_selector_value.type != types.Conflict:
                compiler_env.add_current_message_error(
                    error_types.TypeMismatch('''variant key "{0}" of type '{1}' is not compatible with type '{2}' of selector'''.format(
                        key_value.ftl_source.expr_as_text(),
                        key_value.type,
                        case_selector_value.type
                    )), [variant.key, select_expr.selector])

            # After having checked types above, for default case we actually
            # replace with an 'otherwise' matcher.
            if variant.default:
                key_value = codegen.Otherwise()

            branch = case_expr.add_branch(key_value)
            branch.value = compile_expr(variant.value, branch, compiler_env)

        return case_expr


def resolve_select_expression_statically(select_expr, selector_ast, block, compiler_env):
    """
    Resolve a select expression statically, given a codegen.ElmAst object
    `selector_ast` representing the key value, or return None if not possible.
    """
    # We need to 'peek' inside what we've produce so far to see if it is something
    # static. To do that reliably we must simplify at this point:
    selector_ast = codegen.simplify(selector_ast)
    selector_is_default = isinstance(selector_ast, Default)
    selector_is_number = isinstance(selector_ast, codegen.Number)
    selector_is_string = isinstance(selector_ast, codegen.String)
    if not (selector_is_string or selector_is_number or selector_is_default):
        return None

    if selector_is_number:
        if isinstance(selector_ast, codegen.Number):
            key_number_value = selector_ast.number
        else:
            # peek into the number literal inside the `NUMBER` call.
            key_number_value = selector_ast.args[0].number

    default_variant = None
    found = None
    non_numeric_variant_present = False

    for variant in select_expr.variants:
        if variant.default:
            default_variant = variant
            if selector_is_default:
                found = variant
                break
        if selector_is_string:
            if (
                isinstance(variant.key, ast.Identifier)
                and selector_ast.string_value == variant.key.name
            ):
                found = variant
                break
        elif selector_is_number:
            if isinstance(
                variant.key, ast.NumberLiteral
            ) and key_number_value == numeric_to_native(variant.key.value):
                found = variant
                break
            elif isinstance(variant.key, ast.Identifier):
                # We would a plural category function to check, which we don't
                # have at compile time, so bail out
                non_numeric_variant_present = True

    if found is None:
        if non_numeric_variant_present:
            return None
        else:
            found = default_variant

    return compile_expr(found.value, block, compiler_env)


@compile_expr.register(ast.Identifier)
def compile_expr_identifier(name, local_scope, compiler_env):
    return codegen.String(name.name, ftl_source=compiler_env.make_ftl_source(name))


@compile_expr.register(ast.VariableReference)
def compile_expr_variable_reference(argument, local_scope, compiler_env):
    name = argument.id.name

    if compiler_env.current.term_args is not None:
        # We are in a term, all args are passed explicitly, not inherited from
        # external args.
        if name in compiler_env.current.term_args:
            return compiler_env.current.term_args[name]
        return Default()

    # Otherwise we are in a message, lookup at runtime
    # TODO - some kind of sanitising on the argument name
    args_var = local_scope.variables[MESSAGE_ARGS_NAME]
    inferred_type = compiler_env.message_arg_types[compiler_env.current.message_id][name]
    elm_type, _ = inferred_type_to_elm_type(inferred_type)
    arg = codegen.AttributeReference(args_var, name, type=elm_type)
    return arg


@compile_expr.register(ast.FunctionReference)
def compile_expr_call_expression(expr, local_scope, compiler_env):

    function_name = expr.id.name

    if function_name not in compiler_env.functions:
        error = error_types.ReferenceError("Unknown function: {0}".format(function_name))
        compiler_env.add_current_message_error(error, [expr])
        return codegen.CompilationError()

    function_spec = compiler_env.functions[function_name]

    compiled_args = [compile_expr(arg, local_scope, compiler_env) for arg in expr.arguments.positional]

    match = True
    compiled_kwargs = {}
    for kwarg in expr.arguments.named:
        kwarg_name = kwarg.name.name
        if kwarg_name not in function_spec.keyword_args:
            match = False
            compiler_env.add_current_message_error(
                error_types.FunctionParameterError(
                    "{0}() got an unexpected keyword argument '{1}'".format(
                        function_spec.name,
                        kwarg_name)),
                [kwarg.name]
            )
        kwarg_value = compile_expr(kwarg.value, local_scope, compiler_env)
        compiled_kwargs[kwarg_name] = kwarg_value

    if not function_spec.positional_args == len(compiled_args):
        match = False
        compiler_env.add_current_message_error(
            error_types.FunctionParameterError(
                "{0}() takes {1} positional argument(s) but {2} were given".format(
                    function_spec.name, function_spec.positional_args, len(compiled_args)
                )),
            [expr])

    if not match:
        return codegen.CompilationError()

    return function_spec.compile(
        expr, compiled_args, compiled_kwargs, local_scope, compiler_env,
    )


def render_to_string(compiled_expr, local_scope, compiler_env):
    """
    Wrap a codegen.ElmAst object with whatever is needed to convert it
    to a string.
    """
    if compiled_expr.type == dtypes.String:
        # Underlying type is also string, no more to do
        return compiled_expr
    if compiled_expr.type == dtypes.Number:
        return local_scope.variables[
            "NumberFormat.format"
        ].apply(
            local_scope.variables["NumberFormat.fromLocale"].apply(
                local_scope.variables[LOCALE_ARG_NAME]
            ),
            compiled_expr,
        )
    if compiled_expr.type == fluent.FluentNumber:
        return local_scope.variables[
            "Fluent.formatNumber"
        ].apply(local_scope.variables[LOCALE_ARG_NAME], compiled_expr)
    if compiled_expr.type == fluent.FluentDate:
        return local_scope.variables[
            "Fluent.formatDate"
        ].apply(local_scope.variables[LOCALE_ARG_NAME], compiled_expr)
    if isinstance(compiled_expr, codegen.CompilationError):
        return compiled_expr
    raise NotImplementedError(
        "Don't know how to convert object {0} of type {1} to string".format(
            compiled_expr, compiled_expr.type
        ))


class Default(codegen.Expression):
    """
    Sentinel object for selecting default value in variant list
    """

    def sub_expressions(self):
        return []


# --- Functions ---


class FluentFunction(object):
    pass


def bool_parameter(name, param_value, local_scope, compiler_env):
    if not isinstance(param_value, codegen.Number):
        compiler_env.add_current_message_error(error_types.FunctionParameterError(
            "Expecting a number (0 or 1) for {0} parameter, "
            "got {1}".format(name, param_value.ftl_source.expr_as_text())
        ), [param_value.ftl_source.expr])
        return codegen.CompilationError()

    return dtypes.Bool.False_ if param_value.number == 0 else dtypes.Bool.True_


def maybe_bool_parameter(name, param_value, local_scope, compiler_env):
    return dtypes.Maybe.Just.apply(bool_parameter(name, param_value, local_scope, compiler_env))


def int_parameter(name, param_value, local_scope, compiler_env):
    if not isinstance(param_value, codegen.Number):
        compiler_env.add_current_message_error(error_types.FunctionParameterError(
            "Expecting a number for {0} parameter, "
            "got {1}".format(name, param_value.ftl_source.expr_as_text())
        ), [param_value.ftl_source.expr])
        return codegen.CompilationError()
    return param_value


def maybe_int_parameter(name, param_value, local_scope, compiler_env):
    return dtypes.Maybe.Just.apply(int_parameter(name, param_value, local_scope, compiler_env))


def enum_parameter(enum_type, mapping):
    def parameter_handler(param_name, param_value, local_scope, compiler_env):
        if not isinstance(param_value, codegen.String) or param_value.string_value not in mapping:
            compiler_env.add_current_message_error(
                error_types.FunctionParameterError(
                    "Expecting one of {0} for {1} parameter, got {2}".format(
                        ", ".join('"{}"'.format(k) for k in sorted(mapping.keys())),
                        param_name,
                        param_value.ftl_source.expr_as_text())),
                [param_value.ftl_source.expr])
            return codegen.CompilationError()

        enum_type_module = enum_type.module
        qualifer = local_scope.get_name_qualifier(enum_type_module)
        full_name = "{0}{1}".format(qualifer, mapping[param_value.string_value])
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

    def compile(self, expr, args, kwargs, local_scope, compiler_env):
        assert len(args) == 1
        ftl_source = compiler_env.make_ftl_source(expr)
        arg = args[0]
        types_correct = arg.type == fluent.FluentDate
        if not types_correct and arg.type != types.Conflict:
            compiler_env.add_current_message_error(
                error_types.TypeMismatch("DATETIME() expected date argument, found '{0}'".format(arg.type)),
                [expr],
            )
        if types_correct and not kwargs:
            # We will do a DateTimeFormat.format later, can just return the arg for now
            return arg
        else:
            options_updates = dict(locale=local_scope.variables[LOCALE_ARG_NAME])

            for kw_name, kw_value in kwargs.items():
                handler = self.keyword_args[kw_name]
                options_updates[kw_name] = handler(kw_name, kw_value, local_scope, compiler_env)

            initial_opts = local_scope.add_assignment(
                "initial_opts_",
                local_scope.variables["Fluent.dateFormattingOptions"].apply(
                    arg, ftl_source=ftl_source
                ),
            )
            options = codegen.RecordUpdate(initial_opts, **options_updates)
            fdate = local_scope.add_assignment(
                "fdate_",
                local_scope.variables["Fluent.reformattedDate"].apply(
                    options, arg, ftl_source=ftl_source
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

    def compile(self, expr, args, kwargs, local_scope, compiler_env):
        ftl_source = compiler_env.make_ftl_source(expr)
        assert len(args) == 1
        arg = args[0]
        if isinstance(arg, Default):
            return arg
        types_correct = arg.type in (fluent.FluentNumber, dtypes.Number)
        if not types_correct and arg.type != types.Conflict:
            compiler_env.add_current_message_error(
                error_types.TypeMismatch("NUMBER() expected numeric argument, found '{0}'".format(arg.type)),
                [expr],
            )
        if types_correct and not kwargs:
            # If arg is a literal number, leave it as such, we will deal with it
            # later. This means that hard coded literal numbers don't incur the
            # overhead of creating NumberFormat objects unless necessary
            if isinstance(arg, codegen.Number):
                return arg
            # We will do a NumberFormat.format later
            return arg

        else:
            options_updates = dict(locale=local_scope.variables[LOCALE_ARG_NAME])

            for kw_name, kw_value in kwargs.items():
                handler = self.keyword_args[kw_name]
                options_updates[kw_name] = handler(kw_name, kw_value, local_scope, compiler_env)

            if arg.type == dtypes.Number:
                default_opts = local_scope.add_assignment(
                    "defaults_", local_scope.variables["NumberFormat.defaults"]
                )
                options = codegen.RecordUpdate(default_opts, **options_updates)
                fnum = local_scope.add_assignment(
                    "fnum_",
                    local_scope.variables["Fluent.formattedNumber"].apply(
                        options, arg, ftl_source=ftl_source
                    ),
                )
            else:
                initial_opts = local_scope.add_assignment(
                    "initial_opts_",
                    local_scope.variables["Fluent.numberFormattingOptions"].apply(
                        arg, ftl_source=ftl_source
                    ),
                )
                options = codegen.RecordUpdate(initial_opts, **options_updates)
                fnum = local_scope.add_assignment(
                    "fnum_",
                    local_scope.variables["Fluent.reformattedNumber"].apply(
                        options, arg, ftl_source=ftl_source
                    ),
                )
            return fnum


DateTimeFunction = DateTimeFunction()
NumberFunction = NumberFunction()

FUNCTIONS = {f.name: f for f in [DateTimeFunction, NumberFunction]}
