import os

import h5py
import numpy as np
import pytest

from toughio import H5File


@pytest.mark.parametrize("compression", ["lzf", "gzip"])
def test_h5_compression_roundtrip(tmp_path, monkeypatch, compression):
    monkeypatch.setattr(os, "getlogin", lambda: "compression-test")
    filename = tmp_path / "compressed.h5"
    values = np.arange(12.0).reshape(3, 4)
    with H5File(filename, "w", compression=compression, compression_opts=6) as file:
        file._dump_data("values", values)
    with H5File(filename) as file:
        np.testing.assert_array_equal(file._load_data("values"), values)
    with h5py.File(filename) as file:
        dataset = file["values"]
        assert dataset.compression == compression
        assert dataset.compression_opts == (6 if compression == "gzip" else None)
