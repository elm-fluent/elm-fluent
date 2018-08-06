"""
Stub to define types for the String module
"""
from __future__ import absolute_import, unicode_literals

from . import defaults as dtypes
from .. import codegen, types

module = codegen.Module(name="String")

module.reserve_name("toLower", type=types.Function(dtypes.String, dtypes.String))
