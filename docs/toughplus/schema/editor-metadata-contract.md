# Contract between tough-plusio and an input editor

tough-plusio follows toughio: the library parses and writes files and does not publish
field-level metadata (labels, units, widgets, enumerations). An application that builds
forms owns that metadata. This document fixes what the application may rely on.

## What the library guarantees

1. **Keys.** The canonical keys of [canonical-fields.md](canonical-fields.md) are stable
   within a `th-x.y` tag series. A renamed or removed key is a breaking change and is
   listed in the release notes.
2. **Types.** Values are `int`, `float`, `str`, `bool`, `list` or `dict` (indexed NAMELIST
   variables are `dict[int, ...]` keyed by the Fortran index; `units_of_primvar` starts
   at 0). Numbers read from files keep the type written in the
   file (`1` is an int, `1.0` a float) for NAMELIST and list-directed records; fixed
   format fields have the type of their Fortran descriptor.
3. **Derived counts.** Lengths of lists are never stored; editors must not ask users for
   them.
4. **Absent vs empty.** For `elements`, `connections`, `initial_conditions` and
   `generators`, a missing key means the block is absent and an empty dict/list means the
   block is present without records (written back as an empty block). For the other list
   blocks (`subdomains`, `interfaces`, `ss_groups`, `transient_boundaries`,
   `extended_initial_conditions`) an empty list is the same as absent: the solver
   requires at least one item, so an empty block is neither read nor written.
5. **Round trip.** `read(write(p)) == normalize(p)` for parameters made of documented
   keys. `normalize` applies these rules:
   - `None` as a dict value means "not given": the key is dropped. This includes `None`
     entries of indexed NAMELIST variables (`{1: None, 2: 2e-9}` becomes `{2: 2e-9}`).
   - `None` inside a list of a NAMELIST or list-directed record is a null value and keeps
     its position (`[1, None, 3]`); trailing `None` items are dropped.
   - A NAMELIST array with a single item is a scalar (`[3]` becomes `3`), because Fortran
     input cannot tell them apart. Editors must accept a scalar or a list for NAMELIST
     array variables.
   - Empty lists of the blocks listed in item 4 are dropped.

   Numbers in list-directed and NAMELIST records are written with the shortest text that
   reads back to the same double, so they are exactly equal. Numbers in fixed-format
   fields are equal within the width of their field (E10.4, E14.7, E15.8, E20.13).
6. **Fortran semantics on read.** Fixed-format reals without a decimal point have the
   implied decimals of their descriptor (`      1000` in an E10.4 field is `0.1`, as for
   the solver). A NAMELIST null keeps the value assigned earlier in the same group
   (`x = 2.5, x = ,` gives `2.5`; `x(1) = , 2` leaves `x(1)` unset). A whole-array
   assignment starts at the declared lower bound of the array (rule 3 of
   [canonical-fields.md](canonical-fields.md)); mixing it with indexed assignments of an
   array whose lower bound is not known raises `ValueError`.
7. **No validation on I/O.** `read_input`/`write_input` accept any values the formats can
   hold. `toughio.hydrate.validate(parameters)` returns manual-rule violations as strings;
   editors may display them.
8. **Typed writing.** Each value is written in the type of its field (rule 9 of
   [canonical-fields.md](canonical-fields.md)). A value its field cannot hold raises
   `toughio.hydrate.FieldError` (a `ValueError`) and nothing is returned for the block:
   the writer never truncates a value, writes it in another type or past its columns.
   Its attributes are stable within a tag series: `reason` (`too_wide`, `not_integer`,
   `not_real`, `not_finite`, `not_text`, `not_logical`, `not_ascii`,
   `control_character`, `out_of_range`, `not_a_value`, `negative_time_step`), `kind`
   (`integer`, `real`, `text`, `logical`, `value`), `value`, `width`, and where it is,
   as far as known (else `None`): `block`, `record` (`PARAM.1`), `label` (element,
   medium...), `field` (NAMELIST `Group.variable`), `path` (canonical keys, e.g.
   `("rocks", "SAND", "density")`) and `columns` (first, last). Editors should check
   ranges first; this is the last line of defence against a deck the solver misreads.

## What the application owns

- Field labels, help texts, units, enumerations, default values and widgets, keyed by the
  canonical path (e.g. `rocks.*.permeability`, `options.n_cycle`, `hydrate.kinetics.area_factor`).
- Project storage. Projects store canonical parameters, never fixed-format text. Old
  project files of the previous fork schema are not converted: re-import the INFILE.
- Mapping between mesh selections and `elements[*].activity` (use
  `toughio.hydrate.set_activity` and `mesh_parameters`).
- Text fidelity, if required (comments and column alignment are not preserved by the
  library).

## Change control

A pull request that renames, removes or changes the type of a canonical key must update
[canonical-fields.md](canonical-fields.md), the tests in `tests/tough_hydrate` and the
release notes in the same change.