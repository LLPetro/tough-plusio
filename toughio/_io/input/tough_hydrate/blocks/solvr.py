from __future__ import annotations

from .._helpers import HydrateBlock


KEYS = ("method", None, "z_precond", None, "o_precond", "rel_iter_max", "eps")


class SOLVR(HydrateBlock):
    name = "SOLVR"
    formats = {1: "1d,2s,2s,3s,2s,10f,10f"}
    records = {1: "SOLVR"}
    fields = {1: [("solver", k) if k else None for k in KEYS]}

    def _read(self, f, *args, **kwargs) -> dict:
        """Read SOLVR block data."""
        solver = {k: v for k, v in zip(KEYS, self.readers[1](f)) if k}
        solver = {k: v.strip() if isinstance(v, str) else v for k, v in solver.items()}

        return {"solver": self.prune_values(solver)}

    def _write(self, parameters: dict, *args, **kwargs) -> list[str]:
        """Write SOLVR block data."""
        solver = parameters["solver"]

        return self.writers[1]([solver.get(k) if k else None for k in KEYS])

    def _write_conditions(self, parameters: dict, *args, **kwargs) -> bool:
        return bool(parameters.get("solver"))
