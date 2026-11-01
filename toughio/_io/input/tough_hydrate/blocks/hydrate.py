from __future__ import annotations

from .._helpers import HydrateBlock, read_values, write_values


INHIBITOR = (
    "max_temperature_shift",
    "mole_fraction_at_max_shift",
    "molecular_weight",
    "density",
    "dissolution_enthalpy",
)
KINETICS = ("activation_energy", "rate_constant", "area_factor")
POLYNOMIALS = ("thermal_conductivity", "specific_heat", "density")


class HYDRATE(HydrateBlock):
    name = "HYDRATE"

    def _read(self, f, *args, **kwargs) -> dict:
        """Read HYDRATE block data."""
        hydrate = {"components": []}

        for _ in range(read_values(f, 1)[0]):
            name, number, fraction = read_values(f, 3)
            hydrate["components"].append(
                {"name": name, "hydration_number": number, "mole_fraction": fraction}
            )

        for key in POLYNOMIALS:
            n = read_values(f, 1)[0]
            hydrate[key] = read_values(f, n) if n else []

        data = read_values(f)
        if data[0]:
            data += read_values(f, 9 - len(data)) if len(data) < 9 else []
            hydrate["inhibitor"] = dict(zip(INHIBITOR, data[1:6]))
            hydrate["inhibitor"]["specific_heat"] = data[6:9]

        hydrate["equation_option"] = read_values(f, 1)[0]
        hydrate["reaction_type"] = str(read_values(f, 1)[0]).strip().upper()

        if hydrate["reaction_type"].startswith("KINETIC"):
            hydrate["kinetics"] = dict(zip(KINETICS, read_values(f, 3)))

        return {"hydrate": hydrate}

    def _write(self, parameters: dict, *args, **kwargs) -> list[str]:
        """Write HYDRATE block data (counts are integers, the rest in its type)."""
        hydrate = parameters["hydrate"]
        components = hydrate.get("components", [])
        out = write_values([len(components)])

        for i, component in enumerate(components):
            keys = ("name", "hydration_number", "mole_fraction")
            out += write_values(
                [component.get(k) for k in keys],
                kinds=("text", "real", "real"),
                names=[("hydrate", "components", i, k) for k in keys],
            )

        for key in POLYNOMIALS:
            values = list(hydrate.get(key) or [])
            out += write_values([len(values)])
            out += (
                write_values(
                    values,
                    kinds=len(values) * ["real"],
                    names=[("hydrate", key, i) for i in range(len(values))],
                )
                if values
                else []
            )

        inhibitor = hydrate.get("inhibitor")
        heat = list(inhibitor.get("specific_heat", [])) if inhibitor else []
        out += write_values(
            [True, *(inhibitor.get(k) for k in INHIBITOR), *heat]
            if inhibitor
            else [False],
            kinds=["logical", *(len(INHIBITOR) + len(heat)) * ["real"]],
            names=[
                ("hydrate", "inhibitor"),
                *(("hydrate", "inhibitor", k) for k in INHIBITOR),
                *(
                    ("hydrate", "inhibitor", "specific_heat", i)
                    for i in range(len(heat))
                ),
            ],
        )
        out += write_values(
            [hydrate.get("equation_option")],
            kinds=["integer"],
            names=[("hydrate", "equation_option")],
        )
        reaction_type = hydrate.get("reaction_type", "EQUILIBRIUM")
        out += write_values(
            [reaction_type], kinds=["text"], names=[("hydrate", "reaction_type")]
        )

        if str(reaction_type).upper().startswith("KINETIC"):
            out += write_values(
                [hydrate.get("kinetics", {}).get(k) for k in KINETICS],
                kinds=len(KINETICS) * ["real"],
                names=[("hydrate", "kinetics", k) for k in KINETICS],
            )

        return out

    def _write_conditions(self, parameters: dict, *args, **kwargs) -> bool:
        return bool(parameters.get("hydrate"))
