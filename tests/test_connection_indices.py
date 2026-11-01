import numpy as np
import pytest

from toughio import ConnectionOutput


@pytest.fixture
def output():
    return ConnectionOutput(
        data={"Q": np.array([10.0, 20.0, 30.0])}, time=7.0,
        labels=[["A", "B"], ["B", "C"], ["C", "D"]],
    )


@pytest.mark.parametrize("indices", [[], [2], [0, 2], [2, 0, 2]])
@pytest.mark.parametrize("array", [False, True])
def test_connection_integer_vectors(output, indices, array):
    index = np.asarray(indices, dtype=int) if array else indices
    selected = output[index]
    assert isinstance(selected, ConnectionOutput)
    assert selected.time == output.time
    np.testing.assert_array_equal(selected.labels, output.labels[indices])
    np.testing.assert_array_equal(selected.data["Q"], output.data["Q"][indices])


def test_connection_label_and_scalar_indexing(output):
    assert output[["B", "C"]] == {"Q": 20.0}
    assert output[1] == {"Q": 20.0}
    selected = output[[["C", "D"], ["A", "B"]]]
    np.testing.assert_array_equal(selected.data["Q"], [30.0, 10.0])
    np.testing.assert_array_equal(output["B"].data["Q"], [10.0, 20.0])


@pytest.mark.parametrize("indices", [[0.5, 1.5], ["A", "B", "C"]])
def test_connection_invalid_vectors(output, indices):
    with pytest.raises(ValueError):
        output[indices]
