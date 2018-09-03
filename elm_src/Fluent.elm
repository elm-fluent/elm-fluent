module Fluent exposing (FluentNumber, number, formattedNumber, reformattedNumber, numberFormattingOptions, formatNumber, numberValue, FluentDate, date, formattedDate, reformattedDate, dateFormattingOptions, formatDate, selectAttributes)

{-| Helpers and types for the elm-fluent i18n system

# Numnber types
@docs FluentNumber

# Number functions
@docs number, formattedNumber

# Other
@docs numberFormattingOptions, reformattedNumber, formatNumber, numberValue

# Date types
@docs FluentDate

# Date functions
@docs date, formattedDate

# Other
@docs dateFormattingOptions, reformattedDate, formatDate

# Utils
@docs selectAttributes
-}

import Intl.NumberFormat as NumberFormat
import Intl.DateTimeFormat as DateTimeFormat
import Intl.Locale as Locale
import Date as Date
import Html as Html


{-| A number that can be passed to Fluent message functions, with optional formatting options specified

-}
type FluentNumber number
    = FluentNumber NumberFormat.Options number


{-| Converts an integer or float into a FluentNumber
-}
number : number -> FluentNumber number
number n =
    FluentNumber NumberFormat.defaults n


{-| Packs an integer or float and some formatting options into a FluentNumber

Formatting options are usually created using Intl.NumberFormat.defaults e.g.

    import Intl.NumberFormat as NumberFormat

    baseOptions = NumberFormat.defaults
    myOptions = { baseOptions
                    | useGrouping = False }
    myNumber = formattedNumber myOptions 123.4
-}
formattedNumber : NumberFormat.Options -> number -> FluentNumber number
formattedNumber opts n =
    FluentNumber opts n


{-| Change formatting options for a number

-}
reformattedNumber : NumberFormat.Options -> FluentNumber number -> FluentNumber number
reformattedNumber opts (FluentNumber _ n) =
    FluentNumber opts n


{-| Get formatting options out of a FluentNumber.

Intended for use by ftl2elm, not normally used directly
-}
numberFormattingOptions : FluentNumber number -> NumberFormat.Options
numberFormattingOptions (FluentNumber opts _) =
    opts


{-| Get value out of a FluentNumber.

Intended for use by ftl2elm, not normally used directly
-}
numberValue : FluentNumber number -> number
numberValue (FluentNumber _ num) =
    num


{-| Format a FluentNumber

Intended for use by ftl2elm, not normally used directly
-}
formatNumber : Locale.Locale -> FluentNumber number -> String
formatNumber locale (FluentNumber opts num) =
    NumberFormat.format (NumberFormat.fromOptions { opts | locale = locale }) num



{- Dates -}


{-| A date that can be passed to Fluent message functions, with optional formatting options specified

-}
type FluentDate
    = FluentDate DateTimeFormat.Options Date.Date


{-| Converts a Date into a FluentNumber
-}
date : Date.Date -> FluentDate
date d =
    FluentDate DateTimeFormat.defaults d


{-| Packs a Date and some formatting options into a FluentDate

Formatting options are usually created using Intl.DateTimeFormat.defaults e.g.

    import Intl.DateTimeFormat as DateTimeFormat

    baseOptions = DateTimeFormat.defaults
    myOptions = { baseOptions
                    | month = DateTimeFormat.LongMonth }
    myNumber = formattedDate myOptions
-}
formattedDate : DateTimeFormat.Options -> Date.Date -> FluentDate
formattedDate opts d =
    FluentDate opts d


{-| Change formatting options for a date

-}
reformattedDate : DateTimeFormat.Options -> FluentDate -> FluentDate
reformattedDate opts (FluentDate _ d) =
    FluentDate opts d


{-| Get formatting options out of a FluentDate.

Intended for use by ftl2elm, not normally used directly
-}
dateFormattingOptions : FluentDate -> DateTimeFormat.Options
dateFormattingOptions (FluentDate opts _) =
    opts


{-| Format a FluentDate

Intended for use by ftl2elm, not normally used directly
-}
formatDate : Locale.Locale -> FluentDate -> String
formatDate locale (FluentDate opts d) =
    DateTimeFormat.format (DateTimeFormat.fromOptions { opts | locale = locale }) d


{-| Select attributes for an Html node

Intended for use by ftl2elm, not normally used otherwise
-}
selectAttributes : List ( String, List (Html.Attribute msg) ) -> List String -> List (Html.Attribute msg)
selectAttributes attrList selectors =
    attrList
        |> List.filter
            (\( selector, aList ) ->
                List.member selector selectors
            )
        |> List.map Tuple.second
        |> List.concat
