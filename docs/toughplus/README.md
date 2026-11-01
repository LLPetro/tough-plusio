# toughplusio fork notes

This directory holds the documentation that belongs to the fork only.

| Path | Content |
|---|---|
| [schema/canonical-fields.md](schema/canonical-fields.md) | TOUGH+HYDRATE canonical parameters (keys, types, Fortran names) |
| [schema/editor-metadata-contract.md](schema/editor-metadata-contract.md) | What an input editor may rely on |
| [baseline/](baseline/) | Reviewed upstream test baseline and CI drivers |

User documentation: `doc/source/guide/tough_hydrate.rst`. The repository landing page
is `.github/README.md`: GitHub shows it before the root `README.rst`, which stays the
upstream file. Its install line names the latest `th-x.y.z` tag; update it with each
release.

## Layout

```text
master          = keurfonluu/toughio master (8f8b4fd7)
fixes/*         fixes to toughio, one commit per topic (see scripts/additive_manifest.toml)
toughplus-base  = master + merged fixes/*
toughplus       = toughplus-base + distribution metadata + T+H files and 3 registration imports
```

`master` and `toughplus` (the default branch) are published with the `th-x.y.z` tags.
The commits of `fixes/*` and `toughplus-base` are in the history of `toughplus`; the CI
gate recreates these branches from the pins of `scripts/additive_manifest.toml`. When
toughio `master` moves, the topics, `toughplus-base` and `toughplus` are rebuilt on it
and the manifest is re-pinned.

T+H code lives only in new files:

- `toughio/_io/input/tough_hydrate/` - `read`/`write`, shared helpers, one DataBlock per
  keyword (`blocks/`); CONNE, ELEME, GENER, RPCAP, START, TIMES and ENDCY reuse the
  upstream blocks.
- `toughio/_io/output/tough_hydrate/` - main output (elements and connections),
  `Plot_Data_Elem`, `SAVE`.
- `toughio/_io/table/tough_hydrate/` - `Hydrate_Status` and `*_Time_Series`.
- `toughio/hydrate/` - optional `validate`, `set_activity`, `mesh_parameters`.
- `tests/tough_hydrate/` - write/read tests; official decks and solver outputs only when
  `TOUGH_HYDRATE_REFERENCE_DIR` / `TOUGH_HYDRATE_OUTPUT_DIR` are set.

## Solver findings used by the implementation

Verified with the T+H v1.5 solver on its 15 sample decks:

- Every deck read and rewritten by this format runs and gives a SAVE file identical to
  the original deck after two time steps (15/15, maximum relative difference 0).
- A synthetic deck using DIFFUSION, SOLVR, TIMES options, EXT-INCON (SEQUENCE, LIST,
  GEOMETRY), SUBDOMAINS (Sequence, NameList), SS_GROUPS, GENER well controls and ROCKS
  NAD 2/5/6/8 runs clean and writes the expected time-series files.
- Fixed-format numbers written without exponent (e.g. `    3.1416`) are read correctly.
- INCON/INDOM/PARAM.4 primary variables are read from a single 6E20.13 record; a following
  record whose element field is blank ends INCON.
- Keyword records may carry rulers or comments (`ELEME ---  33 ...`,
  `HYDRATE--1--comment`); unknown blocks such as `FOFT` are ignored by the solver.
- With 8-character element names: CONNE needs two terminating records (an empty line
  alone makes the solver read the next block as a connection); the activity must be
  written in columns 82-84 (`V01`; a single `V` in column 82, as printed in the manual,
  is not recognised); and names that only differ after their 5th character make the
  solver ignore connections. With names unique in their first 5 characters, an 8-character
  deck gives SAVE results identical to the 5-character deck.
- SAVE files are valid INCON input; SAVE -> INCON restarts run clean. NAD = 6 also
  requires `porosity_permeability_dependence = .TRUE.` and MOP(13) > 0.
- ROCKS NAD = 8 reads `&Slippage_Turbulence_Info` with the members `MediumKlinkFlow_F`,
  `MediumKnudsenFlow_F`, `MediumDustyGasModel_F`, `MediumTurbulentFlow_F`,
  `Option_KlinkenbergParam`; turning any flag on requires RealGas data blocks.