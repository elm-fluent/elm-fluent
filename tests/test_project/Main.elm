module Main exposing (..)

import Date
import Html as H
import Html.Attributes as A
import Html.Events exposing (onClick, onInput)
import Intl.Locale as Locale
import Intl.Currency
import Intl.NumberFormat
import Intl.DateTimeFormat
import Intl.TimeZone
import Ftl.Translations.Main as T
import Ftl.Translations.Other as T2
import Fluent


main : Program Never Model Msg
main =
    H.beginnerProgram { model = model, view = view, update = update }


type Msg
    = Increment
    | Decrement
    | NameChange String



-- MODEL


type alias Model =
    { count : Int
    , locale : Locale.Locale
    , clickCount : Int
    , name : String
    }


model : Model
model =
    { count = 0
    , locale = Locale.en
    , clickCount = 0
    , name = ""
    }


update : Msg -> Model -> Model
update msg model =
    case msg of
        Increment ->
            { model
                | count = model.count + 1
                , clickCount = model.clickCount + 1
            }

        Decrement ->
            { model
                | count = model.count - 1
                , clickCount = model.clickCount + 1
            }

        NameChange name ->
            { model
                | name = name
            }



-- TODO - ability to switch Locale


asDollars : number -> Fluent.FluentNumber number
asDollars n =
    let
        baseOptions =
            Intl.NumberFormat.defaults

        finalOptions =
            { baseOptions
                | currency = Intl.Currency.usd
                , style = Intl.NumberFormat.CurrencyStyle
            }
    in
        Fluent.formattedNumber finalOptions n


inUtc : Intl.DateTimeFormat.Options
inUtc =
    let
        defaults =
            Intl.DateTimeFormat.defaults
    in
        { defaults
            | timeZone = Just Intl.TimeZone.utc
        }


view : Model -> H.Html Msg
view model =
    let
        locale =
            model.locale
    in
        H.div []
            [ H.h1 [] [ H.text <| T.pageTitle locale () ]
            , H.p [] [ H.text <| T2.pageIntro locale () ]
            , H.button
                [ A.id "decrement"
                , onClick Decrement
                ]
                [ H.text "-" ]
            , H.div [] [ H.text <| toString model.count ]
            , H.button
                [ A.id "increment"
                , onClick Increment
                ]
                [ H.text "+" ]
            , H.p [] [ H.text <| T.youveClicked locale { count = Fluent.number model.clickCount } ]
            , H.p [] [ H.text <| T.enterName locale () ]
            , H.input
                [ A.value model.name
                , onInput NameChange
                ]
                []
            , H.p [] [ H.text <| T.yourNameIs locale { name = model.name } ]
            , H.h2 [] [ H.text <| T.complexInfoHeader locale () ]
            , H.p []
                [ H.text <|
                    T.complexInfo model.locale
                        { name = model.name
                        , country = "England"
                        }
                ]
            , H.h2 [] [ H.text <| T.numberTestsSectionTitle locale () ]
            , H.p [] [ H.text <| T.messageWithHardCodedNumberAndNumberFunction locale () ]
            , H.p [] [ H.text <| T.messageWithHardCodedBareNumberLiteral locale () ]
            , H.p [] [ H.text <| T.messageWithNumberFunctionAndArg locale { count = Fluent.number 4567.8 } ]
            , H.p [] [ H.text <| T.messageWithMoney locale { money = asDollars 6543.21 } ]
            , H.p [] [ H.text <| T.messageWithNumberFunctionAndParams locale () ]
            , H.p [] [ H.text <| T.messageWithMixedNumericSelect locale { count = Fluent.number 0 } ]
            , H.p [] [ H.text <| T.messageWithMixedNumericSelect locale { count = Fluent.number 1 } ]
            , H.p [] [ H.text <| T.messageWithMixedNumericSelect locale { count = Fluent.number 2 } ]
            , H.h2 [] [ H.text <| T.dateTestsSectionTitle locale () ]
            , H.p []
                [ H.text <|
                    T.hereIsADate locale
                        { mydate =
                            Fluent.formattedDate
                                inUtc
                                -- 1970-01-01 01:02:03
                                (Date.fromTime ((1 * 3600 + 2 * 60 + 3) * 1000))
                        }
                ]
            , H.h2 [] [ H.text <| T.htmlTestsSectionTitle locale () ]
            , H.p [] (T.simpleTextHtml locale ())
            ]
