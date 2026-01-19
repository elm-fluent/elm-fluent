from collections import OrderedDict

from elm_fluent.compiler import (
    get_message_function_ast,
    get_processing_order,
    parse_ftl,
)
from elm_fluent.inference import (
    Conflict,
    DateTime,
    InferredType,
    Number,
    String,
    infer_arg_types,
)
from elm_fluent.utils import FtlSource

from .utils import dedent_ftl


def ftl_to_types(ftl):
    source_text = dedent_ftl(ftl)
    messages, junk = parse_ftl(source_text)
    message_ids_to_ast = OrderedDict(get_message_function_ast(messages))
    processing_order = get_processing_order(message_ids_to_ast)
    sorted_message_ids = [msg_id for msg_id, i in sorted(processing_order.items(), key=lambda pair: pair[1])]
    return infer_arg_types(message_ids_to_ast, sorted_message_ids, "<string>", source_text)


class FakeFtlSource:
    """
    An object that will compare equal to an actual `FtlSource`
    object without requiring a real AST object for `expr`
    like `FtlSource` has.
    """

    def __init__(self, message_id, row, col):
        self.message_id = message_id
        self.row = row
        self.col = col

    def __repr__(self):
        return f"<FakeFtlSource {self.message_id} {self.row} {self.col}>"

    def __eq__(self, other):
        if isinstance(other, FtlSource):
            if self.message_id != other.message_id:
                return False
            row, col = other.position
            return row == self.row and col == self.col
        return NotImplemented


def test_no_args():
    assert ftl_to_types("""
        foo = Hello
    """) == {"foo": {}}


def test_string():
    assert ftl_to_types("""
        foo = Hello { $name }
    """) == {"foo": {"name": InferredType(type=String, evidences=[FakeFtlSource("foo", 1, 15)])}}


def test_number_function():
    assert ftl_to_types("""
        foo = You have { NUMBER($count) } emails!
    """) == {"foo": {"count": InferredType(type=Number, evidences=[FakeFtlSource("foo", 1, 18)])}}


def test_datetime_function():
    assert ftl_to_types("""
       foo = Today is { DATETIME($today) }!
    """) == {"foo": {"today": InferredType(type=DateTime, evidences=[FakeFtlSource("foo", 1, 18)])}}


def test_conflict():
    assert ftl_to_types("""
        foo =
           Today is { DATETIME($count) }!
           You have { NUMBER($count) } emails!
    """) == {
        "foo": {
            "count": Conflict(
                types=[
                    InferredType(type=DateTime, evidences=[FakeFtlSource("foo", 2, 15)]),
                    InferredType(
                        type=Number,
                        evidences=[FakeFtlSource("foo", 3, 15)],
                    ),
                ],
                message_source=FakeFtlSource("foo", 1, 1),
            )
        }
    }


def test_called_message():
    arg_types = ftl_to_types("""
        bar = { foo }
        foo = Hello { $name }, you have { NUMBER($count) } emails.
    """)
    assert arg_types["foo"] == {
        "name": InferredType(type=String, evidences=[FakeFtlSource("foo", 2, 15)]),
        "count": InferredType(type=Number, evidences=[FakeFtlSource("foo", 2, 35)]),
    }

    assert arg_types["bar"] == {
        "name": InferredType(
            type=String,
            evidences=[
                FakeFtlSource("bar", 1, 9),  # We are calling foo
                FakeFtlSource("foo", 2, 15),  # foo thinks 'name' is String
            ],
        ),
        "count": InferredType(
            type=Number,
            evidences=[
                FakeFtlSource("bar", 1, 9),  # We are calling foo
                FakeFtlSource("foo", 2, 35),  # foo thinks 'count' is Number
            ],
        ),
    }


def test_select_number():
    arg_types = ftl_to_types("""
        bar = { $arg ->
            *[1] One
         }
    """)
    assert arg_types == {
        "bar": {
            "arg": InferredType(
                type=Number,
                evidences=[
                    FakeFtlSource("bar", 2, 7),
                ],
            )
        }
    }


def test_select_plural_form():
    arg_types = ftl_to_types("""
        bar = { $arg ->
            *[one] One
         }
    """)
    assert arg_types == {
        "bar": {
            "arg": InferredType(
                type=Number,
                evidences=[
                    FakeFtlSource("bar", 2, 7),
                ],
            )
        }
    }


def test_select_mixed_numeric():
    arg_types = ftl_to_types("""
        bar = { $arg ->
             [0]   Zero
            *[one] One
         }
    """)
    assert arg_types == {
        "bar": {
            "arg": InferredType(
                type=Number,
                evidences=[
                    FakeFtlSource("bar", 2, 7),
                    FakeFtlSource("bar", 3, 7),
                ],
            )
        }
    }


def test_select_string():
    arg_types = ftl_to_types("""
        bar = { $arg ->
            *[Hello]   Hi
         }
    """)
    assert arg_types == {
        "bar": {
            "arg": InferredType(
                type=String,
                evidences=[
                    FakeFtlSource("bar", 2, 7),
                ],
            )
        }
    }


def test_select_string_with_plural_cat():
    # Plural category should not be treated as number if
    # other non plural category strings are present
    arg_types = ftl_to_types("""
        bar = { $arg ->
            *[zero]   Zero
             [positive]  Positive
             [negative]  Negative
         }
    """)
    assert arg_types == {
        "bar": {
            "arg": InferredType(
                type=String,
                evidences=[
                    FakeFtlSource("bar", 2, 7),
                    FakeFtlSource("bar", 3, 7),
                    FakeFtlSource("bar", 4, 7),
                ],
            )
        }
    }


def test_select_conflict():
    arg_types = ftl_to_types("""
        bar = { $arg ->
             [0]  Zero
            *[Hello]   Hi
         }
    """)
    assert arg_types == {
        "bar": {
            "arg": Conflict(
                types=[
                    InferredType(
                        type=Number,
                        evidences=[
                            FakeFtlSource("bar", 2, 7),
                        ],
                    ),
                    InferredType(
                        type=String,
                        evidences=[
                            FakeFtlSource("bar", 3, 7),
                        ],
                    ),
                ],
                message_source=FakeFtlSource("bar", 1, 1),
            )
        }
    }


def test_conflicting_called_message():
    arg_types = ftl_to_types("""
        bar = { foo } { NUMBER($name) }
        foo = Hello { $name }
    """)
    assert arg_types["foo"] == {
        "name": InferredType(type=String, evidences=[FakeFtlSource("foo", 2, 15)]),
    }

    assert type(arg_types["bar"]["name"]) is Conflict
    assert len(arg_types["bar"]["name"].types) == 2
    assert arg_types["bar"]["name"].types[0] == InferredType(
        type=String,
        evidences=[
            FakeFtlSource("bar", 1, 9),  # We are calling foo
            FakeFtlSource("foo", 2, 15),  # foo thinks 'name' is String
        ],
    )
    assert arg_types["bar"]["name"].types[1] == InferredType(
        type=Number,
        evidences=[
            FakeFtlSource("bar", 1, 17),  # NUMBER call
        ],
    )
