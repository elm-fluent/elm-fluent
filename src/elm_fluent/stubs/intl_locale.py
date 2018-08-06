"""
Stub to define types for the Intl.Locale module
"""
from __future__ import absolute_import, unicode_literals

from . import defaults as dtypes
from .. import codegen, types

module = codegen.Module(name="Intl.Locale")

Locale = types.Type("Locale", module)

module.reserve_name("toLanguageTag", type=types.Function(Locale, dtypes.String))
