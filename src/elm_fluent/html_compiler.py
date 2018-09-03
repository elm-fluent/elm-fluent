"""
HTML specific compilation functions
"""
import re

import bs4
import six
from fluent.syntax import ast

from . import codegen
from .stubs import defaults as dtypes, html, html_attributes

text_type = six.text_type

html_output_type = dtypes.List.specialize(a=html.Html)


def compile_pattern(pattern, local_scope, compiler_env):
    skeleton, expr_replacements = replace_non_text_expressions(pattern.elements)
    # TODO - handle parse failures gracefully, and check the parser is ensuring
    # well-formedness
    dom = bs4.BeautifulSoup("<root>{0}</root>".format(skeleton), "lxml").find("root")

    return dom_nodes_to_elm(
        list(dom.children), expr_replacements, local_scope, compiler_env
    )


def dom_nodes_to_elm(nodes, expr_replacements, local_scope, compiler_env):
    # We have to structure this as a list of lists, then do a List.concat
    # at the end. In many cases the List.concat will disappear after
    # simplify.

    items = []
    for node in nodes:
        if isinstance(node, bs4.element.NavigableString):
            parts = interpolate_replacements(text_type(node), expr_replacements)
            for part in parts:
                if isinstance(part, text_type):
                    items.append(
                        codegen.List(
                            [
                                local_scope.variables["Html.text"].apply(
                                    codegen.String(part)
                                )
                            ]
                        )
                    )
                else:
                    val = compiler.compile_expr(part, local_scope, compiler_env)
                    # TODO - we should optimize outputted code by replacing:
                    #  [ ...
                    #  , Html.text a
                    #  , Html.text b
                    #  , Html.text c
                    #  ...
                    #  ]
                    #
                    # with:
                    # [ ...
                    # , Html.text (String.concat [a, b, c])
                    # ...
                    # ]

                    if val.type == html_output_type:
                        # This is a list type, so simply append to our list of lists
                        items.append(val)
                    else:
                        val = local_scope.variables["Html.text"].apply(
                            compiler.Stringable(val, local_scope)
                        )
                        items.append(codegen.List([val]))
        else:
            assert isinstance(node, bs4.element.Tag)
            tag_name = node.name.lower()
            static_attributes = []
            for attr_name, attr_value in sorted(node.attrs.items()):
                if isinstance(attr_value, list):
                    # Bs4 treats class attribute differently, returns a list, which we convert
                    # back to a string here:
                    attr_value = " ".join(attr_value)

                attr_value_parts = interpolate_replacements(
                    attr_value, expr_replacements
                )
                attr_output_parts = []
                for part in attr_value_parts:
                    if isinstance(part, text_type):
                        attr_output_parts.append(codegen.String(part))
                    else:
                        with compiler_env.modified(html_context=False):
                            attr_output_parts.append(
                                compiler.compile_expr(part, local_scope, compiler_env)
                            )
                attr_final_value = codegen.StringConcat(attr_output_parts)

                if attr_name in html_attributes.ATTRIBUTES:
                    attr_constructor = local_scope.variables[
                        "Attributes.{0}".format(attr_name)
                    ]
                else:
                    attr_constructor = local_scope.variables[
                        "Attributes.attribute"
                    ].apply(codegen.String(attr_name))
                static_attributes.append(attr_constructor.apply(attr_final_value))

            if compiler_env.dynamic_html_attributes:
                selectors_for_node = codegen.List(
                    list(map(codegen.String, get_selectors_for_node(node)))
                )
                dynamic_attributes = local_scope.variables[
                    "Fluent.selectAttributes"
                ].apply(
                    local_scope.variables[compiler.ATTRS_ARG_NAME], selectors_for_node
                )
            else:
                dynamic_attributes = codegen.List([])
            attributes = codegen.ListConcat(
                [codegen.List(static_attributes), dynamic_attributes],
                dtypes.List.specialize(a=html.Attribute),
            )

            sub_items = dom_nodes_to_elm(
                list(node.children), expr_replacements, local_scope, compiler_env
            )
            if tag_name in html.ELEMENTS:
                node_constructor = local_scope.variables["Html.{0}".format(tag_name)]
            else:
                node_constructor = local_scope.variables["Html.node"].apply(
                    codegen.String(tag_name)
                )
            item = node_constructor.apply(attributes, sub_items)
            items.append(codegen.List([item]))

    return codegen.ListConcat(items, html_output_type)


def replace_non_text_expressions(elements):
    """
    Given a list of ast.Expression objects, returns a string
    with replacement markers and a dictionary of replacement info
    """
    parts = []
    expr_replacements = {}

    for element in elements:
        if isinstance(element, ast.TextElement):
            parts.append(element.value)
        else:
            # Need a replacement that doesn't have any special HTML chars in it
            # that would cause the HTML parser to do anything funny with it.
            # TODO - some mechanism that would guarantee this generated string
            # does not appear by chance in the actual message.
            replacement_name = "SSS{0}EEE".format(str(id(element)))
            expr_replacements[replacement_name] = element
            parts.append(replacement_name)

    return "".join(parts), expr_replacements


def interpolate_replacements(text, expr_replacements):
    """
    Given a text with replacement markers, and a dictionary
    of replacement markers to expression objects, returns
    a list containing text/expression objects.
    """
    if not expr_replacements:
        return [text]

    replacement_strings = list(expr_replacements.keys())
    splitter = re.compile(
        "({0})".format("|".join(re.escape(r) for r in replacement_strings))
    )
    split_text = [p for p in splitter.split(text) if p]
    return [expr_replacements.get(t, t) for t in split_text]


def get_selectors_for_node(node):
    tag_name = node.name.lower()
    yield tag_name

    classes = node.attrs.get("class", [])
    for class_ in classes:
        class_selector = ".{0}".format(class_)
        yield class_selector
        yield tag_name + class_selector

    id = node.attrs.get("id", None)
    if id is not None:
        id_selector = "#{0}".format(id)
        yield id_selector
        yield tag_name + id_selector

    for attr_name, attr_value in sorted(node.attrs.items()):
        if attr_name in ["id", "class"]:
            continue

        attr_present_selector = "[{0}]".format(attr_name)
        yield attr_present_selector
        yield tag_name + attr_present_selector

        attr_value_selector = '[{0}="{1}"]'.format(attr_name, attr_value)
        yield attr_value_selector
        yield tag_name + attr_value_selector


from . import compiler  # flake8: noqa  isort:skip
