from __future__ import annotations

from .._helpers import END_OF_LIST, FortranRecords, is_terminator
from ...tough.blocks import CONNE as _CONNE


class CONNE(FortranRecords, _CONNE):
    """CONNE block; '+++' cross references written by the solver are skipped."""

    _space_between_blocks = False
    label_fields = 2  # the two element names

    def _write(self, parameters: dict, *args, **kwargs) -> list[str]:
        return super()._write(parameters, *args, **kwargs) + END_OF_LIST

    def _write_conditions(self, parameters: dict, *args, **kwargs) -> bool:
        """Write CONNE if present, even if empty."""
        return "connections" in parameters

    def _read(self, f, *args, **kwargs) -> dict:
        data = super()._read(f, *args, **kwargs)

        if data.pop("flag"):
            skip_cross_references(f)

        return data


def skip_cross_references(f) -> None:
    """Skip the element numbers following a '+++' record."""
    while not is_terminator(f.peek()):
        f.next()
