# Reviewed upstream baseline and local CI entry points

`upstream-results.tsv` records all 344 nodeids from official commit
`8f8b4fd723e2c63a74aaaedf44ee0a4b7f835f16`, tested against
`toughplus-base` at `eb7e3bcfb6039af0953ad20ff3cbec24e0159f74`.
It contains 294 passed, 30 failed and 20 skipped outcomes. It does not turn the
30 failures into xfails or skips. The manifest pins its SHA-256 digest.
`provenance.toml` and `constraints.txt` record the reviewed environment.

The gate scripts require Python 3.11. The library's upstream Python metadata is
unchanged. The upstream project currently defines no `full` extra; pip's
`.[full]` spelling still installs all declared runtime dependencies and may warn
that the extra is absent. Do not change upstream packaging merely to hide that warning.

## Commands

After installing the pinned dependencies, from the fork checkout:

```sh
python scripts/check_additive.py fixes
python scripts/check_additive.py base
python scripts/check_additive.py
python scripts/check_additive.py pr fixes/upstream-defects
python docs/toughplus/baseline/test_check_additive.py
python docs/toughplus/baseline/run_tests.py extensions
python docs/toughplus/baseline/run_tests.py upstream
```

`check_additive.py` uses only the standard library and Git. It checks committed
objects; commit proposed changes before relying on a pass. The manifest is
reviewed policy, so changes to pins, allowed files or baselines require review.
Local branches are preferred over `origin/*` refs. Missing refs/objects are errors;
none of these scripts fetches anything.

The policy tests construct and delete temporary local clones and commits, never
violation branches in the source repository. They also verify that changed
nodeids or swapped outcomes fail even when result counts stay the same.

The test driver always changes into a temporary directory before importing
`toughio`, asserts every loaded `toughio.*` module comes from the checkout and
prints `toughio.__file__`. Use `--output-dir /outside/the/checkout` to retain
result TSV and import-context files. The driver exports the **M tests**, not the
checkout's modified tests, and verifies/materializes their LFS pointers only from
`.git/lfs/objects`. CI's full checkout with `lfs: true` must provide these objects.
A missing or corrupt object fails; it is never downloaded by the test driver.

`extensions` runs T+H plus the 73 pinned fix regressions.
Without local data, the 5 marked T+H cases skip and the other 102 cases pass.
Unexpected skips fail. Set the following variables to run all 107 cases:

```sh
export TOUGH_HYDRATE_REFERENCE_DIR=/path/to/sample/decks
export TOUGH_HYDRATE_OUTPUT_DIR=/path/to/solver/outputs
```

`upstream` requires identical collected nodeids and identical outcomes for every
one of the 344 baseline rows. Added/missing cases, changed skips, newly failed
cases and newly passed cases all require explicit baseline review. Counts alone
are never accepted. Runtime-version drift also fails with the package/version.

## Workflow

Only `.github/workflows/toughplus.yml` is fork-specific. It runs on pushes and
pull requests targeting `toughplus`, plus manual dispatch, and recreates the
`fixes/*` and `toughplus-base` branches from the manifest pins before its ref
checks. The upstream workflows are unchanged.
