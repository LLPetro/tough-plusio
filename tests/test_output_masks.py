import numpy as np
import pytest

from toughio import ConnectionOutput, ElementOutput


@pytest.mark.parametrize("cls", [ElementOutput, ConnectionOutput])
@pytest.mark.parametrize("mask", [[True, False, True], [True] * 3, [False] * 3])
@pytest.mark.parametrize("array", [False, True])
def test_output_boolean_mask_preserves_rows(cls, mask, array):
    labels = ["A", "B", "C"] if cls is ElementOutput else [
        ["A", "B"], ["B", "C"], ["C", "D"]
    ]
    output = cls(data={"P": np.array([10.0, 20.0, 30.0])}, labels=labels, time=7)
    selected = output[np.asarray(mask) if array else mask]
    assert type(selected) is cls
    assert selected.time == output.time
    assert selected.n_data == sum(mask)
    np.testing.assert_array_equal(selected.data["P"], output.data["P"][mask])
    if any(mask):
        np.testing.assert_array_equal(selected.labels, output.labels[mask])
    else:
        assert len(selected.labels) == 0


@pytest.mark.parametrize("cls", [ElementOutput, ConnectionOutput])
@pytest.mark.parametrize("mask", [[True, False], [True] * 4])
def test_output_boolean_mask_length_must_match(cls, mask):
    labels = ["A", "B", "C"] if cls is ElementOutput else [
        ["A", "B"], ["B", "C"], ["C", "D"]
    ]
    output = cls(data={"P": np.arange(3.0)}, labels=labels)
    with pytest.raises(ValueError, match="mask must match output rows"):
        output[mask]
