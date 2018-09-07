"""
HTML specific compilation functions
"""
from __future__ import absolute_import, unicode_literals

import re

import bs4
import six
from fluent.syntax import ast

from elm_fluent import codegen
from elm_fluent.stubs import defaults as dtypes, html, html_attributes

text_type = six.text_type
string_types = six.string_types

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
    from elm_fluent import compiler

    items = []
    for node in nodes:
        if isinstance(node, bs4.element.NavigableString):
            parts = interpolate_replacements(text_type(node), expr_replacements)
            for part in parts:
                if isinstance(part, string_types):
                    items.append(
                        HtmlList(
                            [
                                local_scope.variables["Html.text"].apply(
                                    codegen.String(text_type(part))
                                )
                            ]
                        )
                    )
                else:
                    val = compiler.compile_expr(part, local_scope, compiler_env)
                    if val.type == html_output_type:
                        # This is a list type, so simply append to our list of lists
                        items.append(val)
                    else:
                        val = local_scope.variables["Html.text"].apply(
                            compiler.Stringable(val, local_scope)
                        )
                        items.append(HtmlList([val]))
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
                    if isinstance(part, string_types):
                        attr_output_parts.append(codegen.String(text_type(part)))
                    else:
                        with compiler_env.modified(html_context=False):
                            attr_output_parts.append(
                                compiler.Stringable(
                                    compiler.compile_expr(
                                        part, local_scope, compiler_env
                                    ),
                                    local_scope,
                                    from_ftl_source=compiler.make_ftl_source(
                                        part, compiler_env
                                    ),
                                )
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
                    list(
                        map(
                            codegen.String,
                            get_selectors_for_node(node, expr_replacements),
                        )
                    )
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
            items.append(HtmlList([item]))

    return HtmlListConcat(items)


class HtmlList(codegen.List):
    def simplify(self, changes):
        retval = super(HtmlList, self).simplify(changes)
        if retval is not self:
            return retval

        def is_html_text_call(item):
            return (
                isinstance(item, codegen.FunctionCall)
                and isinstance(item.expr, codegen.VariableReference)
                and (
                    "{0}.{1}".format(item.expr.module_name, item.expr.name)
                    == "Html.text"
                )
            )

        new_items = []
        for item in self.items:
            if (
                len(new_items) > 0
                and is_html_text_call(new_items[-1])
                and is_html_text_call(item)
            ):
                last_item = new_items[-1]
                if not isinstance(last_item.args[0], codegen.StringConcat):
                    last_item.args = [codegen.StringConcat([last_item.args[0]])]

                last_item.args[0].parts.append(item.args[0])
                changes.append(True)
            else:
                new_items.append(item)
        self.items = new_items
        return self


class HtmlListConcat(codegen.ListConcat):
    literal = HtmlList

    def __init__(self, parts):
        super(HtmlListConcat, self).__init__(parts, html_output_type)


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


def get_selectors_for_node(node, expr_replacements):
    tag_name = node.name.lower()
    yield tag_name

    def is_static_only(attr_value):
        parts = interpolate_replacements(attr_value, expr_replacements)
        return all(isinstance(p, string_types) for p in parts)

    classes = node.attrs.get("class", [])
    if is_static_only(" ".join(classes)):
        for class_ in classes:
            class_selector = ".{0}".format(class_)
            yield class_selector
            yield tag_name + class_selector

    id = node.attrs.get("id", None)
    if id is not None and is_static_only(id):
        id_selector = "#{0}".format(id)
        yield id_selector
        yield tag_name + id_selector

    for attr_name, attr_value in sorted(node.attrs.items()):
        if attr_name in ["id", "class"]:
            continue

        attr_present_selector = "[{0}]".format(attr_name)
        yield attr_present_selector
        yield tag_name + attr_present_selector

        if is_static_only(attr_value):
            attr_value_selector = '[{0}="{1}"]'.format(attr_name, attr_value)
            yield attr_value_selector
            yield tag_name + attr_value_selector
