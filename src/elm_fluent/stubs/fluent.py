"""
Stub to define types for the Fluent module
"""
from __future__ import absolute_import, unicode_literals

from . import (
    date,
    defaults as dtypes,
    html,
    intl_datetimeformat,
    intl_locale,
    intl_numberformat,
)
from .. import codegen, types

module = codegen.Module(name="Fluent")

# Numbers

FluentNumber = types.Type("FluentNumber number", module)

module.reserve_name("number", type=types.Function(dtypes.Number, FluentNumber))

module.reserve_name(
    "formattedNumber",
    type=types.Function.for_multiple_inputs(
        [intl_numberformat.Options, dtypes.Number], FluentNumber
    ),
)

module.reserve_name(
    "reformattedNumber",
    type=types.Function.for_multiple_inputs(
        [intl_numberformat.Options, FluentNumber], FluentNumber
    ),
)

module.reserve_name(
    "numberFormattingOptions",
    type=types.Function(FluentNumber, intl_numberformat.Options),
)

module.reserve_name(
    "formatNumber",
    type=types.Function.for_multiple_inputs(
        [intl_locale.Locale, FluentNumber], dtypes.String
    ),
)

module.reserve_name("numberValue", type=types.Function(FluentNumber, dtypes.Number))

# Dates

FluentDate = types.Type("FluentDate", module)

module.reserve_name("date", type=types.Function(date.Date, FluentDate))

module.reserve_name(
    "formattedDate",
    type=types.Function.for_multiple_inputs(
        [intl_datetimeformat.Options, date.Date], FluentDate
    ),
)

module.reserve_name(
    "reformattedDate",
    type=types.Function.for_multiple_inputs(
        [intl_datetimeformat.Options, FluentDate], FluentDate
    ),
)

module.reserve_name(
    "dateFormattingOptions",
    type=types.Function(FluentDate, intl_datetimeformat.Options),
)

module.reserve_name(
    "formatDate",
    type=types.Function.for_multiple_inputs(
        [intl_locale.Locale, FluentDate], dtypes.String
    ),
)


module.reserve_name(
    "selectAttributes",
    type=types.Function.for_multiple_inputs(
        [
            dtypes.List.specialize(
                a=types.Tuple(dtypes.String, dtypes.List.specialize(a=html.Attribute))
            ),
            dtypes.List.specialize(a=dtypes.String),
        ],
        dtypes.List.specialize(a=html.Attribute),
    ),
)
