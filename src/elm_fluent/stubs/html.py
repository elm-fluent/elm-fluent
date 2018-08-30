"""
Types for Elm defaults
"""
from __future__ import absolute_import, unicode_literals

from .. import codegen, types
from . import defaults as dtypes

module = codegen.Module(name="Html")

Html = types.Type("Html msg", module)

module.reserve_name("text", type=types.Function(dtypes.String, Html))
