Release process
===============

* Tests, including linters

* Update HISTORY.rst, removing "(in development)". Commit.

* Update the version number, removing the ``.dev1`` part

  * pyproject.toml
  * src/elm_fluent/__init__.py
  * docs/conf.py

* Make sure all is committed

* Release to PyPI::

    ./release.sh

* Update the version numbers again, moving to the next release, and adding ".dev1"

* Add new section to HISTORY.rst
