module Notifications exposing (..)

{- Example project for elm-fluent docs.

   Build it like this:

    elm-make Notifications.elm --output=notifications.js

   Then open 'notifications.html' in a browser

-}

import Html as H
import Html.Attributes as A
import Html.Events as E
import Json.Decode as JD
import Set


main : Program Flags Model Msg
main =
    H.programWithFlags
        { init = init
        , view = view
        , update = update
        , subscriptions = subscriptions
        }


type alias Flags =
    {}


type alias Model =
    { notifications : List Notification
    , userName : String
    , selectedNotifications : Set.Set NotificationId
    , searchBoxText : String
    , deleteConfirmationOpen : Bool
    }


type alias NotificationId =
    Int


type alias Notification =
    { id : NotificationId
    , message : String
    , read : Bool
    }


type Msg
    = NotificationSelected NotificationId
    | NotificationUnselected NotificationId
    | SearchBoxInput String
    | MarkRead
    | MarkUnread
    | Delete
    | DeleteConfirm
    | DeleteCancel


init : Flags -> ( Model, Cmd Msg )
init flags =
    ( { notifications = dummyNotifications
      , userName = dummyUserName
      , selectedNotifications = Set.empty
      , searchBoxText = ""
      , deleteConfirmationOpen = False
      }
    , Cmd.none
    )


{-| in a real app we'd get this from some API call or something
-}
dummyNotifications : List Notification
dummyNotifications =
    [ { id = 1
      , message = "Welcome to MyApp! Hope you enjoy it."
      , read = True
      }
    , { id = 2
      , message = "Thank you for your payment!"
      , read = False
      }
    , { id = 3
      , message = "Your order has been scheduled, and should be with you in a few days."
      , read = False
      }
    ]


dummyUserName : String
dummyUserName =
    "Mary"


unreadNotifications : Model -> List Notification
unreadNotifications model =
    model.notifications |> List.filter (.read >> not)


visibleSortedNotifications : Model -> List Notification
visibleSortedNotifications model =
    model.notifications
        |> List.filter (\n -> String.contains (String.toLower model.searchBoxText) (String.toLower n.message))
        |> List.sortBy .id
        |> List.reverse


view : Model -> H.Html Msg
view model =
    H.div []
        [ H.h1 [] [ H.text "MyApp Notifications" ]
        , H.p []
            [ H.text "Hello, "
            , H.text model.userName
            , H.text ". "
            , H.text
                (let
                    unreadNotificationsCount =
                        unreadNotifications model |> List.length
                 in
                    if unreadNotificationsCount == 1 then
                        "You have 1 unread message."
                    else
                        ("You have " ++ toString unreadNotificationsCount ++ " unread messages.")
                )
            ]
        , if model.notifications |> List.isEmpty then
            H.text ""
          else
            H.div []
                [ viewSearchBar model
                , viewNotificationList model
                , viewActionBar model
                ]
        ]


viewSearchBar : Model -> H.Html Msg
viewSearchBar model =
    H.div []
        [ H.input
            [ A.type_ "search"
            , A.name "q"
            , A.placeholder "Search"
            , A.attribute "aria-label" "Search through notifications"
            , A.value model.searchBoxText
            , E.onInput SearchBoxInput
            ]
            []
        ]


viewNotificationList : Model -> H.Html Msg
viewNotificationList model =
    H.table []
        [ H.thead []
            [ H.tr []
                [ H.th []
                    [ H.text ""
                    ]
                , H.th []
                    [ H.text "Message"
                    ]
                ]
            ]
        , H.tbody []
            (List.map
                (\n ->
                    H.tr
                        [ A.class
                            (if n.read then
                                "read-message"
                             else
                                "unread-message"
                            )
                        ]
                        [ H.td []
                            [ H.input
                                [ A.type_ "checkbox"
                                , A.checked (Set.member n.id model.selectedNotifications)
                                , E.onClick
                                    (if Set.member n.id model.selectedNotifications then
                                        NotificationUnselected n.id
                                     else
                                        NotificationSelected n.id
                                    )
                                ]
                                []
                            ]
                        , H.td []
                            [ H.text n.message ]
                        ]
                )
                (visibleSortedNotifications model)
            )
        ]


viewActionBar : Model -> H.Html Msg
viewActionBar model =
    H.div []
        (if model.deleteConfirmationOpen then
            [ H.text "These "
            , H.text <| toString <| Set.size model.selectedNotifications
            , H.text " messages will be permanently deleted - "
            , H.a
                [ A.href "#"
                , onClickSimply DeleteCancel
                ]
                [ H.text "cancel" ]
            , H.text " or "
            , H.a
                [ A.href "#"
                , onClickSimply DeleteConfirm
                ]
                [ H.text "confirm" ]
            ]
         else
            [ H.button [ E.onClick Delete ]
                [ H.text "Delete"
                ]
            , H.button [ E.onClick MarkRead ]
                [ H.text "Mark read"
                ]
            , H.button [ E.onClick MarkUnread ]
                [ H.text "Mark unread"
                ]
            ]
        )


update : Msg -> Model -> ( Model, Cmd Msg )
update msg model =
    let
        newModel =
            case msg of
                NotificationSelected id ->
                    { model
                        | selectedNotifications = Set.insert id model.selectedNotifications
                    }

                NotificationUnselected id ->
                    { model
                        | selectedNotifications = Set.remove id model.selectedNotifications
                    }

                SearchBoxInput text ->
                    { model
                        | searchBoxText = text
                    }

                Delete ->
                    { model
                        | deleteConfirmationOpen = True
                    }

                DeleteCancel ->
                    { model
                        | deleteConfirmationOpen = False
                    }

                DeleteConfirm ->
                    { model
                        | notifications = List.filter (\n -> not (Set.member n.id model.selectedNotifications)) model.notifications
                        , deleteConfirmationOpen = False
                    }

                MarkRead ->
                    { model
                        | notifications =
                            List.map
                                (\n ->
                                    { n
                                        | read = n.read || Set.member n.id model.selectedNotifications
                                    }
                                )
                                model.notifications
                    }

                MarkUnread ->
                    { model
                        | notifications =
                            List.map
                                (\n ->
                                    { n
                                        | read = not ((not n.read) || Set.member n.id model.selectedNotifications)
                                    }
                                )
                                model.notifications
                    }
    in
        ( newModel, Cmd.none )


subscriptions : Model -> Sub Msg
subscriptions model =
    Sub.none


onClickSimply : msg -> H.Attribute msg
onClickSimply msg =
    E.onWithOptions
        "click"
        { stopPropagation = False
        , preventDefault = True
        }
        (JD.succeed msg)
