from __future__ import annotations

from .._helpers import HydrateBlock, check_title


class TITLE(HydrateBlock):
    name = "TITLE"

    def _read(self, f, *args, **kwargs) -> dict:
        """Read TITLE record (first line of the input file, up to 132 characters)."""
        return {"title": f.next().rstrip()}

    def _write(self, parameters: dict, *args, **kwargs) -> list[str]:
        """Write TITLE record (one line: a line break would start a block)."""
        title = parameters.get("title", "")
        title = title[0] if isinstance(title, (list, tuple)) else title

        return [f"{check_title(title)}\n"]

    def _write_header(self) -> str:
        return ""
