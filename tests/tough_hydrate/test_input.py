import io

import pytest

import toughio
from toughio import hydrate
from toughio._io.input import _helpers as input_helpers


def test_registration_is_additive():
    assert "tough+hydrate" in input_helpers._reader_map
    for name in ("tough", "tough3", "tough4", "json"):
        assert (
            input_helpers._reader_map[name].__module__.split(".")[3] != "tough_hydrate"
        )
    assert input_helpers._filename_to_file_format["INFILE"] == "tough"


def test_memory(deck, write_read):
    parameters = deck()
    assert write_read(parameters) == parameters


@pytest.mark.parametrize("kinetic", [False, True])
def test_hydrate(deck, write_read, kinetic):
    hydrate = {
        "components": [{"name": "CH4", "hydration_number": 6.0, "mole_fraction": 1.0}],
        "thermal_conductivity": [0.45],
        "specific_heat": [1200.5, 11.96],
        "density": [] if kinetic else [920.0],
        "equation_option": 2,
        "reaction_type": "KINETIC" if kinetic else "EQUILIBRIUM",
    }
    if kinetic:
        hydrate["inhibitor"] = {
            "max_temperature_shift": 2.0,
            "mole_fraction_at_max_shift": 0.01335,
            "molecular_weight": 58.448,
            "density": 2600.0,
            "dissolution_enthalpy": 66479.0,
            "specific_heat": [41.293, 0.033607, -1.3927e-05],
        }
        hydrate["kinetics"] = {
            "activation_energy": 81000.0,
            "rate_constant": 36000.0,
            "area_factor": 1.0,
        }

    parameters = deck(hydrate=hydrate)
    assert write_read(parameters)["hydrate"] == hydrate


@pytest.mark.parametrize("nad", [0, 1, 2, 5, 6, 8])
def test_rocks(deck, write_read, nad):
    rock = {
        "density": 2600.0,
        "porosity": 0.3,
        "permeability": [1.0e-13, 2.0e-13, 3.0e-13],
        "conductivity": 3.1,
        "specific_heat": 1000.0,
        "grain_radius": 1.0e-4,
    }
    if nad >= 1:
        rock.update(
            {
                "compressibility": 1.0e-8,
                "conductivity_dry": 0.5,
                "critical_saturation": 0.05,
                "permeability_exponent": 3.0,
                "porosity_zero_stress": 0.25,
            }
        )
    if nad >= 2:
        rock["relative_permeability"] = {"id": 9, "parameters": [0.12, 0.02, 3.0]}
        rock["capillarity"] = {"id": 7, "parameters": [0.45, 0.11, 8.0e-5, 1.0e6, 1.0]}
    if nad == 5:
        rock["porosity_polynomial"] = {
            "order": 2,
            "coefficients": [1.0, 1.0e-9, 2.5e-18],
        }
    if nad == 6:
        rock["cementing_compressibility"] = [1.0e-10, 0.6, 1.0e-8, 0.1, 0.015]
    if nad == 8:
        rock["slippage_turbulence"] = {
            "mediumklinkflow_f": False,
            "mediumknudsenflow_f": False,
        }

    parameters = deck(
        rocks={"SAND1": rock, "BOUND": {"density": 2600.0, "porosity": 0.0}}
    )
    assert write_read(parameters)["rocks"] == parameters["rocks"]


def test_param(deck, write_read):
    parameters = deck(
        start=True,
        options={
            "n_iteration": 3,
            "verbosity": 1,
            "n_cycle": 80,
            "n_cycle_print": 2,
            "gas_diffusion_coefficient": 1.0e-5,
            "temperature_dependence_gas": 1.8,
            "n_cycle_save": 100,
            "n_cycle_time_series": 1,
            "t_max": 864000.0,
            "t_steps": [1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0, 128.0, 256.0],
            "t_step_max": 8.64e6,
            "track_element": "A00 1",
            "gravity": 9.806,
            "eps1": 1.0e-5,
            "eps2": 1.0,
            "derivative_factor": 1.0e-8,
            "w_implicitness": 1.0,
            "p_overshoot": 1.0e-5,
        },
        extra_options={1: 1, 8: 4, 16: 5, 19: 8, 24: 0},
        default={"phase_state": "AqH", "initial_condition": [6.0e6, 0.5, 7.2]},
    )
    assert write_read(parameters) == parameters


def test_solvr_times(deck, write_read):
    parameters = deck(
        solver={
            "method": 3,
            "z_precond": "Z1",
            "o_precond": "O0",
            "rel_iter_max": 0.1,
            "eps": 1.0e-8,
        },
        times=[1.0, 10.0, 100.0, 1000.0, 1.0e4, 1.0e5, 1.0e6, 1.0e7, 1.0e8],
        times_options={"max_n_times": 12, "t_step_max": 3600.0, "t_increment": 1.0e8},
    )
    assert write_read(parameters) == parameters


@pytest.mark.parametrize("label_length", [5, 8])
def test_mesh_and_initial_conditions(deck, write_read, label_length):
    names = (
        ["A00 0", "A00 1", "A00 2"]
        if label_length == 5
        else ["AAAAA001", "AAAAA002", "AAAAA003"]
    )
    elements = {
        names[0]: {
            "material": 1,
            "volume": 1.0e-3,
            "heat_exchange_area": 4.0e-3,
            "center": [5.0e-4, -0.5, -0.5],
            "activity": "I",
        },
        names[1]: {"material": "SAND1", "volume": 0.1, "center": [0.051, -0.5, -0.5]},
        names[2]: {"material": 1, "volume": 0.1, "center": [0.151, -0.5, -0.5]},
    }
    connections = {
        names[0] + names[1]: {
            "permeability_direction": 1,
            "nodal_distances": [5.0e-4, 0.05],
            "interface_area": 1.0,
        },
        names[1] + names[2]: {
            "permeability_direction": 1,
            "nodal_distances": [0.05, 0.05],
            "interface_area": 1.0,
            "gravity_cosine_angle": -1.0,
        },
    }
    initial_conditions = {
        names[0]: {"porosity": 0.3, "phase_state": "Aqu", "values": [2.7e6, 0.0, 1.0]},
        names[1]: {
            "phase_state": "AqH",
            "permeability": [1.0e-13, 1.0e-13, 2.0e-13],
            "values": [6.0e6, 0.5, 7.2, 0.01, 0.2],
        },
    }
    parameters = deck(
        label_length=label_length,
        rocks={
            "SAND1": {
                "density": 2600.0,
                "phase_state": "AqH",
                "initial_condition": [9.11e6, 0.5, 12.0],
            }
        },
        elements=elements,
        connections=connections,
        initial_conditions=initial_conditions,
        continuation_run={"timesteps_to_this_point": 10, "time_to_this_point": 3600.0},
    )
    out = write_read(parameters)

    for label, element in elements.items():
        assert {
            k: v for k, v in out["elements"][label].items() if k in element
        } == element
    for label, connection in connections.items():
        assert {
            k: v for k, v in out["connections"][label].items() if k in connection
        } == connection
    assert out["initial_conditions"] == initial_conditions
    assert out["rocks"] == parameters["rocks"]
    assert out["continuation_run"] == parameters["continuation_run"]


def test_gener(deck, write_read):
    generators = [
        {
            "label": "A00 0",
            "name": "Pro01",
            "type": "COM1",
            "rates": -0.3,
            "well_response": "ADJU",
            "pressure_limit": 2.0e6,
            "rate_step_change": 0.1,
            "rate_limit": 0.01,
        },
        {
            "label": "A00 1",
            "name": "Het01",
            "type": "HEAT",
            "times": [0.0, 10.0, 100.0, 1000.0, 1.0e4],
            "rates": [1.0, 2.0, 3.0, 4.0, 5.0],
            "specific_enthalpy": [1.0e5, 1.0e5, 2.0e5, 2.0e5, 3.0e5],
        },
    ]
    out = write_read(deck(generators=generators))["generators"]

    for generator, read in zip(generators, out):
        assert {k: v for k, v in read.items() if k in generator} == generator


def test_namelist_blocks(deck, write_read):
    parameters = deck(
        multiphase_diffusion={
            "gas_diffusivity_equation_exponent": 1.8,
            "full_multiphase_diffusion": False,
            "phases": [
                {
                    "phase": "Aqueous",
                    "phase_number": 2,
                    "component": {1: "CH4", 2: "H2O"},
                    "component_diffusivity": {1: 1.0e-9, 2: 1.0e-9},
                },
                {
                    "phase": "Gas",
                    "phase_number": 1,
                    "component": {1: "CH4", 2: "H2O"},
                    "component_diffusivity": {1: 1.0e-5, 2: 1.0e-5},
                },
            ],
        },
        transient_boundaries=[
            {
                "boundary_number": 1,
                "boundary_name": "V01",
                "pv_numbers": [3, 1],
                "data_form": "Table",
                "read_by_row_or_by_col": "row",
                "rowcolnum_to_primvarnum": [3, -1, 0, 1],
                "units_of_primvar": {0: "sec", 1: "Pa", 3: "C"},
                "read_format": "*",
                "comment": "Temperature, dummy, time, pressure (it's a comment)",
                "table": [[2.0, -1222.34, 0.0, 3.5e6], [1.5, -1480.0, 4.32e5, 3.0e6]],
            }
        ],
        subdomains=[
            {
                "subdomain_name": "SD1",
                "regions": [
                    {
                        "definition_mode": "Sequence",
                        "number_of_elements": 3,
                        "first_element_number": 1,
                        "element_sequence_stride": 1,
                    },
                    {
                        "definition_mode": "NameList",
                        "format_to_read_data": "*",
                        "elements": ["A00 1", "A00 2"],
                    },
                    {
                        "definition_mode": "NumberList",
                        "format_to_read_data": "*",
                        "elements": [4, 5, 6],
                    },
                ],
            }
        ],
        interfaces=[
            {
                "interface_name": "Int_1",
                "sign_of_flow_direction": "DIR",
                "surfaces": [
                    {
                        "definition_mode": "NameList",
                        "format_to_read_data": "*",
                        "connections": ["A00 0A00 1"],
                    }
                ],
            }
        ],
        ss_groups=[
            {
                "ssgroup_name": "Wells",
                "definition_mode": "NameList",
                "format_to_read_data": "*",
                "sources": ["Pro01", "Het01"],
            }
        ],
        extended_initial_conditions=[
            {
                "type": "GEOMETRY",
                "xmin": 0.0,
                "xmax": 1.0,
                "ymin": -1.0,
                "ymax": 0.0,
                "zmin": -1.0,
                "zmax": 0.0,
                "phase_state": "AqH",
                "values": [5.0e6, 0.5, 5.0],
            },
            {
                "type": "GEOMETRY",
                "rmin": 0.0,
                "rmax": 1.0,
                "zmin": -1.0,
                "zmax": 0.0,
                "phase_state": "AqH",
                "values": [5.0e6, 0.5, 5.0],
            },
            {
                "type": "SEQUENCE",
                "first_element": 1,
                "last_element": 3,
                "stride": 1,
                "phase_state": "Aqu",
                "values": [5.0e6, 0.0, 5.0],
            },
            {
                "type": "LIST",
                "n_per_row": 2,
                "elements": [1, 2, 3],
                "phase_state": "Gas",
                "values": [1.0e5, 0.0, 5.0],
            },
            {
                "type": "COLUMN",
                "first_element": 1,
                "n_elements": 4,
                "stride": 1,
                "states": [
                    {"phase_state": "AqH", "values": [5.0e6, 0.5, 5.0]},
                    {"phase_state": "AqH", "values": [5.1e6, 0.5, 5.1]},
                ],
            },
        ],
    )
    assert write_read(parameters) == parameters


@pytest.mark.parametrize("end", ["ENDCY", "ENDFI"])
def test_end(deck, write_read, end):
    assert write_read(deck(end=end))["end"] == end


def test_separate_files(deck, tmp_path):
    parameters = deck(
        label_length=8,
        elements={
            "AAAAA001": {"material": 1, "volume": 1.0},
            "AAAAA002": {"material": 1, "volume": 1.0},
        },
        connections={
            "AAAAA001AAAAA002": {
                "permeability_direction": 3,
                "nodal_distances": [0.5, 0.5],
                "interface_area": 1.0,
            }
        },
        initial_conditions={
            "AAAAA001": {"porosity": 0.3, "values": [1.0e6, 0.0, 10.0]}
        },
        generators=[
            {"label": "AAAAA001", "name": "Pro01", "type": "MASS", "rates": -1.0}
        ],
    )
    for block, keys in [
        ("MESH", {"elements", "connections"}),
        ("INCON", {"initial_conditions"}),
        ("GENER", {"generators"}),
    ]:
        path = tmp_path / block
        toughio.write_input(path, parameters, file_format="tough+hydrate", blocks=block)
        out = toughio.read_input(path, file_format="tough+hydrate", label_length=8)
        assert keys <= set(out) and "title" not in out
        assert list(out[sorted(keys)[0]]) == list(parameters[sorted(keys)[0]])


def test_solver_written_cross_references():
    text = """MEMORY
'HYDRATE-EQUILIBRIUM'
2 3 4 .FALSE.
'Cartesian' 2 1 5 .FALSE. .FALSE.
1
1
.FALSE. .FALSE. .FALSE. 'Saturation'
.FALSE. 'Continuous'
.FALSE. ' ' 'Continuous' 0
ELEME ---     2    4    0   30   0.00000   500.100
A00 0              10.1000E+000.4000E+00          0.5100E-01-.5000E+00-.5000E+00
A00 1              10.1000E+000.4000E+00          0.1510E+00-.5000E+00-.5000E+00

CONNE
A00 0A00 1                   10.5000E-010.5000E-010.1000E+01
+++
    1    2
GENER
A00 0Pro01                         COM1  -1.00E-00
+++
    1
TIMES----1
    1
1.0000E+02

ENDCY
"""
    out = toughio.read_input(io.StringIO(text), file_format="tough+hydrate")
    assert list(out["connections"]) == ["A00 0A00 1"]
    assert [g["name"] for g in out["generators"]] == ["Pro01"]
    assert out["times"] == [100.0]
    assert "title" not in out


def test_title_and_free_records():
    title = "T" * 132
    text = f"""{title}
MEMORY
'HYDRATE-EQUILIBRIUM'   ! eos, with a comment
   2,  3,  4,  .FALSE.
'Cartesian'   15   30    5  .FALSE.  .FALSE.   ! comment, with commas
   2
   2
.FALSE.  .FALSE.  .FALSE.  'Saturation'
.FALSE.  'Continuous'
.FALSE.  'a, b'  'Continuous'  0
HYDRATE--1----*-Modified data-*----5
     1
'CH4'  6.0d0 1.00d00
     1
  4.5e-1
     1
  2.1e03
     0
.FALSE.
2
'EQUILIBRIUM'
ENDCY
"""
    out = toughio.read_input(io.StringIO(text), file_format="tough+hydrate")
    assert out["title"] == title
    assert out["memory"]["geomechanics_code"] == "a, b"
    assert out["n_phase"] == 4
    assert out["hydrate"]["components"][0]["hydration_number"] == 6.0


def test_unsupported_block():
    with pytest.raises(toughio.core.ReadError):
        toughio.read_input(
            io.StringIO("Title\nMESHMAKER1----*\nXYZ\nENDCY\n"),
            file_format="tough+hydrate",
        )


@pytest.mark.hydrate_samples
def test_official_decks(samples, tmp_path):
    decks = sorted(p for p in samples.glob("Test_*") if "." not in p.name)
    assert len(decks) == 15

    for path in decks:
        parameters = toughio.read_input(path, file_format="tough+hydrate")
        assert {"title", "eos", "rocks", "options", "connections"} <= set(parameters)
        toughio.write_input(
            tmp_path / path.name, parameters, file_format="tough+hydrate"
        )
        assert (
            toughio.read_input(tmp_path / path.name, file_format="tough+hydrate")
            == parameters
        )
        assert hydrate.validate(parameters) == [], path.name
