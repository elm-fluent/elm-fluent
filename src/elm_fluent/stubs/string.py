"""
Stub to define types for the String module
"""
from .. import codegen, types
from . import defaults as dtypes

module = codegen.Module(name="String")

module.reserve_name("toLower", type=types.Function(dtypes.String, dtypes.String))
