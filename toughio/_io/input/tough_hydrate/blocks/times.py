from __future__ import annotations

import numpy as np

from .._helpers import FortranRecords, next_record
from ...tough.blocks import TIMES as _TIMES


KEYS = ("max_n_times", "t_step_max", "t_increment")


class TIMES(FortranRecords, _TIMES):
    """TIMES block keeping the TIMES.1 output controls in 'times_options'."""

    records = {1: "TIMES.1", "2/fixed": "TIMES.2"}
    fields = {
        1: [("times",), *(("times_options", k) for k in KEYS)],
        "2/fixed": ("times",),
    }

    def _read(self, f, *args, **kwargs) -> dict:
        data = self.readers[1](next_record(f, "TIMES.1 record"))
        n = data[0] or 0
        times = []

        while len(times) < n:
            line = next_record(f, f"time {len(times) + 1} of {n}")
            key = "2/free" if self.free_format or "," in line else "2/fixed"
            times += self.prune_values(self.readers[key](line))

        out = {"times": times}
        options = self.prune_values(dict(zip(KEYS, data[1:])))
        if options:
            out["times_options"] = options

        return out

    def _write(self, parameters: dict, *args, **kwargs) -> list[str]:
        times = parameters["times"]
        times = list(times) if np.ndim(times) else [times]
        options = parameters.get("times_options", {})

        return self.writers[1](
            [len(times), *(options.get(k) for k in KEYS)]
        ) + self.writers["2/fixed"](times)
