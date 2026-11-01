"""
Check the committed fixes and T+H additions against the manifest, using Git and
Python 3.11+ only.

The TOML manifest is reviewed policy, not an automatically inferred allowlist.
All modes are read-only; missing objects or refs fail without fetching anything.
"""

from __future__ import annotations

import argparse
import difflib
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

import tomllib


ADD_PREFIXES = (
    "toughio/_io/input/tough_hydrate/",
    "toughio/_io/output/tough_hydrate/",
    "toughio/_io/table/tough_hydrate/",
    "toughio/hydrate/",
    "tests/tough_hydrate/",
    "docs/toughplus/",
)
ADD_FILES = {
    "doc/source/guide/tough_hydrate.rst",
    ".github/workflows/toughplus.yml",
    # GitHub shows .github/README.md before the root README.rst: the fork's landing
    # page, while README.rst stays the upstream file.
    ".github/README.md",
    "scripts/check_additive.py",
    "scripts/additive_manifest.toml",
}
REGISTRATIONS = {
    f"toughio/_io/{group}/__init__.py" for group in ("input", "output", "table")
}
INDEX = "doc/source/guide/index.rst"
LFS_HEADER = b"version https://git-lfs.github.com/spec/v1"
SHA = re.compile(r"[0-9a-f]{40}")


class Violation(Exception):
    """A policy violation with a stable diagnostic code."""


def require(condition, code, message):
    if not condition:
        raise Violation(f"[{code}] {message}")


def added_path(path):
    return path in ADD_FILES or path.startswith(ADD_PREFIXES)


def text_path(path):
    if not added_path(path):
        return False
    if not path.startswith("tests/tough_hydrate/"):
        return True
    return PurePosixPath(path).suffix in {
        ".py",
        ".md",
        ".rst",
        ".toml",
        ".txt",
        ".yml",
        ".yaml",
    }


def valid_path(path):
    return (
        isinstance(path, str)
        and path
        and not PurePosixPath(path).is_absolute()
        and not set(PurePosixPath(path).parts) & {"..", ".git"}
        and "\\" not in path
    )


def strip_metadata(text):
    """Remove only the two scalar fields and the permitted metadata tables."""
    section = ""
    result = []
    for line in text.splitlines(keepends=True):
        match = re.fullmatch(r"\[([^\[\]]+)\]\s*", line.strip())
        if match:
            section = match[1]
        if section in {"project.urls", "tool.setuptools.package-data"}:
            continue
        if section == "project" and re.match(r"^(name|description)\s*=", line):
            continue
        result.append(line)
    return "".join(result)


class Gate:
    def __init__(self, repo, manifest):
        self.repo = Path(repo).resolve()
        self.manifest = Path(manifest)
        self.data = tomllib.loads(self.manifest.read_text(encoding="utf-8"))
        require(
            self.data.get("schema_version") == 1,
            "MANIFEST",
            "unsupported schema_version",
        )
        self.upstream = self.data["upstream"]["sha"]
        self.base = self.data["base"]["sha"]
        self.topics = self.data["topics"]
        require(self.topics, "MANIFEST", "topics must not be empty")
        seen = {}
        branches = set()
        for topic in self.topics:
            for field in ("sha", "parent_sha", "merge_sha"):
                require(
                    bool(SHA.fullmatch(topic[field])),
                    "MANIFEST",
                    f"invalid {field}: {topic['id']}",
                )
            branch = topic["branch"]
            require(
                branch.startswith("fixes/") and branch not in branches,
                "MANIFEST",
                f"invalid or duplicate topic branch: {branch}",
            )
            require(topic["sha"] not in seen, "MANIFEST", "duplicate topic SHA")
            files = topic["files"]
            require(
                files
                and len(files) == len(set(files))
                and all(valid_path(p) for p in files),
                "MANIFEST",
                f"invalid files: {branch}",
            )
            parent = topic["parent_sha"]
            expected_parent = (
                self.data["upstream"]["branch"]
                if parent == self.upstream
                else seen.get(parent)
            )
            require(
                expected_parent is not None
                and expected_parent == topic["parent_branch"],
                "MANIFEST",
                f"unknown or unordered parent: {branch}",
            )
            seen[topic["sha"]] = branch
            branches.add(branch)
        for value in (self.upstream, self.base, self.data["packaging"]["rename_sha"]):
            require(bool(SHA.fullmatch(value)), "MANIFEST", "invalid pinned SHA")

    def git(self, *args, raw=False, check=True):
        proc = subprocess.run(
            ["git", *args],
            cwd=self.repo,
            capture_output=True,
            text=not raw,
            encoding=None if raw else "utf-8",
        )
        if check:
            require(
                proc.returncode == 0,
                "GIT",
                f"git {' '.join(args)}: {str(proc.stderr).strip()}",
            )
        return proc.stdout if check else proc

    def commit(self, revision):
        proc = self.git("rev-parse", "--verify", f"{revision}^{{commit}}", check=False)
        require(
            proc.returncode == 0,
            "MISSING_COMMIT",
            f"commit is unavailable locally: {revision}",
        )
        return proc.stdout.strip()

    def branch(self, name):
        require(
            self.git("check-ref-format", f"refs/heads/{name}", check=False).returncode
            == 0,
            "MANIFEST",
            f"invalid branch: {name}",
        )
        for ref in (f"refs/heads/{name}", f"refs/remotes/origin/{name}"):
            if (
                self.git("show-ref", "--verify", "--quiet", ref, check=False).returncode
                == 0
            ):
                return self.commit(ref)
        raise Violation(f"[MISSING_BRANCH] local/origin branch is unavailable: {name}")

    def blob(self, revision, path):
        return self.git("show", f"{revision}:{path}", raw=True)

    def changes(self, left, right):
        fields = self.git(
            "diff", "--no-renames", "--name-status", "-z", left, right
        ).split("\0")
        fields = fields[:-1] if fields[-1] == "" else fields
        require(len(fields) % 2 == 0, "GIT", "invalid diff output")
        return dict(zip(fields[1::2], fields[0::2]))

    def parents(self, revision):
        return self.git("rev-list", "--parents", "-n", "1", revision).split()[1:]

    def ancestor(self, left, right):
        return (
            self.git("merge-base", "--is-ancestor", left, right, check=False).returncode
            == 0
        )

    def pr(self, revision):
        available = self.git(
            "rev-parse", "--verify", f"{revision}^{{commit}}", check=False
        )
        target = (
            self.commit(revision)
            if available.returncode == 0
            else self.branch(revision)
        )
        require(
            self.ancestor(self.upstream, target),
            "PR_ANCESTRY",
            "M must be an ancestor of the PR",
        )
        require(
            self.blob(self.upstream, "pyproject.toml")
            == self.blob(target, "pyproject.toml"),
            "PR_METADATA",
            "PR pyproject.toml must be byte-identical to M",
        )
        for path in self.changes(self.upstream, target):
            require(
                not added_path(path), "PR_FORK_PATH", f"fork-only path in PR: {path}"
            )
            if path in REGISTRATIONS:
                require(
                    b"tough_hydrate" not in self.blob(target, path),
                    "PR_REGISTRATION",
                    f"fork registration in PR: {path}",
                )
        rename = self.data["packaging"]["rename_sha"]
        require(
            not self.ancestor(rename, target),
            "PR_RENAME_HISTORY",
            "PR includes the fork distribution-name commit",
        )
        return target

    def fixes(self):
        require(
            self.branch(self.data["upstream"]["branch"]) == self.commit(self.upstream),
            "UPSTREAM_SHA",
            "upstream branch differs from manifest",
        )
        for topic in self.topics:
            name, sha = topic["branch"], topic["sha"]
            require(
                self.branch(name) == sha,
                "FIX_SHA",
                f"{name}: branch SHA differs from manifest",
            )
            require(
                self.parents(sha) == [topic["parent_sha"]],
                "FIX_PARENT",
                f"{name}: direct parent differs from manifest",
            )
            actual = set(self.changes(topic["parent_sha"], sha))
            require(
                actual == set(topic["files"]),
                "FIX_FILES",
                f"{name}: changed paths differ from allowlist; extra={sorted(actual - set(topic['files']))}; missing={sorted(set(topic['files']) - actual)}",
            )
            self.pr(sha)

    def check_base(self):
        require(
            self.branch(self.data["base"]["branch"]) == self.base,
            "BASE_SHA",
            "base branch SHA differs from manifest",
        )
        require(
            self.ancestor(self.upstream, self.base),
            "BASE_ANCESTRY",
            "M is not an ancestor of base",
        )
        chain = self.git(
            "rev-list", "--first-parent", "--reverse", f"{self.upstream}..{self.base}"
        ).split()
        require(
            chain == [t["merge_sha"] for t in self.topics],
            "BASE_CHAIN",
            "base first-parent chain must contain exactly the approved topic merges in order",
        )
        previous = self.upstream
        for topic in self.topics:
            merge = topic["merge_sha"]
            require(
                self.parents(merge) == [previous, topic["sha"]],
                "BASE_PARENTS",
                f"{topic['id']}: unexpected merge parents",
            )
            actual = set(self.changes(previous, merge))
            require(
                actual == set(topic["files"]),
                "BASE_FILES",
                f"{topic['id']}: merge introduced unapproved paths: {sorted(actual - set(topic['files']))}",
            )
            require(
                self.ancestor(topic["sha"], self.base),
                "BASE_TOPIC",
                f"missing topic ancestor: {topic['id']}",
            )
            previous = merge

    def pyproject(self, target):
        old = self.blob(self.base, "pyproject.toml").decode("utf-8")
        new = self.blob(target, "pyproject.toml").decode("utf-8")
        before, after = tomllib.loads(old), tomllib.loads(new)
        require(
            after["project"]["name"] in {before["project"]["name"], "toughplusio"},
            "PYPROJECT_FIELDS",
            "unexpected distribution name",
        )
        for key in ("name", "description", "urls"):
            before["project"].pop(key, None)
            after["project"].pop(key, None)
        require(
            "package-data" not in after["tool"]["setuptools"],
            "PYPROJECT_FIELDS",
            "package-data is not permitted",
        )
        require(
            before == after,
            "PYPROJECT_FIELDS",
            "pyproject changes exceed name, description and urls",
        )
        require(
            strip_metadata(old) == strip_metadata(new),
            "PYPROJECT_TEXT",
            "pyproject has extra edits outside the permitted metadata lines/tables",
        )

    def toughplus(self):
        target = self.commit("HEAD")
        require(
            self.ancestor(self.base, target),
            "TH_ANCESTRY",
            "toughplus-base must be an ancestor of HEAD",
        )
        # Ancestry is checked above, so this is base...HEAD's exact tree diff.
        changes = self.changes(self.base, target)
        for path, status in changes.items():
            require(valid_path(path), "TH_PATH", f"invalid path: {path}")
            if path in REGISTRATIONS:
                require(
                    status == "M",
                    "REGISTRATION",
                    f"registration must only modify its existing file: {path}",
                )
                old = self.blob(self.base, path)
                lines = old.splitlines(keepends=True)
                expected = (
                    lines[0].rstrip(b"\n") + b", tough_hydrate\n" + b"".join(lines[1:])
                )
                require(
                    self.blob(target, path) == expected,
                    "REGISTRATION",
                    f"only one registration import is allowed: {path}",
                )
            elif path == "pyproject.toml":
                require(
                    status == "M",
                    "PYPROJECT_FIELDS",
                    "pyproject must not be added or removed",
                )
                self.pyproject(target)
            elif path == INDEX:
                old = self.blob(self.base, path).decode().splitlines(keepends=True)
                new = self.blob(target, path).decode().splitlines(keepends=True)
                delta = list(difflib.ndiff(old, new))
                require(
                    not any(s.startswith("- ") for s in delta)
                    and [s[2:] for s in delta if s.startswith("+ ")]
                    == ["   tough_hydrate\n"],
                    "TOCTREE",
                    "only the tough_hydrate toctree line may be added",
                )
            else:
                require(
                    status == "A" and added_path(path),
                    "TH_PATH",
                    f"path is outside the additive whitelist or modifies an upstream file: {status} {path}",
                )
        tree = self.git("ls-tree", "-r", "-z", target).split("\0")
        for entry in filter(None, tree):
            meta, path = entry.split("\t", 1)
            mode, kind, oid = meta.split()
            if path in changes:
                require(
                    mode in {"100644", "100755"} and kind == "blob",
                    "FILE_MODE",
                    f"new/changed path must be a regular file: {path}",
                )
            if text_path(path):
                content = self.git("cat-file", "blob", oid, raw=True)
                lines = content.lstrip(b"\xef\xbb\xbf \t\r\n").splitlines()
                first = lines[0] if lines else b""
                require(
                    first != LFS_HEADER,
                    "LFS_TEXT",
                    f"LFS pointer in fork text path: {path}; keep fixtures in LFS, not documentation/code",
                )
        return len(changes)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode",
        nargs="?",
        default="toughplus",
        choices=("fixes", "base", "toughplus", "pr"),
    )
    parser.add_argument("branch", nargs="?", help="required PR branch/ref")
    parser.add_argument(
        "--repo", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument(
        "--manifest", type=Path, help="default: <repo>/scripts/additive_manifest.toml"
    )
    args = parser.parse_args(argv)
    if (args.mode == "pr") != bool(args.branch):
        parser.error("only pr accepts and requires a branch/ref")
    try:
        gate = Gate(
            args.repo, args.manifest or args.repo / "scripts/additive_manifest.toml"
        )
        if args.mode == "pr":
            target = gate.pr(args.branch)
            print(
                f"PASS pr: {args.branch} {target}; upstream metadata and fork-path isolation"
            )
        else:
            gate.fixes()
            print(
                f"PASS fixes: {len(gate.topics)} pinned branches, parents and exact file scopes"
            )
            if args.mode in {"base", "toughplus"}:
                gate.check_base()
                print(
                    f"PASS base: {gate.base}; {len(gate.topics)} approved first-parent merges"
                )
            if args.mode == "toughplus":
                count = gate.toughplus()
                print(
                    f"PASS toughplus: {count} additive paths; strict upstream edits; no LFS text pointers"
                )
    except (Violation, OSError, KeyError, TypeError, ValueError) as error:
        print(f"FAIL {args.mode}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
