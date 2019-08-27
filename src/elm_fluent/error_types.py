import attr

# These error objects are not exceptions that are thrown, therefore we don't
# inherit from an Exception subclass, and have more freedom.


class FluentError:
    # NB not all errors use this base, only the simpler ones
    def __init__(self, message):
        self.message = message
        self.error_sources = []

    # This equality method exists to make exact tests for errors much
    # simpler to write, at least for our own errors.
    def __eq__(self, other):
        return (other.__class__ == self.__class__) and other.message == self.message

    def __repr__(self):
        return '<{0}: {1!r}>'.format(self.__class__.__name__, self.message)

    def __hash__(self):
        return hash(self.message)


class ReferenceError(FluentError):
    pass


class CyclicReferenceError(FluentError):
    pass


class JunkFound(FluentError):
    def __init__(self, message, annotations):
        super().__init__(message)
        self.annotations = annotations


class MissingMessage(FluentError):
    pass


class MissingMessageFile(FluentError):
    pass


class BadMessageId(FluentError):
    pass


class TypeMismatch(FluentError):
    def display(self):
        output = []
        primary_source = self.error_sources[0]
        output.append("{0}: In message '{1}': {2}".format(
            primary_source.display_location(),
            primary_source.message_id,
            self.message
        ))
        if len(self.error_sources) > 1:
            output.append("  Compare to:")
            for source in self.error_sources[1:]:
                output.append("    {0}: {1}".format(
                    source.display_location(),
                    source.expr_as_text(),
                ))
        return '\n'.join(output)


class HtmlTypeMismatch(FluentError):
    pass


class FunctionParameterError(FluentError):
    pass


class TermParameterError(FluentError):
    pass


@attr.s
class ArgumentConflictError:
    message_id = attr.ib()
    arg_name = attr.ib()
    conflict = attr.ib()  # Conflict instance
    master = attr.ib(default=False)  # True for compiling master function

    def display(self):
        from . import inference
        output = []
        if self.master:
            output.append("For master '{0}' function: Conflicting inferred types for argument '${1}'".format(
                self.message_id,
                self.arg_name,
            ))
        else:
            source = self.conflict.message_source
            output.append("{0}: In message '{1}': Conflicting inferred types for argument '${2}'".format(
                source.display_location(),
                self.message_id,
                self.arg_name,
            ))

        inferred_types = self.conflict.types
        if inferred_types:
            output.append("  Compare the following:")
            for inferred_type in inferred_types:
                for evidence in inferred_type.evidences:
                    output.append("    {0}: Inferred type: {1}".format(
                        evidence.display_location(), inferred_type.type.name))

            if any(inferred_type.type == inference.String for inferred_type in inferred_types):
                output.append("")
                output.append("  Hint: You may need to use NUMBER() or DATETIME() builtins to force the correct type.")
        return "\n".join(output)
