from ._tough_hydrate import read_element, read_out, read_save
from .._helpers import register


register("tough+hydrate-element", [], read_element)
register("tough+hydrate-save", [], read_save)
register("tough+hydrate-out", [], read_out)
