from __future__ import annotations

from .._helpers import (
    FieldError,
    HydrateBlock,
    as_integer,
    as_text,
    format_value,
    located,
    read_values,
    write_field,
    write_values,
)


FIELDS = {
    "SEQUENCE": ("first_element", "last_element", "stride"),
    "LIST": ("n_elements", "n_per_row"),
    "COLUMN": ("n_states",),
}
COLUMN = ("first_element", "n_elements", "stride")
CARTESIAN = ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")
CYLINDRICAL = ("rmin", "rmax", "zmin", "zmax")


class EXT_INCON(HydrateBlock):
    name = "EXT-INCON"

    def _read(self, f, *args, **kwargs) -> dict:
        """Read EXT-INCON block data (free format)."""
        entries = []

        for _ in range(read_values(f, 1)[0]):
            kind = str(read_values(f, 1)[0]).upper()
            entry = {"type": kind}

            if kind == "GEOMETRY":
                values = read_values(f)
                entry.update(
                    zip(CARTESIAN if len(values) >= 6 else CYLINDRICAL, values)
                )

            elif kind == "COLUMN":
                n = read_values(f, 1)[0]
                entry.update(zip(COLUMN, read_values(f, 3)))
                entry["states"] = [_read_state(f) for _ in range(n)]

            else:
                entry.update(zip(FIELDS[kind], read_values(f)))

                if kind == "LIST":
                    entry["elements"] = read_values(f, entry.pop("n_elements"))

            if kind != "COLUMN":
                entry.update(_read_state(f))

            entries.append(entry)

        return {"extended_initial_conditions": entries} if entries else {}

    def _write(self, parameters: dict, *args, **kwargs) -> list[str]:
        """Write EXT-INCON block data."""
        entries = parameters["extended_initial_conditions"]
        out = write_values([len(entries)])

        for i, entry in enumerate(entries):
            with located(prefix=("extended_initial_conditions", i)):
                out += _write_entry(entry)

        return out

    def _write_conditions(self, parameters: dict, *args, **kwargs) -> bool:
        return bool(parameters.get("extended_initial_conditions"))


def _write_entry(entry: dict) -> list[str]:
    with located(path=("type",)):
        kind = as_text(entry.get("type")).upper()
    out = [f"{kind}\n"]

    if kind == "GEOMETRY":
        keys = CARTESIAN if "xmin" in entry else CYLINDRICAL
        out += _values(entry, keys, len(keys) * ["real"])

    elif kind == "LIST":
        elements = list(entry["elements"])
        with located(path=("n_per_row",)):
            n = as_integer(entry.get("n_per_row") or len(elements))
        n = n if n > 0 else max(len(elements), 1)
        out += write_values([len(elements), n])
        for i in range(0, len(elements), n):
            out += write_values(
                elements[i : i + n], names=[("elements", j) for j in range(i, i + n)]
            )

    elif kind == "COLUMN":
        out += write_values([len(entry["states"])])
        out += _values(entry, COLUMN, [None, "integer", "integer"])
        for i, state in enumerate(entry["states"]):
            with located(prefix=("states", i)):
                out += _write_state(state)

    else:
        out += _values(entry, FIELDS[kind], [None, None, "integer"])

    if kind != "COLUMN":
        out += _write_state(entry)

    return out


def _values(entry: dict, keys: tuple, kinds: list) -> list[str]:
    return write_values(
        [entry.get(k) for k in keys], kinds=kinds, names=[(k,) for k in keys]
    )


def _read_state(f) -> dict:
    values = read_values(f)
    return {"phase_state": str(values[0]), "values": values[1:]}


def _write_state(data: dict) -> list[str]:
    """The state record: the state index unquoted (3 characters), then the reals."""
    state = data.get("phase_state")
    try:
        text = write_field(state, "3s").strip()
        if not text or " " in text:
            raise FieldError("not_text", "text", state)
    except FieldError as e:
        raise e.locate(path=("phase_state",))

    values = []
    for i, x in enumerate(data.get("values", [])):
        try:
            values.append(format_value(x, "real"))
        except FieldError as e:
            raise e.locate(path=("values", i))

    return [" ".join([text, *values]) + "\n"]
