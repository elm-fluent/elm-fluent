Overview
========

The big picture for using elm-fluent looks as follows (with some design
justifications thrown in). If you think this fits your needs, please see the
:doc:`installation` docs and the :doc:`tutorial` for the details you'll need to
implement this in your app.

With elm-fluent, all localized text (i.e. text in a specific human language) is
stored in ``.ftl`` files in a ``locales`` directory, and not in Elm source
files.

.. admonition:: Justification

   Some tools such as gettext encourage you to put localized text in source code
   files, at least for ‘source language’, and then extract this text into other
   files from which translation is done for the other (‘destination’) languages.

   That approach has some advantages, but major disadvantages when it comes to
   Fluent. Fluent is a language in its own right, that puts (just enough) power
   into the hands of translators to produce good translations, while maintaining
   proper separation of concerns.

   For Fluent, developers need to put localized text into ``.ftl`` files, so the full
   power of that language will be used. This includes:

   * adding comments that will help translators
   * using Fluent constructs for things like variant selection, rather than using
     Elm flow control constructs for variant selection, which would cause the
     destination languages to suffer.
   * choosing good message IDs, and being aware of the issues surrounding changes to
     IDs or changes to text without changing IDs

So, if your web app has a ‘notifications’ component with a title ‘Notifications’
and some intro text, you would have a ``locales/en/notifications.ftl`` file that looks
something like this:

.. code-block:: ftl

   notifications-title = Notifications

   notifications-intro = Hello { $username }, you have unread notifications


You compile this to Elm files using ``ftl2elm``. (Normally the generated
``.elm`` files should not be stored in your VCS, you store only the ``.ftl``
files). You can then use the generated functions from your Elm source code.

Your app first needs some way to determine the user's current locale. This is
usually best done by allowing them to choose from a list, and then saving this
in the model somewhere. Let's assume we have ``model.locale`` set up already.
Then our Elm source code might look like this:

.. code-block:: elm

   import Ftl.Translations.Notifications as T

   viewNotifications model =
        Html.div []
                 [ Html.h2 (T.notificationsTitle model.locale ())
                 , Html.p (T.notificationsIntro model.locale { username = model.username })
                 ]

The generated functions (in this case ``notificationsTitle`` and
``notificationsIntro``) all have the same signature - they take a locale value
and a strongly typed record of substitution parameters, and return a string (or
``Html`` for advanced use cases).

.. admonition:: Justifcation

   Using a strongly typed record type means that we can catch the vast majority
   of errors at compile time. If a translator includes a parameter in their
   translation that is not passed by the developer, the code will not compile.
   We can also ensure that numbers get passed as numbers etc.

Depending on the locale parameter, the generated functions dispatch to the
function for the correct language (we just have one so far).

You now need to distribute your ``.ftl`` files and get translations for the
other languages you support. These are saved into the correct sub folder in your
locales directory and committed to VCS. (Mozilla has developed the `Pontoon
<https://github.com/mozilla/pontoon>`_ system to help with this part, but
elm-fluent doesn't have good integration with it yet).

Finally, you can now compile the ``.ftl`` for all the languages, compile your
Elm app and deploy.
