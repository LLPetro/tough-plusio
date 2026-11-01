from __future__ import annotations

from .._helpers import HydrateBlock


class ENDFI(HydrateBlock):
    """ENDFI keyword: read the input without running the simulation."""

    name = "ENDFI"

    def _read(self, f, *args, **kwargs) -> dict:
        return {}

    def _write(self, parameters: dict, *args, **kwargs) -> list[str]:
        return []

    def _write_header(self) -> str:
        return "ENDFI\n"
