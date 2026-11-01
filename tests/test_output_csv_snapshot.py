import numpy as np
import pytest

import toughio


@pytest.mark.parametrize("connection", [False, True])
@pytest.mark.parametrize("time_steps", [None, 0, -1])
def test_csv_snapshot_roundtrip(tmp_path, connection, time_steps):
    cls = toughio.ConnectionOutput if connection else toughio.ElementOutput
    labels = [["A", "B"], ["B", "C"]] if connection else ["A", "B"]
    snapshot = cls(data={"P": np.array([2.5, 4.5])}, labels=labels, time=None)
    filename = tmp_path / "snapshot.csv"
    toughio.write_output(filename, snapshot, file_format="csv")
    assert "TIME [sec]" not in filename.read_text()
    loaded = toughio.read_output(
        filename, file_format="csv", connection=connection, time_steps=time_steps
    )
    if time_steps is None:
        assert len(loaded) == 1
        loaded = loaded[0]
    assert loaded.time is None
    np.testing.assert_array_equal(loaded.labels, labels)
    np.testing.assert_array_equal(loaded.data["P"], snapshot.data["P"])
