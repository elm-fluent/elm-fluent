import os.path
from dataclasses import dataclass

from fluent.syntax import ast

TERM_SIGIL = "-"
ATTRIBUTE_SEPARATOR = "."

CLDR_PLURAL_FORMS = set(["zero", "one", "two", "few", "many", "other"])


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


def get_ast_nodes(
    node, exclude_attributes=STANDARD_TRAVERSE_EXCLUDE_ATTRIBUTES, exclude_types=STANDARD_TRAVERSE_EXCLUDE_TYPES
):
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


@dataclass
class FtlSource:
    """
    Bundle of data used to indicate a specific source within an FTL file, down
    to the expression level.
    """

    expr: ast.SyntaxNode
    source_filename: str
    message_id: str
    messages_string: str  # complete text

    @property
    def position(self):
        return span_to_position(self.expr.span, self.messages_string)

    def expr_as_text(self):
        return self.messages_string[self.expr.span.start : self.expr.span.end]

    def display_location(self):
        row, col = self.position
        return f"{self.source_filename}:{row}:{col}"


def span_to_position(span, source_text):
    start = span.start
    relevant = source_text[0:start]
    row = relevant.count("\n") + 1
    col = len(relevant) - relevant.rfind("\n")
    return row, col


def reference_to_id(ref):
    """
    Returns a string reference for a MessageReference or TermReference
    AST node.

    e.g.
       message
       message.attr
       -term
       -term.attr
    """
    if isinstance(ref, ast.TermReference):
        start = TERM_SIGIL + ref.id.name
    else:
        start = ref.id.name

    if ref.attribute:
        return _make_attr_id(start, ref.attribute.name)
    return start


def ast_to_id(ast_obj):
    """
    Returns a string reference for a Term or Message
    """
    if isinstance(ast_obj, ast.Term):
        return TERM_SIGIL + ast_obj.id.name
    return ast_obj.id.name


def attribute_ast_to_id(attribute, parent_ast):
    """
    Returns a string reference for an Attribute, given Attribute and parent Term or Message
    """
    return _make_attr_id(ast_to_id(parent_ast), attribute.id.name)


def _make_attr_id(parent_ref_id, attr_name):
    """
    Given a parent id and the attribute name, return the attribute id
    """
    return f"{parent_ref_id}{ATTRIBUTE_SEPARATOR}{attr_name}"


def get_term_used_variables(term, compiler_env):
    found_variables = []
    term_ids_to_ast = compiler_env.term_ids_to_ast

    # We only traverse TermReferences, not MessageReferences, because we
    # currently don't support calling messages from terms.
    def finder(node):
        sub_node = None
        if isinstance(node, ast.VariableReference):
            found_variables.append(node.id.name)
        elif isinstance(node, ast.TermReference):
            ref = reference_to_id(node)
            if ref in term_ids_to_ast:
                sub_node = term_ids_to_ast[ref]

        if sub_node is not None:
            traverse_ast(sub_node, finder)

    traverse_ast(term, finder)
    return sorted(set(found_variables))


def is_cldr_plural_form_key(key_expr):
    return isinstance(key_expr, ast.Identifier) and key_expr.name in CLDR_PLURAL_FORMS
