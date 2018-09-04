.. highlight:: shell

============
Installation
============


Stable release
--------------

elm-fluent works primarily as a command line application that compiles ``.ftl``
files to Elm code. This application is written in Python, and if you already have
a Python installation (2.7 or 3.3+) you can easily install it as follows:

We recommend making a virtualenv for the installation to isolate it from your
system Python:

.. code-block:: console

   $ virtualenv my_virtual_env
   $ . my_virtual_env/bin/activate

Then install the latest version from PyPI using pip:

.. code-block:: console

   $ pip install elm_fluent

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
time, these dependencies are a bit problematic: Fluent has `built-in date and
number formatting functions
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
<https://discourse.elm-lang.org/t/state-of-localization-l10n-and-v0-19/1541/18>`_.
Until then elm-fluent depends on the `elm-intl
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
        "thetalecrafter/elm-intl": "2.0.0 <= v < 3.0.0"
        "elm-fluent/elm-fluent": "1.0.0 <= v < 2.0.0"
    }

and dependency sources - this will be a new section if you haven't used
``elm-github-install`` before::

    "dependency-sources": {
        "thetalecrafter/elm-intl": {
            "url": "https://github.com/elm-fluent/elm-intl",
            "ref": "master"
        },
        "elm-fluent/elm-fluent": {
            "url": "https://github.com/elm-fluent/elm-fluent",
            "ref": "master"
        }
    },

This adds the ``elm-fluent`` package (a very small module provided by this
project), and the ``elm-intl`` package (for now pointed at our fork of it which
has a few bug fixes).

Elm 0.19
~~~~~~~~

Elm 0.19 has added restrictions that make it harder to use third party packages
with native code, so for the time being there is no easy way to install the
required dependencies with Elm 0.19.
