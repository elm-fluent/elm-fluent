"""
HTML specific compilation functions
"""
from xml.dom.minidom import parseString

from fluent.syntax import ast

from . import codegen

from .stubs import html

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

    skeleton = "<root>{0}</root>".format(''.join(parts))
    # TODO - handle parse failures gracefully, and check the parser is ensuring
    # well-formedness
    dom = parseString(skeleton)
    return dom_nodes_to_elm(dom.childNodes[0].childNodes, local_scope, compiler_env)


def dom_nodes_to_elm(nodes, local_scope, compiler_env):
    items = []
    for n in nodes:
        if n.nodeType == n.TEXT_NODE:
            items.append(local_scope.variables["Html.text"].apply(
                codegen.String(n.data)))
        else:
            tag = n.tagName.lower()
            sub_items = dom_nodes_to_elm(n.childNodes, local_scope, compiler_env)
            if tag in html.ELEMENTS:
                node_constructor = local_scope.variables["Html.{0}".format(tag)]
            else:
                node_constructor = local_scope.variables["Html.node"].apply(codegen.String(tag))
            item = node_constructor.apply(
                codegen.List([]),
                sub_items)
            items.append(item)

    return codegen.List(items)
