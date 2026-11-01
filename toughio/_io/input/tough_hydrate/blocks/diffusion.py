from __future__ import annotations

from .._helpers import HydrateBlock, read_namelist, write_namelist


class DIFFUSION(HydrateBlock):
    name = "DIFFUSION"

    def _read(self, f, *args, **kwargs) -> dict:
        """Read DIFFUSION block data (NAMELIST groups)."""
        diffusion = read_namelist(f)[1]
        diffusion["phases"] = []

        while _next_is_group(f):
            diffusion["phases"].append(read_namelist(f)[1])

        return {"multiphase_diffusion": diffusion}

    def _write(self, parameters: dict, *args, **kwargs) -> list[str]:
        """Write DIFFUSION block data."""
        diffusion = dict(parameters["multiphase_diffusion"])
        phases = diffusion.pop("phases", [])
        out = write_namelist("Diffusion_Key_Parameters", diffusion)

        for phase in phases:
            out += write_namelist("Component_Diffusivities_in_Phases", phase, 3)

        return out

    def _write_conditions(self, parameters: dict, *args, **kwargs) -> bool:
        return bool(parameters.get("multiphase_diffusion"))


def _next_is_group(f) -> bool:
    """True if the next non-blank record starts a NAMELIST group."""
    for line in f.lines[f.count :]:
        if line.strip():
            return line.lstrip().startswith("&")

    return False
