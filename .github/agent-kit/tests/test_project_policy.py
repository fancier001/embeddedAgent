from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml


AGENT_KIT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = AGENT_KIT_ROOT.parents[1]
FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "commit"
sys.path.insert(0, str(AGENT_KIT_ROOT / "scripts"))

from project_policy import (  # noqa: E402
    DECISION_AUTO_UPLOAD,
    DECISION_MESSAGE_ONLY,
    DECISION_NO_DELIVERY,
    GitReadError,
    PolicyInputError,
    _matches,
    _redact_url,
    git_plan,
    resolve_push_target,
    resolve_rules,
    validate_message,
)


class ProjectRuleTests(unittest.TestCase):
    def test_missing_project_directory_is_compatible(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            message = root / "message.txt"
            message.write_text("legacy message\n", encoding="utf-8")
            rules_result = resolve_rules(root, ["source/example.c"])
            message_result = validate_message(root, message)
            plan_result = git_plan(
                root,
                operation="commit",
                delivery="commit",
                paths=["source/example.c"],
                message_file=message,
            )
        self.assertEqual("NOT_CONFIGURED", rules_result["status"])
        self.assertEqual("NOT_CONFIGURED", message_result["status"])
        self.assertEqual("NOT_CONFIGURED", plan_result["status"])

    def test_rules_are_selected_by_repository_path(self) -> None:
        c_result = resolve_rules(
            PROJECT_ROOT, ["examples/minimal-firmware/src/status_led.c"]
        )
        doc_result = resolve_rules(PROJECT_ROOT, ["docs/manual-smoke-test.md"])
        self.assertEqual(
            ["repository-path-policy", "embedded-c-conventions"],
            [entry["id"] for entry in c_result["rules"]],
        )
        self.assertEqual(
            ["repository-path-policy"],
            [entry["id"] for entry in doc_result["rules"]],
        )
        self.assertEqual(".project/git/delivery.yml", c_result["git_policy"])

    def test_globs_are_root_anchored_and_double_star_is_recursive(self) -> None:
        self.assertTrue(_matches("examples/a/b/file.c", "examples/**"))
        self.assertFalse(_matches("nested/examples/file.c", "examples/**"))
        self.assertTrue(_matches("root.c", "**/*.c"))
        self.assertTrue(_matches("nested/root.c", "**/*.c"))

    def test_unsafe_path_and_missing_required_rule_are_rejected(self) -> None:
        with self.assertRaises(PolicyInputError):
            resolve_rules(PROJECT_ROOT, ["../outside.c"])
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / "repository"
            shutil.copytree(PROJECT_ROOT / ".project", repo / ".project")
            (repo / ".project" / "rules" / "coding-conventions.md").unlink()
            with self.assertRaises(PolicyInputError):
                resolve_rules(repo, ["source/example.c"])

    def test_git_target_override_is_rejected_anywhere_in_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / "repository"
            shutil.copytree(PROJECT_ROOT / ".project", repo / ".project")
            policy_path = repo / ".project" / "git" / "delivery.yml"
            policy_data = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
            policy_data["extensions"] = {"vendor": {"target-branch": "unsafe"}}
            policy_path.write_text(
                yaml.safe_dump(policy_data, sort_keys=False), encoding="utf-8"
            )
            with self.assertRaises(PolicyInputError):
                resolve_rules(repo, ["README.md"])


class CommitMessageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repo = Path(self.temporary.name) / "repository"
        shutil.copytree(PROJECT_ROOT / ".project", self.repo / ".project")
        self.valid_text = (FIXTURE_ROOT / "valid-qdm047-bug-fix.txt").read_text(
            encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def validate(self, text: str) -> dict[str, object]:
        message = self.repo / "message.txt"
        message.write_text(text, encoding="utf-8")
        return dict(validate_message(self.repo, message))

    def test_qdm047_fixture_and_multiple_jira_ids_pass(self) -> None:
        result = self.validate(self.valid_text)
        self.assertEqual("PASS", result["status"], result["errors"])
        self.assertEqual(["QDM047-5567", "QDM047-5566"], result["jira_ids"])

    def test_configured_primary_and_aliases_control_subject_project(self) -> None:
        manifest_path = self.repo / ".project" / "project.yml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest["project"] = {"primary": "QDM033", "aliases": ["QDM047"]}
        manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
        )
        self.assertEqual("PASS", self.validate(self.valid_text)["status"])
        manifest["project"]["aliases"] = []
        manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
        )
        codes = {item["code"] for item in self.validate(self.valid_text)["errors"]}
        self.assertIn("PROJECT_MISMATCH", codes)

    def test_new_requirements_requires_na_root_cause(self) -> None:
        text = self.valid_text.replace("bug fix", "new requirements").replace(
            "<Root Cause>:Webui logic does not persist the selected DHCP option",
            "<Root Cause>:N/A",
        )
        self.assertEqual("PASS", self.validate(text)["status"])
        invalid = text.replace("<Root Cause>:N/A", "<Root Cause>:A defect")
        codes = {item["code"] for item in self.validate(invalid)["errors"]}
        self.assertIn("ROOT_CAUSE", codes)

    def test_field_order_unknown_field_placeholders_and_empty_values_block(self) -> None:
        mutations = {
            "order": self.valid_text.replace(
                "<Change Reason>:WAN setting DHCP option cannot be configured\n"
                "<Root Cause>:Webui logic does not persist the selected DHCP option",
                "<Root Cause>:Webui logic does not persist the selected DHCP option\n"
                "<Change Reason>:WAN setting DHCP option cannot be configured",
            ),
            "unknown": self.valid_text.replace(
                "<Solution>:", "<Unknown>:value\n<Solution>:"
            ),
            "non-contiguous-jira": self.valid_text.replace(
                "<Jira ID>:QDM047-5567\n<Jira ID>:QDM047-5566",
                "<Jira ID>:QDM047-5567\n\n<Jira ID>:QDM047-5566",
            ),
            "placeholder": self.valid_text.replace("<QDM047><Webui>", "<Project><Webui>"),
            "empty": self.valid_text.replace(
                "<Solution>:Update the Webui logic to persist and apply the DHCP option",
                "<Solution>:",
            ),
        }
        for name, message in mutations.items():
            with self.subTest(name=name):
                self.assertEqual("BLOCKED", self.validate(message)["status"])

    def test_ai_rn_and_test_note_conditions_block_invalid_combinations(self) -> None:
        mutations = {
            "ai-n": self.valid_text.replace("<AI-Tool-Used>:Y", "<AI-Tool-Used>:N"),
            "ai-scenario": self.valid_text.replace(
                "<AI-Tool-Scenario>:Code Inspection",
                "<AI-Tool-Scenario>:Unapproved Scenario",
            ),
            "rn-y": self.valid_text.replace(
                "<RN description>:Fixed the bug that the DHCP option does not work in the WAN Setting menu.",
                "<RN description>:N/A",
            ),
            "test-y": self.valid_text.replace(
                "<Test-Proposal>:Y\n  1. Open the WAN Setting menu.\n"
                "  2. Change the DHCP option and verify that it is applied.",
                "<Test-Proposal>:Y",
            ),
            "stress-y": self.valid_text.replace("<Stress-Test>:N", "<Stress-Test>:Y"),
            "hw-y": self.valid_text.replace("<HW-Test>:N", "<HW-Test>:Y"),
        }
        for name, message in mutations.items():
            with self.subTest(name=name):
                self.assertEqual("BLOCKED", self.validate(message)["status"])

    def test_no_ai_no_rn_and_test_rationale_pass(self) -> None:
        text = self.valid_text
        text = text.replace("<AI-Tool-Used>:Y", "<AI-Tool-Used>:N")
        text = text.replace("<AI-Tool-Scenario>:Code Inspection", "<AI-Tool-Scenario>:N/A")
        text = text.replace(
            "<AI-Tool-Detail>:Used Codex to inspect the existing logic and verify the change",
            "<AI-Tool-Detail>:N/A",
        )
        text = text.replace("<RN>:Y", "<RN>:N")
        text = text.replace(
            "<RN description>:Fixed the bug that the DHCP option does not work in the WAN Setting menu.",
            "<RN description>:N/A",
        )
        text = text.replace(
            "<Test-Proposal>:Y\n  1. Open the WAN Setting menu.\n"
            "  2. Change the DHCP option and verify that it is applied.",
            "<Test-Proposal>:N No dedicated test is needed for this documentation-only change.",
        )
        self.assertEqual("PASS", self.validate(text)["status"])

    def test_unfilled_repository_template_is_rejected_as_a_message(self) -> None:
        template = (self.repo / ".project" / "git" / "commit.template").read_text(
            encoding="utf-8"
        )
        self.assertEqual("BLOCKED", self.validate(template)["status"])


class GitPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("Git is unavailable")
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.repo = self.base / "repository"
        self.remote = self.base / "remote.git"
        self.repo.mkdir()
        self.git(self.repo, "init", "-b", "feature/test")
        self.git(self.remote.parent, "init", "--bare", str(self.remote))
        self.git(self.repo, "config", "user.name", "Policy Test")
        self.git(self.repo, "config", "user.email", "policy@example.invalid")
        shutil.copytree(PROJECT_ROOT / ".project", self.repo / ".project")
        policy_path = self.repo / ".project" / "git" / "delivery.yml"
        policy_data = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
        policy_data["automation"] = {"commit": True, "push": True}
        policy_path.write_text(
            yaml.safe_dump(policy_data, sort_keys=False), encoding="utf-8"
        )
        (self.repo / "README.md").write_text("base\n", encoding="utf-8")
        self.git(self.repo, "add", ".project", "README.md")
        self.git(self.repo, "commit", "-m", "test baseline")
        self.git(self.repo, "remote", "add", "origin", str(self.remote))
        self.git(self.repo, "config", "branch.feature/test.remote", "origin")
        self.git(
            self.repo,
            "config",
            "branch.feature/test.merge",
            "refs/heads/feature/test",
        )
        self.git(self.repo, "push", "origin", "HEAD:refs/heads/feature/test")
        (self.repo / "README.md").write_text("base\noutgoing\n", encoding="utf-8")
        self.git(self.repo, "add", "README.md")
        self.git(self.repo, "commit", "-m", "outgoing change")

    def tearDown(self) -> None:
        if hasattr(self, "temporary"):
            self.temporary.cleanup()

    @staticmethod
    def git(cwd: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(cwd), *arguments],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=check,
        )

    def snapshot(self) -> tuple[str, str, bytes, bytes, str]:
        return (
            self.git(self.repo, "rev-parse", "HEAD").stdout,
            self.git(self.repo, "status", "--porcelain=v1").stdout,
            (self.repo / ".git" / "index").read_bytes(),
            (self.repo / ".git" / "config").read_bytes(),
            self.git(self.remote, "rev-parse", "refs/heads/feature/test").stdout,
        )

    def auto_message(self, text: str | None = None) -> Path:
        message = self.base / "auto-message.txt"
        message.write_text(
            text
            if text is not None
            else (FIXTURE_ROOT / "valid-qdm047-bug-fix.txt").read_text(
                encoding="utf-8"
            ),
            encoding="utf-8",
        )
        return message

    def prepare_auto_change(self) -> Path:
        self.git(self.repo, "push", "origin", "HEAD:refs/heads/feature/test")
        self.git(self.repo, "fetch", "origin")
        current = (self.repo / "README.md").read_text(encoding="utf-8")
        (self.repo / "README.md").write_text(
            current + "pending auto delivery\n", encoding="utf-8"
        )
        return self.auto_message()

    def auto_plan(self, message: Path) -> dict[str, object]:
        return dict(
            git_plan(
                self.repo,
                operation="auto",
                delivery="auto",
                paths=["README.md"],
                message_file=message,
            )
        )

    def test_local_config_resolves_remote_url_branch_and_target_ref(self) -> None:
        target = resolve_push_target(self.repo)
        self.assertEqual("origin", target["remote"])
        self.assertEqual("feature/test", target["current_branch"])
        self.assertEqual("refs/heads/feature/test", target["target_ref"])
        self.assertEqual(self.remote.as_posix(), Path(target["push_url"]).as_posix())
        self.assertTrue(all(target["config_sources"].values()))

    def test_environment_and_global_style_overrides_are_ignored(self) -> None:
        environment = {
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "remote.origin.url",
            "GIT_CONFIG_VALUE_0": "https://attacker.invalid/wrong.git",
        }
        with patch.dict(os.environ, environment, clear=False):
            target = resolve_push_target(self.repo)
        self.assertEqual(self.remote.as_posix(), Path(target["push_url"]).as_posix())

    def test_unique_pushurl_is_preferred_and_credentials_are_redacted(self) -> None:
        self.git(
            self.repo,
            "config",
            "remote.origin.pushurl",
            "https://user:token@example.invalid/repo.git?access_token=secret",
        )
        target = resolve_push_target(self.repo)
        self.assertEqual("https://***@example.invalid/repo.git?***", target["push_url"])
        self.assertNotIn("token", target["push_url"])
        self.assertEqual("https://***@host/repo?***#***", _redact_url("https://u:p@host/repo?q=x#secret"))

    def test_multiple_pushurls_missing_upstream_detached_and_wrong_ref_block(self) -> None:
        self.git(self.repo, "config", "--add", "remote.origin.pushurl", "one")
        self.git(self.repo, "config", "--add", "remote.origin.pushurl", "two")
        with self.assertRaises(GitReadError):
            resolve_push_target(self.repo)
        self.git(self.repo, "config", "--unset-all", "remote.origin.pushurl")
        self.git(self.repo, "config", "--unset", "branch.feature/test.remote")
        with self.assertRaises(GitReadError):
            resolve_push_target(self.repo)
        self.git(self.repo, "config", "branch.feature/test.remote", "origin")
        self.git(self.repo, "config", "branch.feature/test.merge", "refs/tags/test")
        with self.assertRaises(GitReadError):
            resolve_push_target(self.repo)
        self.git(self.repo, "config", "branch.feature/test.merge", "refs/heads/feature/test")
        self.git(self.repo, "checkout", "--detach")
        with self.assertRaises(GitReadError):
            resolve_push_target(self.repo)

    def test_wrong_root_and_missing_git_metadata_block(self) -> None:
        child = self.repo / "child"
        child.mkdir()
        with self.assertRaises(GitReadError):
            resolve_push_target(child)
        outside = self.base / "not-a-repository"
        outside.mkdir()
        with self.assertRaises(GitReadError):
            resolve_push_target(outside)

    def test_push_plan_is_read_only_and_reports_outgoing_paths(self) -> None:
        before = self.snapshot()
        result = git_plan(
            self.repo, operation="push", delivery="commit-and-push"
        )
        after = self.snapshot()
        self.assertEqual("PASS", result["status"], result["reasons"])
        self.assertEqual(["README.md"], result["outgoing_paths"])
        self.assertEqual(before, after)

    def test_auto_plan_selects_upload_and_is_read_only(self) -> None:
        message = self.prepare_auto_change()
        before = self.snapshot()
        result = self.auto_plan(message)
        after = self.snapshot()
        self.assertEqual("PASS", result["status"])
        self.assertEqual(DECISION_AUTO_UPLOAD, result["decision"])
        self.assertEqual([], result["decision_reasons"])
        self.assertEqual(before, after)

    def test_auto_plan_returns_no_delivery_without_changes(self) -> None:
        result = git_plan(self.repo, operation="auto", delivery="auto")
        self.assertEqual("PASS", result["status"])
        self.assertEqual(DECISION_NO_DELIVERY, result["decision"])

    def test_auto_plan_blocks_invalid_message_instead_of_using_placeholders(self) -> None:
        self.prepare_auto_change()
        message = self.auto_message("<Project><Function block>: <Summary>\n")
        result = self.auto_plan(message)
        self.assertEqual("BLOCKED", result["status"])
        self.assertIsNone(result["decision"])

    def test_auto_plan_falls_back_for_existing_outgoing_commit(self) -> None:
        current = (self.repo / "README.md").read_text(encoding="utf-8")
        (self.repo / "README.md").write_text(current + "pending\n", encoding="utf-8")
        before = self.snapshot()
        result = self.auto_plan(self.auto_message())
        after = self.snapshot()
        self.assertEqual(DECISION_MESSAGE_ONLY, result["decision"])
        self.assertTrue(
            any("upstream tracking ref" in reason for reason in result["decision_reasons"])
        )
        self.assertEqual(before, after)

    def test_auto_plan_falls_back_for_existing_incoming_commit(self) -> None:
        message = self.prepare_auto_change()
        tree = self.git(self.repo, "write-tree").stdout.strip()
        parent = self.git(self.repo, "rev-parse", "HEAD").stdout.strip()
        incoming = self.git(
            self.repo,
            "commit-tree",
            tree,
            "-p",
            parent,
            "-m",
            "simulated incoming commit",
        ).stdout.strip()
        self.git(
            self.repo,
            "update-ref",
            "refs/remotes/origin/feature/test",
            incoming,
        )
        result = self.auto_plan(message)
        self.assertEqual(DECISION_MESSAGE_ONLY, result["decision"])
        self.assertTrue(
            any("upstream tracking ref" in reason for reason in result["decision_reasons"])
        )

    def test_auto_plan_falls_back_for_unrelated_or_staged_changes(self) -> None:
        message = self.prepare_auto_change()
        docs = self.repo / "docs"
        docs.mkdir()
        (docs / "unrelated.md").write_text("unrelated\n", encoding="utf-8")
        self.git(self.repo, "add", "README.md")
        result = self.auto_plan(message)
        self.assertEqual(DECISION_MESSAGE_ONLY, result["decision"])
        self.assertTrue(
            any("outside auto delivery scope" in reason for reason in result["decision_reasons"])
        )
        self.assertTrue(
            any("index must be empty" in reason for reason in result["decision_reasons"])
        )

    def test_auto_plan_falls_back_when_automation_or_push_target_is_unavailable(self) -> None:
        message = self.prepare_auto_change()
        policy_path = self.repo / ".project" / "git" / "delivery.yml"
        policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
        policy["automation"]["push"] = False
        policy_path.write_text(yaml.safe_dump(policy, sort_keys=False), encoding="utf-8")
        self.git(self.repo, "config", "--unset", "branch.feature/test.remote")
        result = self.auto_plan(message)
        self.assertEqual(DECISION_MESSAGE_ONLY, result["decision"])
        self.assertTrue(
            any("automatic push is disabled" in reason for reason in result["decision_reasons"])
        )
        self.assertTrue(
            any("must have exactly one value" in reason for reason in result["decision_reasons"])
        )

    def test_auto_plan_falls_back_for_protected_branch(self) -> None:
        message = self.prepare_auto_change()
        self.git(self.repo, "branch", "-m", "main")
        self.git(self.repo, "config", "branch.main.remote", "origin")
        self.git(self.repo, "config", "branch.main.merge", "refs/heads/main")
        result = self.auto_plan(message)
        self.assertEqual(DECISION_MESSAGE_ONLY, result["decision"])
        self.assertTrue(
            any("protected" in reason for reason in result["decision_reasons"])
        )

    def test_auto_plan_falls_back_for_multiple_pushurls(self) -> None:
        message = self.prepare_auto_change()
        self.git(self.repo, "config", "--add", "remote.origin.pushurl", "one")
        self.git(self.repo, "config", "--add", "remote.origin.pushurl", "two")
        result = self.auto_plan(message)
        self.assertEqual(DECISION_MESSAGE_ONLY, result["decision"])
        self.assertTrue(
            any("exactly one" in reason for reason in result["decision_reasons"])
        )

    def test_auto_commit_and_push_preflight_locks_new_commit(self) -> None:
        message = self.prepare_auto_change()
        decision = self.auto_plan(message)
        self.assertEqual(DECISION_AUTO_UPLOAD, decision["decision"])
        self.git(self.repo, "add", "README.md")
        commit_plan = git_plan(
            self.repo,
            operation="commit",
            delivery="auto",
            paths=["README.md"],
            message_file=message,
        )
        self.assertEqual("PASS", commit_plan["status"], commit_plan["reasons"])
        self.git(self.repo, "commit", "-F", str(message))
        commit_sha = self.git(self.repo, "rev-parse", "HEAD").stdout.strip()
        push_plan = git_plan(
            self.repo,
            operation="push",
            delivery="auto",
            expected_fingerprint=decision["push_target"]["fingerprint"],
            expected_commit=commit_sha,
        )
        self.assertEqual("PASS", push_plan["status"], push_plan["reasons"])
        self.assertEqual([commit_sha], push_plan["outgoing_commits"])
        self.git(self.repo, "push", "origin", "HEAD:refs/heads/feature/test")
        remote_sha = self.git(
            self.remote, "rev-parse", "refs/heads/feature/test"
        ).stdout.strip()
        self.assertEqual(commit_sha, remote_sha)

    def test_auto_push_rejects_wrong_expected_commit(self) -> None:
        message = self.prepare_auto_change()
        decision = self.auto_plan(message)
        self.git(self.repo, "add", "README.md")
        self.git(self.repo, "commit", "-F", str(message))
        result = git_plan(
            self.repo,
            operation="push",
            delivery="auto",
            expected_fingerprint=decision["push_target"]["fingerprint"],
            expected_commit="0" * 40,
        )
        self.assertEqual("BLOCKED", result["status"])
        self.assertTrue(
            any("only the newly created commit" in reason for reason in result["reasons"])
        )

    def test_auto_push_stops_on_fingerprint_drift_and_keeps_commit(self) -> None:
        message = self.prepare_auto_change()
        decision = self.auto_plan(message)
        self.git(self.repo, "add", "README.md")
        self.git(self.repo, "commit", "-F", str(message))
        commit_sha = self.git(self.repo, "rev-parse", "HEAD").stdout.strip()
        self.git(
            self.repo,
            "config",
            "remote.origin.pushurl",
            "https://example.invalid/drifted.git",
        )
        result = git_plan(
            self.repo,
            operation="push",
            delivery="auto",
            expected_fingerprint=decision["push_target"]["fingerprint"],
            expected_commit=commit_sha,
        )
        self.assertEqual("BLOCKED", result["status"])
        self.assertTrue(
            any("changed after preflight" in reason for reason in result["reasons"])
        )
        self.assertEqual(commit_sha, self.git(self.repo, "rev-parse", "HEAD").stdout.strip())

    def test_failed_auto_push_keeps_local_commit(self) -> None:
        message = self.prepare_auto_change()
        self.git(
            self.repo,
            "config",
            "remote.origin.url",
            "http://127.0.0.1:9/unavailable.git",
        )
        decision = self.auto_plan(message)
        self.assertEqual(DECISION_AUTO_UPLOAD, decision["decision"])
        self.git(self.repo, "add", "README.md")
        self.git(self.repo, "commit", "-F", str(message))
        commit_sha = self.git(self.repo, "rev-parse", "HEAD").stdout.strip()
        push_plan = git_plan(
            self.repo,
            operation="push",
            delivery="auto",
            expected_fingerprint=decision["push_target"]["fingerprint"],
            expected_commit=commit_sha,
        )
        self.assertEqual("PASS", push_plan["status"], push_plan["reasons"])
        pushed = subprocess.run(
            [
                "git",
                "-C",
                str(self.repo),
                "push",
                "origin",
                "HEAD:refs/heads/feature/test",
            ],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            timeout=15,
        )
        self.assertNotEqual(0, pushed.returncode)
        self.assertEqual(commit_sha, self.git(self.repo, "rev-parse", "HEAD").stdout.strip())

    def test_commit_plan_blocks_staged_files_outside_explicit_scope(self) -> None:
        docs = self.repo / "docs"
        docs.mkdir()
        requested = docs / "note.md"
        requested.write_text("note\n", encoding="utf-8")
        (self.repo / "README.md").write_text("unrelated staged change\n", encoding="utf-8")
        self.git(self.repo, "add", "README.md")
        message = self.repo / "message.txt"
        shutil.copyfile(FIXTURE_ROOT / "valid-qdm047-bug-fix.txt", message)
        result = git_plan(
            self.repo,
            operation="commit",
            delivery="commit",
            paths=["docs/note.md"],
            message_file=message,
        )
        self.assertEqual("BLOCKED", result["status"])
        self.assertTrue(
            any("staged paths are outside delivery scope" in reason for reason in result["reasons"])
        )

    def test_protected_branch_and_configuration_drift_block(self) -> None:
        original = resolve_push_target(self.repo)
        self.git(self.repo, "config", "remote.origin.pushurl", "https://example.invalid/changed.git")
        drift = git_plan(
            self.repo,
            operation="push",
            delivery="commit-and-push",
            expected_fingerprint=original["fingerprint"],
        )
        self.assertIn("local .git push target changed after preflight", drift["reasons"])

        self.git(self.repo, "branch", "-m", "main")
        self.git(self.repo, "config", "branch.main.remote", "origin")
        self.git(self.repo, "config", "branch.main.merge", "refs/heads/main")
        protected = git_plan(
            self.repo, operation="push", delivery="commit-and-push"
        )
        self.assertTrue(any("protected" in reason for reason in protected["reasons"]))

    def test_linked_worktree_uses_common_git_directory(self) -> None:
        linked = self.base / "linked"
        self.git(self.repo, "worktree", "add", "-b", "feature/linked", str(linked), "HEAD")
        self.git(linked, "config", "branch.feature/linked.remote", "origin")
        self.git(linked, "config", "branch.feature/linked.merge", "refs/heads/feature/linked")
        target = resolve_push_target(linked)
        self.assertNotEqual(target["git_dir"], target["git_common_dir"])
        self.assertTrue(target["git_common_dir"].endswith("/.git"))


if __name__ == "__main__":
    unittest.main()
