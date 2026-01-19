"""Console script for elm_fluent."""

import os.path
import time
from dataclasses import dataclass
from typing import Literal

import click
import watchdog.events
import watchdog.observers
from fs.osfs import OSFS

from . import __version__
from .run import ErrorWhenMissing, FallbackToDefaultLocaleWhenMissing, MissingTranslationStrategy, run_compile
from .utils import normpath


@dataclass
class CompilationOptions:
    locales_fs: OSFS
    output_fs: OSFS
    locales_dir: str
    output_dir: str
    include: str
    default_locale: str
    missing_translation_strategy: MissingTranslationStrategy
    use_isolating: bool
    verbose: bool = False


# These functions exist so that we can patch them out when testing. There
# doesn't seem to be a way to pass other extra kwargs to 'main' function
# below.
def get_locales_fs(path):
    return OSFS(path)


def get_output_fs(path):
    return OSFS(path)


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
    help="What to do when translations are missing for a locale, defaults to error",
)
@click.option("--default-locale", default="en", help="The default locale, used for fallbacks")
@click.option("--include", default="**/*.ftl", help="Glob pattern for the FTL files to include")
@click.option(
    "--bdi-isolating/--no-bdi-isolating",
    default=True,
    help="Use BDI isolating characters",
)
@click.option(
    "--watch",
    "watch",
    flag_value=True,
    help="Watch for changes and rebuild as necessary",
)
@click.option("--verbose/--quiet", default=False, help="More verbose output")
@click.option("--version", "version", flag_value=True, help="Print version and exit")
def main(
    locales_dir: str,
    output_dir: str,
    when_missing: Literal["error", "fallback"],
    default_locale: str,
    include: str,
    bdi_isolating: bool,
    watch: bool,
    verbose: bool,
    version: bool,
):
    if version:
        click.echo(f"elm-fluent {__version__}")
        return

    if os.path.isabs(locales_dir):
        locales_fs = get_locales_fs("/")
    else:
        locales_fs = get_locales_fs(".")

    if os.path.isabs(output_dir):
        output_fs = get_output_fs("/")
    else:
        output_fs = get_output_fs(".")

    if not locales_fs.exists(locales_dir) or not locales_fs.isdir(locales_dir):
        raise click.UsageError(
            f"Locales directory '{locales_dir}' does not exist. Please specify a correct locales "
            "directory using the --locales-dir option"
        )

    if not output_fs.exists(output_dir) or not output_fs.isdir(output_dir):
        raise click.UsageError(
            f"Output directory '{output_dir}' does not exist. Please specify a correct output "
            "directory using the --output-dir option"
        )

    if when_missing == "error":
        missing_translation_strategy = ErrorWhenMissing()
    elif when_missing == "fallback":
        missing_translation_strategy = FallbackToDefaultLocaleWhenMissing(default_locale)

    options = CompilationOptions(
        locales_fs=locales_fs,
        output_fs=output_fs,
        locales_dir=locales_dir,
        output_dir=output_dir,
        include=include,
        default_locale=default_locale,
        missing_translation_strategy=missing_translation_strategy,
        use_isolating=bdi_isolating,
        verbose=verbose,
    )

    if watch:
        run_compile_and_ignore_abort(options)
        observer = watchdog.observers.Observer()
        handler = RunCompileEventHandler(options)
        observer.schedule(handler, normpath(options.locales_fs, options.locales_dir), recursive=True)
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

    def on_modified(self, event):
        if event.is_directory:
            return
        click.secho("Changes detected, re-running...\n", fg="yellow")
        run_compile_and_ignore_abort(self.options)
