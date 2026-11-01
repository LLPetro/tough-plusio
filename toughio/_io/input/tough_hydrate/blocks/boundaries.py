from __future__ import annotations

import re

from .._helpers import (
    FortranRecordFormatter,
    HydrateBlock,
    fortran_real,
    header,
    located,
    next_record,
    read_namelist,
    read_values,
    split_record,
    write_namelist,
    write_values,
)


# read_format: list-directed '*' or a repeated real edit descriptor such as '(4E20.13)'
_FORMAT = re.compile(r"\(\s*(\d*)\s*\(?\s*[EFDG](\d+)\.(\d+)\s*\)?\s*\)", re.IGNORECASE)

TABLE = (
    "read_by_row_or_by_col",
    "number_of_rows",
    "tot_number_of_columns",
    "rowcolnum_to_primvarnum",
    "units_of_primvar",
    "read_format",
)


class BOUNDARIES(HydrateBlock):
    name = "BOUNDARIES"

    def _read(self, f, *args, **kwargs) -> dict:
        """Read BOUNDARIES block data (NAMELIST groups and tables, closed by '<<<')."""
        boundaries = []

        for _ in range(read_namelist(f)[1].get("number_of_defined_boundaries", 0)):
            boundary = read_namelist(f)[1]
            boundary.pop("num_pv_to_read", None)
            table = read_namelist(f)[1]
            rows = table.pop("number_of_rows", 0)
            columns = table.pop("tot_number_of_columns", 0)
            boundary.update(table)

            line = next_record(f, "table comment record")
            while not line.strip():
                line = next_record(f, "table comment record")
            tokens = split_record(line)
            boundary["comment"] = str(tokens[0]) if tokens else ""

            if _by_column(boundary):
                rows, columns = columns, rows
            reader = _formatter(boundary, "r")
            boundary["table"] = [
                _read_fixed(f, reader, columns) if reader else read_values(f, columns)
                for _ in range(rows)
            ]
            boundaries.append(boundary)

        # Skip to the closing record, but never into the next data block
        while f.peek() is not None and not header(f.peek())[0]:
            if f.next().startswith("<<<"):
                break

        return {"transient_boundaries": boundaries} if boundaries else {}

    def _write(self, parameters: dict, *args, **kwargs) -> list[str]:
        """Write BOUNDARIES block data."""
        boundaries = parameters["transient_boundaries"]
        n = len(boundaries)
        out = write_namelist(
            "Transient_Boundaries",
            {"number_of_defined_boundaries": n, "num_table_defined_boundaries": n},
        )

        for i, boundary in enumerate(boundaries):
            with located(prefix=("transient_boundaries", i)):
                out += _write_boundary(boundary)

        return out + ["<<<\n"]

    def _write_header(self) -> str:
        return ">>>BOUNDARIES\n"

    def _write_conditions(self, parameters: dict, *args, **kwargs) -> bool:
        return bool(parameters.get("transient_boundaries"))


def _write_boundary(boundary: dict) -> list[str]:
    rows = boundary.get("table", [])
    definition = {
        k: v for k, v in boundary.items() if k not in TABLE + ("comment", "table")
    }
    pv = definition.get("pv_numbers")
    definition["num_pv_to_read"] = len(pv) if isinstance(pv, (list, tuple)) else 1
    table = {k: boundary[k] for k in TABLE if k in boundary}
    shape = (len(rows), len(rows[0]) if rows else 0)
    shape = shape[::-1] if _by_column(boundary) else shape
    table["number_of_rows"], table["tot_number_of_columns"] = shape

    out = write_namelist("Transient_Boundary_Definition", definition, 3)
    out += write_namelist("Tabular_Data_Definition", table, 6)
    out += write_values([boundary.get("comment", "")], 4, names=[("comment",)])
    writer = _formatter(boundary, "w")
    for i, row in enumerate(rows):
        with located(prefix=("table", i)):
            out += (
                writer(row)
                if writer
                else write_values(row, 4, names=[(j,) for j in range(len(row))])
            )

    return out


def _formatter(boundary: dict, mode: str):
    """Reader/writer of a fixed table format, None for list-directed input."""
    fmt = str(boundary.get("read_format", "*")).strip()
    if fmt == "*":
        return None

    match = _FORMAT.fullmatch(fmt)
    if not match:
        raise ValueError(f"unsupported read_format {fmt!r}: use '*' or '(nEw.d)'")

    n, width, decimals = int(match[1] or 1), int(match[2]), int(match[3])
    if n < 1 or width < 1:
        raise ValueError(f"unsupported read_format {fmt!r}: no values per record")
    if mode == "w":
        return FortranRecordFormatter(
            ",".join(n * [f"{width}f"]), mode="w", multiple=True, names=()
        )

    return lambda line: [
        fortran_real(line[i * width : (i + 1) * width], decimals) for i in range(n)
    ]


def _read_fixed(f, reader, n: int) -> list[float]:
    """Read n values; format reversion starts a new record after a full format."""
    values = []
    while len(values) < n:
        line = next_record(f, f"table value {len(values) + 1} of {n}")
        values += [0.0 if x is None else x for x in reader(line)]

    return values[:n]


def _by_column(boundary: dict) -> bool:
    return str(boundary.get("read_by_row_or_by_col", "row")).lower().startswith("col")
