from __future__ import annotations

from .._helpers import (
    HydrateBlock,
    located,
    read_primary_variables,
    write_primary_variables,
)


class INDOM(HydrateBlock):
    name = "INDOM"
    formats = {5: "5s,2s,3s"}
    records = {5: "INDOM.1"}
    fields = {5: [None, None, ("phase_state",)]}

    def _read(self, f, *args, **kwargs) -> dict:
        """Read INDOM block data."""
        rocks = {}

        while True:
            line = f.next() if f.peek() is not None else ""  # EOF ends the block
            if not line.strip():
                break

            data = self.readers[5](line)
            rocks[data[0]] = self.prune_values(
                {
                    "phase_state": (data[2] or "").strip() or None,
                    "initial_condition": read_primary_variables(f.next()),
                }
            )

        return {"rocks": rocks}

    def _write(self, parameters: dict, *args, **kwargs) -> list[str]:
        """Write INDOM block data."""
        out = []

        for name, rock in parameters["rocks"].items():
            if rock.get("initial_condition") or rock.get("phase_state"):
                with located(prefix=("rocks", name), label=name):
                    out += self.writers[5]([name, None, rock.get("phase_state")])
                    with located(record="INDOM.2", prefix=("initial_condition",)):
                        out += write_primary_variables(rock.get("initial_condition"))

        return out + ["\n"]

    def _write_conditions(self, parameters: dict, *args, **kwargs) -> bool:
        return any(
            rock.get("initial_condition") or rock.get("phase_state")
            for rock in parameters.get("rocks", {}).values()
        )
