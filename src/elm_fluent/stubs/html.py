"""
Types for Html module
"""
from __future__ import absolute_import, unicode_literals

from . import defaults as dtypes
from .. import codegen, types

module = codegen.Module(name="Html")

Html = types.Type("Html msg", module)

Attribute = types.Type("Attribute msg", module)

module.reserve_name("text", type=types.Function(dtypes.String, Html))

# From https://package.elm-lang.org/packages/elm-lang/html/latest/Html
# Only the ones with the signature:
#   List (Attribute msg) -> List (Html msg) -> Html msg
ELEMENTS = [
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "div",
    "p",
    "hr",
    "pre",
    "blockquote",
    "span",
    "a",
    "code",
    "em",
    "strong",
    "i",
    "b",
    "u",
    "sub",
    "sup",
    "br",
    "ol",
    "ul",
    "li",
    "dl",
    "dt",
    "dd",
    "img",
    "iframe",
    "canvas",
    "math",
    "form",
    "input",
    "textarea",
    "button",
    "select",
    "option",
    "section",
    "nav",
    "article",
    "aside",
    "header",
    "footer",
    "address",
    "main_",
    "body",
    "figure",
    "figcaption",
    "table",
    "caption",
    "colgroup",
    "col",
    "tbody",
    "thead",
    "tfoot",
    "tr",
    "td",
    "th",
    "fieldset",
    "legend",
    "label",
    "datalist",
    "optgroup",
    "keygen",
    "output",
    "progress",
    "meter",
    "audio",
    "video",
    "source",
    "track",
    "embed",
    "object",
    "param",
    "ins",
    "del",
    "small",
    "cite",
    "dfn",
    "abbr",
    "time",
    "var",
    "samp",
    "kbd",
    "s",
    "q",
    "mark",
    "ruby",
    "rt",
    "rp",
    "bdi",
    "bdo",
    "wbr",
    "details",
    "summary",
    "menuitem",
    "menu",
]


for element in ELEMENTS:
    module.reserve_name(
        element,
        type=types.Function.for_multiple_inputs(
            [dtypes.List.specialize(a=Attribute), dtypes.List.specialize(a=Html)], Html
        ),
    )

module.reserve_name(
    "node",
    type=types.Function.for_multiple_inputs(
        [
            dtypes.String,
            dtypes.List.specialize(a=Attribute),
            dtypes.List.specialize(a=Html),
        ],
        Html,
    ),
)
