from __future__ import annotations

from .._helpers import (
    HydrateBlock,
    read_member,
    read_namelist,
    write_member,
    write_namelist,
)


class SUBDOMAINS(HydrateBlock):
    name = "SUBDOMAINS"

    def _read(self, f, *args, **kwargs) -> dict:
        """Read SUBDOMAINS block data (NAMELIST groups)."""
        subdomains = []

        for _ in range(read_namelist(f)[1].get("number_of_subdomains", 0)):
            subdomain = read_namelist(f)[1]
            n = subdomain.pop("number_of_regions", 0)
            subdomain["regions"] = [
                read_member(f, "number_of_elements", "elements") for _ in range(n)
            ]
            subdomains.append(subdomain)

        return {"subdomains": subdomains} if subdomains else {}

    def _write(self, parameters: dict, *args, **kwargs) -> list[str]:
        """Write SUBDOMAINS block data."""
        subdomains = parameters["subdomains"]
        out = write_namelist(
            "Subdomain_General_Info", {"number_of_subdomains": len(subdomains)}
        )

        for subdomain in subdomains:
            subdomain = dict(subdomain)
            regions = subdomain.pop("regions", [])
            subdomain["number_of_regions"] = len(regions)
            out += write_namelist("Individual_Subdomain_Specifics", subdomain, 3)

            for region in regions:
                out += write_member(
                    "Region_Specifics", region, "number_of_elements", "elements", 6
                )

        return out + ["\n"]

    def _write_conditions(self, parameters: dict, *args, **kwargs) -> bool:
        return bool(parameters.get("subdomains"))
