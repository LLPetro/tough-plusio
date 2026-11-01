"""Exercise policy failures in disposable, local-only Git clones."""

from __future__ import annotations

import hashlib
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import tomllib


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/check_additive.py"
MANIFEST = ROOT / "scripts/additive_manifest.toml"
POINTER = (
    b"version https://git-lfs.github.com/spec/v1\noid sha256:"
    + hashlib.sha256(b"").hexdigest().encode()
    + b"\nsize 0\n"
)
DRIVER_SPEC = importlib.util.spec_from_file_location(
    "baseline_driver", Path(__file__).with_name("run_tests.py")
)
DRIVER = importlib.util.module_from_spec(DRIVER_SPEC)
DRIVER_SPEC.loader.exec_module(DRIVER)


class PolicyClones(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="toughplus-policy-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "clone"
        self.policy = self.root / "manifest.toml"
        self.text = MANIFEST.read_text()
        self.policy.write_text(self.text)
        self.data = tomllib.loads(self.text)
        self.env = dict(
            os.environ,
            GIT_LFS_SKIP_SMUDGE="1",
            GIT_OPTIONAL_LOCKS="0",
            PYTHONDONTWRITEBYTECODE="1",
            GIT_TERMINAL_PROMPT="0",
        )
        subprocess.run(
            [
                "git",
                "-c",
                "core.hooksPath=/dev/null",
                "clone",
                "--shared",
                "--no-checkout",
                "--origin",
                "origin",
                str(ROOT),
                str(self.repo),
            ],
            env=self.env,
            capture_output=True,
            check=True,
        )
        # GitHub checkout may have only remote-tracking refs, so seed the clone's
        # test namespace from the pinned objects, without contacting an origin.
        refs = [(t["branch"], t["sha"]) for t in self.data["topics"]]
        refs += [
            (self.data[g]["branch"], self.data[g]["sha"]) for g in ("upstream", "base")
        ]
        for branch, sha in refs:
            self.git("update-ref", "refs/remotes/origin/" + branch, sha)
        self.head = self.git("rev-parse", "HEAD").strip()

    def git(self, *args, data=None, env=None):
        proc = subprocess.run(
            [
                "git",
                "-c",
                "core.hooksPath=/dev/null",
                "-c",
                "user.name=Additive gate tests",
                "-c",
                "user.email=gate@example.invalid",
                *args,
            ],
            cwd=self.repo,
            env=env or self.env,
            input=data,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr.decode(errors="replace"))
        return proc.stdout.decode()

    def commit(self, parent, changes=None, tree_from=None, parents=None):
        index = self.root / "index"
        if index.exists():
            index.unlink()
        env = dict(self.env, GIT_INDEX_FILE=str(index))
        self.git("read-tree", tree_from or parent, env=env)
        for path, content in (changes or {}).items():
            if content is None:
                self.git("update-index", "--force-remove", "--", path, env=env)
            else:
                oid = self.git(
                    "hash-object", "-w", "--stdin", data=content, env=env
                ).strip()
                self.git(
                    "update-index",
                    "--add",
                    "--cacheinfo",
                    f"100644,{oid},{path}",
                    env=env,
                )
        tree = self.git("write-tree", env=env).strip()
        arguments = ["commit-tree", tree]
        for ancestor in parents if parents is not None else [parent]:
            arguments += ["-p", ancestor]
        arguments += ["-m", "Disposable additive-gate sample"]
        return self.git(*arguments, env=env).strip()

    def at_head(self, sha):
        self.git("update-ref", "refs/heads/violation-sample", sha)
        self.git("symbolic-ref", "HEAD", "refs/heads/violation-sample")

    def replace_pin(self, old, new):
        self.text = self.text.replace(old, new)
        self.policy.write_text(self.text)

    def check(self, mode="toughplus", branch=None, error=None):
        arguments = [sys.executable, "-B", str(SCRIPT), mode]
        if branch:
            arguments.append(branch)
        arguments += ["--repo", str(self.repo), "--manifest", str(self.policy)]
        proc = subprocess.run(
            arguments, cwd=self.root, env=self.env, capture_output=True, text=True
        )
        output = proc.stdout + proc.stderr
        print(f"CASE {self._testMethodName} mode={mode}: {output.strip()}", flush=True)
        self.assertEqual(proc.returncode, 1 if error else 0, output)
        if error:
            self.assertIn("[" + error + "]", output)

    def test_positive_modes_and_all_pr_topics(self):
        for mode in ("fixes", "base", "toughplus"):
            self.check(mode)
        for topic in self.data["topics"]:
            self.check("pr", topic["branch"])

    def test_fixes_missing_branch(self):
        self.git(
            "update-ref",
            "-d",
            "refs/remotes/origin/" + self.data["topics"][0]["branch"],
        )
        self.check("fixes", error="MISSING_BRANCH")

    def test_fixes_sha_mismatch(self):
        self.git(
            "update-ref",
            "refs/heads/" + self.data["topics"][0]["branch"],
            self.data["upstream"]["sha"],
        )
        self.check("fixes", error="FIX_SHA")

    def test_fixes_wrong_parent_even_with_updated_sha(self):
        topic = self.data["topics"][0]
        sha = self.commit(topic["sha"], tree_from=topic["sha"])
        self.git("update-ref", "refs/heads/" + topic["branch"], sha)
        self.replace_pin(topic["sha"], sha)
        self.check("fixes", error="FIX_PARENT")

    def test_fixes_forbidden_file_even_with_updated_sha(self):
        topic = self.data["topics"][0]
        sha = self.commit(
            topic["parent_sha"],
            {"README.rst": b"unapproved fix change\n"},
            tree_from=topic["sha"],
        )
        self.git("update-ref", "refs/heads/" + topic["branch"], sha)
        self.replace_pin(topic["sha"], sha)
        self.check("fixes", error="FIX_FILES")

    def test_base_sha_mismatch(self):
        self.git(
            "update-ref", "refs/heads/toughplus-base", self.data["upstream"]["sha"]
        )
        self.check("base", error="BASE_SHA")

    def test_base_extra_commit_even_with_updated_sha(self):
        old = self.data["base"]["sha"]
        new = self.commit(old, {"README.rst": b"extra base commit\n"})
        self.git("update-ref", "refs/heads/toughplus-base", new)
        self.replace_pin(old, new)
        self.check("base", error="BASE_CHAIN")

    def test_base_wrong_merge_parent_with_consistent_chain_pins(self):
        previous = self.data["upstream"]["sha"]
        replacements = {}
        last = len(self.data["topics"]) - 1
        for index, topic in enumerate(self.data["topics"]):
            # The last merge gets a wrong second parent (its first parent's parent).
            second = (
                self.git("rev-parse", previous + "^").strip()
                if index == last
                else topic["sha"]
            )
            sha = self.commit(
                previous, tree_from=topic["merge_sha"], parents=[previous, second]
            )
            replacements[topic["merge_sha"]] = sha
            previous = sha
        self.git("update-ref", "refs/heads/toughplus-base", previous)
        for old, new in replacements.items():
            self.replace_pin(old, new)
        self.check("base", error="BASE_PARENTS")

    def test_toughplus_forbidden_upstream_file(self):
        self.at_head(
            self.commit(
                self.head, {"toughio/__about__.py": b"__version__ = 'unapproved'\n"}
            )
        )
        self.check(error="TH_PATH")

    def test_toughplus_registration_extra_line(self):
        path = "toughio/_io/input/__init__.py"
        content = self.git("show", f"{self.head}:{path}").encode() + b"# extra change\n"
        self.at_head(self.commit(self.head, {path: content}))
        self.check(error="REGISTRATION")

    def test_toughplus_pyproject_dependency(self):
        original = self.git("show", f"{self.head}:pyproject.toml")
        content = original.replace('    "h5py",', '    "h5py>=999",').encode()
        self.at_head(self.commit(self.head, {"pyproject.toml": content}))
        self.check(error="PYPROJECT_FIELDS")

    def test_toughplus_pyproject_extra_comment(self):
        content = (
            self.git("show", f"{self.head}:pyproject.toml").encode()
            + b"# outside permitted metadata\n"
        )
        self.at_head(self.commit(self.head, {"pyproject.toml": content}))
        self.check(error="PYPROJECT_TEXT")

    def test_toughplus_pyproject_extra_package_data(self):
        original = self.git("show", f"{self.head}:pyproject.toml")
        content = (original + '\n[tool.setuptools.package-data]\n"toughio" = ["*.json"]\n').encode()
        self.at_head(self.commit(self.head, {"pyproject.toml": content}))
        self.check(error="PYPROJECT_FIELDS")

    def test_toughplus_lfs_document(self):
        self.at_head(self.commit(self.head, {"docs/toughplus/violation.md": POINTER}))
        self.check(error="LFS_TEXT")

    def test_toughplus_lfs_python_module(self):
        self.at_head(self.commit(self.head, {"toughio/hydrate/violation.py": POINTER}))
        self.check(error="LFS_TEXT")

    def test_toughplus_lfs_fixture_is_allowed(self):
        self.at_head(
            self.commit(
                self.head, {"tests/tough_hydrate/fixtures/synthetic.out": POINTER}
            )
        )
        self.check()

    def test_toughplus_landing_page_is_allowed(self):
        self.at_head(self.commit(self.head, {".github/README.md": b"# fork\n"}))
        self.check()

    def test_toughplus_other_github_file(self):
        self.at_head(
            self.commit(self.head, {".github/PULL_REQUEST_TEMPLATE.md": b"fork\n"})
        )
        self.check(error="TH_PATH")

    def test_toughplus_upstream_test_modification(self):
        content = (
            self.git("show", f"{self.head}:tests/test_output.py").encode()
            + b"# unapproved test migration\n"
        )
        self.at_head(self.commit(self.head, {"tests/test_output.py": content}))
        self.check(error="TH_PATH")

    def test_toughplus_upstream_deletion(self):
        self.at_head(self.commit(self.head, {"README.rst": None}))
        self.check(error="TH_PATH")

    def test_toughplus_missing_base_ancestor(self):
        self.at_head(self.data["upstream"]["sha"])
        self.check(error="TH_ANCESTRY")

    def test_pr_distribution_metadata(self):
        self.check("pr", "HEAD", error="PR_METADATA")

    def test_pr_fork_document(self):
        sha = self.commit(
            self.data["upstream"]["sha"],
            {"docs/toughplus/violation.md": b"fork content\n"},
        )
        self.git("update-ref", "refs/heads/violation-pr", sha)
        self.check("pr", "violation-pr", error="PR_FORK_PATH")

    def test_pr_landing_page(self):
        sha = self.commit(
            self.data["upstream"]["sha"], {".github/README.md": b"# fork\n"}
        )
        self.git("update-ref", "refs/heads/violation-pr", sha)
        self.check("pr", "violation-pr", error="PR_FORK_PATH")

    def test_pr_registration(self):
        upstream = self.data["upstream"]["sha"]
        path = "toughio/_io/input/__init__.py"
        original = self.git("show", f"{upstream}:{path}")
        content = original.replace("toughreact", "toughreact, tough_hydrate").encode()
        sha = self.commit(upstream, {path: content})
        self.git("update-ref", "refs/heads/violation-pr", sha)
        self.check("pr", "violation-pr", error="PR_REGISTRATION")

    def test_pr_reverted_metadata_still_contains_rename_history(self):
        sha = self.commit(self.head, tree_from=self.data["upstream"]["sha"])
        self.git("update-ref", "refs/heads/violation-pr", sha)
        self.check("pr", "violation-pr", error="PR_RENAME_HISTORY")


class BaselineComparison(unittest.TestCase):
    def test_same_counts_different_nodeids_are_rejected(self):
        with self.assertRaises(DRIVER.Failure):
            DRIVER.compare_results({"tests/a": "passed"}, {"tests/b": "passed"})

    def test_same_counts_swapped_outcomes_are_rejected(self):
        with self.assertRaises(DRIVER.Failure):
            DRIVER.compare_results(
                {"tests/a": "passed", "tests/b": "failed"},
                {"tests/a": "failed", "tests/b": "passed"},
            )

    def test_identical_outcomes_are_accepted(self):
        DRIVER.compare_results({"tests/a": "passed"}, {"tests/a": "passed"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
