from __future__ import annotations

from .._helpers import (
    FieldError,
    HydrateBlock,
    as_real,
    located,
    read_primary_variables,
    write_primary_variables,
)


RECORD_1 = (
    "n_iteration",
    "verbosity",
    "n_cycle",
    "n_second",
    "n_cycle_print",
)
RECORD_1_TAIL = (
    "gas_diffusion_coefficient",
    "temperature_dependence_gas",
    "effective_strength_vapor",
    "n_cycle_save",
    "n_cycle_time_series",
)
RECORD_2 = (
    "t_ini",
    "t_max",
    "t_steps",
    "t_step_max",
    "track_element",
    None,
    "gravity",
    "t_reduce_factor",
    "mesh_scale_factor",
)
RECORD_3 = (
    "eps1",
    "eps2",
    None,  # U_p, not used by T+H v1.5
    "w_upstream",
    "w_newton",
    "derivative_factor",
    "w_implicitness",
    None,
    "phase_state",  # stored in parameters["default"]
    None,
    "p_overshoot",
    "t_overshoot",
    "s_overshoot",
)


class PARAM(HydrateBlock):
    name = "PARAM"
    formats = {
        1: "2d,2d,4d,4d,4d," + ",".join(24 * ["1d"]) + ",10f,10f,10f,5d,5d",
        2: "10f,10f,10f,10f,5s,5s,10f,10f,10f",
        3: ",".join(8 * ["10f"]),
        4: ",".join(7 * ["10f"]) + ",2s,3s,5s,10f,10f,10f",
    }
    multiples = {3}
    records = {1: "PARAM.1", 2: "PARAM.2", 3: "PARAM.2.1", 4: "PARAM.3"}
    fields = {
        1: [
            *(("options", k) for k in RECORD_1),
            *(("extra_options", i) for i in range(1, 25)),
            *(("options", k) for k in RECORD_1_TAIL),
        ],
        2: [("options", k) if k else None for k in RECORD_2],
        3: ("options", "t_steps"),
        4: [
            None
            if k is None
            else ("default", k)
            if k == "phase_state"
            else ("options", k)
            for k in RECORD_3
        ],
    }

    def _read(self, f, *args, **kwargs) -> dict:
        """Read PARAM block data."""
        data = self.readers[1](f)
        options = dict(zip(RECORD_1, data[:5]))
        options.update(zip(RECORD_1_TAIL, data[29:]))
        extra_options = {i + 1: x for i, x in enumerate(data[5:29]) if x is not None}

        data = self.readers[2](f)
        options.update({k: v for k, v in zip(RECORD_2, data) if k})
        options["track_element"] = (options["track_element"] or "").strip() or None

        if options["t_steps"] is not None and options["t_steps"] < 0:
            n, options["t_steps"] = int(-options["t_steps"]), []
            for _ in range(n):
                options["t_steps"] += self.prune_values(self.readers[3](f))

        data = dict(zip(RECORD_3, self.readers[4](f)))
        data.pop(None)
        state = (data.pop("phase_state") or "").strip() or None
        options.update(data)

        default = {
            "phase_state": state,
            "initial_condition": read_primary_variables(f.next()) or None,
        }

        return {
            "options": self.prune_values(options),
            "extra_options": extra_options,
            "default": self.prune_values(default),
        }

    def _write(self, parameters: dict, *args, **kwargs) -> list[str]:
        """Write PARAM block data."""
        options = parameters.get("options", {})
        extra = parameters.get("extra_options", {})
        default = parameters.get("default", {})

        mop = [extra.get(i, extra.get(str(i))) for i in range(1, 25)]
        out = self.writers[1](
            [
                *(options.get(k) for k in RECORD_1),
                *mop,
                *(options.get(k) for k in RECORD_1_TAIL),
            ]
        )

        steps = options.get("t_steps")
        steps = (
            [steps]
            if steps is None or isinstance(steps, str) or not hasattr(steps, "__len__")
            else list(steps)
        )
        if len(steps) == 1 and steps[0] is not None:
            # DELTEN < 0 is the number of PARAM.2.1 records: a negative step is a list
            with located(
                record="PARAM.2", path=("options", "t_steps"), columns=(21, 30)
            ):
                if as_real(steps[0]) < 0:
                    raise FieldError("negative_time_step", "real", steps[0])
        values = {
            **options,
            "t_steps": steps[0] if len(steps) == 1 else -((len(steps) + 7) // 8),
        }
        out += self.writers[2]([values.get(k) if k else None for k in RECORD_2])
        out += self.writers[3](steps) if len(steps) > 1 else []

        values = {**options, "phase_state": default.get("phase_state")}
        out += self.writers[4]([values.get(k) if k else None for k in RECORD_3])
        with located(record="PARAM.4", prefix=("default", "initial_condition")):
            out += write_primary_variables(default.get("initial_condition"))

        return out

    def _write_conditions(self, parameters: dict, *args, **kwargs) -> bool:
        return bool(parameters.get("options") or parameters.get("extra_options"))
