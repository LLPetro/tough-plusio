import io

import numpy as np
import pytest

import toughio


OUT = """
                                                           Output data after (       2,    7)-2-time steps
                    TOTAL TIME (s)
                     3.0000E+00
   ELEM  INDEX     P           T        S_Hydrate   S_Aqueous
                   (Pa)       (dC)
   A00 0     1  2.7000E+06  1.0000E+00  0.0000E+00  1.0000E+00
   A00 1*    2  5.8473-100  4.5788E-01  6.1867E+00  9.0000E-01

   ELEM1    ELEM2   INDEX  Heat Flow    Gas Flow   Aqu. Flow
                              (W)        (Kg/s)      (Kg/s)
   A00 0    A00 1       1  1.9928E+04  5.9195E-03  6.7948E-01
"""


@pytest.mark.parametrize("file_type", ["element", "connection"])
def test_out(file_type):
    output = toughio.read_output(
        io.StringIO(OUT),
        file_format="tough+hydrate-out",
        connection=file_type == "connection",
    )
    output = output[0]
    assert output.time == 3.0

    if file_type == "element":
        assert list(output.labels) == ["A00 0", "A00 1"]
        assert output.data["P"][1] == 5.8473e-100
    else:
        assert [list(x) for x in output.labels] == [["A00 0", "A00 1"]]
        assert output.data["Aqu. Flow"][0] == 0.67948


def test_table():
    text = "Subdomain MON1\nTime [days]   Pressure(Pa)  Saturation\n 1.0  2.0e6  0.5\n Time [days] Pressure(Pa) Saturation\n 2.0  2.1e6  0.4\n"
    history = toughio.read_table(io.StringIO(text), file_format="tough+hydrate")
    assert isinstance(history, toughio.HistoryOutput)
    assert list(history) == ["Time", "Pressure", "Saturation"]
    assert history.units["Time"] == "d"
    np.testing.assert_allclose(history["Pressure (Pa)"], [2.0e6, 2.1e6])
    assert {k: history.metadata[k] for k in ("title", "type", "label")} == {
        "title": "Subdomain MON1",
        "type": "rock",
        "label": "MON1",
    }


@pytest.mark.hydrate_outputs
@pytest.mark.parametrize("case", ["Test_1P", "Test_2Qp", "Test_3T", "Test_VB"])
def test_solver_outputs(outputs, case):
    root = outputs / case
    elements = toughio.read_output(
        root / f"{case}.out", file_format="tough+hydrate-out"
    )
    connections = toughio.read_output(
        root / f"{case}.out", file_format="tough+hydrate-out", connection=True
    )
    assert elements and connections and len(elements) == len(connections)
    assert all(np.shape(c.labels)[1] == 2 for c in connections)

    save = toughio.read_output(root / "SAVE", file_format="tough+hydrate-save")
    assert len(save.labels) == len(elements[-1].labels)

    plot = toughio.read_output(
        root / "Plot_Data_Elem", file_format="tough+hydrate-element"
    )
    assert plot and plot[0].data

    for path in root.iterdir():
        if path.name.endswith("Time_Series") or path.name == "Hydrate_Status":
            history = toughio.read_table(path, file_format="tough+hydrate")
            assert history.metadata["title"] or path.name == "Hydrate_Status"
            assert all(np.ndim(v) == 1 for v in history.values())
