"""The writer writes every field in its Fortran type and refuses what a field cannot hold."""

import io
import math

import numpy as np
import pytest

import toughio
from toughio._io.input.tough_hydrate._helpers import (
    FortranRecordFormatter,
    format_value,
    write_namelist,
)
from toughio.core import RecordFormatter
from toughio.hydrate import FieldError


def write(parameters: dict) -> str:
    buffer = io.StringIO()
    toughio.write_input(buffer, parameters, file_format="tough+hydrate")
    return buffer.getvalue()


def read(text: str) -> dict:
    return toughio.read_input(io.StringIO(text), file_format="tough+hydrate")


def refused(parameters: dict) -> FieldError:
    with pytest.raises(FieldError) as info:
        write(parameters)
    return info.value


def line(text: str, header: str, n: int = 1) -> str:
    """The n-th record after the header of a block."""
    lines = text.splitlines()
    return lines[next(i for i, x in enumerate(lines) if x.startswith(header)) + n]


def param(deck, **options):
    return deck(
        options={"n_cycle": 100, "n_cycle_print": 10, "t_max": 1.0e5, **options},
        extra_options={1: 1, 7: 4},
    )


# Integer fields (Fortran I): whole numbers only, never scientific notation, never wider
@pytest.mark.parametrize("value", [10_000_000, 12345, -1000])
def test_integer_too_wide_for_its_columns(deck, value):
    e = refused(param(deck, n_cycle_print=value))
    assert (e.reason, e.kind, e.width, e.value) == ("too_wide", "integer", 4, value)
    assert (e.block, e.record, e.columns) == ("PARAM", "PARAM.1", (13, 16))
    assert e.path == ("options", "n_cycle_print")
    assert str(e).startswith("PARAM.1 options.n_cycle_print (columns 13-16): integer")


def test_mop_is_one_digit(deck):
    parameters = param(deck)
    parameters["extra_options"] = {7: 10}
    e = refused(parameters)
    assert (e.path, e.columns, e.reason) == (("extra_options", 7), (23, 23), "too_wide")


@pytest.mark.parametrize("value", [100, 100.0, np.int64(100), np.float64(100.0), "100"])
def test_integer_values_by_type(deck, value):
    expected = line(write(param(deck, n_cycle_print=100)), "PARAM")
    assert line(write(param(deck, n_cycle_print=value)), "PARAM") == expected
    assert (
        read(write(param(deck, n_cycle_print=value)))["options"]["n_cycle_print"] == 100
    )


@pytest.mark.parametrize(
    "value, reason",
    [
        (2.5, "not_integer"),
        (True, "not_integer"),
        (np.bool_(False), "not_integer"),
        ("1e3", "not_integer"),
        ([10], "not_integer"),
        (float("nan"), "not_finite"),
        (float("inf"), "not_finite"),
    ],
)
def test_integer_field_refuses_other_types(deck, value, reason):
    e = refused(param(deck, n_cycle_print=value))
    assert (e.reason, e.path) == (reason, ("options", "n_cycle_print"))


def test_negative_initial_time_step(deck):
    e = refused(param(deck, t_steps=-1.0))
    assert e.reason == "negative_time_step"
    assert (e.record, e.columns, e.path) == (
        "PARAM.2",
        (21, 30),
        ("options", "t_steps"),
    )
    # a list of steps is written as PARAM.2.1 records
    steps = [1.0, 2.0, 4.0]
    assert read(write(param(deck, t_steps=steps)))["options"]["t_steps"] == steps


# Real fields (Fortran E): any finite number, with a decimal point and within the width
def test_reals_as_the_upstream_writer():
    rng = np.random.default_rng(0)
    values = [0.0, -0.0, 1.0, -1.0, 3.14159265358979, 9.99999999999, 12345.678, 1e-5]
    values += [3, -7, np.float64(2.5e-3)]
    values += list(rng.choice([-1, 1], 300) * 10 ** rng.uniform(-307, 307, 300))
    for width in (10, 14, 15, 20):
        ours = FortranRecordFormatter(f"{width}f", mode="w")
        upstream = RecordFormatter(f"{width}f", mode="w")
        for value in values:
            assert ours([value]) == upstream([value]), (width, value)


@pytest.mark.parametrize(
    "value", [1e308, -1.5e-308, 2.2250738585072014e-308, 1234.5678e200]
)
def test_extreme_reals_fit_and_read_back(deck, value):
    rocks = {"SAND": {"density": value, "porosity": 0.3}}
    back = read(write(deck(rocks=rocks)))["rocks"]["SAND"]["density"]
    assert math.isclose(back, value, rel_tol=1e-4)


@pytest.mark.parametrize(
    "value, reason",
    [
        (float("nan"), "not_finite"),
        (-float("inf"), "not_finite"),
        (10**400, "not_finite"),
        ("abc", "not_real"),
        (True, "not_real"),
        ({"x": 1}, "not_real"),
    ],
)
def test_real_field_refuses_other_values(deck, value, reason):
    e = refused(deck(rocks={"SAND": {"density": value, "porosity": 0.3}}))
    assert (e.reason, e.kind) == (reason, "real")
    assert (e.block, e.record, e.label) == ("ROCKS", "ROCKS.1", "SAND")
    assert (e.path, e.columns) == (("rocks", "SAND", "density"), (11, 20))


def test_numeric_text_in_a_real_field_gets_a_decimal_point(deck):
    # "1000" in an E10.4 field would be read as 0.1 (implied decimals)
    back = read(write(deck(rocks={"SAND": {"density": "1000", "porosity": 0.3}})))
    assert back["rocks"]["SAND"]["density"] == 1000.0


def test_table_width_too_small_for_a_value():
    writer = FortranRecordFormatter("7f,7f", mode="w", multiple=True, names=())
    assert writer([1.5, -2.0e-30]) == ["    1.5-2.e-30\n"]
    # "-1e-308" has no decimal point: read with implied decimals, it would be smaller
    with pytest.raises(FieldError) as info:
        writer([1.0, 2.0, -1.5e-308])
    assert (info.value.path, info.value.columns) == ((2,), (1, 7))


# Text fields (Fortran A): ASCII without control characters, within the width
@pytest.mark.parametrize(
    "name, reason",
    [("SANDSTONE", "too_wide"), ("砂岩", "not_ascii"), ("SA\nND", "control_character")],
)
def test_text_field(deck, name, reason):
    e = refused(deck(rocks={name: {"density": 2600.0, "porosity": 0.3}}))
    assert (e.reason, e.kind, e.record, e.columns) == (
        reason,
        "text",
        "ROCKS.1",
        (1, 5),
    )
    assert e.path == ("rocks", name)


def test_text_blanks_on_the_padding_side_are_dropped(deck):
    text = write(deck(rocks={"SAND     ": {"density": 2600.0, "porosity": 0.3}}))
    assert line(text, "ROCKS").startswith("SAND     0")
    assert list(read(text)["rocks"]) == ["SAND"]


def test_numpy_labels_and_values_are_shown_plain(deck):
    e = refused(deck(elements={np.str_("A11 1"): {"volume": np.float64("nan")}}))
    assert type(e.label) is str and e.path == ("elements", "A11 1", "volume")
    assert type(e.path[1]) is str and e.shown == "nan"
    assert str(e) == (
        "ELEME 'A11 1' elements.A11 1.volume (columns 21-30): nan is not a finite number"
    )


def test_element_activity_columns(deck):
    elements = {"A11 1": {"material": "SAND", "volume": 1.0, "activity": "V0001"}}
    e = refused(deck(elements=elements))
    assert (e.block, e.label, e.columns) == ("ELEME", "A11 1", (82, 84))
    assert e.path == ("elements", "A11 1", "activity")


def test_element_and_connection_labels(deck):
    elements = {"A11 1": {"material": "SAND", "volume": 1.0}, "A11 2": {"nseq": 10**6}}
    e = refused(deck(elements=elements))
    assert (e.label, e.path, e.columns) == (
        "A11 2",
        ("elements", "A11 2", "nseq"),
        (6, 10),
    )

    connections = {"A11 1A11 2": {"permeability_direction": 123456}}
    e = refused(deck(connections=connections))
    assert (e.block, e.label, e.columns) == ("CONNE", "A11 1A11 2", (26, 30))


def test_primary_variables_are_located(deck):
    incon = {"A11 1": {"porosity": 0.3, "values": [1.0e7, float("nan")]}}
    e = refused(deck(initial_conditions=incon))
    assert (e.block, e.record, e.label) == ("INCON", "INCON.2", "A11 1")
    assert (e.path, e.columns) == (
        ("initial_conditions", "A11 1", "values", 1),
        (21, 40),
    )


def test_times_count(deck):
    e = refused(deck(times=list(range(100_000))))
    assert (e.record, e.path, e.columns) == ("TIMES.1", ("times",), (1, 5))


def test_title_is_one_record(deck):
    e = refused(deck(title="Hydrate test\nROCKS"))
    assert (e.reason, e.path) == ("control_character", ("title",))
    assert read(write(deck(title="Tab\there")))["title"] == "Tab\there"


# List-directed and NAMELIST values: in the declared type, or in the type of the value
def test_memory_types(deck):
    parameters = deck()
    parameters["memory"] = {**parameters["memory"], "max_n_elements": 1000.0}
    back = read(write(parameters))["memory"]["max_n_elements"]
    assert back == 1000 and isinstance(back, int)


@pytest.mark.parametrize(
    "key, value, reason, record",
    [
        ("coordinate_system", [], "not_text", "MEMORY.4"),
        ("max_n_elements", 1.5, "not_integer", "MEMORY.4"),
        ("max_n_elements", 2**31, "out_of_range", "MEMORY.4"),
        ("max_n_sources", "two", "not_integer", "MEMORY.5"),
        ("active_connections_only", 1, "not_logical", "MEMORY.4"),
        ("tortuosity_method", "a\nb", "control_character", "MEMORY.7"),
    ],
)
def test_memory_refuses(deck, key, value, reason, record):
    parameters = deck()
    parameters["memory"] = {**parameters["memory"], key: value}
    e = refused(parameters)
    assert (e.block, e.record, e.path, e.reason) == (
        "MEMORY",
        record,
        ("memory", key),
        reason,
    )


def test_top_level_memory_path(deck):
    e = refused(deck(do_diffusion="no"))
    assert (e.record, e.path, e.reason) == (
        "MEMORY.3",
        ("do_diffusion",),
        "not_logical",
    )


@pytest.mark.parametrize(
    "value, text",
    [
        (np.float64(1.5e-9), "1.5e-09"),
        (np.int64(2), "2"),
        (np.bool_(True), ".TRUE."),
        (False, ".FALSE."),
        (3, "3"),
        (0.1, "0.1"),
        ("it's", "'it''s'"),
        (None, ""),
    ],
)
def test_format_value_by_type(value, text):
    assert format_value(value) == text


@pytest.mark.parametrize(
    "value, reason",
    [
        (float("nan"), "not_finite"),
        ([1, 2], "not_a_value"),
        ({}, "not_a_value"),
        (2**40, "out_of_range"),
        ("a\nb", "control_character"),
    ],
)
def test_format_value_refuses(value, reason):
    with pytest.raises(FieldError) as info:
        format_value(value)
    assert info.value.reason == reason


def test_namelist_value_is_named():
    with pytest.raises(FieldError) as info:
        write_namelist("Group", {"ok": 1.0, "bad": {1: 2.0, 2: float("inf")}})
    assert info.value.field == "Group.bad"
    assert str(info.value) == "record Group.bad: inf is not a finite number"
    assert (
        write_namelist("Group", {"x": np.array([1.0, 2.0])})[1] == "    x = 1.0, 2.0,\n"
    )


def test_hydrate_types(deck):
    hydrate = {
        "components": [{"name": "CH4", "hydration_number": 6, "mole_fraction": 1}],
        "equation_option": 2.0,
        "reaction_type": "EQUILIBRIUM",
    }
    back = read(write(deck(hydrate=hydrate)))["hydrate"]
    assert back["components"] == [
        {"name": "CH4", "hydration_number": 6.0, "mole_fraction": 1.0}
    ]
    assert back["equation_option"] == 2 and isinstance(back["equation_option"], int)

    hydrate["components"][0]["name"] = 4
    e = refused(deck(hydrate=hydrate))
    assert (e.block, e.path, e.reason) == (
        "HYDRATE",
        ("hydrate", "components", 0, "name"),
        "not_text",
    )


def test_field_error_is_a_value_error():
    assert issubclass(FieldError, ValueError)
    assert toughio.hydrate.FieldError is FieldError
