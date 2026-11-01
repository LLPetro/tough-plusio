from __future__ import annotations

from .._helpers import (
    FieldError,
    HydrateBlock,
    read_namelist,
    read_primary_variables,
    write_namelist,
    write_primary_variables,
)


_TAIL = [
    ("porosity",),
    None,
    ("phase_state",),
    None,
    *(("permeability", i) for i in range(3)),
]


class INCON(HydrateBlock):
    name = "INCON"
    formats = {
        5: "5s,5d,5d,15f,2s,3s,36s,15f,15f,15f",
        8: "8s,7s,15f,2s,3s,36s,15f,15f,15f",
    }
    records = {5: "INCON.1", 8: "INCON.1"}
    fields = {5: [None, ("nseq",), ("nadd",), *_TAIL], 8: [None, None, *_TAIL]}

    def _read(self, f, label_length: int = None, *args, **kwargs) -> dict:
        """Read INCON block data; a record with a blank element name closes the block."""
        label_length = 8 if label_length == 8 else 5
        incon = {"initial_conditions": {}}

        while True:
            line = f.next() if f.peek() is not None else ""  # EOF ends the block
            if line.startswith(":::"):
                if f.peek() is not None:
                    incon["continuation_run"] = read_namelist(f)[1]
                if (f.peek() or "").startswith("<<<"):
                    f.next()
                break

            if line.startswith("<<<") or not line[:label_length].strip():
                break

            # Columns 36-71 hold a free text label (e.g. "AGH: P_gas, S_aqu, T" in SAVE files)
            data = self.readers[label_length](f"{line[:35]:<71}{line[71:]}")
            if label_length == 5:
                nseq, nadd, data = data[1], data[2], [data[0], *data[3:]]
            else:
                nseq, nadd, data = None, None, [data[0], *data[2:]]

            incon["initial_conditions"][data[0]] = self.prune_values(
                {
                    "nseq": nseq,
                    "nadd": nadd,
                    "porosity": data[1],
                    "phase_state": (data[3] or "").strip() or None,
                    "permeability": self.prune_values(data[5:8]) or None,
                    "values": read_primary_variables(f.next()),
                }
            )

        return incon

    def _write(self, parameters: dict, *args, **kwargs) -> list[str]:
        """Write INCON block data."""
        incon = parameters.get("initial_conditions", {})
        label_length = 8 if max((len(k) for k in incon), default=5) > 5 else 5
        out = []

        for label, data in incon.items():
            head = (
                [label, data.get("nseq"), data.get("nadd")]
                if label_length == 5
                else [label, None]
            )
            # try rather than located(): no cost per record of a large INCON
            try:
                out += self.writers[label_length](
                    [
                        *head,
                        data.get("porosity"),
                        None,
                        data.get("phase_state"),
                        None,
                        *(data.get("permeability") or []),
                    ]
                )
                try:
                    out += write_primary_variables(data.get("values"))
                except FieldError as e:
                    raise e.locate(record="INCON.2", prefix=("values",))
            except FieldError as e:
                raise e.locate(prefix=("initial_conditions", label), label=label)

        if parameters.get("continuation_run"):
            out += [":::\n"]
            out += write_namelist(
                "Data_For_Continuation_Run", parameters["continuation_run"]
            )
            out += ["<<<\n"]

        return out + ["\n"]

    def _write_conditions(self, parameters: dict, *args, **kwargs) -> bool:
        """Write INCON if present, even if empty."""
        return "initial_conditions" in parameters or bool(
            parameters.get("continuation_run")
        )
