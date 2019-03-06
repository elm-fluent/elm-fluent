"""
Stub to define types for the String module
"""
from __future__ import absolute_import, unicode_literals

from .. import codegen, types
from . import defaults as dtypes

module = codegen.Module(name="String")

module.reserve_name("toLower", type=types.Function(dtypes.String, dtypes.String))
