import os

import h5py
import numpy as np
import pytest

from toughio import CylindricMesh, H5File, Mesh
from toughio.meshmaker import cylindric_grid, structured_grid


@pytest.fixture
def mesh_file(tmp_path, monkeypatch):
    # Isolate mesh-class persistence from the separate login and Unicode fixes.
    monkeypatch.setattr(os, "getlogin", lambda: "mesh-class-test")
    return tmp_path / "mesh.h5"


def test_legacy_mesh_schema_without_mesh_class(mesh_file):
    coordinates = np.meshgrid([0.0, 1.0], [0.0, 1.0], [0.0, 1.0], indexing="ij")
    # Original schema, built independently of the modified H5File writer.
    with h5py.File(mesh_file, "w") as file:
        mesh = file.create_group("Mesh")
        mesh["type"] = "StructuredGrid"
        geometry = mesh.create_group("pyvista")
        for name, values in zip(["x", "y", "z"], coordinates):
            geometry[name] = values
        mesh.create_group("data")
        metadata = mesh.create_group("metadata")
        metadata["Label"] = np.array([b"A0001"])
        metadata["Label Length"] = 5
    with H5File(mesh_file) as file:
        loaded = file.load_mesh()
    assert type(loaded) is Mesh
    np.testing.assert_allclose(loaded.volumes, [1.0])
    np.testing.assert_array_equal(loaded.labels, [b"A0001"])


@pytest.mark.parametrize("kind", ["mesh", "unstructured", "cylindric"])
def test_mesh_class_volume_and_labels_roundtrip(mesh_file, kind):
    if kind == "cylindric":
        mesh = cylindric_grid([1.0, 1.0], [1.0, 1.0])
        assert type(mesh) is CylindricMesh
        np.testing.assert_allclose(np.sort(mesh.volumes), np.pi * np.array([1, 1, 3, 3]))
    else:
        mesh = structured_grid([1.0, 2.0], [1.0], [1.0])
        if kind == "unstructured":
            mesh = Mesh(mesh.pyvista.cast_to_unstructured_grid(), metadata=mesh.metadata)
        np.testing.assert_allclose(np.sort(mesh.volumes), [1.0, 2.0])
    # Fixed-byte ASCII metadata avoids depending on the Unicode writer topic.
    mesh.metadata["Label"] = np.asarray(mesh.labels, dtype="S")
    expected_labels = mesh.labels.copy()
    expected_volumes = mesh.volumes.copy()
    with H5File(mesh_file, "w", compression="gzip") as file:
        file.dump(mesh)
    with h5py.File(mesh_file) as file:
        assert file["Mesh/mesh_class"].asstr()[()] == type(mesh).__name__
    with H5File(mesh_file) as file:
        loaded = file.load_mesh()
    assert type(loaded) is type(mesh)
    np.testing.assert_allclose(loaded.volumes, expected_volumes)
    np.testing.assert_array_equal(loaded.labels, expected_labels)


@pytest.mark.parametrize("stored_class", ["UnknownMesh", ""])
def test_mesh_class_validation(mesh_file, stored_class):
    mesh = structured_grid([1.0], [1.0], [1.0])
    mesh.metadata["Label"] = np.asarray(mesh.labels, dtype="S")
    with H5File(mesh_file, "w", compression="gzip") as file:
        file.dump(mesh)
    with h5py.File(mesh_file, "a") as file:
        del file["Mesh/mesh_class"]
        file["Mesh/mesh_class"] = stored_class
    with H5File(mesh_file) as file:
        if stored_class:
            with pytest.raises(ValueError, match="unknown stored mesh class"):
                file.load_mesh()
        else:
            assert type(file.load_mesh()) is Mesh
