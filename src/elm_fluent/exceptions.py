from __future__ import absolute_import, unicode_literals


class FluentError(ValueError):
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


class BadMessageId(FluentError):
    pass


class TypeMismatch(FluentError):
    pass


class HtmlTypeMismatch(FluentError):
    pass


class FunctionParameterError(FluentError):
    pass
