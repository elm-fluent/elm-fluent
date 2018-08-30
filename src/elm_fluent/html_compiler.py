"""
HTML specific compilation functions
"""
from xml.dom.minidom import parseString

from fluent.syntax import ast

from . import codegen


def compile_pattern(pattern, local_scope, compiler_env):
    parts = []
    expr_mapping = {}

    for element in pattern.elements:
        if isinstance(element, ast.TextElement):
            parts.append(element.value)
        else:
            # Need a replacement that doesn't have any special HTML chars in it.
            # TODO - some mechanism that would guarantee this generated string
            # does not appear by chance in the message.
            replacement_name = "RRR{0}RRR".format(str(id(element)))
            expr_mapping[replacement_name] = element

    # TODO - ensure '<root>' doesn't appear in message.
    skeleton = "<root>{0}</root>".format(''.join(parts))
    dom = parseString(skeleton)
    return dom_nodes_to_elm(dom.childNodes[0].childNodes, local_scope, compiler_env)


def dom_nodes_to_elm(nodes, local_scope, compiler_env):
    items = []
    for n in nodes:
        if n.nodeType == n.TEXT_NODE:
            items.append(local_scope.variables['Html.text'].apply(
                codegen.String(n.data)))
        else:
            raise NotImplementedError("Can't add node {0}".format(repr(n)))

    return codegen.List(items)
