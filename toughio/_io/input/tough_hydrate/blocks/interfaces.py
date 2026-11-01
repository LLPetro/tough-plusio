from __future__ import annotations

from .._helpers import (
    HydrateBlock,
    read_member,
    read_namelist,
    write_member,
    write_namelist,
)


class INTERFACES(HydrateBlock):
    name = "INTERFACES"

    def _read(self, f, *args, **kwargs) -> dict:
        """Read INTERFACES block data (NAMELIST groups)."""
        interfaces = []

        for _ in range(read_namelist(f)[1].get("number_of_interfaces", 0)):
            interface = read_namelist(f)[1]
            n = interface.pop("number_of_surfaces", 0)
            interface["surfaces"] = [
                read_member(f, "number_of_connections", "connections") for _ in range(n)
            ]
            interfaces.append(interface)

        return {"interfaces": interfaces} if interfaces else {}

    def _write(self, parameters: dict, *args, **kwargs) -> list[str]:
        """Write INTERFACES block data."""
        interfaces = parameters["interfaces"]
        out = write_namelist(
            "Interface_General_Info", {"number_of_interfaces": len(interfaces)}
        )

        for interface in interfaces:
            interface = dict(interface)
            surfaces = interface.pop("surfaces", [])
            interface["number_of_surfaces"] = len(surfaces)
            out += write_namelist("Individual_Interface_Specifics", interface, 3)

            for surface in surfaces:
                out += write_member(
                    "Surface_Specifics",
                    surface,
                    "number_of_connections",
                    "connections",
                    6,
                )

        return out + ["\n"]

    def _write_conditions(self, parameters: dict, *args, **kwargs) -> bool:
        return bool(parameters.get("interfaces"))
