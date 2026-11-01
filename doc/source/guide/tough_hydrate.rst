TOUGH+HYDRATE
=============

`toughplusio <https://github.com/LLPetro/tough-plusio>`__ (import name ``toughio``) adds TOUGH+HYDRATE v1.5
(T+H) formats to toughio. Nothing else changes: all toughio formats behave as upstream.
T+H file names are the same as TOUGH2 file names (``INFILE``, ``MESH``, ``INCON``,
``GENER``), so the format must always be given explicitly.

Input
-----

.. code-block:: python

    import toughio

    parameters = toughio.read_input("Test_1P", file_format="tough+hydrate")
    parameters["options"]["n_cycle"] = 10
    toughio.write_input("INFILE", parameters, file_format="tough+hydrate")

Supported data blocks: TITLE, MEMORY, ROCKS (MEDIA, NAD 0-8), HYDRATE, DIFFUSION,
RPCAP (WETTABILITY), START (RANDOMN), PARAM, SOLVR, TIMES, ELEME, CONNE, INDOM, INCON
(including continuation runs), EXT-INCON, BOUNDARIES, GENER, SUBDOMAINS, INTERFACES,
SS_GROUPS, ENDCY and ENDFI. MESHMAKER and UPDATE are not supported.

Separate files are read and written with the same format. Element names have 5 or 8
characters; give ``label_length=8`` when reading a separate file with 8-character names:

.. code-block:: python

    toughio.write_input("MESH", parameters, file_format="tough+hydrate", blocks="MESH")
    mesh = toughio.read_input("MESH", file_format="tough+hydrate", label_length=8)

``blocks`` also accepts ``"INCON"``, ``"GENER"`` or a list of block names. Solver-written
``MESH`` and ``GENER`` files ending with ``+++`` cross references are supported.

The parameters follow toughio conventions: keys shared with TOUGH2 have the same meaning
(``rocks``, ``options``, ``extra_options``, ``default``, ``elements``, ``connections``,
``initial_conditions``, ``generators``, ``solver``, ``times``), T+H-only data use new keys
(``memory``, ``hydrate``, ``multiphase_diffusion``, ``extended_initial_conditions``,
``transient_boundaries``, ``subdomains``, ``interfaces``, ``ss_groups``, ...). The full
list is in ``docs/toughplus/schema/canonical-fields.md``. Reading and writing do not check
the parameters; :func:`toughio.hydrate.validate` returns a list of problems found
according to the T+H manual.

Each value is written in the type of its field: integer fields (Fortran ``I``) hold whole
numbers only (``100.0`` is written ``100``, never ``1e+02``), real fields (``E``) get a
decimal point, text fields (``A``) hold ASCII without control characters, and logical
values are ``.TRUE.``/``.FALSE.``. A value that its field cannot hold (too wide, not a
whole number, ``nan``, a list in a scalar...) raises :class:`toughio.hydrate.FieldError`,
a :class:`ValueError` that names the block, record, field and columns, instead of being
written truncated or shifting the following columns:

.. code-block:: python

    try:
        toughio.write_input("INFILE", parameters, file_format="tough+hydrate")
    except toughio.hydrate.FieldError as e:
        print(e)  # PARAM.1 options.n_cycle_print (columns 13-16): integer 10000000 ...
        print(e.reason, e.path, e.columns)  # too_wide ('options', 'n_cycle_print') (13, 16)

Meshes
------

Element activity (``I`` for inactive elements, ``V01``...``V99`` for time-variable
boundaries) is stored in ``elements[label]["activity"]``.

.. code-block:: python

    from toughio import hydrate

    mesh = toughio.meshmaker.structured_grid(dx, dy, dz)
    hydrate.set_activity(mesh, mesh.centers[:, 0] < 0.01, "V01")
    parameters.update(hydrate.mesh_parameters(mesh))

Dirichlet cells of a :class:`toughio.Mesh` keep their real volume and nodal distances and
become inactive elements.

Outputs
-------

- main output (standard output): :func:`toughio.read_output` with ``file_format="tough+hydrate-out"``
- ``Plot_Data_Elem``: :func:`toughio.read_output` with ``file_format="tough+hydrate-element"``
- ``SAVE``: :func:`toughio.read_output` with ``file_format="tough+hydrate-save"``
- ``Hydrate_Status`` and ``*_Time_Series``: :func:`toughio.read_table` with ``file_format="tough+hydrate"``

The main output reader returns element tables, or connection tables with
``connection=True``. Time series are returned as :class:`toughio.HistoryOutput` with units
and the series type (``rock``, ``connection`` or ``generator``) in ``metadata``.