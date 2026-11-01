from __future__ import annotations

from .._helpers import HydrateBlock, located, read_values, write_values


# MEMORY.2 to MEMORY.9; keys in TOP are stored at the top level of the parameters
RECORDS = (
    ("eos",),
    ("n_component", "n_equation", "n_phase", "do_diffusion"),
    (
        "coordinate_system",
        "max_n_elements",
        "max_n_connections",
        "label_length",
        "active_connections_only",
        "boundaries_in_matrix",
    ),
    ("max_n_sources",),
    ("max_n_media",),
    (
        "element_by_element_properties",
        "porosity_permeability_dependence",
        "scaled_capillary_pressure",
        "tortuosity_method",
    ),
    ("coupled_geochemistry", "geochemistry_update"),
    (
        "coupled_geomechanics",
        "geomechanics_code",
        "geomechanics_update",
        "n_geomechanics_parameters",
    ),
)
TOP = {"eos", "n_component", "n_phase", "do_diffusion", "label_length"}
# Fortran type of each variable (docs/toughplus/schema/canonical-fields.md)
KINDS = {
    "eos": "text",
    "n_component": "integer",
    "n_equation": "integer",
    "n_phase": "integer",
    "do_diffusion": "logical",
    "coordinate_system": "text",
    "max_n_elements": "integer",
    "max_n_connections": "integer",
    "label_length": "integer",
    "active_connections_only": "logical",
    "boundaries_in_matrix": "logical",
    "max_n_sources": "integer",
    "max_n_media": "integer",
    "element_by_element_properties": "logical",
    "porosity_permeability_dependence": "logical",
    "scaled_capillary_pressure": "logical",
    "tortuosity_method": "text",
    "coupled_geochemistry": "logical",
    "geochemistry_update": "text",
    "coupled_geomechanics": "logical",
    "geomechanics_code": "text",
    "geomechanics_update": "text",
    "n_geomechanics_parameters": "integer",
}


class MEMORY(HydrateBlock):
    name = "MEMORY"

    def _read(self, f, *args, **kwargs) -> dict:
        """Read MEMORY block data."""
        memory = {}

        for keys in RECORDS:
            memory.update(zip(keys, read_values(f)))

        data = {k: memory.pop(k) for k in TOP if k in memory}
        data["memory"] = self.prune_values(memory)

        return self.prune_values(data)

    def _write(self, parameters: dict, *args, **kwargs) -> list[str]:
        """Write MEMORY block data."""
        memory = {**parameters.get("memory", {}), **parameters}
        if memory.get("label_length") is None and parameters.get("elements"):
            memory["label_length"] = max(len(k) for k in parameters["elements"])

        out = []
        for i, keys in enumerate(RECORDS):
            with located(record=f"MEMORY.{i + 2}"):
                out += write_values(
                    [memory.get(k) for k in keys],
                    kinds=[KINDS[k] for k in keys],
                    names=[(k,) if k in TOP else ("memory", k) for k in keys],
                )

        return out

    def _write_header(self) -> str:
        return "MEMORY\n"
