import numpy as np
import pytest

from toughio.meshmaker import structured_grid


@pytest.mark.parametrize("two_dimensional", [False, True])
@pytest.mark.parametrize("hide_cell", [False, True])
def test_mesh_without_internal_connections(two_dimensional, hide_cell):
    mesh = structured_grid(
        [1.0, 1.0] if hide_cell else [1.0],
        [0.0] if two_dimensional else [1.0], [1.0],
    )
    if hide_cell:
        mesh.pyvista.cell_data["vtkGhostType"] = np.array([0, 32], dtype=np.uint8)
    connections, centers, normals, areas = mesh._compute_connection_properties()
    assert connections.shape == (0, 2)
    assert connections.dtype.kind in "iu"
    assert centers.shape == normals.shape == (0, 3)
    assert areas.shape == (0,)


def test_internal_connection_geometry_is_unchanged():
    mesh = structured_grid([1.0, 1.0], [1.0], [1.0], origin=(0.0, 0.0, 0.0))
    connections, centers, normals, areas = mesh._compute_connection_properties()
    np.testing.assert_array_equal(np.sort(connections, axis=1), [[0, 1]])
    np.testing.assert_allclose(centers, [[1.0, 0.5, 0.5]])
    np.testing.assert_allclose(np.abs(normals), [[1.0, 0.0, 0.0]])
    np.testing.assert_allclose(areas, [1.0])
