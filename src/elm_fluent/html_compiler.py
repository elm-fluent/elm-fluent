"""
HTML specific compilation functions
"""
import six
import bs4

from fluent.syntax import ast

from . import codegen

from .stubs import html, html_attributes


def compile_pattern(pattern, local_scope, compiler_env):
    parts = []
    expr_mapping = {}

    for element in pattern.elements:
        if isinstance(element, ast.TextElement):
            parts.append(element.value)
        else:
            # Need a replacement that doesn't have any special HTML chars in it
            # that would cause the HTML parser to do anything funny with it.
            # TODO - some mechanism that would guarantee this generated string
            # does not appear by chance in the actual message.
            replacement_name = "SSS{0}EEE".format(str(id(element)))
            expr_mapping[replacement_name] = element

    skeleton = "".join(parts)
    # TODO - handle parse failures gracefully, and check the parser is ensuring
    # well-formedness
    dom = bs4.BeautifulSoup("<root>{0}</root>".format(skeleton), "lxml").find("root")

    return dom_nodes_to_elm(list(dom.children), local_scope, compiler_env)


def dom_nodes_to_elm(nodes, local_scope, compiler_env):
    items = []
    for node in nodes:
        if isinstance(node, bs4.element.NavigableString):
            items.append(
                local_scope.variables["Html.text"].apply(
                    codegen.String(six.text_type(node))
                )
            )
        else:
            assert isinstance(node, bs4.element.Tag)
            tag_name = node.name.lower()
            attributes = []
            for attr_name, attr_value in sorted(node.attrs.items()):
                if isinstance(attr_value, list):
                    # Bs4 treats class attribute differently, returns a list
                    attr_value = " ".join(attr_value)
                if attr_name in html_attributes.ATTRIBUTES:
                    attr_constructor = local_scope.variables[
                        "Attributes.{0}".format(attr_name)
                    ]
                else:
                    attr_constructor = local_scope.variables[
                        "Attributes.attribute"
                    ].apply(codegen.String(attr_name))
                attributes.append(attr_constructor.apply(codegen.String(attr_value)))
            sub_items = dom_nodes_to_elm(list(node.children), local_scope, compiler_env)
            if tag_name in html.ELEMENTS:
                node_constructor = local_scope.variables["Html.{0}".format(tag_name)]
            else:
                node_constructor = local_scope.variables["Html.node"].apply(
                    codegen.String(tag_name)
                )
            item = node_constructor.apply(codegen.List(attributes), sub_items)
            items.append(item)

    return codegen.List(items)
