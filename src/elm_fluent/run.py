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
from .utils import normpath


class MissingTranslationStrategy(object):
    def get_locale_when_missing(self, locale):
        raise NotImplementedError()

    def missing_ftl_file(self, options, filename, locale, errors, warnings):
        raise NotImplementedError()

    def missing_message(self, message_id, locale, errors, warnings):
        raise NotImplementedError()


def missing_file(filename, options):
    return exceptions.MissingMessageFile(
        "Message file '{0}' not found".format(filename)
    )


class ErrorWhenMissing(MissingTranslationStrategy):
    def get_locale_when_missing(self, locale):
        return None

    def missing_ftl_file(self, options, filename, locale, errors, warnings):
        errors.append(missing_file(filename, options))

    def missing_message(self, message_id, locale, errors, warnings):
        errors.append(
            exceptions.MissingMessage(
                "Locale '{0}' - Message '{1}' missing".format(locale, message_id)
            )
        )


class FallbackToDefaultLocaleWhenMissing(MissingTranslationStrategy):
    def __init__(self, fallback_locale):
        self.fallback_locale = fallback_locale

    def _can_fallback(self, locale):
        return locale != self.fallback_locale

    def get_locale_when_missing(self, locale):
        if self._can_fallback(locale):
            return self.fallback_locale
        else:
            return None

    def missing_ftl_file(self, options, filename, locale, errors, warnings):
        if not self._can_fallback(locale):
            # Can't fall back to anything if the fallback is missing
            errors.append(missing_file(filename, options))
        else:
            warnings.append(missing_file(filename, options))

    def missing_message(self, message_id, locale, errors, warnings):
        if locale == self.fallback_locale:
            extra = (
                " This message will be omitted since it is not in the fallback locale."
            )
        else:
            extra = ""
        warnings.append(
            exceptions.MissingMessage(
                "Locale '{0}' - Message '{1}' missing.{2}".format(
                    locale, message_id, extra
                )
            )
        )


def run_compile(options):
    locales = find_locales(options.locales_fs, options.locales_dir, options.include)
    if not locales:
        raise click.UsageError(
            "No locale directories (directories containing .ftl files) found in {0} directory"
            .format(normpath(options.locales_fs, options.locales_dir))
        )
    bad_locales = [l for l in locales if not language_tags.tags.check(l)]
    if bad_locales:
        raise click.UsageError(
            "The following directory names are not valid BCP 47 language tags: {0}"
            .format(", ".join(bad_locales))
        )

    stems = find_all_ftl_stems(options.locales_fs, options.locales_dir, options.include, locales)
    finalizers = []
    error_printers = []
    warning_printers = []
    for stem in stems:
        success, finalizer, error_printer, warning_printer = generate_elm_for_stem(
            options, locales, stem
        )
        if success:
            finalizers.append(finalizer)
        if error_printer:
            error_printers.append(error_printer)
        if warning_printer:
            warning_printers.append(warning_printer)

    if warning_printers:
        click.secho("\nWarnings:\n", fg="red", bold=True)
        for wp in warning_printers:
            wp()

    if error_printers:
        click.secho("\nErrors:\n", fg="red", bold=True)
        for ep in error_printers:
            ep()
        if options.verbose:
            click.secho("Failed!", fg="red", bold=True)
        raise click.Abort()

    if options.verbose:
        click.secho("\nWriting files:\n", fg="green", bold=True)
    for f in finalizers:
        f()

    if options.verbose:
        click.secho("Success!", fg="green", bold=True)


def generate_elm_for_stem(options, locales, stem):
    errors = []
    warnings = []
    locales_fs = options.locales_fs
    output_fs = options.output_fs

    sources = {}
    locale_modules = {}
    modules_to_write = []
    master_message_mapping = {}
    for locale in locales:
        filename = os.path.join(options.locales_dir, locale, stem)
        module_name = module_name_for_stem(stem, locale=locale)
        if locales_fs.exists(filename):
            with locales_fs.open(filename, "rb") as f:
                messages_string = f.read().decode("utf-8")
            sources[filename] = messages_string
            module, compile_errors, message_mapping = compile_messages(
                messages_string,
                locale,
                message_source=filename,
                module_name=module_name,
                use_isolating=options.use_isolating,
            )
            locale_modules[locale] = module
            master_message_mapping.update(message_mapping)
            new_elm_path = path_for_module(options, module_name)
            if compile_errors:
                errors.extend(compile_errors)
            else:
                modules_to_write.append((new_elm_path, module))
        else:
            options.missing_translation_strategy.missing_ftl_file(
                options, filename, locale, errors, warnings
            )

    master_module_name = module_name_for_stem(stem, master=True)
    try:
        master_module, master_errors, master_warnings = compile_master(
            master_module_name, locales, locale_modules, master_message_mapping, options
        )
    except Exception as e:
        click.secho(
            "While compiling {0}, an exception occurred.".format(master_module_name),
            fg="red",
            bold=True,
        )
        click.secho(
            "Please report this as a bug to https://github.com/elm-fluent/elm-fluent",
            fg="red",
            bold=True,
        )
        raise e

    errors.extend(master_errors)
    warnings.extend(master_warnings)

    if not master_errors:
        master_filename = path_for_module(options, master_module_name)
        modules_to_write.append((master_filename, master_module))

    def finalizer():
        if not errors:
            for fname, module in modules_to_write:
                if module.exports:
                    # If there are no exports, there is no point writing the
                    # module, and `exposing ()` is also invalid syntax, so we
                    # must avoid writing it
                    source = module.as_source_code()
                    ensure_path_dirs(output_fs, fname)
                    if options.verbose:
                        click.echo(
                            "Writing {0}".format(fname)
                        )
                    with output_fs.open(fname, "wb") as f:
                        f.write(source.encode("utf-8"))

    def error_printer():
        print_errors(options, errors, sources)

    def warning_printer():
        print_warnings(warnings)

    return (
        len(errors) == 0,
        finalizer,
        error_printer if errors else None,
        warning_printer if warnings else None,
    )


def print_errors(options, errors, sources):
    for err in errors:
        if getattr(err, "error_sources", []):
            for error_source in err.error_sources:
                source_filename = error_source.message_source
                row, col = span_to_position(
                    error_source.expr.span, sources[source_filename]
                )
                if error_source.message_id is not None:
                    click.echo(
                        "{0}:{1}:{2}: In message '{3}': {4}".format(
                            source_filename,
                            row,
                            col,
                            error_source.message_id,
                            err.args[0],
                        )
                    )
                else:
                    click.echo(
                        "{0}:{1}:{2}: {3}".format(source_filename, row, col, err.args[0])
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
                    row, col = span_to_position(
                        type_source.ftl_source.expr.span, sources[t_source_filename]
                    )
                    click.echo(
                        "    {0}:{1}:{2}: Inferred type: {3}".format(
                            t_source_filename, row, col, type_source.type_obj
                        )
                    )

                if any(
                    type_source.type_obj == dtypes.String
                    for type_source in type_sources
                ):
                    click.echo("")
                    click.echo("  Hint: You may need to use NUMBER() or DATETIME() builtins to force the correct type")


def print_warnings(warnings):
    for warning in warnings:
        click.echo(warning.args[0])


def ensure_path_dirs(fs, path):
    dirname = os.path.dirname(path)
    if not fs.exists(dirname):
        fs.makedirs(dirname)


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


def find_locales(locales_fs, locales_dir, include_glob):
    return [
        d.name for d in locales_fs.scandir(locales_dir)
        if d.is_dir and contains_ftl(locales_fs.opendir(locales_dir).opendir(d.name), include_glob)
    ]


def contains_ftl(fs, include_glob):
    return any(
        is_ftl(m.path) for m in fs.glob(include_glob)
    )


def is_ftl(filepath):
    basename = os.path.basename(filepath)
    return basename.endswith(".ftl") and not basename.startswith(".")


def find_all_ftl_stems(locales_fs, locales_dir, include_glob, locales):
    """
    Given a locales directory and a list of locales, finds all the
    ftl stem names. For example, for these files:

    /path/to/locales/en/foo/bar.ftl
    /path/to/locales/de/foo/bar.ftl

    there is a single ftl stem, 'foo/bar.ftl'
    """
    ftl_stems = set([])
    for l in locales:
        locale_base_fs = locales_fs.opendir(os.path.join(locales_dir, l))
        ftl_files = [
            m.path.lstrip('/')
            for m in locale_base_fs.glob(include_glob)
            if is_ftl(m.path)
        ]
        ftl_stems |= set(ftl_files)
    return sorted(list(ftl_stems))
