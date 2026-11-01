# TOUGH+HYDRATE canonical parameters

`toughio.read_input(path, file_format="tough+hydrate")` returns, and
`toughio.write_input(path, parameters, file_format="tough+hydrate")` accepts, the
dictionary described here.

Rules:

1. Same meaning, same key: when a T+H field means the same thing as an upstream toughio
   field, the upstream key is used (`rocks`, `options`, `extra_options`, `default`,
   `elements`, `connections`, `initial_conditions`, `generators`, `solver`, `times`, ...).
2. T+H-only concepts use new snake_case keys. Keys that upstream already uses with another
   meaning are never reused (`diffusion`, `boundary_conditions`).
3. NAMELIST groups keep their Fortran variable names, lower-cased (`interface_name`,
   `definition_mode`, `pv_numbers`, ...). Variables assigned with an index at least once
   (`units_of_Primvar(3)`) become dicts keyed by the Fortran index (`{3: "C"}`). A
   whole-array assignment of such a variable fills indices from the declared lower bound
   of the array: 0 for `units_of_Primvar`, 1 for the other T+H v1.5 arrays (`pv_numbers`,
   `RowColNum_to_PrimVarNum`, `component`, `component_number`,
   `component_diffusivity`, `*_center_xyz`), as probed with the solver. So
   `units_of_Primvar(0) = 'sec', units_of_Primvar = 'sec', 'Pa', ' ', 'C'` gives
   `{0: "sec", 1: "Pa", 2: " ", 3: "C"}`. Mixing both forms for a variable whose lower
   bound is not known raises `ValueError` instead of guessing. Other variables are scalars
   or lists; item `k` of a list is `x(L + k)` and is written back as `x = ...`, so the
   lower bound is not needed.
4. Counts that only describe the length of a list are derived when writing and are not
   stored (`NCom`, `N_ThC`, `NumPrintTimes`, `number_of_interfaces`, `number_of_SS`, ...).
   Counts that carry information (e.g. `number_of_elements` of a `Sequence` region) stay.
5. A missing value is omitted. `None` on write leaves a fixed-format field blank and
   becomes a Fortran null value in list-directed and NAMELIST records (`2, , 4`).
6. ELEME, CONNE, INCON and GENER present without records read as an empty dict/list and
   are written back as empty blocks. Empty NAMELIST-based lists (`subdomains`,
   `interfaces`, `ss_groups`, `transient_boundaries`, `extended_initial_conditions`) are
   treated as absent.
7. Values are read with Fortran semantics: fixed-format reals without a decimal point have
   the implied decimals of the manual descriptor (E10.4, E14.7, E15.8, E20.13); a null in
   `x(1) = , 2` leaves `x(1)` unset.
8. Reading and writing never validate; `toughio.hydrate.validate(parameters)` is optional.
9. Values are written in the type of their field, whatever their Python type:
   - fixed-format integer fields (`I`: NAD, MOP, NSEQ, counts...) hold whole numbers
     (`int`, NumPy integers, whole floats such as `100.0`, integer literals) written as
     digits, never in scientific notation;
   - fixed-format real fields (`E`) hold finite numbers (or numeric literals), written
     with a decimal point so that no implied decimals apply;
   - fixed-format text fields (`A`: names, states, solver options) hold ASCII text
     without control characters; blanks on the padding side may be dropped;
   - list-directed and NAMELIST values have the declared type where the table below
     gives one (MEMORY, HYDRATE, EXT-INCON counts and bounds) and else the type of the
     value: `bool`/NumPy bool as logical, integers within the default INTEGER range
     (±2147483647), finite floats, text without control characters;
   - TITLE is one record (no line break).

   A value its field cannot hold (wider than the field, a fraction in an integer field,
   `nan`, a list where a value is expected, non-ASCII or a line break in a name, a single
   negative `t_steps`, which DELTEN would read as a record count) raises
   `toughio.hydrate.FieldError` naming the block, record, field and columns.

## Top level

| Key | Type | Block / record | Notes |
|---|---|---|---|
| `title` | str | TITLE (first record) | up to 132 characters, never truncated |
| `eos` | str | MEMORY.2 `HYDRATE_EOS` | e.g. `HYDRATE-EQUILIBRIUM`, `HYDRATE-KINETIC` |
| `n_component` | int | MEMORY.3 `NumCom` | upstream key |
| `n_phase` | int | MEMORY.3 `NumPhases` | upstream key |
| `do_diffusion` | bool | MEMORY.3 `binary_diffusion` | upstream key |
| `label_length` | int | MEMORY.4 `ElemNameLength` | 5 or 8; also returned for separate files |
| `memory` | dict | MEMORY.3-9 | see below |
| `rocks` | dict | ROCKS/MEDIA, INDOM | keyed by medium name |
| `hydrate` | dict | HYDRATE | |
| `multiphase_diffusion` | dict | DIFFUSION | |
| `default` | dict | RPCAP, PARAM.3-4 | |
| `start` | bool | START / RANDOMN | upstream key |
| `options`, `extra_options` | dict | PARAM | upstream keys |
| `solver` | dict | SOLVR | upstream keys |
| `times`, `times_options` | list, dict | TIMES | |
| `elements`, `connections` | dict | ELEME, CONNE | upstream keys |
| `initial_conditions` | dict | INCON | upstream key |
| `continuation_run` | dict | INCON `:::` + `&Data_For_Continuation_Run` | |
| `extended_initial_conditions` | list | EXT-INCON | |
| `transient_boundaries` | list | BOUNDARIES | |
| `generators` | list | GENER | upstream key |
| `subdomains`, `interfaces`, `ss_groups` | list | SUBDOMAINS, INTERFACES, SS_GROUPS | |
| `end` | str | ENDCY / ENDFI | `"ENDCY"` (default) or `"ENDFI"` |

## MEMORY (`memory`)

| Key | Fortran | Type |
|---|---|---|
| `n_equation` | NumEqu | int |
| `coordinate_system` | coordinate_system | str |
| `max_n_elements`, `max_n_connections` | Max_NumElem, Max_NumConx | int |
| `active_connections_only`, `boundaries_in_matrix` | active_conx_only, boundaries_in_matrix | bool |
| `max_n_sources`, `max_n_media` | MaxNum_SS, MaxNum_Media | int |
| `element_by_element_properties`, `porosity_permeability_dependence`, `scaled_capillary_pressure` | MEMORY.7 | bool |
| `tortuosity_method` | Option_tortuosity_CompuMethod | str |
| `coupled_geochemistry`, `geochemistry_update` | MEMORY.8 | bool, str |
| `coupled_geomechanics`, `geomechanics_code`, `geomechanics_update`, `n_geomechanics_parameters` | MEMORY.9 | bool, str, str, int |

## ROCKS / MEDIA (`rocks[name]`)

| Key | Fortran | Record |
|---|---|---|
| `density`, `porosity`, `conductivity`, `specific_heat` | mediaDensG, mediaPoros, mediaKThrW, mediaSpcHt | ROCKS.1 (upstream keys) |
| `permeability` | mediaPerm(1:3) | ROCKS.1; float if the three values are equal, else list |
| `grain_radius` | PoMedRGrain | ROCKS.1 (columns 81-90) |
| `compressibility`, `expansivity`, `conductivity_dry`, `tortuosity`, `klinkenberg_parameter` | mediaCompr, mediaExpan, mediaKThrD, mediaTortu, mediaKlink | ROCKS.1.1 (upstream keys) |
| — | mediaOrgCF | ROCKS.1.1 column 6, not used by T+H v1.5, not read |
| `critical_saturation`, `permeability_exponent` | mediaCritSat, mediaPermExpon | ROCKS.1.1 |
| `porosity_stress_beta`, `permeability_porosity_gamma`, `porosity_zero_stress` | mediaBeta, mediaGama, PhiZeroStress | ROCKS.1.1 |
| `relative_permeability`, `capillarity` | ROCKS.1.2, ROCKS.1.3 | `{"id": int, "parameters": list}` (upstream) |
| `porosity_polynomial` | PhiPolyOrder, PhiCoeff | NAD = 5: `{"order": int, "coefficients": list}` |
| `cementing_compressibility` | LoComp, SatAtLoComp, HiComp, SatAtHiComp, DeltaSat | NAD = 6: list |
| `slippage_turbulence` | `&Slippage_Turbulence_Info` | NAD = 8: NAMELIST dict |
| `phase_state`, `initial_condition` | INDOM.1 StateIndex, INDOM.2 | INDOM (upstream `initial_condition`) |

`NAD` is not stored: it is derived from the keys present when writing (8, 6, 5, 2, 1 or 0).
For NAD = 8, member names come from the solver binary (`MediumKlinkFlow_F`,
`MediumKnudsenFlow_F`, `MediumDustyGasModel_F`, `MediumTurbulentFlow_F`,
`Option_KlinkenbergParam`); with T+H v1.5 only all-false flags run.

## HYDRATE (`hydrate`)

| Key | Fortran | Type |
|---|---|---|
| `components` | HYDRATE.2 nameG, hydrN, moleF | list of `{"name", "hydration_number", "mole_fraction"}` |
| `thermal_conductivity`, `specific_heat`, `density` | HYDRATE.4, .6, .8 polynomial coefficients | list (count derived; empty density list uses Ballard) |
| `inhibitor` | HYDRATE.9 | absent if `inhibitor_flag = .FALSE.`; else `{"max_temperature_shift", "mole_fraction_at_max_shift", "molecular_weight", "density", "dissolution_enthalpy", "specific_heat": [3]}` |
| `equation_option` | EquationOption | int |
| `reaction_type` | Reaction_Type | `"EQUILIBRIUM"` or `"KINETIC"` (quotes removed) |
| `kinetics` | HYDRATE.12 | `{"activation_energy", "rate_constant", "area_factor"}` (kinetic only) |

## DIFFUSION (`multiphase_diffusion`)

`&Diffusion_Key_Parameters` variables (lower-cased) plus `phases`: a list of
`&Component_Diffusivities_in_Phases` groups, e.g.
`{"phase": "Aqueous", "phase_number": 2, "component": {1: "CH4"}, "component_diffusivity": {1: 1e-9}}`.

## PARAM (`options`, `extra_options`, `default`)

| Key | Fortran | Record |
|---|---|---|
| `options.n_iteration`, `verbosity`, `n_cycle`, `n_second`, `n_cycle_print` | Max_NumNRIterations, OutputOption, Max_NumTimeSteps, iCPU_MaxTime, PRINT_frequency | PARAM.1 (upstream) |
| `extra_options[i]` | MOP(i), i = 1..24 | PARAM.1 (upstream) |
| `options.gas_diffusion_coefficient` | BaseDiffusionCoef | PARAM.1 |
| `options.temperature_dependence_gas`, `effective_strength_vapor` | DiffusionExpon, DiffusionStrength | PARAM.1 (upstream TEXP, BE) |
| `options.n_cycle_save`, `n_cycle_time_series` | SAVE_frequency, TimeSeries_frequency | PARAM.1 |
| `options.t_ini`, `t_max`, `t_steps`, `t_step_max` | TimeOrigin, SimulationTimeEnd, InitialTimeStep, MaxTimeStep | PARAM.2 (upstream); list `t_steps` = PARAM.2.1 records |
| `options.track_element` | TrackElemName | PARAM.2 |
| `options.gravity`, `t_reduce_factor`, `mesh_scale_factor` | gravity, Dt_reducer, scale | PARAM.2 (upstream) |
| `options.eps1`, `eps2`, `w_upstream`, `w_newton`, `derivative_factor` | rel/abs_convergence_crit, W_upstream, W_NRIteration, derivative_increment | PARAM.3 (upstream) |
| — | U_p | PARAM.3, not used by T+H v1.5, not read |
| `options.w_implicitness` | W_implicitness | PARAM.3 |
| `options.p_overshoot`, `t_overshoot`, `s_overshoot` | P/T/S_overshoot | PARAM.3 |
| `default.phase_state` | DefaultStateIndex | PARAM.3 |
| `default.initial_condition` | default_initial_cond | PARAM.4 (upstream) |
| `default.relative_permeability`, `default.capillarity` | RPCAP / WETTABILITY | upstream RPCAP block |

## SOLVR (`solver`) and TIMES (`times`, `times_options`)

`solver`: `method`, `z_precond`, `o_precond`, `rel_iter_max`, `eps` (upstream keys).
`times`: list of print times. `times_options`: `max_n_times` (Max_NumPrintTimes),
`t_step_max` (TimeStepMax_PostPrint), `t_increment` (PrintTimeIncrement).

## ELEME, CONNE (`elements`, `connections`)

Upstream keys (`material`, `volume`, `heat_exchange_area`, `permeability_modifier`,
`center`, `nseq`, `nadd`; `permeability_direction`, `nodal_distances`, `interface_area`,
`gravity_cosine_angle`, `radiant_emittance_factor`) plus:

| Key | Fortran | Notes |
|---|---|---|
| `elements[label]["activity"]` | elem_activity, columns 82-84 | `"I"` or `"V01"`...`"V99"`, also for 8-character names (verified with the solver); distinct from the VTK `active` flag of `toughio.Mesh` |

Records after `+++` (cross references written by the solver) are skipped.
`toughio.hydrate.mesh_parameters(mesh)` builds these keys from a `toughio.Mesh`.

## INCON (`initial_conditions`, `continuation_run`)

`initial_conditions[label]`: `nseq`, `nadd`, `porosity`, `phase_state` (StateIndex),
`permeability` (perm(1:3)), `values` (one 6E20.13 record). A record whose element name is
blank closes the block, as in the solver; the free text in columns 36-71 (written by the
solver in SAVE files) is not read. `continuation_run` holds the
`&Data_For_Continuation_Run` variables.

## EXT-INCON (`extended_initial_conditions`)

List of entries with `type` (`GEOMETRY`, `SEQUENCE`, `LIST`, `COLUMN`) and:

| Type | Keys |
|---|---|
| GEOMETRY | `xmin`, `xmax`, `ymin`, `ymax`, `zmin`, `zmax` or `rmin`, `rmax`, `zmin`, `zmax`; `phase_state`, `values` |
| SEQUENCE | `first_element`, `last_element`, `stride`; `phase_state`, `values` |
| LIST | `elements`, `n_per_row`; `phase_state`, `values` |
| COLUMN | `first_element`, `n_elements`, `stride`, `states` (list of `{"phase_state", "values"}`) |

## BOUNDARIES (`transient_boundaries`)

List of boundaries: variables of `&Transient_Boundary_Definition` and
`&Tabular_Data_Definition` (lower-cased, merged), `comment` (BOUNDARIES.4) and `table`
(records as written; `read_format` may be `'*'` or a repeated real descriptor such as
`'(4E20.13)'`, other formats raise `ValueError`). Derived: `number_of_defined_boundaries`,
`num_table_defined_boundaries`, `num_pv_to_read`, `number_of_rows`,
`tot_number_of_columns`.

## GENER (`generators`)

Upstream keys (`label`, `name`, `nseq`, `nadd`, `nads`, `type`, `times`, `rates`,
`specific_enthalpy`, `layer_thickness`) plus `well_response` (WellResponse),
`pressure_limit` (PresLimits), `rate_step_change` (RateStepChange), `rate_limit` (RateLimit).

## SUBDOMAINS, INTERFACES, SS_GROUPS

| Key | Structure |
|---|---|
| `subdomains` | list of `&Individual_Subdomain_Specifics` with `regions`: `&Region_Specifics` + `elements` (NameList / NumberList) |
| `interfaces` | list of `&Individual_Interface_Specifics` with `surfaces`: `&Surface_Specifics` + `connections` |
| `ss_groups` | list of `&Individual_SSGroup_Specifics` + `sources` |

## Not supported

MESHMAKER and UPDATE before ENDCY raise `ReadError`; anything after ENDCY/ENDFI is ignored,
as in the solver. Unknown blocks (e.g. TOUGH2 `FOFT`) are skipped, as the solver does.
Comments and column alignment are not preserved.