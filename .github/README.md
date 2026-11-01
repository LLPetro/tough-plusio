# tough-plusio

**[toughio](https://github.com/keurfonluu/toughio) with TOUGH+HYDRATE v1.5 support**

tough-plusio is a fork of toughio, the Python library for pre- and post-processing of
[TOUGH](https://tough.lbl.gov/) simulations. It adds the input and output formats of
TOUGH+HYDRATE v1.5 (T+H) and carries 13 fixes to toughio itself. Everything else is
toughio as published upstream: the `toughplus` branch is the current toughio `master`
plus the commits of this fork. The TOUGH+HYDRATE simulator is not included.

## Features

- **T+H input files.** `toughio.read_input` and `toughio.write_input` with
  `file_format="tough+hydrate"` read and write `INFILE` and separate `MESH`, `INCON`
  and `GENER` files: all T+H v1.5 data blocks except MESHMAKER and UPDATE, 5- or
  8-character element names, continuation runs.
- **Typed writing.** Each value is written in the Fortran type of its field: integers
  without a decimal point, reals with one, ASCII text, `.TRUE.`/`.FALSE.`. A value that
  its field cannot hold raises `toughio.hydrate.FieldError`, which names the block,
  record, field and columns, instead of producing a shifted or truncated file.
- **T+H outputs.** The main output, `Plot_Data_Elem` and `SAVE` with
  `toughio.read_output`; `Hydrate_Status` and `*_Time_Series` with `toughio.read_table`.
- **Helpers.** `toughio.hydrate.mesh_parameters` and `toughio.hydrate.set_activity`
  turn a `toughio.Mesh` into T+H elements and connections, including inactive and
  time-variable boundary cells. `toughio.hydrate.validate` lists the problems it finds
  according to the T+H manual; reading and writing never validate.
- **Fixes to toughio**, listed [below](#fixes-to-toughio).

## Installation

The distribution is named `toughplusio`; the import name stays `toughio`. It replaces
toughio, so do not install both in the same environment.

```bash
pip install "toughplusio @ git+https://github.com/LLPetro/tough-plusio@th-0.2.0"
```

Releases are the `th-x.y.z` [tags](https://github.com/LLPetro/tough-plusio/tags); pin a
tag rather than the branch.

## Usage

T+H file names are the same as TOUGH2 file names, so always give the format:

```python
import toughio
from toughio import hydrate

parameters = toughio.read_input("INFILE", file_format="tough+hydrate")
parameters["options"]["n_cycle"] = 100

try:
    toughio.write_input("INFILE", parameters, file_format="tough+hydrate")
except hydrate.FieldError as e:
    print(e)  # e.g. PARAM.1 options.n_cycle_print (columns 13-16): integer 10000000 does not fit in 4 characters

elements = toughio.read_output("Plot_Data_Elem", file_format="tough+hydrate-element")
status = toughio.read_table("Hydrate_Status", file_format="tough+hydrate")
```

- [T+H guide](https://github.com/LLPetro/tough-plusio/blob/toughplus/doc/source/guide/tough_hydrate.rst):
  data blocks, separate files, meshes and outputs
- [Parameter reference](https://github.com/LLPetro/tough-plusio/blob/toughplus/docs/toughplus/schema/canonical-fields.md):
  every T+H key with its type and Fortran name
- [toughio documentation](https://keurfonluu.github.io/toughio/) for everything else

## Fixes to toughio

The fixes are a single commit on toughio `master`, with regression tests:

- Fix frame and unit-row parsing in CSV output
- Support CSV snapshots without a time value
- Parse Fortran `D` and omitted-`E` exponents consistently
- Distinguish connection index vectors from label pairs
- Keep output labels aligned with boolean row masks
- Read CLI extraction geometry through the input reader
- Return shaped empty arrays for meshes without connections
- Avoid terminal-dependent user lookup in HDF5 files
- Omit compression options for the HDF5 LZF filter
- Store NumPy Unicode arrays as HDF5 strings
- Preserve the mesh class in HDF5 files while reading legacy files
- Resolve native executables from `PATH` before running
- Convert mesh spacings to floating point before construction

## Branches

| Branch | Content |
|---|---|
| `toughplus` (default) | toughio `master` + the fixes + T+H support; releases are tagged here |
| `master` | unmodified mirror of toughio `master` |

Maintenance notes for this fork are in
[docs/toughplus](https://github.com/LLPetro/tough-plusio/tree/toughplus/docs/toughplus).
The original toughio README is
[README.rst](https://github.com/LLPetro/tough-plusio/blob/toughplus/README.rst).

## Credits and license

toughio is developed by Keurfon Luu. If you use it, please cite
K. Luu, *toughio: Pre- and post-processing Python library for TOUGH*, Journal of Open
Source Software (2020), [doi:10.21105/joss.02412](https://doi.org/10.21105/joss.02412).
TOUGH+HYDRATE is developed at Lawrence Berkeley National Laboratory.

tough-plusio keeps toughio's
[BSD 3-Clause license](https://github.com/LLPetro/tough-plusio/blob/toughplus/LICENSE).
