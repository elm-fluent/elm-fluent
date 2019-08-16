import os.path

from fluent.syntax import ast


def normpath(fs, path):
    return os.path.normpath(fs.getsyspath(path))


STANDARD_TRAVERSE_EXCLUDE_ATTRIBUTES = [
    # Message and Term attributes have already been loaded into the
    # message_ids_to_ast dict, and we get to their contents via
    # MessageReference and TermReference
    (ast.Message, "attributes"),
    (ast.Term, "attributes"),
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
