"""A broken deck fails with a ReadError naming the block, never reads on forever."""

import io

import pytest

import toughio
from toughio._io.input.tough_hydrate._helpers import (
    Lines,
    block_start,
    read_namelist,
    read_values,
    split_record,
)


MEMORY = """MEMORY
'HYDRATE-EQUILIBRIUM'
   2     3    4    .FALSE.
'Cartesian'   15   30    5  .FALSE.  .FALSE.
   2
   2
.FALSE.  .FALSE.  .FALSE.  'Saturation'
.FALSE.  'Continuous'
.FALSE.  ' '  'Continuous'  0
"""
START = """START----1----*----2----*----3----*----4----*----5----*----6----*----7----*----8
----*----1 MOP: 123456789*123456789*1234 ---*----5----*----6----*----7----*----8
"""


def hydrate(n_specific_heat="1"):
    return f"""HYDRATE--1----*----2----*----3----*----4----*----5----*----6----*----7----*----8
     1                       ! HCom%NCom
'CH4'  6.0d0 1.00d00         ! Name, hydration number, mole fraction
     1                       ! Number of coefficients in thermal conductivity polynomial
  4.5e-1                     ! Coefficients in the thermal conductivity polynomial
{n_specific_heat:>6}                      ! Number of coefficients in the specific heat polynomial
  2.1e03                     ! Coefficients in the specific heat polynomial
     1                       ! Number of coefficients in density polynomial
  9.2e02                     ! Coefficients in the density polynomial
.FALSE.                      ! inhibitor_present
2                            ! F_EqOption
'EQUILIBRIUM'                ! Type of dissociation
"""


def read(text):
    return toughio.read_input(io.StringIO(text), file_format="tough+hydrate")


def test_complete_deck_reads():
    out = read("Title\n" + MEMORY + hydrate() + START + "ENDCY\n")
    assert out["hydrate"]["specific_heat"] == [2100.0]
    assert out["start"]


def test_count_beyond_the_values_stops_at_the_next_block():
    # 2100 coefficients announced: the values run out at START, whose MOP ruler
    # '123456789*123456789*1234' once expanded to 123456789 items
    with pytest.raises(toughio.core.ReadError) as e:
        read("Title\n" + MEMORY + hydrate("2100") + START + "ENDCY\n")

    message = str(e.value)
    assert "(HYDRATE block)" in message
    assert "value 7 of 2100 missing before the START block" in message
    assert e.value.block == "HYDRATE"
    assert e.value.reason == "value 7 of 2100 missing before the START block"


def test_count_beyond_the_values_stops_at_the_end_of_the_file():
    with pytest.raises(toughio.core.ReadError, match="before the end of the file"):
        read("Title\n" + MEMORY + hydrate("2100"))


def test_deleted_record_shifts_a_value_into_a_count():
    # the thermal conductivity coefficient deleted: 2.1e03 is read as a count
    text = "".join(x for x in hydrate().splitlines(True) if "4.5e-1" not in x)
    with pytest.raises(toughio.core.ReadError, match="invalid count 2100.0"):
        read("Title\n" + MEMORY + text + START + "ENDCY\n")


def test_missing_record_before_the_next_block():
    memory = MEMORY.replace(".FALSE.  ' '  'Continuous'  0\n", "")
    with pytest.raises(toughio.core.ReadError) as e:
        read("Title\n" + memory + hydrate() + "ENDCY\n")

    assert e.value.block == "MEMORY"
    assert "record missing before the HYDRATE block" in str(e.value)


def test_unquoted_character_values_are_not_blocks():
    memory = MEMORY.replace("'HYDRATE-EQUILIBRIUM'", "HYDRATE-EQUILIBRIUM")
    out = read("Title\n" + memory)
    assert out["eos"] == "HYDRATE-EQUILIBRIUM"
    assert block_start("HYDRATE-EQUILIBRIUM") is None
    assert block_start("HYDRATE--1----*") == "HYDRATE"
    assert block_start("ROCKS----1----*----2") == "ROCKS"
    assert block_start("MEMORY") == "MEMORY"
    assert block_start("ELEME ---    33") == "ELEME"
    assert block_start("MESHMAKER1----*") == "MESHMAKER"
    assert block_start("rocks----1") is None


def test_repeats():
    assert split_record("3*1.5 2*") == ["1.5", "1.5", "1.5", None, None]
    # not a repeat: the constant has a '*'
    assert split_record("123456789*123456789*1234") == ["123456789*123456789*1234"]
    with pytest.raises(ValueError, match="repeat count"):
        split_record("99999999*0.0")


def test_read_values_errors():
    with pytest.raises(ValueError, match="invalid count"):
        read_values(Lines("1\n"), -1)
    with pytest.raises(ValueError, match="invalid count"):
        read_values(Lines("1\n"), True)
    with pytest.raises(ValueError, match="value 3 of 3 missing before the end"):
        read_values(Lines("1\n\n2\n\n"), 3)
    assert read_values(Lines("1\n\n2 3\n"), 3) == [1, 2, 3]


def test_namelist_errors():
    with pytest.raises(
        ValueError, match="not closed by '/' before the end of the file"
    ):
        read_namelist(Lines("&Group a = 1,\n b = 2,\n"))
    with pytest.raises(ValueError, match="NAMELIST group missing before the ROCKS"):
        read_namelist(Lines("\nROCKS----1\n"))
    with pytest.raises(ValueError, match="NAMELIST group missing before the end"):
        read_namelist(Lines("\n\n"))


def test_times_count_beyond_the_values():
    text = "Title\n" + MEMORY + "TIMES----1\n    5\n1.0000E+02\nENDCY\n"
    with pytest.raises(toughio.core.ReadError) as e:
        read(text)

    assert e.value.block == "TIMES"
    assert "time 2 of 5 missing before the ENDCY block" in str(e.value)


def test_end_of_file_inside_a_tough_block():
    # a reader of the TOUGH blocks that meets the end of the file
    with pytest.raises(toughio.core.ReadError, match=r"\(\w+ block\): \S"):
        read("Title\n" + MEMORY + "PARAM----1\n")
