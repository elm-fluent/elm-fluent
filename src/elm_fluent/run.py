from __future__ import absolute_import, print_function, unicode_literals

import os
import os.path

import click
import language_tags

from . import exceptions
from .compiler import (
    compile_master,
    compile_messages,
    module_name_for_locale,
    span_to_position,
)
from .stubs import defaults as dtypes

try:
    FileNotFoundError
except NameError:
    FileNotFoundError = IOError


class MissingTranslationStrategy(object):
    def missing_ftl_file(self, options, filename, locale, errors, warnings):
        raise NotImplementedError()

    def missing_message(self, message_id, locale, errors, warnings):
        raise NotImplementedError()


class ErrorWhenMissing(MissingTranslationStrategy):
    def missing_ftl_file(self, options, filename, locale, errors, warnings):
        errors.append(
            FileNotFoundError(
                "{0} - file not found".format(os.path.relpath(filename, options.cwd))
            )
        )


class FallbackToDefaultLocaleWhenMissing(MissingTranslationStrategy):
    def __init__(self, fallback_locale):
        self.fallback_locale = fallback_locale

    def missing_ftl_file(self, options, filename, locale, errors, warnings):
        if locale == self.fallback_locale:
            # Can't fall back to anything if the fallback is missing
            errors.append(FileNotFoundError("{0} not found".format(filename)))
        else:
            warnings.append(FileNotFoundError("{0} not found".format(filename)))


def run_compile(options):
    locales = find_locales(options.locales_dir)
    if not locales:
        raise click.UsageError(
            "No locale directories (directories containing .ftl files) found in {0} directory".format(
                options.locales_dir
            )
        )
    bad_locales = [l for l in locales if not language_tags.tags.check(l)]
    if bad_locales:
        raise click.UsageError(
            "The following directory names are not valid BCP 47 language tags: {0}".format(
                ", ".join(bad_locales)
            )
        )

    stems = find_all_ftl_stems(options.locales_dir, locales)
    errors = []
    warnings = []
    for stem in stems:
        generate_elm_for_stem(options, locales, stem, errors=errors, warnings=warnings)

    if errors:
        click.secho(
            "Compilation to Elm did not succeed, the following errors were reported:",
            fg="red",
            bold=True,
        )
        for error in errors:
            click.secho(error.args[0], fg="red")
        raise click.Abort()


def generate_elm_for_stem(options, locales, stem, errors=None, warnings=None):
    if errors is None:
        errors = []
    if warnings is None:
        warnings = []

    sources = {}
    locale_modules = {}
    files_to_write = []
    for locale in locales:
        filename = os.path.join(options.locales_dir, locale, stem)
        module_name = module_name_for_stem(stem, locale=locale)
        if os.path.exists(filename):
            with open(filename, "rb") as f:
                messages_string = f.read().decode("utf-8")
            sources[filename] = messages_string
            module, compile_errors = compile_messages(
                messages_string,
                locale,
                message_source=filename,
                module_name=module_name,
                use_isolating=options.use_isolating,
            )
            locale_modules[locale] = module
            new_elm_path = path_for_module(options, module_name)
            if compile_errors:
                errors.extend(compile_errors)
            else:
                files_to_write.append((new_elm_path, module.as_source_code()))
        else:
            options.missing_translation_strategy.missing_ftl_file(
                options, filename, locale, errors, warnings
            )

    master_module_name = module_name_for_stem(stem, master=True)
    try:
        master_module, master_errors = compile_master(
            master_module_name, locales, locale_modules, options
        )
    except Exception as e:
        click.secho(
            "While compiling {0}, an exception occurred.".format(master_module_name),
            fg="red",
            bold=True,
        )
        click.secho(
            "Please report this as a bug to https://github.com/elm-fluent/elm-fluent.",
            fg="red",
            bold=True,
        )
        raise e

    errors.extend(master_errors)

    if not master_errors:
        master_filename = path_for_module(options, master_module_name)
        files_to_write.append((master_filename, master_module.as_source_code()))

    print_warnings(warnings)
    if not errors:
        for fname, source in files_to_write:
            ensure_path_dirs(fname)
            with open(fname, "wb") as f:
                f.write(source.encode("utf-8"))

    else:
        print_errors(options, errors, sources)
        raise click.Abort()


def print_errors(options, errors, sources):
    if errors:
        click.secho("Errors found:\n", fg="red", bold=True)
    for err in errors:
        if getattr(err, "error_sources"):
            for error_source in err.error_sources:
                source_filename = error_source.message_source
                row, col = span_to_position(
                    error_source.expr.span, sources[source_filename]
                )
                short_filename = os.path.relpath(source_filename, options.cwd)
                if error_source.message_id is not None:
                    click.echo(
                        "{0}:{1}:{2}: In message '{3}': {4}".format(
                            short_filename,
                            row,
                            col,
                            error_source.message_id,
                            err.args[0],
                        )
                    )
                else:
                    click.echo(
                        "{0}:{1}:{2}: {3}".format(short_filename, row, col, err.args[0])
                    )
        else:
            if hasattr(err, "message_func_name"):
                click.echo(
                    "While trying to compile master '{0}' function:".format(
                        err.message_func_name
                    )
                )
                click.echo("  {0}".format(err.args[0]))
            else:
                click.echo(err.args[0])
        if isinstance(err, exceptions.RecordTypeMismatch):
            click.echo(
                "  Explanation: incompatible types were detected for message argument '${0}'".format(
                    err.field_name
                )
            )
            type_sources = err.record_type.field_type_ftl_sources[err.field_name]
            if type_sources:
                click.echo("  Compare the following:")
                for type_source in type_sources:
                    t_source_filename = type_source.ftl_source.message_source
                    t_short_filename = os.path.relpath(t_source_filename, options.cwd)
                    row, col = span_to_position(
                        type_source.ftl_source.expr.span, sources[t_source_filename]
                    )
                    click.echo(
                        "    {0}:{1}:{2}: Inferred type: {3}".format(
                            t_short_filename, row, col, type_source.type_obj
                        )
                    )

                if any(
                    type_source.type_obj == dtypes.String
                    for type_source in type_sources
                ):
                    click.echo("")
                    click.echo(
                        "  Hint: You may need to use NUMBER() or DATETIME() builtins to force the correct type"
                    )
        click.echo("")


def print_warnings(warnings):
    pass  # TODO


def ensure_path_dirs(path):
    dirname = os.path.dirname(path)
    if not os.path.exists(dirname):
        os.makedirs(dirname)


def module_name_for_stem(ftl_stem, locale=None, master=False):
    if locale is None:
        assert master
    if locale is not None:
        assert not master

    if master:
        first_part = "Translations"
    else:
        first_part = module_name_for_locale(locale)

    return "Ftl.{0}.{1}".format(
        first_part,
        ".".join(part.title() for part in ftl_stem.replace(".ftl", "").split("/")),
    )


def path_for_module(options, module_name):
    return os.path.join(options.output_dir, module_name.replace(".", "/") + ".elm")


def find_locales(locales_dir):
    return [
        d for d in os.listdir(locales_dir) if contains_ftl(os.path.join(locales_dir, d))
    ]


def contains_ftl(directory):
    if not os.path.isdir(directory):
        return False
    return any(
        is_ftl(f) for dirpath, dirnames, files in os.walk(directory) for f in files
    )


def is_ftl(path):
    return path.endswith(".ftl") and not os.path.basename(path).startswith(".")


def find_all_ftl_stems(locales_dir, locales):
    """
    Given a locales directory and a list of locales, finds all the
    ftl stem names. For example, for these files:

    /path/to/locales/en/foo/bar.ftl
    /path/to/locales/de/foo/bar.ftl

    there is a single ftl stem, 'foo/bar.ftl'
    """
    ftl_stems = set([])
    for l in locales:
        locale_base_dir = os.path.join(locales_dir, l)
        stem_offset = len(locale_base_dir) + 1
        ftl_files = [
            os.path.join(dirpath, f)[stem_offset:]
            for dirpath, dirnames, files in os.walk(locale_base_dir)
            for f in files
            if is_ftl(f)
        ]
        ftl_stems |= set(ftl_files)
    return sorted(list(ftl_stems))


def compile_ftl_set(files):

    pass
