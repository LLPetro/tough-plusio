"""Optional local acceptance data; solver files are never fetched or redistributed."""

import os
import pathlib

import pytest

import toughio


GATES = {
    "hydrate_samples": "TOUGH_HYDRATE_REFERENCE_DIR",
    "hydrate_outputs": "TOUGH_HYDRATE_OUTPUT_DIR",
}


def pytest_configure(config):
    for marker, variable in GATES.items():
        config.addinivalue_line("markers", f"{marker}: requires ${variable}")


@pytest.fixture(autouse=True)
def require_local_acceptance_data(request):
    for marker, variable in GATES.items():
        if request.node.get_closest_marker(marker) and not os.environ.get(variable):
            pytest.skip(f"Set {variable} to run local acceptance tests")


MEMORY = {
    "title": "Synthetic T+H deck",
    "eos": "HYDRATE-EQUILIBRIUM",
    "n_component": 2,
    "n_phase": 4,
    "do_diffusion": False,
    "label_length": 5,
    "memory": {
        "n_equation": 3,
        "coordinate_system": "Cartesian",
        "max_n_elements": 15,
        "max_n_connections": 30,
        "active_connections_only": False,
        "boundaries_in_matrix": False,
        "max_n_sources": 2,
        "max_n_media": 2,
        "element_by_element_properties": False,
        "porosity_permeability_dependence": False,
        "scaled_capillary_pressure": False,
        "tortuosity_method": "Saturation",
        "coupled_geochemistry": False,
        "geochemistry_update": "Continuous",
        "coupled_geomechanics": False,
        "geomechanics_code": " ",
        "geomechanics_update": "Continuous",
        "n_geomechanics_parameters": 0,
    },
    "end": "ENDCY",
}


@pytest.fixture
def deck():
    """Minimal T+H parameters (TITLE, MEMORY, END) updated with keyword arguments."""
    return lambda **kwargs: {**MEMORY, **kwargs}


@pytest.fixture
def write_read(tmp_path):
    def _write_read(parameters, writer_kws=None, reader_kws=None):
        path = tmp_path / "INFILE"
        toughio.write_input(
            path, parameters, file_format="tough+hydrate", **(writer_kws or {})
        )
        return toughio.read_input(
            path, file_format="tough+hydrate", **(reader_kws or {})
        )

    return _write_read


@pytest.fixture
def samples():
    return pathlib.Path(os.environ.get("TOUGH_HYDRATE_REFERENCE_DIR", "."))


@pytest.fixture
def outputs():
    return pathlib.Path(os.environ.get("TOUGH_HYDRATE_OUTPUT_DIR", "."))
