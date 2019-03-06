"""
Stub to define types for the Intl.Locale module
"""
from __future__ import absolute_import, unicode_literals

from .. import codegen, types
from . import defaults as dtypes

module = codegen.Module(name="Intl.Locale")

Locale = types.Type("Locale", module)

module.reserve_name("toLanguageTag", type=types.Function(Locale, dtypes.String))
