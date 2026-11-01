"""
TOUGH+HYDRATE v1.5 output formats.

Two readers, registered the same way the tough+hydrate INPUT format plugs into
the input registry (a self-contained package and one registration import):

* ``tough+hydrate-element`` — the ``Plot_Data_Elem`` file (written when PARAM
  MOP(19)=8). It is Tecplot POINT format and this reader REUSES toughio's own
  tecplot zone machinery; the only T+H quirk is blank separator lines between
  zones, on which the tecplot reader's buffer loop would stop after the first
  zone. Returns one :class:`ElementOutput` per print-out time.

* ``tough+hydrate-save`` — the T+H ``SAVE`` file. Same role as the TOUGH2 SAVE
  the ``save`` format reads, but the record layout differs (the T+H record
  carries the phase-state name, e.g. ``AGH``, a descriptive label for the
  primary variables, and reference permeability/porosity), which breaks the
  TOUGH2 parser. Returns ONE :class:`ElementOutput` (time from the header)
  with per-element porosity, state, primary variables X1..Xn and, when
  present, the reference permeability/porosity.
"""

import io
import re

import numpy as np

from .._common import to_output
from ...._common import open_file
from ....core.record_formatter import to_float as _ffloat


def _select_outputs(outputs, time_steps):
    """Select snapshots with upstream scalar/list and negative-index semantics."""
    if time_steps is None:
        return outputs
    if isinstance(time_steps, int):
        return outputs[time_steps]
    return [outputs[index] for index in time_steps]


def read_element(filename, file_type="element", labels_order=None, time_steps=None):
    """Read a Plot_Data_Elem file -> list of ElementOutput (one per ZONE)."""
    from ..tecplot._tecplot import read_buffer

    if file_type != "element":
        raise ValueError("TOUGH+HYDRATE reader supports element output only")

    with open_file(filename, "r") as f:
        text = f.read()
    # T+H separates zones with blank lines; the tecplot buffer loop treats a
    # blank line as end-of-file. Filtering them out is the whole adaptation.
    body = "\n".join(ln for ln in text.splitlines() if ln.strip())
    headers, zones = read_buffer(io.StringIO(body), None)

    times, labels, data = [], [], []
    for zone in zones:
        times.append(float(zone["title"].split()[0]) if "title" in zone else None)
        # Plot_Data_Elem has no labels; the caller supplies its row labels.
        labels.append(labels_order)
        data.append(np.asarray(zone["data"]).reshape(-1, len(headers)))
    outputs = to_output(file_type, None, headers, times, labels, data, return_list=True)
    return _select_outputs(outputs, time_steps)


def _is_elem_header(line):
    """
    True for an ELEMENT data-table header (``ELEM  INDEX  <vars…>``).
    Filters out connection (``ELEM1 ELEM2 INDEX``) and source
    (``ELEMENT SOURCE INDEX``) tables, whose column names are multi-word.
    """
    t = line.split()
    return len(t) >= 3 and t[0] == "ELEM" and t[1] == "INDEX"


def _out_time_seconds(chunk):
    """Time (SECONDS) of a print-out = first value under the TOTAL TIME (s) row."""
    for i, line in enumerate(chunk):
        if "TOTAL TIME (s)" in line:
            for line2 in chunk[i + 1 : i + 6]:
                toks = line2.split()
                if toks:
                    try:
                        return float(toks[0])
                    except ValueError:
                        continue
    return None


def _out_element_tables(chunk):
    """
    Merge every ELEMENT table in a print-out into {variable: array}, keyed by
    element order. Element names carry an embedded space (e.g. ``A00 0``), so the
    name is sliced by the fixed INDEX column rather than whitespace-split.
    """
    data, labels = {}, None
    i = 0
    while i < len(chunk):
        line = chunk[i]
        if not _is_elem_header(line):
            i += 1
            continue
        variables = line.split()[2:]
        idx_col = line.index("INDEX")
        names = []
        cols = [[] for _ in variables]
        j, started = i + 1, False
        while j < len(chunk):
            d = chunk[j]
            rest = (d[idx_col:] if len(d) > idx_col else d).split()
            is_data = False
            if rest:
                try:
                    int(rest[0])
                    vals = [_ffloat(x) for x in rest[1:]]
                    is_data = len(vals) >= 1
                except ValueError:
                    is_data = False
            if is_data:
                started = True
                # drop the solver's inactive/boundary '*' flag so labels match
                # the canonical element names (SAVE / mesh / connection tables)
                names.append(d[:idx_col].strip().rstrip("*"))
                for k in range(min(len(variables), len(vals))):
                    cols[k].append(vals[k])
                j += 1
            elif started or _is_elem_header(d) or d.lstrip()[:1] in ("@", "="):
                break  # table ended (or next block begins)
            else:
                j += 1  # skip units / underline / blank before data
        if names:
            if labels is None:
                labels = names
            for k, var in enumerate(variables):
                if len(cols[k]) == len(names):
                    data.setdefault(var, np.asarray(cols[k], dtype=float))
        i = j
    return data, labels


def _out_connection_tables(chunk):
    """Merge the connection tables (``ELEM1 ELEM2 INDEX ...``) of a print-out."""
    data, labels = {}, None
    for i, line in enumerate(chunk):
        tokens = line.split()
        if tokens[:3] != ["ELEM1", "ELEM2", "INDEX"]:
            continue
        i2, i3 = line.index("ELEM2"), line.index("INDEX")
        variables = re.split(r"\s{2,}", line[i3 + 5 :].strip())
        names, rows = [], []
        for d in chunk[i + 1 :]:
            rest = d[i3:].split()
            try:
                int(rest[0])
                values = [_ffloat(x) for x in rest[1:]]
            except (IndexError, ValueError):
                if rows:
                    break
                continue
            names.append([d[:i2].strip().rstrip("*"), d[i2:i3].strip().rstrip("*")])
            rows.append(values)
        if rows:
            labels = labels or names
            for k, var in enumerate(variables):
                if len(names) == len(labels):
                    data.setdefault(var, np.asarray([r[k] for r in rows], dtype=float))
    return data, labels


def read_out(filename, file_type="element", labels_order=None, time_steps=None):
    """
    Read a T+H main ``.out`` file -> list of :class:`ElementOutput`, one per
    print-out. Unlike ``Plot_Data_Elem`` (only the ~9 primary variables), the
    ``.out`` carries EVERY per-element table the solver prints — primary state
    (P, T, saturations, partial/equilibrium pressures, inhibitor), secondary
    properties (densities, viscosities, porosity, capillary pressure, rel-perms),
    the raw primary variables X1..X3 with increments, and enthalpies / reaction
    rates — all merged here into one rich variable set per time step. Connection
    and source tables are skipped (element-field focus). Time is in seconds.
    """
    from ....core import ConnectionOutput, ElementOutput

    if file_type not in {"element", "connection"}:
        raise ValueError(f"unsupported file type: {file_type}")
    tables, output = (
        (_out_element_tables, ElementOutput)
        if file_type == "element"
        else (_out_connection_tables, ConnectionOutput)
    )

    # The main output (solver stdout / run.log) is latin-1 and may carry bytes
    # that are invalid UTF-8 (e.g. 0xd5), so decode latin-1 rather than the
    # utf-8 default of open_file — else read_out would raise on real runs.
    if hasattr(filename, "read"):
        text = filename.read()
        if isinstance(text, bytes):
            text = text.decode("latin-1", "replace")
    else:
        with open(filename, "r", encoding="latin-1", errors="replace") as f:
            text = f.read()
    lines = text.splitlines()

    starts = [
        i for i, ln in enumerate(lines) if ln.lstrip().startswith("Output data after")
    ]
    if not starts:
        return []
    bounds = starts + [len(lines)]

    outs = []
    for s, e in zip(bounds, bounds[1:]):
        chunk = lines[s:e]
        data, labels = tables(chunk)
        if not data:
            continue
        outs.append(output(time=_out_time_seconds(chunk), data=data, labels=labels))

    if labels_order is not None:
        outs = [output[labels_order] for output in outs]
    return _select_outputs(outs, time_steps)


def read_save(filename, file_type="element", labels_order=None, time_steps=None):
    """
    Read a T+H SAVE file -> ElementOutput at the saved time.

    SAVE files are INCON data blocks: records are parsed by the tough+hydrate input
    reader (fixed columns, Fortran numbers), then converted to element data.
    """
    from ...input.tough_hydrate import read_buffer
    from ...input.tough_hydrate._helpers import fortran_real
    from ....core import ElementOutput

    if file_type != "element":
        raise ValueError("TOUGH+HYDRATE reader supports element output only")

    if hasattr(filename, "read"):
        text = filename.read()
    else:
        with open(filename, encoding="latin-1") as f:
            text = f.read()

    lines = text.splitlines()
    header = lines[0] if lines else ""
    time = float(header.split()[-1]) if "time" in header.lower() else None
    label_length = 8 if len(lines) > 1 and lines[1][5:8].strip() else 5
    incon = read_buffer(text, label_length=label_length).get("initial_conditions", {})

    names = list(incon)
    values = [v.get("values", []) for v in incon.values()]
    data = {
        "porosity": np.array([v.get("porosity", np.nan) for v in incon.values()]),
        "state": np.array([v.get("phase_state", "") for v in incon.values()]),
    }
    for k in range(max((len(v) for v in values), default=0)):
        data[f"X{k + 1}"] = np.array([v[k] if k < len(v) else np.nan for v in values])

    permeability = [v.get("permeability") or [] for v in incon.values()]
    if names and all(len(k) == 3 for k in permeability):
        data["perm_x"], data["perm_y"], data["perm_z"] = np.transpose(permeability)

    # SAVE records carry the reference porosity after the 3 permeabilities (cols 117-131)
    records = []
    for line in lines[1::2]:
        if line.startswith((":::", "<<<")) or not line[:label_length].strip():
            break
        records.append(fortran_real(line[116:131], 8))
    if names and len(records) == len(names) and all(x is not None for x in records):
        data["porosity_ref"] = np.array(records)

    output = ElementOutput(time=time, data=data, labels=names)
    if labels_order is not None:
        output = output[labels_order]
    if time_steps is not None:
        return _select_outputs([output], time_steps)
    return output
