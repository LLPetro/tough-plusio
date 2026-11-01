"""
TOUGH+HYDRATE v1.5 time-series tables.

``Hydrate_Status``, ``<SSGroup>_Time_Series``, ``Int_<n>_Time_Series`` and
``<Subdomain>_Time_Series`` files: an optional title record (``SSGroup Wells``,
``Interface Int_1``, ``Subdomain MON1``), a header record, then numeric rows. Repeated
headers and marker records inside the file are skipped. Units written as
``Time(d)``, ``Time [days]`` or ``Time:d`` become ``Time (d)`` keys.
"""

import pathlib
import re

import numpy as np

from ...._common import open_file
from ....core import HistoryOutput
from ....core.record_formatter import to_float


_UNITS = {"days": "d", "day": "d", "seconds": "s", "sec": "s"}
_KINDS = {"SSGroup": "generator", "Interface": "connection", "Subdomain": "rock"}


def read(filename):
    """Read a T+H time-series file -> :class:`toughio.HistoryOutput`."""
    with open_file(filename, "r") as f:
        lines = f.read().splitlines()

    title, header, rows = None, None, []
    for line in lines:
        tokens = line.split()
        if not tokens:
            continue
        try:
            rows.append([to_float(t) for t in tokens])
        except ValueError:
            if header is None:
                if title is None and len(tokens) <= 3:
                    title = " ".join(tokens)
                else:
                    header = tokens

    if header is None:
        raise ValueError(f"{filename}: no header line found")

    merged = []
    for token in header:
        if merged and token.startswith("[") and token.endswith("]"):
            merged[-1] += token
        else:
            merged.append(token)

    table = np.full((len(rows), len(merged)), np.nan)
    for i, row in enumerate(rows):
        table[i, : min(len(row), len(merged))] = row[: len(merged)]

    data = {}
    for j, name in enumerate(merged):
        match = re.fullmatch(r"(.*?)(?:\(([^()]*)\)|\[([^\[\]]*)\]|:([^:]*))", name)
        name, unit = (
            (match[1], match[2] or match[3] or match[4]) if match else (name, None)
        )
        unit = _UNITS.get(unit.strip(), unit.strip()) if unit else None
        data[f"{name} ({unit})" if unit else name] = table[:, j]

    kind, _, label = (title or "").partition(" ")
    metadata = {
        "title": title,
        "type": _KINDS.get(kind, "rock"),
        "label": label or pathlib.Path(getattr(filename, "name", filename)).name,
    }

    return HistoryOutput(data, metadata=metadata)
