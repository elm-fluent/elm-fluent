.. highlight:: shell

============
Installation
============


Stable release
--------------

elm-fluent works primarily as a command line application that compiles ``.ftl``
files to Elm code. This application is written in Python, and if you already have
a Python installation (3.10+) you can easily install it as follows.

We recommend using `pipx <https://pypi.org/project/pipx/>`_ to allow you to
install Python binaries in their own virtualenvs which are isolated from your
system Python. With pipx installed, do:

.. code-block:: console

   pipx install elm-fluent


Alternatively, you can manually create the virtualenv:

.. code-block:: console

   $ virtualenv my_virtual_env
   $ . my_virtual_env/bin/activate

Then install the latest version from PyPI using pip:

.. code-block:: console

   $ pip install elm-fluent

An executable ``ftl2elm`` should have been added to your PATH, in your system
``bin`` or the virtualenv ``bin`` directory.

If you don't have Python, `pip`_ or virtualenv installed, this `Python
installation guide`_ can guide you through the process.

.. _pip: https://pip.pypa.io
.. _Python installation guide: http://docs.python-guide.org/en/latest/starting/installation/


From sources
------------

The sources for elm-fluent can be downloaded from the `Github repo`_.

.. _Github repo: https://github.com/elm-fluent/elm-fluent


Elm dependencies
----------------

The ``.elm`` files that elm-fluent produces have dependencies. At this point in
time, these dependencies are a bit problematic: the Fluent spec has `built-in
date and number formatting functions
<https://projectfluent.org/fluent/guide/functions.html#built-in-functions>`_
(``DATETIME`` and ``NUMBER``), as well as support for handling of plural forms,
which are covered by built-in browser Javascript modules `Intl.DateTimeFormat
<https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/DateTimeFormat>`_,
`Intl.NumberFormat
<https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/NumberFormat>`_
and `Intl.PluralRules
<https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/PluralRules>`_
respectively.

However, these Javascript APIs are not yet wrapped by any core Elm libraries,
although `the core team are looking into it
<https://discourse.elm-lang.org/t/state-of-localization-l10n-and-v0-19/1541/18>`_,
and implementing them in pure Elm has many difficulties. Until there is an
official solution, elm-fluent depends on the `elm-intl
<https://github.com/vanwagonet/elm-intl/>`_ wrapping.

Since this uses native/kernel modules, it can't be uploaded to
packages.elm-lang.org, but it can be installed using `elm-github-install
<https://github.com/gdotdesign/elm-github-install/>`_.

Elm 0.18 instructions
~~~~~~~~~~~~~~~~~~~~~

First install `elm-github-install
<https://github.com/gdotdesign/elm-github-install/>`_ if you don't have it.
Quick version:

.. code-block:: console

   $ npm install elm-github-install -g

Add the following dependencies to your elm-package.json::

    "dependencies": {
        "thetalecrafter/elm-intl": "2.0.0 <= v < 3.0.0",
        "elm-fluent/elm-fluent": "1.0.0 <= v < 2.0.0"
    }

and dependency sources - this will be a new section if you haven't used
``elm-github-install`` before::

    "dependency-sources": {
        "thetalecrafter/elm-intl": {
            "url": "https://github.com/vanwagonet/elm-intl",
            "ref": "master"
        },
        "elm-fluent/elm-fluent": {
            "url": "https://github.com/elm-fluent/elm-fluent",
            "ref": "master"
        }
    },

This adds the ``elm-fluent`` package (a very small module provided by this
project), and the ``elm-intl`` package. You should also check `elm-intl
<https://github.com/vanwagonet/elm-intl>`_ installation notes for info regarding
polyfills.

Finally, run::

  $ elm-install

.. warning::

   NOTE: by using ``elm-github-install`` and adding these dependencies, you are
   opening yourself up to the problems that Javascript code brings - you are
   essentially trusting these packages in the same way that you currently trust
   Javascript from core Elm packages, rather than relying on the Elm compiler to
   protect you from many issues that Javascript brings.


Elm 0.19
~~~~~~~~

Elm 0.19 has added restrictions that make it harder to use third party packages
with native code, so for the time being there is no easy way to install the
required dependencies with Elm 0.19.

Hopefully for Elm 0.19 we will have official ``Intl`` wrappers of some kind
soon. It will probably not be too hard to adapt the elm-fluent compiler to
depend on those libraries instead. This will likely mean some changes to user
code, but possibly just types/imports.

It is hoped that this project will provide feedback/prototyping that will help
to shape a useful set of ``Intl`` wrappers for package.elm-lang.org.
