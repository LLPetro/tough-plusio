import pytest

from toughio._io.output.csv._csv import _float
from toughio.core.record_formatter import RecordFormatter, to_float


@pytest.mark.parametrize(
    "text, expected",
    [("1.25D+02", 125.0), ("1.25d-02", 0.0125), ("1.25E+02", 125.0),
     ("1.25-02", 0.0125), ("-1.25+02", -125.0), (".25-003", 0.00025),
     (" 1.25+003 ", 1250.0)],
)
def test_fortran_numbers_in_core_and_csv(text, expected):
    assert to_float(text) == expected
    assert _float(text) == expected
    assert RecordFormatter("20e", free_format=True)(text) == [expected]


@pytest.mark.parametrize("text", ["bad", "1.2-3", "1.2+0001", "1.2-003junk"])
def test_fortran_numbers_reject_invalid_tokens(text):
    for converter in [to_float, _float]:
        with pytest.raises(ValueError):
            converter(text)
    with pytest.raises(ValueError):
        RecordFormatter("20e", free_format=True)(text)


def test_fortran_writer_format_is_unchanged():
    assert RecordFormatter("10e", mode="w")([1.25]) == ["      1.25\n"]
