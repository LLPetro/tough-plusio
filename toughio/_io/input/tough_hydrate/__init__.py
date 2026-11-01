from ._read import read, read_buffer
from ._write import write, write_buffer
from .._helpers import register


__all__ = ["read", "read_buffer", "write", "write_buffer"]


register("tough+hydrate", [], read, write)
