class FluentError(ValueError):
    def __init__(self, *args):
        super(FluentError, self).__init__(*args)
        self.error_sources = []

    # This equality method exists to make exact tests for exceptions much
    # simpler to write, at least for our own errors.
    def __eq__(self, other):
        return (other.__class__ == self.__class__) and other.args == self.args

    def __hash__(self):
        return hash(self.args)


class ReferenceError(FluentError):
    pass


class CyclicReferenceError(FluentError):
    pass


class DuplicateMessageId(FluentError):
    pass


class JunkFound(FluentError):
    def __init__(self, *args):
        super(JunkFound, self).__init__(*args)
        self.message = args[0]
        self.annotations = args[1]


class MissingMessage(FluentError):
    pass


class MissingMessageFile(FluentError):
    pass


class BadMessageId(FluentError):
    pass


class TypeMismatch(FluentError):
    pass


class RecordTypeMismatch(TypeMismatch):
    def __init__(self, *args, record_type=None, field_name=None):
        super(RecordTypeMismatch, self).__init__(*args)
        self.record_type = record_type
        self.field_name = field_name


class HtmlTypeMismatch(FluentError):
    pass


class FunctionParameterError(FluentError):
    pass


class TermParameterError(FluentError):
    pass
