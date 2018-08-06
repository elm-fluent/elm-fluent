# -*- coding: utf-8 -*-
"""Console script for elm_fluent."""
from __future__ import absolute_import, unicode_literals

import os.path

import attr
import click

from .run import ErrorWhenMissing, FallbackToDefaultLocaleWhenMissing, run_compile


@attr.s
class CompilationOptions(object):
    locales_dir = attr.ib()
    output_dir = attr.ib()
    default_locale = attr.ib()
    missing_translation_strategy = attr.ib()
    use_isolating = attr.ib()


@click.command()
@click.option(
    "--locales-dir",
    default="locales",
    help="Location of the locales directory that holds all FTL files.",
)
@click.option("--output-dir", default=".", help="Location of the outputted Elm files.")
@click.option(
    "--when-missing",
    default="error",
    type=click.Choice(["error", "fallback"]),
    help="What to do when translations are missing for a locale",
)
@click.option(
    "--default-locale", default="en", help="The default locale, used for fallbacks"
)
@click.option(
    "--bdi-isolating/--no-bdi-isolating",
    default=True,
    help="Use BDI isolating characters",
)
def main(locales_dir, output_dir, when_missing, default_locale, bdi_isolating):
    locales_dir = os.path.normpath(os.path.abspath(locales_dir))
    if not os.path.exists(locales_dir) or not os.path.isdir(locales_dir):
        raise click.UsageError(
            "Locales directory '{0}' does not exist. Please specify a correct locales "
            "directory using the --locales-dir option".format(locales_dir)
        )

    output_dir = os.path.normpath(os.path.abspath(output_dir))
    if not os.path.exists(output_dir) or not os.path.isdir(output_dir):
        raise click.UsageError(
            "Output directory '{0}' does not exist. Please specify a correct output "
            "directory using the --output-dir option".format(output_dir)
        )

    if when_missing == "error":
        missing_translation_strategy = ErrorWhenMissing()
    elif when_missing == "fallback":
        missing_translation_strategy = FallbackToDefaultLocaleWhenMissing(
            default_locale
        )

    options = CompilationOptions(
        locales_dir=locales_dir,
        output_dir=output_dir,
        default_locale=default_locale,
        missing_translation_strategy=missing_translation_strategy,
        use_isolating=bdi_isolating,
    )

    return run_compile(options)
