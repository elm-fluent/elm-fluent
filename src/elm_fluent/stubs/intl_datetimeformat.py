"""
Stub to define types for the Intl.DateTimeFormat module
"""
from __future__ import absolute_import, unicode_literals

from . import defaults as dtypes, intl_locale, intl_timezone
from .. import codegen, types

module = codegen.Module(name="Intl.DateTimeFormat")

DateTimeFormat = types.Type("DateTimeFormat", module)


NameStyle = types.Type(
    "NameStyle",
    module,
    constructors=["NarrowName", "ShortName", "LongName", "OmitName"],
)

NumberStyle = types.Type(
    "NumberStyle",
    module,
    constructors=["NumericNumber", "TwoDigitNumber", "OmitNumber"],
)

MonthStyle = types.Type(
    "MonthStyle",
    module,
    constructors=[
        "NarrowMonth",
        "ShortMonth",
        "LongMonth",
        "NumericMonth",
        "TwoDigitMonth",
        "OmitMonth",
    ],
)

TimeZoneStyle = types.Type(
    "TimeZoneStyle",
    module,
    constructors=["ShortTimeZone", "LongTimeZone", "OmitTimeZone"],
)

Options = types.Record(
    locale=intl_locale.Locale,
    timeZone=dtypes.Maybe.specialize(a=intl_timezone.TimeZone),
    hour12=dtypes.Maybe.specialize(a=dtypes.Bool),
    weekday=NameStyle,
    era=NameStyle,
    year=NumberStyle,
    month=MonthStyle,
    day=NumberStyle,
    hour=NumberStyle,
    minute=NumberStyle,
    second=NumberStyle,
    timeZoneName=TimeZoneStyle,
)
