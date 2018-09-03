==========
elm-fluent
==========


.. image:: https://img.shields.io/pypi/v/elm_fluent.svg
        :target: https://pypi.python.org/pypi/elm_fluent

.. image:: https://img.shields.io/travis/elm-fluent/elm-fluent.svg
        :target: https://travis-ci.org/elm-fluent/elm-fluent

.. image:: https://readthedocs.org/projects/elm-fluent/badge/?version=latest
        :target: https://elm-fluent.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status


`Fluent <https://projectfluent.org/>`_ i18n solution for Elm


Fluent is a next-generation translation/localization solution, designed by the
folks at Mozilla, and extracted from their l20n solution to be a re-usable
specification.

elm-fluent is a full implementation of this specification for Elm. It operates
as a command line tool that compiles ``.ftl`` files to Elm files. The result is
that each message becomes a function that will generate a translated string (or
HTML fragment) for a given locale and an optional set of strongly typed
parameters (string, dates or numbers).

Dates and numbers can also be passed with formatting parameters supplied - for
example, to attach a currency to a number, so that it can be correctly formatted
as a currency according to the rules of the locale in use.

Please see the `docs
<https://elm-fluent.readthedocs.io/en/latest/>`_ for more
information.

Status
------

* Alpha, but usable
* Under very heavy development
* A working test suite
* Compatibility: Elm 0.18 only at the moment.
* Free software: MIT license


Main TODO items
---------------

* DONE: Complete compiler for Fluent 0.6 syntax
* DONE: NUMBER and DATETIME builtin functions (using `elm-intl <https://github.com/vanwagonet/elm-intl>`_,
  which means you need `elm-github-install <https://github.com/gdotdesign/elm-github-install/>`_ to install at the moment.
* DONE: Mechanism for HTML messages, with attaching of event handlers or other arbitrary Attributes to nodes
* TODO: Good error handling for all errors in FTL files
* TODO: Docs!!!

Credits
-------

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
