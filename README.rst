==========
elm-fluent
==========


.. image:: https://badge.fury.io/py/elm-fluent.svg
    :target: https://badge.fury.io/py/elm-fluentt/

.. image:: https://travis-ci.org/elm-fluent/elm-fluent.svg?branch=master
        :target: https://travis-ci.org/elm-fluent/elm-fluent

.. image:: https://codecov.io/gh/elm-fluent/elm-fluent/branch/master/graph/badge.svg
        :target: https://codecov.io/gh/elm-fluent/elm-fluent

.. image:: https://readthedocs.org/projects/elm-fluent/badge/?version=latest
        :target: https://elm-fluent.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status


elm-fluent is an internationalization/localization solution for Elm.

It features:

- A full implementation of `Fluent - Mozilla's brilliant next generation translation/internationalization/localization system <https://projectfluent.org/>`_.
- A compiler approach that means you get excellent performance.
- Proper support for the classic 'plurals' problem in i18n, along with other i18n issues.
- Compile-time checking of every possible syntax or type error in your Fluent FTL files, by leveraging
  both Elm's type system and our own checks.
- Built-in ability to format numbers and dates according to locale, with ability to customize.
  This means **strongly-typed messages and substitutions** that help you avoid i18n issues
  you might not even know exist.
- An elegant solution for the thorny problem of internationalizing messages that contain
  HTML fragments (such as bold text and hyperlinks), while also allowing such
  elements to work as normal in Elm's event model (e.g. clickable links that send
  Elm messages).
- Excellent, explicit compile-time error messages - inspired by the Elm compiler.

It combines the power of Fluent with Elm's you-just-cant-break-it safety to give
a very capable i18n solution.

Oveview
-------

elm-fluent operates as a command line tool that compiles ``.ftl`` files to ``.elm``
files. The result is that each message becomes a function that will generate a
translated string (or HTML fragment) for a given locale and an optional set of
strongly typed parameters (string, dates or numbers).

Dates and numbers can also be passed with formatting parameters supplied - for
example, to attach a currency to a number, so that it can be correctly formatted
as a currency according to the rules of the locale in use.

Please see the `docs
<https://elm-fluent.readthedocs.io/en/latest/>`_ for more
information.

For discussion regarding Fluent, including elm-fluent, see also the `Mozilla
Discourse Fluent category <https://discourse.mozilla.org/c/fluent>`_.

Status
------

* Stable - used in production.
* A few rough edges - please see the list of `open issues <https://github.com/elm-fluent/elm-fluent/issues>`_.
* A pretty complete test suite, and a nice set of docs.
* **Compatibility: Elm 0.18 only**.

  Elm 0.19 is problematic - we require a wrapper for `Intl
  <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl>`_,
  but Elm doesn't have one yet and the restriction on native modules blocks us
  from writing our own.

  It is unclear if/when an official wrapper will be provided, or whether it will
  be suitable for elm-fluent. We use `elm-intl
  <https://github.com/vanwagonet/elm-intl>`_ which has proved ideal for our
  usage, but the core team apparently `quickly dismissed
  <https://discourse.elm-lang.org/t/state-of-localization-l10n-and-v0-19/1541/18>`_
  adoption of a library like that.

  In light of this, and other problems caused by the restriction on native
  modules in 0.19, the author of elm-fluent may well be forced to move away from
  Elm. In this event the most likely outcome is a migration to `bucklescript
  <https://bucklescript.github.io/>`_ with `bucklescript-tea
  <https://github.com/OvermindDL1/bucklescript-tea>`_ and elm-fluent will be
  forked to target that platform instead. This repo will not be deleted but
  further development will likely stop.

* Free software: MIT license

Credits
-------

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
