from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Literal, Optional, TextIO

from .blocks import registered_blocks


FILES = {"MESH": ("ELEME", "CONNE"), "INCON": ("INCON",), "GENER": ("GENER",)}


def write(
    filename: str | os.PathLike | TextIO,
    parameters: dict,
    blocks: Optional[Sequence[str] | Literal["MESH", "INCON", "GENER"]] = None,
    space_between_blocks: bool = False,
    space_between_values: bool = False,
    simulator: Optional[str] = None,
) -> None:
    """
    Write TOUGH+HYDRATE v1.5 input file.

    Parameters
    ----------
    filename : str | PathLike | TextIO
        Output file name or buffer.
    parameters : dict
        Parameters to export.
    blocks : Sequence[str] | {'MESH', 'INCON', 'GENER'}, optional
        Only write these blocks (no TITLE, MEMORY or ENDCY unless listed). The
        strings 'MESH', 'INCON' and 'GENER' write the corresponding separate file.
    space_between_blocks : bool, default False
        If True, add an empty record between blocks.
    space_between_values : bool, default False
        If True, add a white space between floating point values.
    simulator : str, optional
        Ignored, accepted for compatibility with :func:`toughio.write_input`.

    """
    text = "".join(
        write_buffer(parameters, blocks, space_between_blocks, space_between_values)
    )

    if hasattr(filename, "write"):
        filename.write(text)
    else:
        with open(filename, "w", encoding="latin-1", newline="\n") as f:
            f.write(text)


def write_buffer(
    parameters: dict,
    blocks: Optional[Sequence[str] | str] = None,
    space_between_blocks: bool = False,
    space_between_values: bool = False,
) -> list[str]:
    """Write TOUGH+HYDRATE v1.5 input records."""
    if isinstance(blocks, str):
        blocks = FILES[blocks.upper()]

    if blocks is None:
        end = parameters.get("end", "ENDCY")
        blocks = {block.name for block in registered_blocks} - (
            {"ENDCY", "ENDFI"} - {end}
        )

    out = []
    for block in registered_blocks:
        if block.name in blocks:
            out += block(
                space_between_blocks=space_between_blocks,
                space_between_values=space_between_values,
            ).write(parameters, simulator="tough")

    return out
