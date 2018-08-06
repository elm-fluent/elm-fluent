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

Status
------

* Alpha, but usable
* Under very heavy development
* A working test suite
* No docs :-( . The contents of ``tests/test_project``, and the ``test_end_to_end.py`` file, are the closest
  to docs currently.
* Compatibility: Elm 0.18 only at the moment.

  With Elm 0.19, lack of builtin support for `Intl
  <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl>`_,
  plus the changes that make 3rd party native code much harder, means this will
  not be fixed very quickly.

----

* Free software: MIT license
* Documentation: https://elm-fluent.readthedocs.io


Main TODO items
---------------

* DONE: Complete compiler for Fluent 0.6 syntax
* DONE: NUMBER and DATETIME builtin functions (using `elm-intl <https://github.com/vanwagonet/elm-intl>`_,
  which means you need `elm-github-install <https://github.com/gdotdesign/elm-github-install/>`_ to install at the moment.
* TODO: Good error handling for all errors in FTL files
* TODO: Mechanism for HTML messages (designed in my head, not implemented)


Credits
-------

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
