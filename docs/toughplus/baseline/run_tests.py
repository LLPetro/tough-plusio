"""Run CI tests against pinned source objects and compare every nodeid."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import tomllib


ROOT = Path(__file__).resolve().parents[3]
LFS_HEADER = b"version https://git-lfs.github.com/spec/v1"
GATES = {
    "hydrate_samples": "TOUGH_HYDRATE_REFERENCE_DIR",
    "hydrate_outputs": "TOUGH_HYDRATE_OUTPUT_DIR",
}


class Failure(Exception):
    """A test-environment or nodeid comparison failure."""


def ensure(condition, message):
    if not condition:
        raise Failure(message)


def git(*args, raw=False):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=not raw)


def normalize(nodeid):
    path, separator, parameters = nodeid.replace("\\", "/").partition("::")
    offset = path.rfind("tests/")
    return (path[offset:] if offset >= 0 else path) + separator + parameters


def read_results(path):
    with Path(path).open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        ensure(
            reader.fieldnames == ["nodeid", "outcome"], f"invalid TSV header: {path}"
        )
        result = {}
        for row in reader:
            nodeid, outcome = row["nodeid"], row["outcome"]
            ensure(
                nodeid not in result and nodeid.startswith("tests/"),
                f"invalid/duplicate nodeid: {nodeid}",
            )
            ensure(
                outcome in {"passed", "failed", "skipped", "error"},
                f"invalid outcome: {outcome}",
            )
            result[nodeid] = outcome
    return result


def write_results(path, outcomes):
    with Path(path).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
        writer.writerow(["nodeid", "outcome"])
        writer.writerows(sorted(outcomes.items()))


def compare_results(expected, actual):
    missing = sorted(expected.keys() - actual.keys())
    extra = sorted(actual.keys() - expected.keys())
    changed = {
        key: [expected[key], actual[key]]
        for key in expected.keys() & actual.keys()
        if expected[key] != actual[key]
    }
    ensure(
        not (missing or extra or changed),
        f"nodeid mismatch: missing={missing}; extra={extra}; changed={changed}",
    )


def materialize_tests(upstream, destination):
    """Export M's tests and hydrate pointers only from the existing LFS cache."""
    archive = git("archive", upstream, "tests", raw=True)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(destination, filter="data")
    common = Path(
        git("rev-parse", "--path-format=absolute", "--git-common-dir").strip()
    )
    count = 0
    for path in (destination / "tests").rglob("*"):
        if not path.is_file():
            continue
        content = path.read_bytes()
        if not content.startswith(LFS_HEADER + b"\n"):
            continue
        lines = content.decode("ascii").splitlines()
        ensure(
            len(lines) == 3
            and lines[1].startswith("oid sha256:")
            and lines[2].startswith("size "),
            f"invalid LFS pointer: {path}",
        )
        oid, size = lines[1].split(":", 1)[1], int(lines[2].split()[1])
        ensure(
            len(oid) == 64 and all(c in "0123456789abcdef" for c in oid),
            "invalid LFS oid",
        )
        obj = common / "lfs/objects" / oid[:2] / oid[2:4] / oid
        ensure(
            obj.is_file(),
            f"missing LOCAL LFS object {oid}; checkout with lfs: true before running tests",
        )
        data = obj.read_bytes()
        ensure(
            len(data) == size and hashlib.sha256(data).hexdigest() == oid,
            f"corrupt local LFS object: {oid}",
        )
        path.write_bytes(data)
        count += 1
    return count


class Capture:
    def __init__(self):
        self.collected = []
        self.outcomes = {}
        self.allowed_skips = set()
        self.collection_errors = []

    def pytest_collection_finish(self, session):
        self.collected = [normalize(item.nodeid) for item in session.items]
        for item in session.items:
            if any(
                item.get_closest_marker(marker) and not os.environ.get(variable)
                for marker, variable in GATES.items()
            ):
                self.allowed_skips.add(normalize(item.nodeid))

    def pytest_collectreport(self, report):
        if report.failed:
            self.collection_errors.append(str(report.longrepr))

    def pytest_runtest_logreport(self, report):
        key = normalize(report.nodeid)
        if report.when == "call":
            self.outcomes[key] = report.outcome
        elif report.failed:
            self.outcomes[key] = "error"
        elif report.skipped:
            self.outcomes[key] = "skipped"


def run(mode, output, working):
    ensure(sys.version_info[:2] == (3, 11), "baseline CI uses Python 3.11")
    for line in (
        (ROOT / "docs/toughplus/baseline/constraints.txt").read_text().splitlines()
    ):
        if line and not line.startswith("#"):
            package, version = line.split("==")
            actual = importlib.metadata.version(package)
            ensure(
                actual == version,
                f"runtime drift: {package}={actual}, expected {version}",
            )
    manifest = tomllib.loads((ROOT / "scripts/additive_manifest.toml").read_text())
    os.chdir(working)
    sys.path.insert(0, str(ROOT))
    os.environ["PYTHONPATH"] = str(ROOT)
    import pytest

    import toughio

    actual = Path(toughio.__file__).resolve()
    ensure(actual == ROOT / "toughio/__init__.py", f"wrong toughio import: {actual}")
    context = {
        "cwd": str(Path.cwd()),
        "toughio_file": str(actual),
        "python": sys.version,
        "upstream_sha": manifest["upstream"]["sha"],
        "base_sha": manifest["base"]["sha"],
        "mode": mode,
    }
    print("CI CONTEXT " + json.dumps(context), flush=True)
    (output / f"{mode}-context.txt").write_text(json.dumps(context, indent=2) + "\n")
    if mode == "upstream":
        baseline = ROOT / manifest["baseline"]["path"]
        ensure(
            hashlib.sha256(baseline.read_bytes()).hexdigest()
            == manifest["baseline"]["sha256"],
            "baseline TSV differs from manifest digest",
        )
        expected = read_results(baseline)
        ensure(
            len(expected) == manifest["baseline"]["collected"],
            "baseline collection size differs from manifest",
        )
        count = materialize_tests(manifest["upstream"]["sha"], working)
        print(
            f"Materialized M tests with {count} existing local LFS objects", flush=True
        )
        test_root = working
        targets = [str(working / "tests")]
    else:
        test_root = ROOT
        targets = [str(ROOT / "tests/tough_hydrate")]
        targets += [
            str(ROOT / target)
            for topic in manifest["topics"]
            for target in topic["regression_targets"]
        ]
    capture = Capture()
    status = pytest.main(
        [
            "-q",
            "--tb=short",
            "-p",
            "no:cacheprovider",
            "--rootdir=" + str(test_root),
            "-o",
            "markers=hydrate_samples: local official decks\nhydrate_outputs: local output fixtures",
            *targets,
        ],
        plugins=[capture],
    )
    ensure(
        not capture.collection_errors, f"collection errors: {capture.collection_errors}"
    )
    ensure(
        len(capture.collected) == len(set(capture.collected))
        and set(capture.collected) == capture.outcomes.keys(),
        "collection has duplicate or missing outcomes",
    )
    loaded = {
        name: module.__file__
        for name, module in list(sys.modules.items())
        if (name == "toughio" or name.startswith("toughio."))
        and getattr(module, "__file__", None)
    }
    ensure(
        all(Path(path).resolve().is_relative_to(ROOT) for path in loaded.values()),
        "mixed toughio module origins",
    )
    write_results(output / f"{mode}-results.tsv", capture.outcomes)
    if mode == "upstream":
        ensure(status in {0, 1}, f"pytest did not complete normally: {status}")
        compare_results(expected, capture.outcomes)
        print(
            f"PASS upstream: all {len(expected)} nodeids and outcomes match baseline",
            flush=True,
        )
    else:
        ensure(status == 0, f"extension pytest exit status: {status}")
        regression_ids = {
            nodeid
            for topic in manifest["topics"]
            for nodeid in topic["regression_nodeids"]
        }
        ensure(
            len(regression_ids) == manifest["regressions"]["expected_count"],
            "manifest regression count mismatch",
        )
        ensure(
            regression_ids <= capture.outcomes.keys()
            and all(capture.outcomes[n] == "passed" for n in regression_ids),
            "a fix regression is missing or did not pass",
        )
        ensure(
            all(
                value == "passed"
                or (value == "skipped" and key in capture.allowed_skips)
                for key, value in capture.outcomes.items()
            ),
            "unexpected skip or failure in extension tests",
        )
        print(
            f"PASS extensions: {len(capture.collected)} cases; {len(regression_ids)} fix regressions; {len(capture.allowed_skips)} local-data skips permitted",
            flush=True,
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("upstream", "extensions"))
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        output = (
            args.output_dir or Path(tempfile.mkdtemp(prefix="toughplus-results-"))
        ).resolve()
        output.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="toughplus-ci-") as working:
            run(args.mode, output, Path(working))
    except (Failure, OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"FAIL CI {args.mode}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
