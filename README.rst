==========
elm-fluent
==========


.. image:: https://img.shields.io/pypi/v/elm_fluent.svg
        :target: https://pypi.org/project/elm-fluent/

.. image:: https://img.shields.io/travis/elm-fluent/elm-fluent.svg
        :target: https://travis-ci.org/elm-fluent/elm-fluent

.. image:: https://codecov.io/gh/elm-fluent/elm-fluent/branch/master/graph/badge.svg
        :target: https://codecov.io/gh/elm-fluent/elm-fluent

.. image:: https://readthedocs.org/projects/elm-fluent/badge/?version=latest
        :target: https://elm-fluent.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status


elm-fluent is a `Fluent <https://projectfluent.org/>`_ implementation for Elm.

Fluent is a next-generation translation/localization solution, designed by the
folks at Mozilla, based on many years of experience with localizing into a large
number of different languages. Mozilla have extracted parts of their 'l20n'
solution (used by apps like Firefox and Thunderbird) into a re-usable
specification designed specifically for the web.

elm-fluent is a full implementation of this specification for Elm (currently
supporting the Fluent 0.8 syntax).

It operates as a command line tool that compiles ``.ftl`` files to ``.elm``
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

* Rough around the edges, but being used in production. Please see the list of `open issues
  <https://github.com/elm-fluent/elm-fluent/issues>`_.
* A pretty complete test suite and sufficient docs.
* Compatibility: Elm 0.18 only.

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
  Elm. In this event the most likely outcome is a migration to `Reason
  <https://reasonml.github.io/>`_ + `bucklescript
  <https://bucklescript.github.io/>`_ and elm-fluent will be forked to target
  that platform instead. This repo will not be deleted but further development
  will likely stop.

* Free software: MIT license

Credits
-------

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
