from __future__ import annotations

from .._helpers import FieldError, FortranRecords, write_field
from ...tough.blocks import ELEME as _ELEME


# Fields of an ELEME record (upstream _get_values_default)
FIELDS = [
    None,
    ("nseq",),
    ("nadd",),
    ("material",),
    ("volume",),
    ("heat_exchange_area",),
    ("permeability_modifier",),
    ("center", 0),
    ("center", 1),
    ("center", 2),
]


class ELEME(FortranRecords, _ELEME):
    """ELEME block with the T+H element activity indicator (columns 82-84)."""

    fields = {5: FIELDS, 8: FIELDS}

    def _read_record_default(self, line: str, label_length: int) -> tuple[str, dict]:
        label, data = super()._read_record_default(line[:80], label_length)
        data["activity"] = line[81:84].strip() or None

        return label, data

    def update(self, parameters: dict, data: dict) -> None:
        """Update parameters (T+H has no COORD block)."""
        parameters.update(data["data"])

    def _write(self, parameters: dict, *args, **kwargs) -> list[str]:
        """Write ELEME block data."""
        if not parameters["elements"]:
            return []

        label_length = max(len(max(parameters["elements"], key=len)), 5)
        out = []

        for label, element in parameters["elements"].items():
            # try rather than located(): no cost per record of a large ELEME
            try:
                values = {k: v for k, v in element.items() if k != "permeability"}
                line = self.writers[label_length](
                    [label, *self._get_values_default(values)]
                )
                line = line[0].rstrip()

                activity = element.get("activity")
                if activity:
                    try:
                        activity = write_field(activity, "3s").rstrip()
                    except FieldError as e:
                        raise e.locate(path=("activity",), columns=(82, 84))
                    line = f"{line:<80} {activity}"
            except FieldError as e:
                raise e.locate(prefix=("elements", label), label=label)

            out.append(f"{line}\n")

        return out

    def _write_conditions(self, parameters: dict, *args, **kwargs) -> bool:
        """Write ELEME if present, even if empty."""
        return "elements" in parameters
