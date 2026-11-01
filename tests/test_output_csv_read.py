from io import StringIO

import numpy as np
import pytest

import toughio
from toughio._io.output.csv._csv import _read_csv


@pytest.mark.parametrize("units", [False, True])
@pytest.mark.parametrize("connection", [False, True])
def test_csv_frames_with_optional_units(tmp_path, units, connection):
    headers = '"ELEM1","ELEM2","P"' if connection else '"ELEM","P"'
    unit_row = '"()","()","(PA)"' if connection else '"()","(PA)"'
    labels = '"A,1","B"' if connection else '"A,1"'
    rows = [headers]
    if units:
        rows.append(unit_row)
    rows += ['"TIME [sec]  1.0"', labels + ',2.5', '',
             '"TIME [sec]  2.0"', labels + ',4.5']
    filename = tmp_path / "output.csv"
    filename.write_text("\n".join(rows) + "\n")
    output = toughio.read_output(filename, file_format="csv", connection=connection)
    assert [item.time for item in output] == [1.0, 2.0]
    assert [item.data["P"][0] for item in output] == [2.5, 4.5]
    expected = [["A,1", "B"]] if connection else ["A,1"]
    np.testing.assert_array_equal(output[0].labels, expected)
    selected = toughio.read_output(
        filename, file_format="csv", connection=connection, time_steps=1
    )
    assert selected.time == 2.0
    np.testing.assert_array_equal(selected.data["P"], [4.5])


@pytest.mark.parametrize("units", [False, True])
def test_csv_reader_keeps_initial_untimed_frame(units):
    text = '"ELEM","P"\n'
    if units:
        text += '"()","(PA)"\n'
    text += '"A",3.0\n'
    headers, times, labels, data = _read_csv(StringIO(text), "element")
    assert headers == ["P"]
    assert times == [None]
    assert labels == [["A"]]
    assert data == [[[3.0]]]
