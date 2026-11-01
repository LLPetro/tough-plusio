from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Optional, TextIO

from ._helpers import Lines, header
from .blocks import registered_blocks
from ....core import ReadError


def read(
    filename: str | os.PathLike | TextIO,
    blocks: Optional[Sequence[str]] = None,
    label_length: Optional[int] = None,
    simulator: Optional[str] = None,
) -> dict:
    """
    Read TOUGH+HYDRATE v1.5 input file.

    Parameters
    ----------
    filename : str | PathLike | TextIO
        Input file name or buffer. Complete input files and separate MESH, INCON
        or GENER files are supported.
    blocks : Sequence[str], optional
        Only store these blocks (all blocks are parsed).
    label_length : int, optional
        Number of characters in element names (5 or 8). Read from MEMORY if not
        provided, required for separate files with 8-character names.
    simulator : str, optional
        Ignored, accepted for compatibility with :func:`toughio.read_input`.

    Returns
    -------
    dict
        TOUGH+HYDRATE input parameters.

    """
    if hasattr(filename, "read"):
        text = filename.read()
    else:
        with open(filename, encoding="latin-1") as f:
            text = f.read()

    return read_buffer(text, blocks, label_length)


def read_error(error: Exception, line: int, block: Optional[str]) -> ReadError:
    """
    Make the ReadError for a failure at *line* (1-based) while reading *block*.

    The error has the attributes line, block and reason (the message of *error*).

    """
    reason = str(error) or (
        "unexpected end of the file"
        if isinstance(error, StopIteration)
        else type(error).__name__
    )
    where = f" ({block} block)" if block else ""
    out = ReadError(f"failed to parse line {line}{where}: {reason}")
    out.line, out.block, out.reason = line, block, reason

    return out


def read_buffer(
    text: str,
    blocks: Optional[Sequence[str]] = None,
    label_length: Optional[int] = None,
) -> dict:
    """Read TOUGH+HYDRATE v1.5 input text."""
    readers = {block.name: block() for block in registered_blocks}
    blocks = set(blocks) if blocks is not None else None
    parameters = {}
    f = Lines(text)
    name = "TITLE"

    try:
        first = f.peek()
        if first is not None and not header(first)[0]:
            parameters.update(readers["TITLE"].read(f))

        for line in f:
            is_header, name = header(line)

            if not is_header:
                continue

            if name is None:
                raise ValueError(f"unsupported data block '{line.split()[0]}'")

            if name in {"ENDCY", "ENDFI"}:
                parameters["end"] = name
                break

            data = readers[name].read(
                f, label_length=label_length, simulator="tough", parameters=parameters
            )

            if not label_length and data.get("label_length"):
                label_length = data["label_length"]

            if blocks is None or name in blocks:
                readers[name].update(parameters, data)

    except Exception as e:
        raise read_error(e, f.count, name) from e

    if label_length and (blocks is None or "MEMORY" in blocks):
        parameters["label_length"] = label_length

    return parameters
