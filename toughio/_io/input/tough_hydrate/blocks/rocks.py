from __future__ import annotations

from .._helpers import HydrateBlock, located, read_namelist, write_namelist


ROCK_1_1 = (
    "compressibility",
    "expansivity",
    "conductivity_dry",
    "tortuosity",
    "klinkenberg_parameter",
    None,  # mediaOrgCF, not used by T+H v1.5
    "critical_saturation",
    "permeability_exponent",
    "porosity_stress_beta",
    "permeability_porosity_gamma",
    "porosity_zero_stress",
)


class ROCKS(HydrateBlock):
    name = "ROCKS"
    formats = {
        1: "5s,5d,10f,10f,10f,10f,10f,10f,10f,10f",
        2: ",".join(11 * ["10f"]),
        3: "5d,5s,10f,10f,10f,10f,10f,10f,10f",
        5: "5d,5s," + ",".join(7 * ["20f"]),
        6: ",".join(10 * ["10f"]),
    }
    records = {1: "ROCKS.1", 2: "ROCKS.1.1"}
    fields = {
        1: [
            None,
            None,  # NAD, derived
            ("density",),
            ("porosity",),
            *3 * [("permeability",)],
            ("conductivity",),
            ("specific_heat",),
            ("grain_radius",),
        ],
        2: [(k,) if k else None for k in ROCK_1_1],
        3: [("id",), None, *(("parameters", i) for i in range(7))],
        5: [("order",), None, *(("coefficients", i) for i in range(7))],
        6: [("cementing_compressibility", i) for i in range(10)],
    }

    def _read(self, f, *args, **kwargs) -> dict:
        """Read ROCKS (MEDIA) block data."""
        rocks = {}

        while True:
            line = f.next() if f.peek() is not None else ""  # EOF ends the block
            if not line.strip():
                break

            data = self.readers[1](line)
            name, nad = data[0], data[1] or 0
            permeability = data[4:7]
            rock = {
                "density": data[2],
                "porosity": data[3],
                "permeability": (
                    permeability[0] if len(set(permeability)) == 1 else permeability
                ),
                "conductivity": data[7],
                "specific_heat": data[8],
                "grain_radius": data[9],
            }

            if nad >= 1:
                rock.update({k: v for k, v in zip(ROCK_1_1, self.readers[2](f)) if k})

            if nad >= 2:
                rock["relative_permeability"] = self.read_model_record(
                    f, self.readers[3]
                )
                rock["capillarity"] = self.read_model_record(f, self.readers[3])

            if nad == 5:
                data = self.readers[5](f)
                rock["porosity_polynomial"] = {
                    "order": data[0],
                    "coefficients": self.prune_values(data[2:]),
                }

            elif nad == 6:
                rock["cementing_compressibility"] = self.prune_values(
                    self.readers[6](f)
                )

            elif nad == 8:
                rock["slippage_turbulence"] = read_namelist(f)[1]

            rocks[name] = self.prune_values(rock)

        return {"rocks": rocks}

    def _write(self, parameters: dict, *args, **kwargs) -> list[str]:
        """Write ROCKS block data."""
        out = []

        for name, rock in parameters["rocks"].items():
            with located(prefix=("rocks", name), label=name):
                out += self._write_rock(name, rock)

        return out + ["\n"]

    def _write_rock(self, name: str, rock: dict) -> list[str]:
        nad = (
            8
            if "slippage_turbulence" in rock
            else 6
            if "cementing_compressibility" in rock
            else 5
            if "porosity_polynomial" in rock
            else 2
            if "relative_permeability" in rock or "capillarity" in rock
            else 1
            if any(rock.get(k) is not None for k in ROCK_1_1 if k)
            else 0
        )
        permeability = rock.get("permeability")
        permeability = (
            3 * [permeability]
            if permeability is None or isinstance(permeability, (int, float))
            else list(permeability)
        )
        out = self.writers[1](
            [
                name,
                nad,
                rock.get("density"),
                rock.get("porosity"),
                *permeability,
                rock.get("conductivity"),
                rock.get("specific_heat"),
                rock.get("grain_radius"),
            ]
        )

        if nad >= 1:
            out += self.writers[2]([rock.get(k) if k else None for k in ROCK_1_1])

        if nad >= 2:
            for record, key in (
                ("ROCKS.1.2", "relative_permeability"),
                ("ROCKS.1.3", "capillarity"),
            ):
                with located(record=record, prefix=(key,)):
                    out += (
                        self.write_model_record(rock, key, self.writers[3])
                        if key in rock
                        else ["\n"]
                    )

        if nad == 5:
            polynomial = rock["porosity_polynomial"]
            with located(prefix=("porosity_polynomial",)):
                out += self.writers[5](
                    [polynomial.get("order"), None, *polynomial.get("coefficients", [])]
                )

        elif nad == 6:
            out += self.writers[6](rock["cementing_compressibility"])

        elif nad == 8:
            out += write_namelist(
                "Slippage_Turbulence_Info", rock["slippage_turbulence"]
            )

        return out

    def _write_conditions(self, parameters: dict, *args, **kwargs) -> bool:
        return bool(parameters.get("rocks"))
