# -*- coding: utf-8 -*-
"""Console script for elm_fluent."""
from __future__ import absolute_import, unicode_literals

import os.path
import time

import attr
import click
import watchdog.observers
import watchdog.events

from .run import ErrorWhenMissing, FallbackToDefaultLocaleWhenMissing, run_compile


@attr.s
class CompilationOptions(object):
    locales_dir = attr.ib()
    output_dir = attr.ib()
    default_locale = attr.ib()
    missing_translation_strategy = attr.ib()
    use_isolating = attr.ib()
    cwd = attr.ib()
    verbose = attr.ib(default=False)


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
@click.option(
    "--watch/",
    "watch",
    flag_value=True,
    help="Watch for changes and rebuild as necessary",
)
@click.option("--verbose/--quiet", default=False, help="More verbose output")
def main(
    locales_dir, output_dir, when_missing, default_locale, bdi_isolating, watch, verbose
):
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
        cwd=os.getcwd(),
        verbose=verbose,
    )

    if watch:
        run_compile_and_ignore_abort(options)
        observer = watchdog.observers.Observer()
        handler = RunCompileEventHandler(options)
        observer.schedule(handler, options.locales_dir, recursive=True)
        observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()
    else:
        return run_compile(options)


def run_compile_and_ignore_abort(options):
    try:
        run_compile(options)
    except click.Abort:
        pass


class RunCompileEventHandler(watchdog.events.FileSystemEventHandler):
    def __init__(self, options):
        self.options = options

    def on_any_event(self, event):
        click.secho("Changes detected, re-running...\n", fg="yellow")
        run_compile_and_ignore_abort(self.options)
