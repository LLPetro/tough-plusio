from __future__ import annotations

from .conne import skip_cross_references
from .._helpers import END_OF_LIST, FortranRecords
from ...tough.blocks import GENER as _GENER


TAIL = ("well_response", None, "pressure_limit", "rate_step_change", "rate_limit")


class GENER(FortranRecords, _GENER):
    """GENER block; the TOUGHREACT KTAB column is replaced by the T+H well controls."""

    _space_between_blocks = False
    formats = {
        **_GENER.formats,
        5: "5s,5s,5d,5d,5d,5d,5s,4s,1s,10f,10f,10f,4s,6s,10f,10f,10f",
        8: "8s,5s,4d,4d,4d,5d,5s,4s,1s,10f,10f,10f,4s,6s,10f,10f,10f",
    }

    def _read(self, f, *args, **kwargs) -> dict:
        data = super()._read(f, *args, **kwargs)

        if data.pop("flag"):
            skip_cross_references(f)

        return data

    def _write(self, parameters: dict, *args, **kwargs) -> list[str]:
        records = (
            super()._write(parameters, *args, **kwargs)
            if parameters["generators"]
            else []
        )

        return records + END_OF_LIST

    def _write_conditions(self, parameters: dict, *args, **kwargs) -> bool:
        """Write GENER if present, even if empty."""
        return "generators" in parameters

    def _read_record_default(self, line: str, label_length: int) -> tuple[dict, dict]:
        generator, other = super()._read_record_default(line, label_length)
        data = self.readers[label_length](line)
        generator.update({k: v for k, v in zip(TAIL, data[12:]) if k})
        other["ktab"] = None

        return generator, other

    def _get_values_default(self, data: dict, ltab: int, itab: str) -> list:
        return [
            *super()._get_values_default(data, ltab, itab),
            *(data.get(k) if k else None for k in TAIL),
        ]
