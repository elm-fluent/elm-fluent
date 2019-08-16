import os.path

from fluent.syntax import ast


def normpath(fs, path):
    return os.path.normpath(fs.getsyspath(path))


STANDARD_TRAVERSE_EXCLUDE_ATTRIBUTES = {
    # Message and Term attributes have already been loaded into the
    # message_ids_to_ast dict, and we get to their contents via
    # MessageReference and TermReference
    (ast.Message, "attributes"),
    (ast.Term, "attributes"),
    # for speed
    (ast.Message, "comment"),
    (ast.Term, "comment"),
}

STANDARD_TRAVERSE_EXCLUDE_TYPES = {ast.Span}


def get_ast_nodes(node, exclude_attributes=STANDARD_TRAVERSE_EXCLUDE_ATTRIBUTES, exclude_types=STANDARD_TRAVERSE_EXCLUDE_TYPES):
    """
    Yields all nodes in AST tree, postorder traversal
    """
    if exclude_types is not None and type(node) in exclude_types:
        return
    if isinstance(node, ast.BaseNode):
        parts = vars(node).items()
        for name, value in parts:
            if exclude_attributes is not None and (type(node), name) in exclude_attributes:
                continue
            yield from get_ast_nodes(value)
        yield node
    elif isinstance(node, list):
        for item in node:
            yield from get_ast_nodes(item)
        yield node
    elif isinstance(node, (int, str)):
        yield node


def traverse_ast(node, fun, exclude_attributes=STANDARD_TRAVERSE_EXCLUDE_ATTRIBUTES):
    """Postorder-traverse this node and apply `fun` to all child nodes.

    Traverse this node depth-first applying `fun` to subnodes and leaves.
    Children are processed before parents (postorder traversal).

    exclude_attributes is a list of (node type, attribute name) tuples
    that should not be recursed into.
    """
    for subnode in get_ast_nodes(node):
        fun(subnode)
