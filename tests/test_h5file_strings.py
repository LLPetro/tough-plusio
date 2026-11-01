import os

import h5py
import numpy as np
import pytest

from toughio import H5File


@pytest.mark.parametrize("values", [np.array(["A", "BC"]), ["A", "BC"]])
def test_h5_numpy_unicode_array_roundtrip(tmp_path, monkeypatch, values):
    monkeypatch.setattr(os, "getlogin", lambda: "strings-test")
    filename = tmp_path / "strings.h5"
    with H5File(filename, "w", compression="gzip") as file:
        file._dump_data("labels", values)
    with H5File(filename) as file:
        np.testing.assert_array_equal(file._load_data("labels"), values)


def test_h5_unicode_array_is_written_as_utf8(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "getlogin", lambda: "strings-test")
    filename = tmp_path / "unicode.h5"
    values = np.array(["温度", "é", "A"])
    with H5File(filename, "w", compression="gzip") as file:
        file._dump_data("labels", values)
    # Read through h5py: non-ASCII decoding in H5File is a separate reader issue.
    with h5py.File(filename) as file:
        np.testing.assert_array_equal(file["labels"].asstr()[:], values)
        assert h5py.check_string_dtype(file["labels"].dtype).encoding == "utf-8"
