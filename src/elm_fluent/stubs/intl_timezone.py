"""
Stub to define types for the Intl.TimeZone module
"""
from __future__ import absolute_import, unicode_literals

from . import defaults as dtypes
from .. import codegen, types

module = codegen.Module(name="Intl.TimeZone")


TimeZone = types.Type("TimeZone", module, constructors=[("TimeZone", dtypes.String)])
