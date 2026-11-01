import getpass
import os

import h5py

from toughio import H5File


def test_h5_creation_without_controlling_terminal(tmp_path, monkeypatch):
    def no_terminal():
        raise OSError("no controlling terminal")

    monkeypatch.setattr(os, "getlogin", no_terminal)
    filename = tmp_path / "no-terminal.h5"
    with H5File(filename, "w", compression="gzip") as container:
        assert "VersionInfo" in container
    with h5py.File(filename) as container:
        assert container["VersionInfo/user"].asstr()[()] == getpass.getuser()
        assert container["VersionInfo/version"].asstr()[()] == "1.0"
