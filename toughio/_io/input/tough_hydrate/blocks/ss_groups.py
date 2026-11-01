from __future__ import annotations

from .._helpers import (
    HydrateBlock,
    read_member,
    read_namelist,
    write_member,
    write_namelist,
)


class SS_GROUPS(HydrateBlock):
    name = "SS_GROUPS"

    def _read(self, f, *args, **kwargs) -> dict:
        """Read SS_GROUPS block data (NAMELIST groups)."""
        n = read_namelist(f)[1].get("number_of_ssgroups", 0)
        groups = [read_member(f, "number_of_ss", "sources") for _ in range(n)]

        return {"ss_groups": groups} if groups else {}

    def _write(self, parameters: dict, *args, **kwargs) -> list[str]:
        """Write SS_GROUPS block data."""
        groups = parameters["ss_groups"]
        out = write_namelist(
            "SSGroup_General_Info", {"number_of_ssgroups": len(groups)}
        )

        for group in groups:
            out += write_member(
                "Individual_SSGroup_Specifics", group, "number_of_ss", "sources", 3
            )

        return out + ["\n"]

    def _write_conditions(self, parameters: dict, *args, **kwargs) -> bool:
        return bool(parameters.get("ss_groups"))
