from __future__ import annotations

from collections.abc import Sequence
from typing import Any


STATES = {
    "Gas",
    "Aqu",
    "AqG",
    "IcG",
    "GsH",
    "AqH",
    "AqI",
    "IcH",
    "AGH",
    "AIG",
    "AIH",
    "IGH",
    "QuP",
}
EOS = {"HYDRATE-EQUILIBRIUM", "HYDRATE-KINETIC"}

# DIFFUSION component numbering. The T+H v1.5 manual (p. 56) prints CH4 = 1 and
# H2O = 2, but the solver does not read the names or numbers: it takes
# component_diffusivity(i) by position i in its own internal order
#     H2O, CH4, hydrate (kinetic only), inhibitor (NaCl, last),
# and only echoes the names back. Verified by running the solver on otherwise
# identical two-cell decks: naming position 1 "H2O" lets CH4 diffuse, while the
# manual order (position 1 "CH4") leaves CH4 essentially immobile. Decks must
# therefore number and name components in the solver order, which validate()
# enforces.
SOLVER_COMPONENTS = ("H2O", "CH4", "Hydrate", "NaCl")


def _as_sequence(value: Any) -> list:
    """NAMELIST array as read: a list, a scalar, or a sparse {index: value}."""
    if value is None:
        return []
    if isinstance(value, dict):
        return [value[k] for k in sorted(value)]
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _expected_components(parameters: dict) -> list[str]:
    """
    Solver component order for this deck: H2O, CH4, then Hydrate only when
    kinetic, then NaCl (inhibitor) last; truncated to n_component after the
    mode filter (equilibrium + inhibitor skips the hydrate slot entirely).
    """
    kinetic = (
        "KINETIC" in str(parameters.get("eos", "")).upper()
        or "KINETIC"
        in str((parameters.get("hydrate") or {}).get("reaction_type", "")).upper()
    )
    n = parameters.get("n_component") or len(SOLVER_COMPONENTS)
    return [name for name in SOLVER_COMPONENTS if kinetic or name != "Hydrate"][:n]


def _check_diffusion_components(parameters: dict, errors: list) -> None:
    """DIFFUSION phases must list components in the solver's internal order."""
    diffusion = parameters.get("multiphase_diffusion") or {}
    expected = _expected_components(parameters)

    for i, phase in enumerate(diffusion.get("phases") or []):
        where = f"multiphase_diffusion phases[{i}] ({phase.get('phase', '?')})"
        names = [str(v).strip() for v in _as_sequence(phase.get("component"))]
        numbers = _as_sequence(phase.get("component_number"))

        if not names:
            errors.append(f"{where}: missing component names")
            continue

        for j, (name, number) in enumerate(zip(names, numbers), start=1):
            if j <= len(expected) and name != expected[j - 1]:
                errors.append(
                    f"{where}: component({j}) = '{name}': the solver reads "
                    f"component_diffusivity by position in the order {expected}; "
                    f"position {j} belongs to '{expected[j - 1]}'"
                )
            if number != j:
                errors.append(
                    f"{where}: component_number({j}) = {number!r}: must equal the "
                    "position (the solver ignores the value; keep it consistent)"
                )


def validate(parameters: dict) -> list[str]:
    """
    Check T+H input parameters against the rules of the T+H v1.5 manual.

    This function is optional: reading and writing never validate.

    Parameters
    ----------
    parameters : dict
        Parameters as returned by ``toughio.read_input(..., file_format="tough+hydrate")``.

    Returns
    -------
    list[str]
        Error messages (empty if no problem is found).

    """
    errors = []
    memory = parameters.get("memory", {})
    rocks = parameters.get("rocks", {})
    elements = parameters.get("elements", {})

    def check(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    for key in (
        "title",
        "eos",
        "n_component",
        "n_phase",
        "label_length",
        "hydrate",
        "options",
    ):
        check(key in parameters, f"missing '{key}'")
    check(memory.get("n_equation") is not None, "missing memory 'n_equation'")
    check(bool(rocks), "missing 'rocks'")

    eos = str(parameters.get("eos", "")).upper()
    check(not eos or eos in EOS, f"unknown eos '{parameters.get('eos')}'")
    check(parameters.get("label_length") in {None, 5, 8}, "label_length must be 5 or 8")

    check(
        not parameters.get("do_diffusion")
        or bool(parameters.get("multiphase_diffusion")),
        "do_diffusion requires a DIFFUSION block (the solver otherwise gives irreproducible runs)",
    )

    if parameters.get("multiphase_diffusion"):
        _check_diffusion_components(parameters, errors)

    reaction = str(parameters.get("hydrate", {}).get("reaction_type", "")).upper()
    check(
        not (eos and reaction) or ("KINETIC" in eos) == ("KINETIC" in reaction),
        "eos and hydrate 'reaction_type' select different reaction modes",
    )

    for key, limit in (
        ("rocks", "max_n_media"),
        ("elements", "max_n_elements"),
        ("connections", "max_n_connections"),
        ("generators", "max_n_sources"),
    ):
        n, n_max = len(parameters.get(key) or []), memory.get(limit)
        check(
            n_max is None or n <= n_max, f"{n} {key} exceed memory '{limit}' ({n_max})"
        )

    n_equation = memory.get("n_equation")
    conditions = [("default", parameters.get("default", {}))]
    conditions += [(f"rocks['{k}']", v) for k, v in rocks.items()]
    conditions += [
        (f"initial_conditions['{k}']", v)
        for k, v in parameters.get("initial_conditions", {}).items()
    ]
    for where, data in conditions:
        values = data.get("initial_condition", data.get("values"))
        if values is not None and n_equation is not None:
            check(
                n_equation <= len(values) <= 6,
                f"{where}: {len(values)} primary variables, expected {n_equation} (at most 6)",
            )
        state = data.get("phase_state")
        check(
            state is None or state in STATES, f"{where}: unknown phase_state '{state}'"
        )

    for name, rock in rocks.items():
        check(
            bool(set(rock) - {"initial_condition", "phase_state"}),
            f"rocks['{name}'] has initial conditions (INDOM) but is not defined in ROCKS",
        )

    names = list(rocks)
    for label, element in elements.items():
        material = element.get("material")
        check(
            material is None
            or material in rocks
            or (isinstance(material, int) and 1 <= material <= len(names)),
            f"elements['{label}']: unknown material '{material}'",
        )
        activity = element.get("activity")
        check(
            activity in {None, "", "I"}
            or (len(activity) == 3 and activity[0] == "V" and activity[1:].isdigit()),
            f"elements['{label}']: invalid activity '{activity}'",
        )

    if parameters.get("label_length") == 8:
        prefixes = [label[:5] for label in elements]
        check(
            len(set(prefixes)) == len(prefixes),
            "8-character element names must differ in their first 5 characters "
            "(otherwise TOUGH+HYDRATE v1.5 ignores connections)",
        )

    variable = {
        e.get("activity")
        for e in elements.values()
        if str(e.get("activity", "")).startswith("V")
    }
    for boundary in parameters.get("transient_boundaries", []):
        name = boundary.get("boundary_name")
        check(
            name in variable, f"transient boundary '{name}' is not used by any element"
        )

    for i, entry in enumerate(parameters.get("extended_initial_conditions", [])):
        states = entry.get("states", [entry])
        for state in states:
            check(
                state.get("phase_state") in STATES,
                f"extended_initial_conditions[{i}]: unknown phase_state",
            )

    return errors
