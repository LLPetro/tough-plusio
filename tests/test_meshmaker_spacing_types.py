import numpy as np
import pytest

from toughio.meshmaker import cylindric_grid, structured_grid


@pytest.mark.parametrize("dtype", [np.int64, np.float32])
def test_grid_preserves_small_spacing_after_large_coordinate(dtype):
    mesh = structured_grid(
        np.array([2**24, 1], dtype=dtype), [1], [1], origin=(0, 0, 0)
    )
    assert mesh.points.dtype == np.dtype(float)
    np.testing.assert_allclose(np.sort(mesh.volumes), [1.0, float(2**24)])
    assert mesh.points[:, 0].max() == 2**24 + 1


@pytest.mark.parametrize("cylindric", [False, True])
def test_unsigned_spacing_uses_negative_default_origin(cylindric):
    dz = np.array([1, 2], dtype=np.uint64)
    if cylindric:
        mesh = cylindric_grid(np.array([1], dtype=np.uint64), dz)
        expected_volumes = np.pi * np.array([1.0, 2.0])
    else:
        mesh = structured_grid([1], [1], dz)
        expected_volumes = np.array([1.0, 2.0])
    assert mesh.points[:, 2].min() == -3.0
    assert mesh.points[:, 2].max() == 0.0
    np.testing.assert_allclose(np.sort(mesh.volumes), expected_volumes)
