"""
Stub to define types for the Intl.NumberFormat module
"""
from __future__ import absolute_import, unicode_literals

from . import defaults as dtypes, intl_locale
from .. import codegen, types

module = codegen.Module(name="Intl.NumberFormat")

NumberFormat = types.Type("NumberFormat", module)

CurrencyDisplay = types.Type(
    "CurrencyDisplay",
    module,
    constructors=["CurrencyCode", "CurrencyName", "CurrencySymbol"],
)

# We exclude the items that we don't need to generate, because they are
# developer only options (as defined by Fluent spec), such as 'currency'
Options = types.Record(
    locale=intl_locale.Locale,
    currencyDisplay=CurrencyDisplay,
    useGrouping=dtypes.Bool,
    minimumIntegerDigits=dtypes.Maybe.specialize(a=dtypes.Int),
    minimumFractionDigits=dtypes.Maybe.specialize(a=dtypes.Int),
    maximumFractionDigits=dtypes.Maybe.specialize(a=dtypes.Int),
    minimumSignificantDigits=dtypes.Maybe.specialize(a=dtypes.Int),
    maximumSignificantDigits=dtypes.Maybe.specialize(a=dtypes.Int),
)

module.reserve_name("defaults", type=Options)

module.reserve_name("fromLocale", type=types.Function(intl_locale.Locale, NumberFormat))

module.reserve_name("fromOptions", type=types.Function(Options, NumberFormat))

module.reserve_name(
    "format",
    type=types.Function.for_multiple_inputs(
        [NumberFormat, dtypes.Number], dtypes.String
    ),
)
