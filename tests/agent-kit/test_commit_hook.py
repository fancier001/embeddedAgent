from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = (
    REPO_ROOT
    / "tests"
    / "agent-kit"
    / "fixtures"
    / "commit"
    / "valid-qdm047-bug-fix.txt"
)


class CommitMessageHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.repo = Path(self.temporary_directory.name) / "repository"
        self.repo.mkdir()
        self.git("init", "-b", "feature/hook-gate")
        self.git("config", "user.name", "Hook Test")
        self.git("config", "user.email", "hook@example.invalid")

        shutil.copytree(REPO_ROOT / ".project", self.repo / ".project")
        shutil.copytree(REPO_ROOT / ".githooks", self.repo / ".githooks")
        scripts = self.repo / ".github" / "agent-kit" / "scripts"
        scripts.mkdir(parents=True)
        shutil.copy2(
            REPO_ROOT / ".github" / "agent-kit" / "scripts" / "project_policy.py",
            scripts / "project_policy.py",
        )
        (self.repo / "README.md").write_text("baseline\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-m", "test baseline")

        self.valid_message = Path(self.temporary_directory.name) / "valid-message.txt"
        shutil.copy2(FIXTURE, self.valid_message)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def git(
        self,
        *arguments: str,
        check: bool = True,
        environment: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            ["git", "-C", str(self.repo), *arguments],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            env=environment,
        )
        if check and completed.returncode != 0:
            self.fail(
                f"git {' '.join(arguments)} failed with {completed.returncode}:\n"
                f"{completed.stdout}\n{completed.stderr}"
            )
        return completed

    def hook_environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        environment["PROJECT_POLICY_PYTHON"] = str(Path(sys.executable).resolve())
        return environment

    def stage_change(self, content: str = "baseline\nchanged\n") -> None:
        (self.repo / "README.md").write_text(content, encoding="utf-8")
        self.git("add", "--", "README.md")

    def commit_with_hook(
        self,
        message_file: Path,
        *,
        environment: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        hook = self.repo / ".githooks" / "commit-msg"
        self.assertTrue(hook.is_file(), "Agent precondition: commit-msg hook must exist")
        return self.git(
            "-c",
            f"core.hooksPath={hook.parent.resolve()}",
            "commit",
            "--file",
            str(message_file.resolve()),
            "--cleanup=verbatim",
            check=False,
            environment=environment or self.hook_environment(),
        )

    def snapshot(self) -> tuple[str, str, str, bytes]:
        return (
            self.git("rev-parse", "HEAD").stdout.strip(),
            self.git("write-tree").stdout.strip(),
            self.git("status", "--porcelain=v1", "--untracked-files=all").stdout,
            (self.repo / ".git" / "config").read_bytes(),
        )

    def test_invalid_messages_are_rejected_without_repository_changes(self) -> None:
        valid_text = self.valid_message.read_text(encoding="utf-8")
        invalid_messages = {
            "single line": "not a project commit message\n",
            "missing field": valid_text.replace("<HW-Test>:N\n", ""),
            "invalid field value": valid_text.replace(
                "<AI-Tool-Used>:Y",
                "<AI-Tool-Used>:MAYBE",
            ),
        }

        for name, content in invalid_messages.items():
            with self.subTest(name=name):
                self.stage_change()
                message = Path(self.temporary_directory.name) / f"{name}.txt"
                message.write_text(content, encoding="utf-8")
                before = self.snapshot()

                committed = self.commit_with_hook(message)

                self.assertNotEqual(0, committed.returncode)
                self.assertEqual(before, self.snapshot())
                self.git("restore", "--staged", "--worktree", "--", "README.md")

    def test_complete_template_commits_exact_message_without_installing_hook(self) -> None:
        self.stage_change()
        configured_before = self.git(
            "config",
            "--local",
            "--get-all",
            "core.hooksPath",
            check=False,
        )
        self.assertEqual(1, configured_before.returncode)

        committed = self.commit_with_hook(self.valid_message)

        self.assertEqual(0, committed.returncode, committed.stderr)
        actual = self.git("log", "-1", "--format=%B").stdout.rstrip("\n")
        expected = self.valid_message.read_text(encoding="utf-8").rstrip("\n")
        self.assertEqual(expected, actual)
        configured_after = self.git(
            "config",
            "--local",
            "--get-all",
            "core.hooksPath",
            check=False,
        )
        self.assertEqual(1, configured_after.returncode)

    def test_hook_fails_closed_when_policy_dependencies_are_missing(self) -> None:
        dependency_paths = (
            self.repo / ".project",
            self.repo / ".project" / "git" / "delivery.yml",
            self.repo / ".project" / "git" / "commit.template",
            self.repo
            / ".github"
            / "agent-kit"
            / "scripts"
            / "project_policy.py",
        )

        for dependency in dependency_paths:
            with self.subTest(dependency=dependency.relative_to(self.repo).as_posix()):
                self.stage_change()
                backup = Path(self.temporary_directory.name) / "dependency-backup"
                was_directory = dependency.is_dir()
                if was_directory:
                    shutil.copytree(dependency, backup)
                    shutil.rmtree(dependency)
                else:
                    shutil.copy2(dependency, backup)
                    dependency.unlink()
                before = self.snapshot()

                try:
                    committed = self.commit_with_hook(self.valid_message)

                    self.assertNotEqual(0, committed.returncode)
                    self.assertEqual(before, self.snapshot())
                finally:
                    if was_directory:
                        shutil.copytree(backup, dependency)
                        shutil.rmtree(backup)
                    else:
                        shutil.copy2(backup, dependency)
                        backup.unlink()
                    self.git(
                        "restore",
                        "--staged",
                        "--worktree",
                        "--",
                        "README.md",
                    )

    def test_hook_fails_closed_when_configured_python_is_unavailable(self) -> None:
        self.stage_change()
        before = self.snapshot()
        environment = self.hook_environment()
        environment["PROJECT_POLICY_PYTHON"] = str(
            Path(self.temporary_directory.name) / "missing-python"
        )

        committed = self.commit_with_hook(
            self.valid_message,
            environment=environment,
        )

        self.assertNotEqual(0, committed.returncode)
        self.assertEqual(before, self.snapshot())


if __name__ == "__main__":
    unittest.main()
