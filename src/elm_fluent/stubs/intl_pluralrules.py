"""
Stub to define types for the Intl.PluralRules module
"""
from __future__ import absolute_import, unicode_literals

from . import defaults as dtypes, intl_locale
from .. import codegen, types

module = codegen.Module(name="Intl.PluralRules")

PluralRules = types.Type("PluralRules", module)

module.reserve_name("fromLocale", type=types.Function(intl_locale.Locale, PluralRules))

module.reserve_name(
    "select",
    type=types.Function.for_multiple_inputs(
        [PluralRules, dtypes.Number], dtypes.String
    ),
)
