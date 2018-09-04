"""
Types for Elm defaults
"""
from __future__ import absolute_import, unicode_literals

from elm_fluent import codegen, types

# Default imports: see http://package.elm-lang.org/packages/elm-lang/core/latest
# or https://github.com/elm-lang/core/blob/5.1.1/src/Basics.elm

# As we use things from this list, we add types for them (below) and comment
# them out here
ELM_DEFAULT_IMPORTS = set(
    [
        "max",
        "min",
        "Order",
        "LT",
        "EQ",
        "GT",
        "compare",
        "not",
        "&&",
        "||",
        "xor",
        "+",
        "-",
        "*",
        "/",
        "^",
        "//",
        "rem",
        "%",
        "negate",
        "abs",
        "sqrt",
        "clamp",
        "logBase",
        "e",
        "pi",
        "cos",
        "sin",
        "tan",
        "acos",
        "asin",
        "atan",
        "atan2",
        "round",
        "floor",
        "ceiling",
        "truncate",
        "toFloat",
        "degrees",
        "radians",
        "turns",
        "toPolar",
        "fromPolar",
        "isNaN",
        "isInfinite",
        "toString",
        "++",
        "identity",
        "always",
        "<|",
        "|>",
        "<<",
        ">>",
        "flip",
        "curry",
        "uncurry",
        "Never",
        "never",
        # "List",
        "::",
        # "Maybe", "Just", "Nothing",  - added below
        "Result",
        "Ok",
        "Err",
        "String",
        "Tuple",
        "Debug",
        "Program",
        "Cmd",
        "!",
        "Sub",
    ]
)


class DefaultImports(codegen.Scope):
    is_default_imports = True


default_imports = DefaultImports()

for i in ELM_DEFAULT_IMPORTS:
    default_imports.reserve_name(i)


String = types.Type("String", default_imports)

Float = types.Type("Float", default_imports)

Int = types.Type("Int", default_imports)

# 'number' is a hard-coded Elm 'type class', we can treat it as a simple type
# for our purposes
Number = types.Type("number", default_imports)


Bool = types.Type("Bool", default_imports, constructors=["True", "False"])


Maybe = types.Type(
    "Maybe a", default_imports, constructors=["Nothing", ("Just", types.TypeParam("a"))]
)

List = types.Type("List a", default_imports)
