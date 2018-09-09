==========
elm-fluent
==========


.. image:: https://img.shields.io/pypi/v/elm_fluent.svg
        :target: https://pypi.org/project/elm-fluent/

.. image:: https://img.shields.io/travis/elm-fluent/elm-fluent.svg
        :target: https://travis-ci.org/elm-fluent/elm-fluent

.. image:: https://readthedocs.org/projects/elm-fluent/badge/?version=latest
        :target: https://elm-fluent.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status


elm-fluent is a `Fluent <https://projectfluent.org/>`_ implementation for Elm.

Fluent is a next-generation translation/localization solution, designed by the
folks at Mozilla, based on many years of experience with localizing into a large
number of different languages. Mozilla have extracted parts of their 'l20n'
solution (used by apps like Firefox and Thunderbird) into a re-usable
specification designed specifically for the web.

elm-fluent is a full implementation of this specification for Elm. It operates
as a command line tool that compiles ``.ftl`` files to ``.elm`` files. The
result is that each message becomes a function that will generate a translated
string (or HTML fragment) for a given locale and an optional set of strongly
typed parameters (string, dates or numbers).

Dates and numbers can also be passed with formatting parameters supplied - for
example, to attach a currency to a number, so that it can be correctly formatted
as a currency according to the rules of the locale in use.

Please see the `docs
<https://elm-fluent.readthedocs.io/en/latest/>`_ for more
information.

Status
------

* Rough around the edges, but usable. Please see the list of `open issues
  <https://github.com/elm-fluent/elm-fluent/issues>`_.
* A pretty complete test suite.
* Compatibility: Elm 0.18 only at the moment.
* Free software: MIT license

Credits
-------

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
