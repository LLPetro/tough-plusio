"""
Optional TOUGH+HYDRATE helpers.

These functions are not used by :func:`toughio.read_input` and
:func:`toughio.write_input` (``file_format="tough+hydrate"``), which only parse and
write files. :class:`FieldError` is what the writer raises for a value that a record
cannot hold.
"""

from .mesh import mesh_parameters, set_activity
from .validate import validate
from .._io.input.tough_hydrate._helpers import FieldError


__all__ = ["FieldError", "mesh_parameters", "set_activity", "validate"]
