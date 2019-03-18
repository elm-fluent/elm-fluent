#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

import sys

from setuptools import find_packages, setup

with open("README.rst") as readme_file:
    readme = readme_file.read()

with open("HISTORY.rst") as history_file:
    history = history_file.read()

requirements = [
    "Click>=6.0",
    "fluent.syntax>=0.10.0,<0.13.0",
    "attrs>=18",
    "language-tags>=0.4.4",
    "beautifulsoup4>=4.6.3",
    "lxml>=4.2.4",
    "watchdog>=0.8.3",
    "fs>=2.4.2",
]

if sys.version_info < (3, 4):
    # functools.singledispatch is in stdlib from Python 3.4 onwards.
    requirements.append("singledispatch>=3.4")

# It would be nice to inline requirements_dev.txt here, add:
#    extras_require={
#        'develop': test_requirements,
#    },
# and then in tox.ini we could do '.[develop]' as a requirement.
# Unfortunately, 'pip install' from a directory is super slow:
#  https://github.com/pypa/pip/issues/2195
test_requirements = open("requirements_dev.txt").read().split("\n")

setup(
    author="Luke Plant",
    author_email="L.Plant.98@cantab.net",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
    ],
    description="Fluent i18n solution for Elm",
    entry_points={"console_scripts": ["ftl2elm=elm_fluent.cli:main"]},
    install_requires=requirements,
    license="MIT license",
    long_description=readme + "\n\n" + history,
    keywords="elm_fluent",
    name="elm_fluent",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    tests_require=test_requirements,  # for setup.py test
    url="https://github.com/elm-fluent/elm-fluent",
    version="0.4.0",
    zip_safe=False,
)
