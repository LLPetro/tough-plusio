import numpy as np
import pytest

import toughio
from toughio import hydrate


def test_mesh_parameters_dirichlet_and_activity():
    mesh = toughio.meshmaker.structured_grid([1.0] * 4, [1.0], [1.0])
    reference = mesh.to_tough()
    mesh.dirichlet = [True, False, False, False]
    hydrate.set_activity(mesh, np.array([False, False, False, True]), "V01")

    parameters = hydrate.mesh_parameters(mesh)
    labels = list(parameters["elements"])

    assert parameters["elements"][labels[0]]["activity"] == "I"
    assert parameters["elements"][labels[3]]["activity"] == "V01"
    assert (
        parameters["elements"][labels[0]]["volume"]
        == reference["elements"][labels[0]]["volume"]
    )
    assert parameters["connections"] == reference["connections"]
    assert np.asarray(mesh.dirichlet).tolist() == [True, False, False, False]


def test_mesh_parameters_single_cell():
    mesh = toughio.meshmaker.structured_grid([1.0], [1.0], [1.0])
    parameters = hydrate.mesh_parameters(mesh)
    assert len(parameters["elements"]) == 1 and not parameters["connections"]


def test_set_activity_rejects_bad_flags():
    mesh = toughio.meshmaker.structured_grid([1.0, 1.0], [1.0], [1.0])
    with pytest.raises(ValueError):
        hydrate.set_activity(mesh, [True, False], "X01")


def test_validate():
    parameters = {
        "title": "t",
        "eos": "HYDRATE-KINETIC",
        "n_component": 3,
        "n_phase": 4,
        "label_length": 8,
        "do_diffusion": True,
        "memory": {"n_equation": 4, "max_n_media": 1},
        "hydrate": {"reaction_type": "EQUILIBRIUM"},
        "options": {},
        "rocks": {
            "SAND1": {"density": 2600.0},
            "DIRT1": {"initial_condition": [1.0, 2.0]},
        },
        "elements": {"AAAAA001": {"material": "CLAY", "activity": "X"}, "AAAAA002": {}},
        "default": {"phase_state": "Foo"},
    }
    errors = hydrate.validate(parameters)
    assert any("reaction modes" in e for e in errors)
    assert any("max_n_media" in e for e in errors)
    assert any("unknown material" in e for e in errors)
    assert any("invalid activity" in e for e in errors)
    assert any("phase_state" in e for e in errors)
    assert any("primary variables" in e for e in errors)
    assert any("not defined in ROCKS" in e for e in errors)
    assert any("first 5 characters" in e for e in errors)
    assert any("DIFFUSION block" in e for e in errors)


def _diffusion_deck(**kwargs):
    """Minimal deck whose DIFFUSION phases follow the solver component order."""
    parameters = {
        "title": "t",
        "eos": "HYDRATE-EQUILIBRIUM",
        "n_component": 2,
        "n_phase": 4,
        "do_diffusion": True,
        "label_length": 5,
        "memory": {"n_equation": 3, "max_n_media": 1},
        "hydrate": {"reaction_type": "EQUILIBRIUM"},
        "options": {},
        "rocks": {"SAND1": {"density": 2600.0}},
        "multiphase_diffusion": {
            "phases": [
                {
                    "phase": "Aqueous",
                    "phase_number": 2,
                    "component": ["H2O", "CH4"],
                    "component_number": [1, 2],
                    "component_diffusivity": [1.0e-9, 1.0e-9],
                },
                {
                    "phase": "Gas",
                    "phase_number": 1,
                    "component": ["H2O", "CH4"],
                    "component_number": [1, 2],
                    "component_diffusivity": [1.0e-5, 1.0e-5],
                },
            ]
        },
    }
    parameters.update(kwargs)
    return parameters


def _phases(parameters):
    return parameters["multiphase_diffusion"]["phases"]


def test_diffusion_solver_order_validates():
    assert not [e for e in hydrate.validate(_diffusion_deck()) if "component" in e]


def test_diffusion_manual_order_rejected():
    # The manual (p. 56) numbers CH4 = 1, H2O = 2; the solver disagrees.
    parameters = _diffusion_deck()
    for phase in _phases(parameters):
        phase["component"] = ["CH4", "H2O"]

    errors = hydrate.validate(parameters)
    assert any("component(1) = 'CH4'" in e for e in errors), errors
    assert any("position 1 belongs to 'H2O'" in e for e in errors), errors


def test_diffusion_kinetic_and_inhibitor_variants():
    # Kinetic: hydrate is the third component.
    parameters = _diffusion_deck(
        eos="HYDRATE-KINETIC",
        n_component=3,
        hydrate={"reaction_type": "KINETIC"},
    )
    for phase in _phases(parameters):
        phase["component"] = ["H2O", "CH4", "Hydrate"]
        phase["component_number"] = [1, 2, 3]
    assert not [e for e in hydrate.validate(parameters) if "component" in e]

    # Equilibrium deck must not claim a hydrate diffusivity slot.
    parameters["eos"] = "HYDRATE-EQUILIBRIUM"
    parameters["hydrate"] = {"reaction_type": "EQUILIBRIUM"}
    errors = hydrate.validate(parameters)
    assert any("position 3" in e for e in errors), errors

    # Inhibitor: NaCl takes the last slot whatever n_component says before it.
    parameters = _diffusion_deck(n_component=3)
    for phase in _phases(parameters):
        phase["component"] = ["H2O", "CH4", "NaCl"]
        phase["component_number"] = [1, 2, 3]
    assert not [e for e in hydrate.validate(parameters) if "component" in e]


def test_diffusion_component_number_must_equal_position():
    parameters = _diffusion_deck()
    _phases(parameters)[0]["component_number"] = [2, 1]

    errors = hydrate.validate(parameters)
    assert any("component_number(1) = 2" in e for e in errors), errors


def test_diffusion_indexed_and_sparse_forms():
    # Round-tripped decks keep NAMELIST arrays as {index: value} maps.
    parameters = _diffusion_deck()
    for phase in _phases(parameters):
        phase["component"] = {1: "H2O", 2: "CH4"}
        phase["component_number"] = {1: 1, 2: 2}
        phase["component_diffusivity"] = {1: 1.0e-9, 2: 1.0e-9}
    assert not [e for e in hydrate.validate(parameters) if "component" in e]

    _phases(parameters)[1]["component"] = {1: "CH4", 2: "H2O"}
    errors = hydrate.validate(parameters)
    assert any("phases[1]" in e for e in errors), errors


def test_diffusion_missing_names():
    parameters = _diffusion_deck()
    _phases(parameters)[0]["component"] = []

    errors = hydrate.validate(parameters)
    assert any("missing component names" in e for e in errors), errors
