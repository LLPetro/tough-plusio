from .boundaries import BOUNDARIES
from .conne import CONNE
from .diffusion import DIFFUSION
from .eleme import ELEME
from .endfi import ENDFI
from .ext_incon import EXT_INCON
from .gener import GENER
from .hydrate import HYDRATE
from .incon import INCON
from .indom import INDOM
from .interfaces import INTERFACES
from .memory import MEMORY
from .param import PARAM
from .rocks import ROCKS
from .rpcap import RPCAP
from .solvr import SOLVR
from .ss_groups import SS_GROUPS
from .subdomains import SUBDOMAINS
from .times import TIMES
from .title import TITLE
from ...tough.blocks import ENDCY, START


# Order in which blocks are written (Table 4.1 of the T+H v1.5 manual)
registered_blocks = [
    TITLE,
    MEMORY,
    ROCKS,
    HYDRATE,
    DIFFUSION,
    RPCAP,
    START,
    PARAM,
    SOLVR,
    TIMES,
    ELEME,
    CONNE,
    INDOM,
    INCON,
    EXT_INCON,
    BOUNDARIES,
    GENER,
    SUBDOMAINS,
    INTERFACES,
    SS_GROUPS,
    ENDCY,
    ENDFI,
]
