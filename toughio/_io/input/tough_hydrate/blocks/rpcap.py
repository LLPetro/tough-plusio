from __future__ import annotations

from .._helpers import FortranRecords
from ...tough.blocks import RPCAP as _RPCAP


class RPCAP(FortranRecords, _RPCAP):
    """Upstream RPCAP block read with Fortran implied decimals and typed fields."""
