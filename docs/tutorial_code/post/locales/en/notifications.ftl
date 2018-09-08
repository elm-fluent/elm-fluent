### Localization for the Notifications page of MyApp

# This title appears at the top of the notifications page
notifications-title = MyApp Notifications

notifications-greeting = Hello, { $username }.

notifications-greeting-html = Hello, <b>{ $username }</b>, so nice to have you back!

notifications-unread-count = { $count ->
    [one]     You have 1 unread messsage.
   *[other]   You have { NUMBER($count) } unread messages.
 }

notifications-search-box
                        .placeholder = Search
                        .aria-label = Search through notifications

# Caption in the 'message' column in the notifications table
notifications-table-message-caption = Message

# Caption on the button that causes selected message to be deleted
notifications-delete-button = Delete

# Caption on the button that causes selected message to be marked as 'read'
notifications-mark-read-button = Mark read

# Caption on the button that causes selected message to be marked as 'unread'
notifications-mark-unread-button = Mark unread

# Confirmation message when deleting notifications.
# It includes two hyperlinks - 'cancel' to cancel the deletion,
# and 'confirm' to continue.
# You must wrap the 'cancel' text in:
#
#   <a data-ftl-cancel>...</a>
#
# and wrap the `confirm' text in:
#
#   <a data-ftl-confirm>...</a>
#
notifications-delete-confirm-panel-html =
  { $count ->
     [one]   This message
    *[one]   These { $count } messages
  } will be permanently deleted - <a data-ftl-cancel>cancel</a> or <a data-ftl-confirm>confirm</a>
