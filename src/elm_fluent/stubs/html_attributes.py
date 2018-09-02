"""
Types for Html.Attributes module
"""
from __future__ import absolute_import, unicode_literals

from . import defaults as dtypes, html
from .. import codegen, types

module = codegen.Module(name="Html.Attributes")

# From https://package.elm-lang.org/packages/elm-lang/html/latest/Html-Attributes
# Only the ones with the signatureL
#   String -> Attribute msg


ATTRIBUTES = [
    "class",
    "id",
    "title",
    "type_",
    "value",
    "defaultValue",
    "placeholder",
    "accept",
    "acceptCharset",
    "action",
    "enctype",
    "formaction",
    "list",
    "method",
    "name",
    "pattern",
    "for",
    "form",
    "max",
    "min",
    "step",
    "wrap",
    "href",
    "target",
    "downloadAs",
    "hreflang",
    "media",
    "ping",
    "rel",
    "usemap",
    "shape",
    "coords",
    "src",
    "alt",
    "preload",
    "poster",
    "kind",
    "srclang",
    "sandbox",
    "srcdoc",
    "align",
    "headers",
    "scope",
    "charset",
    "content",
    "httpEquiv",
    "language",
    "contextmenu",
    "dir",
    "draggable",
    "dropzone",
    "itemprop",
    "lang",
    "challenge",
    "keytype",
    "cite",
    "dyatetime",
    "pubdate",
    "manifest",
]

for attr in ATTRIBUTES:
    module.reserve_name(attr, type=types.Function(dtypes.String, html.Attribute))

module.reserve_name(
    "attribute",
    type=types.Function.for_multiple_inputs(
        [dtypes.String, dtypes.String], html.Attribute
    ),
)
