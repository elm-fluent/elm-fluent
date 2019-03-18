"""
Stub to define types for the Date module
"""
from .. import codegen, types

# https://package.elm-lang.org/packages/elm-lang/core/latest/Date
module = codegen.Module(name="Date")
Date = types.Type("Date", module)
