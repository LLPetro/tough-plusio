"""Regression tests for edge cases of the T+H input format."""

import io

import numpy as np
import pytest

import toughio
from toughio._io.input.tough_hydrate._helpers import (
    Lines,
    fortran_real,
    read_namelist,
    split_record,
)


def write_read_text(parameters):
    buffer = io.StringIO()
    toughio.write_input(buffer, parameters, file_format="tough+hydrate")
    text = buffer.getvalue()

    return text, toughio.read_input(io.StringIO(text), file_format="tough+hydrate")


def boundary(read_format):
    return {
        "boundary_number": 1,
        "boundary_name": "V01",
        "pv_numbers": [3, 1],
        "data_form": "Table",
        "read_by_row_or_by_col": "row",
        "rowcolnum_to_primvarnum": [3, -1, 0, 1],
        "read_format": read_format,
        "comment": "table",
        "table": [[2.0, -1222.34, 0.0, 3.5e6], [-1.5, -1480.0, 4.32e5, 3.0e6]],
    }


@pytest.mark.parametrize("read_format", ["*", "(4E20.13)", "(2(E15.6))", "(6E20.13)"])
def test_boundaries_table_format(deck, read_format):
    parameters = deck(
        transient_boundaries=[boundary(read_format)],
        generators=[{"label": "A00 0", "name": "Pro01", "type": "MASS", "rates": -1.0}],
    )
    text, out = write_read_text(parameters)

    assert out["transient_boundaries"] == parameters["transient_boundaries"]
    assert out["generators"][0]["name"] == "Pro01"
    if read_format == "(4E20.13)":
        assert "                 2.0            -1222.34" in text


def test_boundaries_fixed_table_without_separators(deck):
    parameters = deck(transient_boundaries=[boundary("(4E20.13)")])
    text, _ = write_read_text(parameters)
    rows = "".join(f"{x:20.13E}" for x in (2.0, -1222.34, 0.0, 3.5e6))
    rows += "\n" + "".join(f"{x:20.13E}" for x in (-1.5, -1480.0, 4.32e5, 3.0e6))
    start = text.index("'table'")
    start = text.index("\n", start) + 1
    end = text.index("<<<")
    out = toughio.read_input(
        io.StringIO(text[:start] + rows + "\n" + text[end:]),
        file_format="tough+hydrate",
    )

    assert out["transient_boundaries"][0]["table"] == boundary("*")["table"]


def test_boundaries_unsupported_format(deck):
    with pytest.raises(ValueError):
        write_read_text(deck(transient_boundaries=[boundary("(4A20)")]))


def test_namelist_array_assignment():
    _, group = read_namelist(
        Lines(
            "&G phase = 'Gas', component(1) = 'CH4', 'H2O', number(2) = 3, 4, x(5) = 1 /\n"
        )
    )

    assert group == {
        "phase": "Gas",
        "component": {1: "CH4", 2: "H2O"},
        "number": {2: 3, 3: 4},
        "x": {5: 1},
    }


@pytest.mark.parametrize(
    "record, tokens",
    [
        ("2, ,4,.FALSE.", ["2", None, "4", ".FALSE."]),
        (", 1", [None, "1"]),
        ("1,,2", ["1", None, "2"]),
        ("1 2,", ["1", "2"]),
        ("2*5 3* 'a, b' ! c, d", ["5", "5", None, None, None, "a, b"]),
    ],
)
def test_list_directed_null_values(record, tokens):
    assert split_record(record) == tokens


def test_memory_with_missing_middle_value(deck):
    parameters = deck()
    parameters["memory"] = {
        k: v for k, v in parameters["memory"].items() if k != "geomechanics_code"
    }
    text, out = write_read_text(parameters)

    assert ".FALSE., , 'Continuous', 0" in text
    assert out["memory"] == parameters["memory"]


def test_save_fixed_fields():
    record = f"{'A00 0           3.00000000E-01  AqH: P, S_aqu, T':<71}"
    record += 2 * " 0.10000000E-12" + " 0.20000000E-12\n"
    save = (
        "INCON: Initial conditions for 2 elements at time 1.0000000E+00\n"
        + record
        + "-1.0000000000000E+00-2.0000000000000E+00 1.0000000000000-100\n"
        + record.replace("A00 0", "A00 1")
        + " 1.0000000000000E+00 2.0000000000000E+00 3.0000000000000E+00\n"
        + ":::\n"
        + "&Data_For_Continuation_Run  timesteps_to_this_point = 2 /\n"
    )
    out = toughio.read_output(io.StringIO(save), file_format="tough+hydrate-save")

    assert out.time == 1.0
    assert list(out.labels) == ["A00 0", "A00 1"]
    np.testing.assert_allclose(out.data["X1"], [-1.0, 1.0])
    np.testing.assert_allclose(out.data["X3"], [1.0e-100, 3.0])
    np.testing.assert_allclose(out.data["perm_z"], [2.0e-13, 2.0e-13])


@pytest.mark.parametrize(
    "key, empty",
    [
        ("elements", {}),
        ("connections", {}),
        ("initial_conditions", {}),
        ("generators", []),
    ],
)
def test_empty_list_blocks_are_kept(deck, key, empty):
    _, out = write_read_text(deck(**{key: empty}))
    assert out[key] == empty


@pytest.mark.parametrize(
    "key",
    [
        "subdomains",
        "interfaces",
        "ss_groups",
        "transient_boundaries",
        "extended_initial_conditions",
    ],
)
def test_empty_namelist_blocks_are_absent(deck, key):
    text, out = write_read_text(deck(**{key: []}))
    assert key not in out


@pytest.mark.parametrize(
    "text, decimals, value",
    [
        ("      1000", 4, 0.1),
        ("    1000.0", 4, 1000.0),
        ("    -25E+3", 4, -2.5),
        ("     12-02", 4, 1.2e-5),
        ("  1.0D+00 ", 4, 1.0),
        ("          ", 4, None),
        ("         5", 0, 5.0),
    ],
)
def test_fortran_implied_decimals(text, decimals, value):
    expected = None if value is None else pytest.approx(value)
    assert fortran_real(text, decimals) == expected


def test_fixed_fields_use_implied_decimals(deck):
    text, _ = write_read_text(
        deck(rocks={"SAND1": {"density": 2600.0, "specific_heat": 1000.0}})
    )
    text = text.replace("    1000.0", "      1000")
    out = toughio.read_input(io.StringIO(text), file_format="tough+hydrate")

    assert out["rocks"]["SAND1"]["specific_heat"] == pytest.approx(0.1)


def test_boundaries_fixed_table_implied_decimals(deck):
    parameters = deck(transient_boundaries=[boundary("(4E20.4)")])
    text, _ = write_read_text(parameters)
    rows = [[2.0, -1222.34, 0.0, 3.5e6], [-1.5, -1480.0, 4.32e5, 3.0e6]]
    table = "".join(
        "".join(f"{round(x * 1e4):20d}" for x in row) + "\n" for row in rows
    )
    start = text.index("'table'")
    start = text.index("\n", start) + 1
    out = toughio.read_input(
        io.StringIO(text[:start] + table + text[text.index("<<<") :]),
        file_format="tough+hydrate",
    )

    np.testing.assert_allclose(out["transient_boundaries"][0]["table"], rows)


def test_namelist_null_values():
    _, group = read_namelist(
        Lines("&G d(1) = 1.0e-9, 1.0e-9, d(1) = , 2.0e-9, v = 1, , 3 /\n")
    )

    assert group == {"d": {1: 1.0e-9, 2: 2.0e-9}, "v": [1, None, 3]}


def test_save_reference_porosity():
    record = f"{'A00 0           3.00000000E-01  AqH: P, S_aqu, T':<71}"
    record += 3 * " 0.10000000E-12" + " 0.25000000E+00\n"
    save = "INCON: at time 1.0\n" + record + " 1.0000000000000E+00\n"
    out = toughio.read_output(io.StringIO(save), file_format="tough+hydrate-save")

    np.testing.assert_allclose(out.data["porosity_ref"], [0.25])


def test_namelist_null_keeps_previous_value():
    _, group = read_namelist(
        Lines("&G x = 2.5, x = , y = 1, 2, 3, y = , 9, z = , w = 4, w = 5, /\n")
    )

    assert group == {"x": 2.5, "y": [1, 9, 3], "w": 5}


def test_namelist_single_item_array_is_scalar(deck):
    parameters = deck(transient_boundaries=[{**boundary("*"), "pv_numbers": [3]}])
    _, out = write_read_text(parameters)

    assert out["transient_boundaries"][0]["pv_numbers"] == 3


def test_free_format_numbers_are_exact(deck):
    value = 0.12345678901234566
    parameters = deck(
        hydrate={
            "components": [
                {"name": "CH4", "hydration_number": 6.0, "mole_fraction": 1.0}
            ],
            "thermal_conductivity": [value, 1.0e-300],
            "specific_heat": [value],
            "density": [],
            "equation_option": 2,
            "reaction_type": "EQUILIBRIUM",
        },
        multiphase_diffusion={"gas_diffusivity_equation_exponent": value, "phases": []},
    )
    _, out = write_read_text(parameters)

    assert out["hydrate"] == parameters["hydrate"]
    assert out["multiphase_diffusion"] == parameters["multiphase_diffusion"]


@pytest.mark.parametrize(
    "text, expected",
    [
        ("x = 1, 2, x(2) = 9", {1: 1, 2: 9}),
        ("x(1) = 1, 2, x = , 9", {1: 1, 2: 9}),
        ("x = 1, , 3, x(2) = , 8", {1: 1, 3: 8}),
        ("x(2) = 5, x = 7", {1: 7, 2: 5}),
        ("x(3) = , x = ,", None),
    ],
)
def test_namelist_mixed_assignments(text, expected):
    # component_diffusivity is declared from 1
    text = text.replace("x", "component_diffusivity")
    _, group = read_namelist(Lines(f"&Component_Diffusivities_in_Phases {text} /\n"))

    assert group.get("component_diffusivity") == expected


UNITS = {0: "sec", 1: "Pa", 2: " ", 3: "C"}


@pytest.mark.parametrize(
    "text",
    [
        "units_of_Primvar(0) = 'sec', units_of_Primvar = 'sec', 'Pa', ' ', 'C'",
        "units_of_Primvar = 'sec', 'Pa', ' ', 'C', units_of_Primvar(0) = 'sec'",
        "units_of_Primvar = 'min', 'Pa', ' ', 'K', units_of_Primvar(3) = 'C',"
        " units_of_Primvar(0) = 'sec'",
        "units_of_Primvar(1) = 'Pa', 'Pa', units_of_Primvar = 'sec', , ' ', 'C'",
    ],
)
def test_namelist_mixed_assignments_zero_lower_bound(deck, text):
    # units_of_PrimVar is declared from 0 (units_of_PrimVar(0) is the time unit)
    _, table = read_namelist(Lines(f"&Tabular_Data_Definition {text} /\n"))

    assert table["units_of_primvar"] == UNITS

    parameters = deck(transient_boundaries=[{**boundary("*"), **table}])
    _, out = write_read_text(parameters)

    assert out["transient_boundaries"][0]["units_of_primvar"] == UNITS


def test_namelist_whole_array_without_index_keeps_list():
    _, table = read_namelist(
        Lines("&Tabular_Data_Definition units_of_Primvar = 'sec', 'Pa', ' ', 'C' /\n")
    )

    assert table["units_of_primvar"] == ["sec", "Pa", " ", "C"]


@pytest.mark.parametrize("text", ["x = 1, 2, x(2) = 9", "x(2) = 9, x = , 1"])
def test_namelist_mixed_assignments_unknown_lower_bound(text):
    with pytest.raises(ValueError, match="lower bound"):
        read_namelist(Lines(f"&G {text} /\n"))


def test_namelist_null_whole_assignment_needs_no_lower_bound():
    _, group = read_namelist(Lines("&G x(3) = 4, x = , , /\n"))

    assert group == {"x": {3: 4}}


def test_namelist_mixed_assignments_round_trip(deck):
    text = (
        "&Component_Diffusivities_in_Phases phase = 'Gas', component(1) = 'CH4', 'H2O',\n"
        "   component_diffusivity = 1.0e-5, 1.0e-5, component_diffusivity(2) = 2.0e-5 /\n"
    )
    _, phase = read_namelist(Lines(text))
    parameters = deck(multiphase_diffusion={"phases": [phase]})
    _, out = write_read_text(parameters)

    assert out["multiphase_diffusion"]["phases"][0]["component_diffusivity"] == {
        1: 1.0e-5,
        2: 2.0e-5,
    }


@pytest.mark.parametrize("text", ["x(1, 2) = 3", "x(1:2) = 3, 4"])
def test_namelist_unsupported_assignment(text):
    with pytest.raises(ValueError):
        read_namelist(Lines(f"&G y = 1, {text} /\n"))
