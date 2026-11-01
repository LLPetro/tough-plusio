"""Shared helpers for TOUGH+HYDRATE v1.5 input files."""

from __future__ import annotations

import contextlib
import math
import numbers
import re
from collections.abc import Sequence
from typing import Any, Optional

import numpy as np

from ....core import DataBlock, RecordFormatter
from ....core.record_formatter import (
    to_float,
    tokens as TOKENS,
)


# Records closing CONNE and GENER. With 8-character element names the solver reads one
# more record after the blank terminator of CONNE (T+H v1.5 solver), so two are written.
END_OF_LIST = ["\n", "\n"]

RULER = "----1----*----2----*----3----*----4----*----5----*----6----*----7----*----8"

# Header spelling -> block name (Table 4.1 of the T+H v1.5 manual)
KEYWORDS = {
    "MEMORY": "MEMORY",
    "ROCKS": "ROCKS",
    "MEDIA": "ROCKS",
    "HYDRATE": "HYDRATE",
    "DIFFUSION": "DIFFUSION",
    "DIFFU": "DIFFUSION",
    "RPCAP": "RPCAP",
    "WETTABILITY": "RPCAP",
    "START": "START",
    "RANDOMN": "START",
    "PARAM": "PARAM",
    "SOLVR": "SOLVR",
    "TIMES": "TIMES",
    "ELEME": "ELEME",
    "CONNE": "CONNE",
    "INDOM": "INDOM",
    "INCON": "INCON",
    "EXT-INCON": "EXT-INCON",
    "EXT_INCON": "EXT-INCON",
    ">>>BOUNDARIES": "BOUNDARIES",
    "BOUNDARIES": "BOUNDARIES",
    "GENER": "GENER",
    "SUBDOMAINS": "SUBDOMAINS",
    "SUBDOMAIN": "SUBDOMAINS",
    "INTERFACES": "INTERFACES",
    "INTERFACE": "INTERFACES",
    "INTER": "INTERFACES",
    "SS_GROUPS": "SS_GROUPS",
    "SS_GROUP": "SS_GROUPS",
    "ENDCY": "ENDCY",
    "ENDFI": "ENDFI",
    # Recognized but not supported by this format
    "MESHMAKER": None,
    "MESHM": None,
    "UPDATE": None,
}
_SPELLINGS = sorted(KEYWORDS, key=len, reverse=True)


class Lines:
    """Line iterator with look-ahead, duck-typing :class:`toughio.FileIterator`."""

    def __init__(self, text: str) -> None:
        self.lines = text.splitlines()
        self.count = 0
        self.line = ""

    def __iter__(self):
        return self

    def __next__(self) -> str:
        return self.next()

    def next(self, *args, **kwargs) -> str:
        if self.count >= len(self.lines):
            raise StopIteration
        self.line = self.lines[self.count]
        self.count += 1

        return self.line

    def peek(self) -> Optional[str]:
        return self.lines[self.count] if self.count < len(self.lines) else None


def header(line: str) -> tuple[bool, Optional[str]]:
    """
    Return (is_header, block_name) for a keyword record.

    A keyword must start the record and must not be followed by a letter, e.g.
    'ROCKS----1----*', 'MEMORY', 'ELEME ---    33' or 'HYDRATE--1--comment'.

    """
    upper = line.upper()

    for spelling in _SPELLINGS:
        if upper.startswith(spelling):
            following = upper[len(spelling) : len(spelling) + 1]
            if not (following.isalpha() or following == "_"):
                return True, KEYWORDS[spelling]

    return False, None


def is_terminator(line: Optional[str]) -> bool:
    """True at end of file, on a blank record or on a block header."""
    return line is None or not line.strip() or header(line)[0]


# What may follow the keyword of a record that starts a block: nothing, a blank, a
# ruler ('ROCKS----1----*', 'HYDRATE--1', 'MESHMAKER1----*') or a comment
_AFTER_KEYWORD = re.compile(r"\s|--|-?[\d*]|$")


def block_start(line: Optional[str]) -> Optional[str]:
    """
    The block a record starts, or None.

    Stricter than :func:`header`: the keyword is upper case, as the solver needs
    it, and is followed by nothing, a blank or a ruler, so that a list-directed value
    such as an unquoted HYDRATE-EQUILIBRIUM is not taken for a block.

    """
    if not line:
        return None

    for spelling in _SPELLINGS:
        if line.startswith(spelling) and _AFTER_KEYWORD.match(line, len(spelling)):
            return KEYWORDS[spelling] or spelling

    return None


def block_end(line: Optional[str]) -> Optional[str]:
    """
    Say where the records of a block run out at this record.

    Returns 'the end of the file', 'the <NAME> block' at a record that starts a
    block, or None if the record may belong to the current block.

    """
    if line is None:
        return "the end of the file"

    name = block_start(line)

    return f"the {name} block" if name else None


def next_record(f, what: str = "record") -> str:
    """
    Read the next record of a block.

    Raises ValueError ('<what> missing before the end of the file / the <NAME>
    block') instead of reading past the end of the file or into the next block.

    """
    end = block_end(f.peek())
    if end:
        raise ValueError(f"{what} missing before {end}")

    return f.next()


# Typed values. A field holds an integer (Fortran I descriptor), a real (E/F), text (A)
# or, in list-directed and NAMELIST records, a logical. A value the field cannot hold
# raises FieldError: it is never written truncated, in another type or past its columns
# (where the solver would read it, and every following field, wrongly).
INTEGER_LIMIT = 2**31 - 1  # default Fortran INTEGER
_INTEGER_TEXT = re.compile(r"\s*[+-]?\d+\s*")
# control characters (C0, DEL and the line breaks of str.splitlines)
_CONTROL = re.compile("[\x00-\x1f\x7f\x85\u2028\u2029]")
_TITLE_CONTROL = re.compile("[\x00-\x08\x0a-\x1f\x7f\x85\u2028\u2029]")  # tab allowed

_PROBLEMS = {
    "not_integer": "{value} is not an integer",
    "not_real": "{value} is not a number",
    "not_finite": "{value} is not a finite number",
    "not_text": "{value} is not text",
    "not_logical": "{value} is not a logical (True or False)",
    "not_ascii": "text {value} is not ASCII",
    "control_character": "text {value} has a control character",
    "out_of_range": "integer {value} is outside the range of a Fortran INTEGER",
    "not_a_value": "{type} {value} is not a Fortran value",
    "negative_time_step": "{value}: a negative initial time step is read as the "
    "number of PARAM.2.1 records",
}


def _plain(value: Any) -> Any:
    """A NumPy scalar as the Python value (np.str_('A1') -> 'A1')."""
    return value.item() if isinstance(value, np.generic) else value


class FieldError(ValueError):
    """
    A value that a record of a TOUGH+HYDRATE input file cannot hold.

    Attributes
    ----------
    reason : str
        'too_wide', 'not_integer', 'not_real', 'not_finite', 'not_text',
        'not_logical', 'not_ascii', 'control_character', 'out_of_range',
        'not_a_value' or 'negative_time_step'.
    kind : str
        What the field holds: 'integer', 'real', 'text', 'logical' or 'value' (a
        list-directed or NAMELIST value of any type).
    value : Any
        The value given.
    width : int or None
        Width of the fixed-format field.
    block, record, label, field, path, columns
        Where, as far as known (else None): block name, record ('PARAM.1'), label of
        the item the record belongs to (element, medium...), field name, canonical
        path (tuple of keys, e.g. ``("options", "n_cycle_print")``) and the columns
        (first, last) of a fixed-format field.
    shown : str
        The value as messages show it (repr, at most 40 characters).

    """

    def __init__(self, reason: str, kind: str, value: Any, width=None, **where):
        super().__init__(reason)
        self.reason, self.kind, self.value, self.width = reason, kind, value, width
        self.block = self.record = self.label = self.field = None
        self.path = self.columns = None
        self.locate(**where)

    def locate(self, prefix: Optional[Sequence] = None, **where) -> "FieldError":
        """
        Fill in the location fields not known yet (the innermost caller knows best);
        *prefix* is prepended to the path. Labels and keys are plain Python values.
        """
        for key, value in where.items():
            if getattr(self, key) is None and value is not None:
                if key == "label":
                    value = str(value)
                elif key == "path":
                    value = tuple(_plain(k) for k in value)
                setattr(self, key, value)
        if prefix is not None:
            self.path = (*(_plain(k) for k in prefix), *(self.path or ()))

        return self

    @property
    def shown(self) -> str:
        """The value as written in messages: its repr, at most 40 characters."""
        value = repr(_plain(self.value))

        return value if len(value) <= 40 else value[:37] + "..."

    @property
    def problem(self) -> str:
        value = self.shown
        if self.reason == "too_wide":
            return f"{self.kind} {value} does not fit in {self.width} characters"
        text = _PROBLEMS.get(self.reason, "{value}: " + self.reason)

        return text.format(value=value, type=type(self.value).__name__)

    def __str__(self) -> str:
        where = self.record or self.block or "record"
        if self.label is not None:
            where += f" {self.label!r}"
        name = self.field or (".".join(str(k) for k in self.path) if self.path else "")
        if name:
            where += f" {name}"
        if self.columns:
            where += f" (columns {self.columns[0]}-{self.columns[1]})"

        return f"{where}: {self.problem}"


@contextlib.contextmanager
def located(**where):
    """Add the location of the records written inside to their FieldError."""
    try:
        yield
    except FieldError as e:
        e.locate(**where)
        raise


def _logical(value: Any) -> bool:
    return isinstance(value, (bool, np.bool_))


def as_integer(value: Any) -> int:
    """
    The integer a value stands for (an int or NumPy integer, a whole float or an
    integer literal); FieldError otherwise.
    """
    if isinstance(value, numbers.Integral) and not _logical(value):
        return int(value)
    if isinstance(value, numbers.Real) and not _logical(value):
        x = float(value)
        if not math.isfinite(x):
            raise FieldError("not_finite", "integer", value)
        if x.is_integer():
            return int(x)
    elif isinstance(value, str) and _INTEGER_TEXT.fullmatch(value):
        return int(value)

    raise FieldError("not_integer", "integer", value)


def as_real(value: Any) -> float:
    """
    The finite real a value stands for (a number or a numeric literal); FieldError
    otherwise.
    """
    if isinstance(value, numbers.Real) and not _logical(value):
        try:
            x = float(value)
        except OverflowError:  # an int beyond the double range
            raise FieldError("not_finite", "real", value) from None
    elif isinstance(value, str):
        try:
            x = to_float(value)
        except ValueError:
            raise FieldError("not_real", "real", value) from None
    else:
        raise FieldError("not_real", "real", value)

    if not math.isfinite(x):
        raise FieldError("not_finite", "real", value)

    return x


def as_text(value: Any, fixed: bool = True) -> str:
    """
    A text value: a str without control characters, ASCII in a fixed-format field
    (where every character must take one column in any character set).
    """
    if not isinstance(value, str):
        raise FieldError("not_text", "text", value)
    if _CONTROL.search(value):
        raise FieldError("control_character", "text", value)
    if fixed and not value.isascii():
        raise FieldError("not_ascii", "text", value)

    return value


def as_logical(value: Any) -> bool:
    """A logical value: a bool or NumPy bool; FieldError otherwise."""
    if _logical(value):
        return bool(value)

    raise FieldError("not_logical", "logical", value)


def real_text(x: float, n: int) -> str:
    """
    Text of a real in at most n characters, as the upstream writer: Python's
    shortest text, else scientific notation with as many digits as fit.
    """
    text = str(x)
    if len(text) > n or "e" in text:
        if 1.0 <= abs(x) < 10.0:
            text = text[:n]
        else:
            from ....utils import scientific_notation

            text = scientific_notation(x, n)

    return text


def write_field(value: Any, token: str, space_between_values: bool = False) -> str:
    """
    Text of one fixed-format field.

    token: width and type of the field: 'd' integer (right-justified), 'f' or 'e' real
    (with a decimal point, so that no implied decimals apply), 's' text (left-justified)
    or 'S' text (right-justified). None is a blank field.

    """
    return field_text(value, int(token[:-1]), token[-1], space_between_values)


def field_text(value: Any, width: int, kind: str, space: bool = False) -> str:
    """:func:`write_field` with the token split (fast paths for int, float, str)."""
    if value is None:
        return " " * width

    t = type(value)
    if kind == "d":
        n = value if t is int else None
        if n is None:
            if t is str and not value.strip():
                return " " * width
            n = as_integer(value)
        text = str(n)
        if len(text) > width:
            raise FieldError("too_wide", "integer", value, width)

        return text.rjust(width)

    if kind in "fe":
        if t is float and math.isfinite(value):
            x = value
        elif t is str and not value.strip():
            return " " * width
        else:
            x = as_real(value)
        n = width - 1 if space else width
        text = real_text(x, n)
        if len(text) > n or "." not in text:
            raise FieldError("too_wide", "real", value, width)

        return text.rjust(width)

    text = as_text(value)
    if len(text) > width:  # blanks on the padding side may go
        text = text.rstrip() if kind == "s" else text.lstrip()
        if len(text) > width:
            raise FieldError("too_wide", "text", value, width)

    return text.ljust(width) if kind == "s" else text.rjust(width)


def check_title(title: Any) -> str:
    """The TITLE record: text without line breaks (the next line is a block)."""
    title = "" if title is None else title
    if not isinstance(title, str):
        raise FieldError("not_text", "text", title, path=("title",))
    if _TITLE_CONTROL.search(title):
        raise FieldError("control_character", "text", title, path=("title",))

    return title


# List-directed (free-format) records
_TOKEN = re.compile(r"'(?:[^']|'')*'|\"[^\"]*\"|!|,|[^\s,'\"!]+")
_INTEGER = re.compile(r"[+-]?\d+")
# r*c (r copies of the constant c) or r* (r null values); the constant has no '*'
_REPEAT = re.compile(r"(\d+)\*([^*]*)")
# Largest r of a repeat: a larger one is a typo that would allocate a huge list
MAX_REPEAT = 1_000_000


class Text(str):
    """String token that was quoted in the input file."""


def to_value(token: Optional[str]) -> Any:
    """Convert a list-directed token to None (null value), bool, int, float or str."""
    if token is None:
        return None

    if isinstance(token, Text):
        return str(token)

    upper = token.upper()
    if upper in {".TRUE.", ".T."}:
        return True
    if upper in {".FALSE.", ".F."}:
        return False
    if _INTEGER.fullmatch(token):
        return int(token)

    try:
        return to_float(token)
    except ValueError:
        return token


def split_record(line: str) -> list[Optional[str]]:
    """
    Split a list-directed record into tokens.

    Quotes protect separators, '!' starts a comment, 'r*c' repeats a value and an
    empty field between commas ('2, ,4') is a null value (None), as in Fortran.

    """
    tokens = []
    separated = True

    for token in _TOKEN.findall(line):
        if token == "!":
            break

        if token == ",":
            if separated:
                tokens.append(None)
            separated = True
            continue

        if token[0] in "'\"":
            tokens.append(Text(token[1:-1].replace("''", "'")))
        else:
            match = _REPEAT.fullmatch(token)
            if match and int(match[1]) > MAX_REPEAT:
                raise ValueError(
                    f"repeat count of '{token[:40]}' is larger than {MAX_REPEAT}"
                )
            tokens += [match[2] or None] * int(match[1]) if match else [token]

        separated = False

    return tokens


def read_values(f, n: Optional[int] = None) -> list[Any]:
    """
    Read one list-directed record, or *n* values spanning several records.

    Raises ValueError if *n* is not a count (a non-negative integer) or if the
    records run out first, at the end of the file or at the next block.

    """
    if n is not None and (isinstance(n, bool) or not isinstance(n, int) or n < 0):
        raise ValueError(f"invalid count {n!r} (expected a non-negative integer)")

    values = []

    while True:
        what = "record" if n is None else f"value {len(values) + 1} of {n}"
        line = next_record(f, what)

        if not line.strip() and n is not None:
            continue

        values += [to_value(token) for token in split_record(line)]

        if n is None or len(values) >= n:
            return values[:n] if n is not None else values


def format_value(value: Any, kind: Optional[str] = None) -> str:
    """
    Format a value for list-directed or NAMELIST input.

    kind: the type of the variable ('integer', 'real', 'text' or 'logical'); if None,
    the type of the value (NumPy numbers included). None is a null value. Raises
    FieldError for a value the type cannot hold or of no Fortran type (list, dict...).

    """
    if value is None:
        return ""

    numeric = isinstance(value, numbers.Real) and not _logical(value)
    if kind == "integer" or (
        kind is None and numeric and isinstance(value, numbers.Integral)
    ):
        n = as_integer(value)
        if abs(n) > INTEGER_LIMIT:
            raise FieldError("out_of_range", "integer", value)

        return str(n)

    if kind == "real" or (kind is None and numeric):
        return repr(as_real(value))  # shortest text that reads back to the same double

    if kind == "logical" or (kind is None and _logical(value)):
        return ".TRUE." if as_logical(value) else ".FALSE."

    if kind == "text" or (kind is None and isinstance(value, str)):
        return "'" + as_text(value, fixed=False).replace("'", "''") + "'"

    raise FieldError("not_a_value", "value", value)


def write_values(
    values: Sequence[Any],
    indent: int = 0,
    kinds: Optional[Sequence[Optional[str]]] = None,
    names: Optional[Sequence[Optional[tuple]]] = None,
) -> list[str]:
    """
    Write a list-directed record; None becomes a null value.

    kinds: the type of each value (see :func:`format_value`); names: the canonical
    path of each value, for FieldError.

    """
    values = list(values)
    while values and values[-1] is None:
        values.pop()
    sep = ", " if None in values else "  "

    texts = []
    for i, value in enumerate(values):
        kind = kinds[i] if kinds is not None and i < len(kinds) else None
        try:
            texts.append(format_value(value, kind))
        except FieldError as e:
            path = names[i] if names is not None and i < len(names) else None
            raise e.locate(path=path)

    return [" " * indent + sep.join(texts) + "\n"]


# NAMELIST groups
def _code(line: str) -> str:
    """Strip a '!' comment outside quotes."""
    quote = None

    for i, char in enumerate(line):
        if quote:
            if char == quote:
                quote = None
        elif char in "'\"":
            quote = char
        elif char == "!":
            return line[:i]

    return line


def _mask(text: str) -> tuple[str, list[str]]:
    """Replace quoted literals by placeholders."""
    literals = []

    def repl(match):
        token = match[0]
        literals.append(token[1:-1].replace("''", "'"))
        return f"\x00{len(literals) - 1}\x00"

    return re.sub(r"'(?:[^']|'')*'|\"[^\"]*\"", repl, text), literals


_ASSIGNMENT = re.compile(r"([A-Za-z_]\w*)\s*(?:\(\s*(-?\d+)\s*\))?\s*=")
_PLACEHOLDER = re.compile("\x00(\\d+)\x00")

# Declared lower bounds of the T+H v1.5 NAMELIST arrays (group -> variable -> bound),
# observed with the T+H v1.5 solver: x(L - 1) = ... aborts the run, x(L) = ... does not.
LOWER_BOUNDS = {
    "transient_boundary_definition": {"pv_numbers": 1},
    "tabular_data_definition": {"rowcolnum_to_primvarnum": 1, "units_of_primvar": 0},
    "component_diffusivities_in_phases": {
        "component": 1,
        "component_number": 1,
        "component_diffusivity": 1,
    },
    "region_specifics": {
        "top_cylinder_center_xyz": 1,
        "bot_cylinder_center_xyz": 1,
        "sphere_center_xyz": 1,
    },
    "surface_specifics": {
        "top_cylinder_center_xyz": 1,
        "bot_cylinder_center_xyz": 1,
        "circle_center_xyz": 1,
    },
}


def read_namelist(f) -> tuple[str, dict]:
    """Read a '&Group key = value, ... /' NAMELIST group; keys are lower-cased."""
    line = next_record(f, "NAMELIST group")
    while not line.strip():
        line = next_record(f, "NAMELIST group")

    parts = []
    while True:
        code = _code(line)
        parts.append(code)

        if "/" in _mask(code)[0]:
            break

        if f.peek() is None:
            first = parts[0].split()
            group = first[0] if first else "group"
            raise ValueError(
                f"NAMELIST {group} not closed by '/' before the end of the file"
            )

        line = f.next()

    text, literals = _mask(" ".join(parts))
    name, _, body = text.strip().lstrip("&").partition(" ")
    name, body = name.strip(), body.split("/", 1)[0]

    assignments = list(_ASSIGNMENT.finditer(body))
    if body.count("=") != len(assignments):
        # e.g. x(1,2) = ... or x(1:3) = ...; refuse rather than misassign values
        raise ValueError(f"unsupported NAMELIST assignment in group '{name}'")

    parsed = []
    for i, match in enumerate(assignments):
        end = assignments[i + 1].start() if i + 1 < len(assignments) else len(body)
        segment = _PLACEHOLDER.sub(
            lambda m: "'" + literals[int(m[1])].replace("'", "''") + "'",
            body[match.end() : end],
        )
        values = [to_value(token) for token in split_record(segment)]
        index = None if match[2] is None else int(match[2])
        parsed.append((match[1].lower(), index, values))

    # Every assignment fills {index: value}, and a null value leaves the item unchanged
    # (Fortran semantics). "x(i) = a, b" starts at x(i); "x = a, b" starts at the
    # declared lower bound L of x. Variables never assigned with an index are lists
    # whose item k is x(L + k), so L is not needed; for the others it must be known.
    indexed = {key for key, index, _ in parsed if index is not None}
    bounds = LOWER_BOUNDS.get(name.lower(), {})
    items = {}
    for key, index, values in parsed:
        if index is None and key in indexed:
            if key not in bounds and any(v is not None for v in values):
                raise ValueError(
                    f"whole-array and indexed assignments of '{key}' in group "
                    f"'{name}': the lower bound of '{key}' is unknown"
                )
            index = bounds.get(key)
        start = 0 if index is None else index

        entry = items.setdefault(key, {})
        entry.update({start + k: v for k, v in enumerate(values) if v is not None})

    # Variables assigned with an index are dicts; others are scalars or lists
    # (unassigned positions are None)
    group = {}
    for key, entry in items.items():
        if not entry:
            continue

        if key in indexed:
            group[key] = dict(sorted(entry.items()))
        else:
            values = [entry.get(k) for k in range(max(entry) + 1)]
            group[key] = values[0] if len(values) == 1 else values
    return name, group


def write_namelist(name: str, group: dict, indent: int = 0) -> list[str]:
    """Write a NAMELIST group; None values are omitted."""
    pad = " " * indent
    out = [f"{pad}&{name}\n"]

    for key, value in group.items():
        if value is None:
            continue

        with located(field=f"{name}.{key}"):
            if isinstance(value, dict):
                out += [
                    f"{pad}    {key}({i}) = {format_value(x)},\n"
                    for i, x in value.items()
                ]
            elif isinstance(value, (list, tuple, np.ndarray)):
                out.append(
                    f"{pad}    {key} = {', '.join(format_value(x) for x in value)},\n"
                )
            else:
                out.append(f"{pad}    {key} = {format_value(value)},\n")

    out.append(f"{pad}    /\n")

    return out


def read_items(f, n: int) -> list[Any]:
    """Read *n* list-directed items (element/connection/source names or numbers)."""
    return read_values(f, n) if n else []


def write_items(items: Sequence[Any]) -> list[str]:
    """Write one item per record."""
    out = []
    for i, item in enumerate(items):
        with located(field=f"item {i + 1}"):
            out.append(f"{format_value(item)}\n")

    return out


def read_member(f, count: str, key: str) -> dict:
    """Read a NAMELIST group followed by its list of names or numbers (if any)."""
    group = read_namelist(f)[1]

    if str(group.get("definition_mode", "NameList")).lower() in {
        "namelist",
        "numberlist",
    }:
        group[key] = read_items(f, group.pop(count, 0))

    return group


def write_member(
    name: str, group: dict, count: str, key: str, indent: int
) -> list[str]:
    """Write a NAMELIST group followed by its list of names or numbers (if any)."""
    group = dict(group)
    items = group.pop(key, None)

    if items is not None:
        group[count] = len(items)

    return write_namelist(name, group, indent) + write_items(items or [])


# Fixed-format reals. Fortran Ew.d/Fw.d input without a decimal point has d implied
# decimals ("    1000" in E10.4 is 0.1, verified with the T+H v1.5 solver). In the T+H manual
# formats, the number of decimals follows from the field width.
IMPLIED_DECIMALS = {10: 4, 14: 7, 15: 8, 20: 13}
_NO_POINT = re.compile(r"([+-]?\d+)(?:[EeDd]([+-]?\d+)|([+-]\d+))?")


def fortran_real(text: str, decimals: int) -> Optional[float]:
    """Read a fixed-format real field; None if blank."""
    text = text.replace(" ", "")
    if not text:
        return None

    match = None if "." in text else _NO_POINT.fullmatch(text)
    if not match:
        return to_float(text)

    exponent = int(match[2] or match[3] or 0) - decimals

    return float(f"{match[1]}e{exponent}")


class FortranRecordFormatter(RecordFormatter):
    """
    RecordFormatter for T+H fixed-format records.

    The reader applies Fortran implied decimals. The writer writes each field in the
    type of its descriptor (:func:`write_field`) and raises FieldError, with the
    record, the field and its columns, for a value the field cannot hold.

    record: name of the record ('PARAM.1'); names: canonical path of each field (a
    tuple: of every field, with the index of the value appended in a record written
    as several lines); label_fields: number of leading text fields that make the
    label of the record (an element name...).

    """

    def __init__(
        self,
        fmt,
        mode="r",
        free_format=False,
        space_between_values=False,
        multiple=False,
        delimiter=",",
        record: Optional[str] = None,
        names: Optional[Sequence[Optional[tuple]] | tuple] = None,
        label_fields: int = 1,
    ) -> None:
        super().__init__(
            fmt, mode, free_format, space_between_values, multiple, delimiter
        )
        tokens = fmt.split(",") if isinstance(fmt, str) else fmt
        self._tokens = [x.strip() for x in tokens]
        self._fields = (
            [(int(x[:-1]), x[-1]) for x in self._tokens] if mode != "r" else []
        )
        self.record, self.names, self.label_fields = record, names, label_fields

    def __call__(self, arg=None):
        if self.mode != "r":
            if self.free_format or arg is None:
                return super().__call__(arg)

            values, n = list(arg), len(self._tokens)
            if not self.multiple:
                return [self._write_record(values)]

            return [
                self._write_record(values[i : i + n], i)
                for i in range(0, len(values), n)
            ]

        data = arg if isinstance(arg, str) else arg.next()
        if self.free_format or "," in data:
            return super().__call__(data)

        i, out = 0, []
        for token in self.format:
            n = int(token[:-1].split(".")[0])
            field = data[i : i + n]
            if token[-1] in "fe":
                out.append(fortran_real(field, IMPLIED_DECIMALS.get(n, 0)))
            else:
                field = field.rstrip()
                out.append(TOKENS[token[-1]]["converter"](field) if field else None)
            i += n

        return out

    def _write_record(self, values: list, offset: int = 0) -> str:
        space = self.space_between_values
        try:
            return (
                "".join(
                    field_text(value, width, kind, space)
                    for value, (width, kind) in zip(values, self._fields)
                )
                + "\n"
            )
        except FieldError:
            pass

        # locate the first field that fails
        column = 1
        for i, (value, (width, kind)) in enumerate(zip(values, self._fields)):
            try:
                field_text(value, width, kind, space)
            except FieldError as e:
                raise e.locate(
                    record=self.record,
                    label=self._label(values, i),
                    path=self._name(offset + i),
                    columns=(column, column + width - 1),
                ) from None
            column += width

        raise AssertionError("unreachable")  # pragma: no cover

    def _label(self, values: list, index: int) -> Optional[str]:
        """The label of the record: its leading text fields, unless they are wrong."""
        n = self.label_fields
        if index < n or not all(
            isinstance(v, str) and t[-1] in "sS"
            for v, t in zip(values[:n], self._tokens[:n])
        ):
            return None

        return "".join(values[:n]).strip() or None

    def _name(self, index: int) -> Optional[tuple]:
        if self.names is None:
            return None
        if isinstance(self.names, tuple):
            return (*self.names, index) if self.multiple else self.names

        return self.names[index] if index < len(self.names) else None


class FortranRecords:
    """
    Mixin building the block's readers and writers with
    :class:`FortranRecordFormatter`, and naming the block in its FieldError.

    records: names of the records keyed like formats ('PARAM.1'); fields: canonical
    paths of their fields keyed like formats (see FortranRecordFormatter.names);
    label_fields: leading text fields making the label of a record.

    """

    records: dict = {}
    fields: dict = {}
    label_fields: int = 1

    def read(self, f, *args, **kwargs) -> dict:
        if not hasattr(self, "readers"):
            self.readers = {
                k: FortranRecordFormatter(
                    v, mode="r", free_format=self.free_format, delimiter=self.delimiter
                )
                for k, v in self.formats.items()
            }

        return super().read(f, *args, **kwargs)

    def write(self, parameters: Optional[dict] = None, *args, **kwargs) -> list[str]:
        if not hasattr(self, "writers"):
            self.writers = {
                k: FortranRecordFormatter(
                    v,
                    mode="w",
                    free_format=self.free_format,
                    space_between_values=self.space_between_values,
                    multiple=k in self.multiples,
                    delimiter=self.delimiter,
                    record=self.records.get(k),
                    names=self.fields.get(k),
                    label_fields=self.label_fields,
                )
                for k, v in self.formats.items()
            }

        with located(block=self.name):
            return super().write(parameters, *args, **kwargs)


# Primary variables: one record of 6E20.13
_PV_READER = FortranRecordFormatter(",".join(6 * ["20f"]))
_PV_WRITER = FortranRecordFormatter(
    ",".join(6 * ["20f"]), mode="w", multiple=True, names=()
)


def read_primary_variables(line: str) -> list[float]:
    """Read primary variables from a 6E20.13 record."""
    return DataBlock.prune_values(_PV_READER(line))


def write_primary_variables(values: Optional[Sequence[float]]) -> list[str]:
    """Write primary variables as 6E20.13 records; a blank record if empty."""
    return _PV_WRITER(list(values)) if values else ["\n"]


class HydrateBlock(FortranRecords, DataBlock):
    """Base class for T+H data blocks: T+H headers and merging updates."""

    formats = {}

    def _write_header(self) -> str:
        return f"{self.name}{RULER[max(len(self.name) - 5, 0) :]}\n"

    def update(self, parameters: dict, data: dict) -> None:
        for key, value in data.items():
            if isinstance(value, dict) and isinstance(parameters.get(key), dict):
                for k, v in value.items():
                    if isinstance(v, dict) and isinstance(parameters[key].get(k), dict):
                        parameters[key][k].update(v)
                    else:
                        parameters[key][k] = v
            else:
                parameters[key] = value
