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


TEST_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = TEST_ROOT.parents[1]
FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "commit"
sys.path.insert(0, str(PROJECT_ROOT / ".github" / "agent-kit" / "scripts"))

from project_policy import (  # noqa: E402
    DECISION_AUTO_UPLOAD,
    DECISION_CONFIRM_AUTO_CONTENT,
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
        doc_result = resolve_rules(
            PROJECT_ROOT, ["tests/agent-kit/manual/vscode-smoke-test.md"]
        )
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

    def test_commit_template_requires_canonical_no_ai_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / "repository"
            shutil.copytree(PROJECT_ROOT / ".project", repo / ".project")
            template = repo / ".project" / "git" / "commit.template"
            template.write_text(
                template.read_text(encoding="utf-8").replace(
                    "<AI-Tool-Scenario>: /", "<AI-Tool-Scenario>: N/A"
                ),
                encoding="utf-8",
            )
            with self.assertRaises(PolicyInputError):
                resolve_rules(repo, ["README.md"])

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

    def test_legacy_allowed_paths_do_not_restrict_product_code(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / "repository"
            shutil.copytree(PROJECT_ROOT / ".project", repo / ".project")
            policy_path = repo / ".project" / "git" / "delivery.yml"
            policy_data = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
            policy_data["scope"]["allowed_paths"] = ["docs/**"]
            policy_path.write_text(
                yaml.safe_dump(policy_data, sort_keys=False), encoding="utf-8"
            )
            result = resolve_rules(repo, ["source/product.c"])
            self.assertEqual("PASS", result["status"])


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
        text = text.replace("<AI-Tool-Used>:Y", "<AI-Tool-Used>: N")
        text = text.replace("<AI-Tool-Scenario>:Code Inspection", "<AI-Tool-Scenario>: /")
        text = text.replace(
            "<AI-Tool-Detail>:Used Codex to inspect the existing logic and verify the change",
            "<AI-Tool-Detail>: /",
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

    def test_no_ai_rejects_na_empty_and_usage_content(self) -> None:
        canonical = self.valid_text
        canonical = canonical.replace("<AI-Tool-Used>:Y", "<AI-Tool-Used>:N")
        canonical = canonical.replace(
            "<AI-Tool-Scenario>:Code Inspection", "<AI-Tool-Scenario>:/"
        )
        canonical = canonical.replace(
            "<AI-Tool-Detail>:Used Codex to inspect the existing logic and verify the change",
            "<AI-Tool-Detail>:/",
        )
        mutations = {
            "na": canonical.replace("<AI-Tool-Scenario>:/", "<AI-Tool-Scenario>:N/A").replace(
                "<AI-Tool-Detail>:/", "<AI-Tool-Detail>:N/A"
            ),
            "empty": canonical.replace("<AI-Tool-Detail>:/", "<AI-Tool-Detail>:"),
            "scenario": canonical.replace(
                "<AI-Tool-Scenario>:/", "<AI-Tool-Scenario>:Code Inspection"
            ),
            "detail": canonical.replace(
                "<AI-Tool-Detail>:/", "<AI-Tool-Detail>:AI inspected the change"
            ),
        }
        for name, message in mutations.items():
            with self.subTest(name=name):
                codes = {item["code"] for item in self.validate(message)["errors"]}
                self.assertIn("AI_CONDITION", codes)

    def test_ai_used_rejects_slash_detail(self) -> None:
        text = self.valid_text.replace(
            "<AI-Tool-Detail>:Used Codex to inspect the existing logic and verify the change",
            "<AI-Tool-Detail>:/",
        )
        codes = {item["code"] for item in self.validate(text)["errors"]}
        self.assertIn("AI_DETAIL", codes)

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
            ["git", "-C"ãNº¶‰žËkºwµçM•±˜¹…ÍÍ•ÉÑQÉÕ”¡…¹ä ‰Á…Ñ ¥Ì‘•¹¥•ˆ¥¸É•…Í½¸™½ÈÉ•…Í½¸¥¸É•ÍÕ±Ñl‰É•…Í½¹Ì‰t¤¤((€€€‘•˜Ñ•ÍÑ}½¹™¥Éµ•‘}½µµ¥Ñ}…¹¹½Ñ}ÕÍ•}Õ¹½µµ¥ÑÑ•‘}‘•±¥Ù•Éå}½¹ÑÉ½±Ì¡Í•±˜¤€´ø9½¹”è(€€€€€€€Á½±¥å}Á…Ñ €ôÍ•±˜¹É•Á¼€¼€ˆ¹ÁÉ½©•Ðˆ€¼€‰¥Ðˆ€¼€‰‘•±¥Ù•Éä¹åµ°ˆ(€€€€€€€Á½±¥ä€ôå…µ°¹Í…™•}±½…¡Á½±¥å}Á…Ñ ¹É•…‘}Ñ•áÐ¡•¹½‘¥¹œô‰ÕÑ˜´àˆ¤¤(€€€€€€€Á½±¥ål‰…ÕÑ½µ…Ñ¥½¸‰t€ôì‰½µµ¥Ðˆè…±Í”°€‰ÁÕÍ ˆè…±Í•ô(€€€€€€€Á½±¥å}Á…Ñ ¹ÝÉ¥Ñ•}Ñ•áÐ¡å…µ°¹Í…™•}‘ÕµÀ¡Á½±¥ä°Í½ÉÑ}­•åÌõ…±Í”¤°•¹½‘¥¹œô‰ÕÑ˜´àˆ¤(€€€€€€€ÁÉ½‘ÕÐ€ôÍ•±˜¹É•Á¼€¼€‰Í½ÕÉ”ˆ€¼€‰ÁÉ½‘ÕÐ¹Œˆ(€€€€€€€ÁÉ½‘ÕÐ¹Á…É•¹Ð¹µ­‘¥È ¤(€€€€€€€ÁÉ½‘ÕÐ¹ÝÉ¥Ñ•}Ñ•áÐ ‰¥¹ÐÁÉ½‘ÕÐ¡Ù½¥¤ìÉ•ÑÕÉ¸€Àìõq¸ˆ°•¹½‘¥¹œô‰ÕÑ˜´àˆ¤((€€€€€€€É•ÍÕ±Ð€ô¥Ñ}Á±…¸ (€€€€€€€€€€€Í•±˜¹É•Á¼°(€€€€€€€€€€€½Á•É…Ñ¥½¸ô‰½µµ¥Ðˆ°(€€€€€€€€€€€‘•±¥Ù•Éäô‰½µµ¥Ðˆ°(€€€€€€€€€€€Á…Ñ¡ÌõmÁÉ½‘ÕÐ¹É•±…Ñ¥Ù•}Ñ¼¡Í•±˜¹É•Á¼¤¹…Í}Á½Í¥à ¥t°(€€€€€€€€€€€µ•ÍÍ…•}™¥±”õÍ•±˜¹…ÕÑ½}µ•ÍÍ…” ¤°(€€€€€€€€¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…° ‰	1=-ˆ°É•ÍÕ±Ñl‰ÍÑ…ÑÕÌ‰t¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑQÉÕ” (€€€€€€€€€€€…¹ä (€€€€€€€€€€€€€€€€‰Õ¹½µµ¥ÑÑ•‘•±¥Ù•Éä½¹ÑÉ½±Ìˆ¥¸É•…Í½¸(€€€€€€€€€€€€€€€™½ÈÉ•…Í½¸¥¸É•ÍÕ±Ñl‰É•…Í½¹Ì‰t(€€€€€€€€€€€€¤(€€€€€€€€¤((€€€‘•˜Ñ•ÍÑ}…ÕÑ½}Á±…¹}Í•±•ÑÍ}ÕÁ±½…‘}…¹‘}¥Í}É•…‘}½¹±ä¡Í•±˜¤€´ø9½¹”è(€€€€€€€µ•ÍÍ…”€ôÍ•±˜¹ÁÉ•Á…É•}…ÕÑ½}¡…¹” ¤(€€€€€€€‰•™½É”€ôÍ•±˜¹Í¹…ÁÍ¡½Ð ¤(€€€€€€€É•ÍÕ±Ð€ôÍ•±˜¹…ÕÑ½}Á±…¸¡µ•ÍÍ…”¤(€€€€€€€…™Ñ•È€ôÍ•±˜¹Í¹…ÁÍ¡½Ð ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…° ‰AMLˆ°É•ÍÕ±Ñl‰ÍÑ…ÑÕÌ‰t¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡%M%=9}UQ=}UA1=°É•ÍÕ±Ñl‰‘•¥Í¥½¸‰t¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡mt°É•ÍÕ±Ñl‰‘•¥Í¥½¹}É•…Í½¹Ì‰t¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…° ‰=9%I5ˆ°É•ÍÕ±Ñl‰½¹Ñ•¹Ñ}½¹™¥Éµ…Ñ¥½¸‰ul‰ÍÑ…ÑÕÌ‰t¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡‰•™½É”°…™Ñ•È¤((€€€‘•˜Ñ•ÍÑ}…ÕÑ½}Á±…¹}É•ÅÕ¥É•Í}½¹™¥Éµ•‘}½µµ¥Ñ}½¹Ñ•¹Ñ}…¹‘}É•©•ÑÍ}‘É¥™Ð¡Í•±˜¤€´ø9½¹”è(€€€€€€€µ•ÍÍ…”€ôÍ•±˜¹ÁÉ•Á…É•}…ÕÑ½}¡…¹” ¤(€€€€€€€‰•™½É”€ôÍ•±˜¹Í¹…ÁÍ¡½Ð ¤(€€€€€€€Á•¹‘¥¹œ€ôÍ•±˜¹…ÕÑ½}Á±…¸¡µ•ÍÍ…”°½¹™¥Éµ}½¹Ñ•¹Ðõ…±Í”¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…° ‰AMLˆ°Á•¹‘¥¹l‰ÍÑ…ÑÕÌ‰t¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡%M%=9}=9%I5}UQ=}=9Q9P°Á•¹‘¥¹l‰‘•¥Í¥½¸‰t¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…° ‰A9%9ˆ°Á•¹‘¥¹l‰½¹Ñ•¹Ñ}½¹™¥Éµ…Ñ¥½¸‰ul‰ÍÑ…ÑÕÌ‰t¤(€€€€€€€™¥¹•ÉÁÉ¥¹Ð€ôÁ•¹‘¥¹l‰½µµ¥Ñ}½¹Ñ•¹Ð‰ul‰™¥¹•ÉÁÉ¥¹Ð‰t(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…° (€€€€€€€€€€€™¥¹•ÉÁÉ¥¹Ð°(€€€€€€€€€€€Á•¹‘¥¹l‰½¹Ñ•¹Ñ}½¹™¥Éµ…Ñ¥½¸‰ul‰ÕÉÉ•¹Ñ}™¥¹•ÉÁÉ¥¹Ð‰t°(€€€€€€€€¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡‰•™½É”°Í•±˜¹Í¹…ÁÍ¡½Ð ¤¤((€€€€€€€É•…‘µ”€ôÍ•±˜¹É•Á¼€¼€‰I5¹µˆ(€€€€€€€É•…‘µ”¹ÝÉ¥Ñ•}Ñ•áÐ (€€€€€€€€€€€É•…‘µ”¹É•…‘}Ñ•áÐ¡•¹½‘¥¹œô‰ÕÑ˜´àˆ¤€¬€‰‘É¥™Ð…™Ñ•ÈÁÉ•Ù¥•Ýq¸ˆ°(€€€€€€€€€€€•¹½‘¥¹œô‰ÕÑ˜´àˆ°(€€€€€€€€¤(€€€€€€€ÍÑ…±”€ô‘¥Ð (€€€€€€€€€€€¥Ñ}Á±…¸ (€€€€€€€€€€€€€€€Í•±˜¹É•Á¼°(€€€€€€€€€€€€€€€½Á•É…Ñ¥½¸ô‰…ÕÑ¼ˆ°(€€€€€€€€€€€€€€€‘•±¥Ù•Éäô‰…ÕÑ¼ˆ°(€€€€€€€€€€€€€€€Á…Ñ¡Ìõl‰I5¹µ‰t°(€€€€€€€€€€€€€€€µ•ÍÍ…•}™¥±”õµ•ÍÍ…”°(€€€€€€€€€€€€€€€•áÁ•Ñ•‘}½¹Ñ•¹Ñ}™¥¹•ÉÁÉ¥¹Ðõ™¥¹•ÉÁÉ¥¹Ð°(€€€€€€€€€€€€¤(€€€€€€€€¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡%M%=9}=9%I5}UQ=}=9Q9P°ÍÑ…±•l‰‘•¥Í¥½¸‰t¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…° ‰MQ1ˆ°ÍÑ…±•l‰½¹Ñ•¹Ñ}½¹™¥Éµ…Ñ¥½¸‰ul‰ÍÑ…ÑÕÌ‰t¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ9½ÑÅÕ…° (€€€€€€€€€€€™¥¹•ÉÁÉ¥¹Ð°(€€€€€€€€€€€ÍÑ…±•l‰½¹Ñ•¹Ñ}½¹™¥Éµ…Ñ¥½¸‰ul‰ÕÉÉ•¹Ñ}™¥¹•ÉÁÉ¥¹Ð‰t°(€€€€€€€€¤((€€€€€€€½¹™¥Éµ•€ô‘¥Ð (€€€€€€€€€€€¥Ñ}Á±…¸ (€€€€€€€€€€€€€€€Í•±˜¹É•Á¼°(€€€€€€€€€€€€€€€½Á•É…Ñ¥½¸ô‰…ÕÑ¼ˆ°(€€€€€€€€€€€€€€€‘•±¥Ù•Éäô‰…ÕÑ¼ˆ°(€€€€€€€€€€€€€€€Á…Ñ¡Ìõl‰I5¹µ‰t°(€€€€€€€€€€€€€€€µ•ÍÍ…•}™¥±”õµ•ÍÍ…”°(€€€€€€€€€€€€€€€•áÁ•Ñ•‘}½¹Ñ•¹Ñ}™¥¹•ÉÁÉ¥¹ÐõÍÑ…±•l‰½µµ¥Ñ}½¹Ñ•¹Ð‰ul‰™¥¹•ÉÁÉ¥¹Ð‰t°(€€€€€€€€€€€€¤(€€€€€€€€¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡%M%=9}UQ=}UA1=°½¹™¥Éµ•‘l‰‘•¥Í¥½¸‰t¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…° ‰=9%I5ˆ°½¹™¥Éµ•‘l‰½¹Ñ•¹Ñ}½¹™¥Éµ…Ñ¥½¸‰ul‰ÍÑ…ÑÕÌ‰t¤((€€€‘•˜Ñ•ÍÑ}…ÕÑ½}Á±…¹}É•ÑÕÉ¹Í}¹½}‘•±¥Ù•Éå}Ý¥Ñ¡½ÕÑ}¡…¹•Ì¡Í•±˜¤€´ø9½¹”è(€€€€€€€É•ÍÕ±Ð€ô¥Ñ}Á±…¸¡Í•±˜¹É•Á¼°½Á•É…Ñ¥½¸ô‰…ÕÑ¼ˆ°‘•±¥Ù•Éäô‰…ÕÑ¼ˆ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…° ‰AMLˆ°É•ÍÕ±Ñl‰ÍÑ…ÑÕÌ‰t¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡%M%=9}9=}1%YId°É•ÍÕ±Ñl‰‘•¥Í¥½¸‰t¤((€€€‘•˜Ñ•ÍÑ}…ÕÑ½}Á±…¹}‰±½­Í}¥¹Ù…±¥‘}µ•ÍÍ…•}¥¹ÍÑ•…‘}½™}ÕÍ¥¹}Á±…•¡½±‘•ÉÌ¡Í•±˜¤€´ø9½¹”è(€€€€€€€Í•±˜¹ÁÉ•Á…É•}…ÕÑ½}¡…¹” ¤(€€€€€€€µ•ÍÍ…”€ôÍ•±˜¹…ÕÑ½}µ•ÍÍ…” ˆñAÉ½©•ÐøñÕ¹Ñ¥½¸‰±½¬øè€ñMÕµµ…Éäùq¸ˆ¤(€€€€€€€É•ÍÕ±Ð€ôÍ•±˜¹…ÕÑ½}Á±…¸¡µ•ÍÍ…”¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…° ‰	1=-ˆ°É•ÍÕ±Ñl‰ÍÑ…ÑÕÌ‰t¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%Í9½¹”¡É•ÍÕ±Ñl‰‘•¥Í¥½¸‰t¤((€€€‘•˜Ñ•ÍÑ}…ÕÑ½}Á±…¹}™…±±Í}‰…­}™½É}•á¥ÍÑ¥¹}½ÕÑ½¥¹}½µµ¥Ð¡Í•±˜¤€´ø9½¹”è(€€€€€€€ÕÉÉ•¹Ð€ô€¡Í•±˜¹É•Á¼€¼€‰I5¹µˆ¤¹É•…‘}Ñ•áÐ¡•¹½‘¥¹œô‰ÕÑ˜´àˆ¤(€€€€€€€€¡Í•±˜¹É•Á¼€¼€‰I5¹µˆ¤¹ÝÉ¥Ñ•}Ñ•áÐ¡ÕÉÉ•¹Ð€¬€‰Á•¹‘¥¹q¸ˆ°•¹½‘¥¹œô‰ÕÑ˜´àˆ¤(€€€€€€€‰•™½É”€ôÍ•±˜¹Í¹…ÁÍ¡½Ð ¤(€€€€€€€É•ÍÕ±Ð€ôÍ•±˜¹…ÕÑ½}Á±…¸¡Í•±˜¹…ÕÑ½}µ•ÍÍ…” ¤¤(€€€€€€€…™Ñ•È€ôÍ•±˜¹Í¹…ÁÍ¡½Ð ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡%M%=9}5MM}=91d°É•ÍÕ±Ñl‰‘•¥Í¥½¸‰t¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑQÉÕ” (€€€€€€€€€€€…¹ä ‰ÕÁÍÑÉ•…´ÑÉ…­¥¹œÉ•˜ˆ¥¸É•…Í½¸™½ÈÉ•…Í½¸¥¸É•ÍÕ±Ñl‰‘•¥Í¥½¹}É•…Í½¹Ì‰t¤(€€€€€€€€¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡‰•™½É”°…™Ñ•È¤((€€€‘•˜Ñ•ÍÑ}…ÕÑ½}Á±…¹}™…±±Í}‰…­}™½É}•á¥ÍÑ¥¹}¥¹½µ¥¹}½µµ¥Ð¡Í•±˜¤€´ø9½¹”è(€€€€€€€µ•ÍÍ…”€ôÍ•±˜¹ÁÉ•Á…É•}…ÕÑ½}¡…¹” ¤(€€€€€€€ÑÉ•”€ôÍ•±˜¹¥Ð¡Í•±˜¹É•Á¼°€‰ÝÉ¥Ñ”µÑÉ•”ˆ¤¹ÍÑ‘½ÕÐ¹ÍÑÉ¥À ¤(€€€€€€€Á…É•¹Ð€ôÍ•±˜¹¥Ð¡Í•±˜¹É•Á¼°€‰É•ØµÁ…ÉÍ”ˆ°€‰!ˆ¤¹ÍÑ‘½ÕÐ¹ÍÑÉ¥À ¤(€€€€€€€¥¹½µ¥¹œ€ôÍ•±˜¹¥Ð (€€€€€€€€€€€Í•±˜¹É•Á¼°(€€€€€€€€€€€€‰½µµ¥ÐµÑÉ•”ˆ°(€€€€€€€€€€€ÑÉ•”°(€€€€€€€€€€€€ˆµÀˆ°(€€€€€€€€€€€Á…É•¹Ð°(€€€€€€€€€€€€ˆµ´ˆ°(€€€€€€€€€€€€‰Í¥µÕ±…Ñ•¥¹½µ¥¹œ½µµ¥Ðˆ°(€€€€€€€€¤¹ÍÑ‘½ÕÐ¹ÍÑÉ¥À ¤(€€€€€€€Í•±˜¹¥Ð (€€€€€€€€€€€Í•±˜¹É•Á¼°(€€€€€€€€€€€€‰ÕÁ‘…Ñ”µÉ•˜ˆ°(€€€€€€€€€€€€‰É•™Ì½É•µ½Ñ•Ì½½É¥¥¸½™•…ÑÕÉ”½Ñ•ÍÐˆ°(€€€€€€€€€€€¥¹½µ¥¹œ°(€€€€€€€€¤(€€€€€€€É•ÍÕ±Ð€ôÍ•±˜¹…ÕÑ½}Á±…¸¡µ•ÍÍ…”¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡%M%=9}5MM}=91d°É•ÍÕ±Ñl‰‘•¥Í¥½¸‰t¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑQÉÕ” (€€€€€€€€€€€…¹ä ‰ÕÁÍÑÉ•…´ÑÉ…­¥¹œÉ•˜ˆ¥¸É•…Í½¸™½ÈÉ•…Í½¸¥¸É•ÍÕ±Ñl‰‘•¥Í¥½¹}É•…Í½¹Ì‰t¤(€€€€€€€€¤((€€€‘•˜Ñ•ÍÑ}…ÕÑ½}Á±…¹}™…±±Í}‰…­}™½É}Õ¹É•±…Ñ•‘}½É}ÍÑ…•‘}¡…¹•Ì¡Í•±˜¤€´ø9½¹”è(€€€€€€€µ•ÍÍ…”€ôÍ•±˜¹ÁÉ•Á…É•}…ÕÑ½}¡…¹” ¤(€€€€€€€‘½Ì€ôÍ•±˜¹É•Á¼€¼€‰‘½Ìˆ(€€€€€€€‘½Ì¹µ­‘¥È ¤(€€€€€€€€¡‘½Ì€¼€‰Õ¹É•±…Ñ•¹µˆ¤¹ÝÉ¥Ñ•}Ñ•áÐ ‰Õ¹É•±…Ñ•‘q¸ˆ°•¹½‘¥¹œô‰ÕÑ˜´àˆ¤(€€€€€€€Í•±˜¹¥Ð¡Í•±˜¹É•Á¼°€‰…‘ˆ°€‰I5¹µˆ¤(€€€€€€€É•ÍÕ±Ð€ôÍ•±˜¹…ÕÑ½}Á±…¸¡µ•ÍÍ…”¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡%M%=9}5MM}=91d°É•ÍÕ±Ñl‰‘•¥Í¥½¸‰t¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑQÉÕ” (€€€€€€€€€€€…¹ä ‰½ÕÑÍ¥‘”…ÕÑ¼‘•±¥Ù•ÉäÍ½Á”ˆ¥¸É•…Í½¸™½ÈÉ•…Í½¸¥¸É•ÍÕ±Ñl‰‘•¥Í¥½¹}É•…Í½¹Ì‰t¤(€€€€€€€€¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑQÉÕ” (€€€€€€€€€€€…¹ä ‰¥¹‘•àµÕÍÐ‰”•µÁÑäˆ¥¸É•…Í½¸™½ÈÉ•…Í½¸¥¸É•ÍÕ±Ñl‰‘•¥Í¥½¹}É•…Í½¹Ì‰t¤(€€€€€€€€¤((€€€‘•˜Ñ•ÍÑ}…ÕÑ½}Á±…¹}™…±±Í}‰…­}Ý¡•¹}…ÕÑ½µ…Ñ¥½¹}½É}ÁÕÍ¡}Ñ…É•Ñ}¥Í}Õ¹…Ù…¥±…‰±”¡Í•±˜¤€´ø9½¹”è(€€€€€€€µ•ÍÍ…”€ôÍ•±˜¹ÁÉ•Á…É•}…ÕÑ½}¡…¹” ¤(€€€€€€€Á½±¥å}Á…Ñ €ôÍ•±˜¹É•Á¼€¼€ˆ¹ÁÉ½©•Ðˆ€¼€‰¥Ðˆ€¼€‰‘•±¥Ù•Éä¹åµ°ˆ(€€€€€€€Á½±¥ä€ôå…µ°¹Í…™•}±½…¡Á½±¥å}Á…Ñ ¹É•…‘}Ñ•áÐ¡•¹½‘¥¹œô‰ÕÑ˜´àˆ¤¤(€€€€€€€Á½±¥ål‰…ÕÑ½µ…Ñ¥½¸‰ul‰ÁÕÍ ‰t€ô…±Í”(€€€€€€€Á½±¥å}Á…Ñ ¹ÝÉ¥Ñ•}Ñ•áÐ¡å…µ°¹Í…™•}‘ÕµÀ¡Á½±¥ä°Í½ÉÑ}­•åÌõ…±Í”¤°•¹½‘¥¹œô‰ÕÑ˜´àˆ¤(€€€€€€€Í•±˜¹¥Ð¡Í•±˜¹É•Á¼°€‰½¹™¥œˆ°€ˆ´µÕ¹Í•Ðˆ°€‰‰É…¹ ¹™•…ÑÕÉ”½Ñ•ÍÐ¹É•µ½Ñ”ˆ¤(€€€€€€€É•ÍÕ±Ð€ôÍ•±˜¹…ÕÑ½}Á±…¸¡µ•ÍÍ…”¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡%M%=9}5MM}=91d°É•ÍÕ±Ñl‰‘•¥Í¥½¸‰t¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑQÉÕ” (€€€€€€€€€€€…¹ä ‰…ÕÑ½µ…Ñ¥ŒÁÕÍ ¥Ì‘¥Í…‰±•ˆ¥¸É•…Í½¸™½ÈÉ•…Í½¸¥¸É•ÍÕ±Ñl‰‘•¥Í¥½¹}É•…Í½¹Ì‰t¤(€€€€€€€€¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑQÉÕ” (€€€€€€€€€€€…¹ä ‰µÕÍÐ¡…Ù”•á…Ñ±ä½¹”Ù…±Õ”ˆ¥¸É•…Í½¸™½ÈÉ•…Í½¸¥¸É•ÍÕ±Ñl‰‘•¥Í¥½¹}É•…Í½¹Ì‰t¤(€€€€€€€€¤((€€€‘•˜Ñ•ÍÑ}…ÕÑ½}Á±…¹}™…±±Í}‰…­}™½É}ÁÉ½Ñ•Ñ•‘}‰É…¹ ¡Í•±˜¤€´ø9½¹”è(€€€€€€€µ•ÍÍ…”€ôÍ•±˜¹ÁÉ•Á…É•}…ÕÑ½}¡…¹” ¤(€€€€€€€Í•±˜¹¥Ð¡Í•±˜¹É•Á¼°€‰‰É…¹ ˆ°€ˆµ´ˆ°€‰µ…¥¸ˆ¤(€€€€€€€Í•±˜¹¥Ð¡Í•±˜¹É•Á¼°€‰½¹™¥œˆ°€‰‰É…¹ ¹µ…¥¸¹É•µ½Ñ”ˆ°€‰½É¥¥¸ˆ¤(€€€€€€€Í•±˜¹¥Ð¡Í•±˜¹É•Á¼°€‰½¹™¥œˆ°€‰‰É…¹ ¹µ…¥¸¹µ•É”ˆ°€‰É•™Ì½¡•…‘Ì½µ…¥¸ˆ¤(€€€€€€€É•ÍÕ±Ð€ôÍ•±˜¹…ÕÑ½}Á±…¸¡µ•ÍÍ…”¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡%M%=9}5MM}=91d°É•ÍÕ±Ñl‰‘•¥Í¥½¸‰t¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑQÉÕ” (€€€€€€€€€€€…¹ä ‰ÁÉ½Ñ•Ñ•ˆ¥¸É•…Í½¸™½ÈÉ•…Í½¸¥¸É•ÍÕ±Ñl‰‘•¥Í¥½¹}É•…Í½¹Ì‰t¤(€€€€€€€€¤((€€€‘•˜Ñ•ÍÑ}…ÕÑ½}Á±…¹}™…±±Í}‰…­}™½É}µÕ±Ñ¥Á±•}ÁÕÍ¡ÕÉ±Ì¡Í•±˜¤€´ø9½¹”è(€€€€€€€µ•ÍÍ…”€ôÍ•±˜¹ÁÉ•Á…É•}…ÕÑ½}¡…¹” ¤(€€€€€€€Í•±˜¹¥Ð¡Í•±˜¹É•Á¼°€‰½¹™¥œˆ°€ˆ´µ…‘ˆ°€‰É•µ½Ñ”¹½É¥¥¸¹ÁÕÍ¡ÕÉ°ˆ°€‰½¹”ˆ¤(€€€€€€€Í•±˜¹¥Ð¡Í•±˜¹É•Á¼°€‰½¹™¥œˆ°€ˆ´µ…‘ˆ°€‰É•µ½Ñ”¹½É¥¥¸¹ÁÕÍ¡ÕÉ°ˆ°€‰ÑÝ¼ˆ¤(€€€€€€€É•ÍÕ±Ð€ôÍ•±˜¹…ÕÑ½}Á±…¸¡µ•ÍÍ…”¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡%M%=9}5MM}=91d°É•ÍÕ±Ñl‰‘•¥Í¥½¸‰t¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑQÉÕ” (€€€€€€€€€€€…¹ä ‰•á…Ñ±ä½¹”ˆ¥¸É•…Í½¸™½ÈÉ•…Í½¸¥¸É•ÍÕ±Ñl‰‘•¥Í¥½¹}É•…Í½¹Ì‰t¤(€€€€€€€€¤((€€€‘•˜Ñ•ÍÑ}…ÕÑ½}½µµ¥Ñ}…¹‘}ÁÕÍ¡}ÁÉ•™±¥¡Ñ}±½­Í}¹•Ý}½µµ¥Ð¡Í•±˜¤€´ø9½¹”è(€€€€€€€µ•ÍÍ…”€ôÍ•±˜¹ÁÉ•Á…É•}…ÕÑ½}¡…¹” ¤(€€€€€€€‘•¥Í¥½¸€ôÍ•±˜¹…ÕÑ½}Á±…¸¡µ•ÍÍ…”¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡%M%=9}UQ=}UA1=°‘•¥Í¥½¹l‰‘•¥Í¥½¸‰t¤(€€€€€€€Í•±˜¹¥Ð¡Í•±˜¹É•Á¼°€‰…‘ˆ°€‰I5¹µˆ¤(€€€€€€€½µµ¥Ñ}Á±…¸€ô¥Ñ}Á±…¸ (€€€€€€€€€€€Í•±˜¹É•Á¼°(€€€€€€€€€€€½Á•É…Ñ¥½¸ô‰½µµ¥Ðˆ°(€€€€€€€€€€€‘•±¥Ù•Éäô‰…ÕÑ¼ˆ°(€€€€€€€€€€€Á…Ñ¡Ìõl‰I5¹µ‰t°(€€€€€€€€€€€µ•ÍÍ…•}™¥±”õµ•ÍÍ…”°(€€€€€€€€¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…° ‰AMLˆ°½µµ¥Ñ}Á±…¹l‰ÍÑ…ÑÕÌ‰t°½µµ¥Ñ}Á±…¹l‰É•…Í½¹Ì‰t¤(€€€€€€€Í•±˜¹¥Ð¡Í•±˜¹É•Á¼°€‰½µµ¥Ðˆ°€ˆµˆ°ÍÑÈ¡µ•ÍÍ…”¤¤(€€€€€€€½µµ¥Ñ}Í¡„€ôÍ•±˜¹¥Ð¡Í•±˜¹É•Á¼°€‰É•ØµÁ…ÉÍ”ˆ°€‰!ˆ¤¹ÍÑ‘½ÕÐ¹ÍÑÉ¥À ¤(€€€€€€€ÁÕÍ¡}Á±…¸€ô¥Ñ}Á±…¸ (€€€€€€€€€€€Í•±˜¹É•Á¼°(€€€€€€€€€€€½Á•É…Ñ¥½¸ô‰ÁÕÍ ˆ°(€€€€€€€€€€€‘•±¥Ù•Éäô‰…ÕÑ¼ˆ°(€€€€€€€€€€€•áÁ•Ñ•‘}™¥¹•ÉÁÉ¥¹Ðõ‘•¥Í¥½¹l‰ÁÕÍ¡}Ñ…É•Ð‰ul‰™¥¹•ÉÁÉ¥¹Ð‰t°(€€€€€€€€€€€•áÁ•Ñ•‘}½µµ¥Ðõ½µµ¥Ñ}Í¡„°(€€€€€€€€¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…° ‰AMLˆ°ÁÕÍ¡}Á±…¹l‰ÍÑ…ÑÕÌ‰t°ÁÕÍ¡}Á±…¹l‰É•…Í½¹Ì‰t¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡m½µµ¥Ñ}Í¡…t°ÁÕÍ¡}Á±…¹l‰½ÕÑ½¥¹}½µµ¥ÑÌ‰t¤(€€€€€€€Í•±˜¹¥Ð¡Í•±˜¹É•Á¼°€‰ÁÕÍ ˆ°€‰½É¥¥¸ˆ°€‰!éÉ•™Ì½¡•…‘Ì½™•…ÑÕÉ”½Ñ•ÍÐˆ¤(€€€€€€€É•µ½Ñ•}Í¡„€ôÍ•±˜¹¥Ð (€€€€€€€€€€€Í•±˜¹É•µ½Ñ”°€‰É•ØµÁ…ÉÍ”ˆ°€‰É•™Ì½¡•…‘Ì½™•…ÑÕÉ”½Ñ•ÍÐˆ(€€€€€€€€¤¹ÍÑ‘½ÕÐ¹ÍÑÉ¥À ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡½µµ¥Ñ}Í¡„°É•µ½Ñ•}Í¡„¤((€€€‘•˜Ñ•ÍÑ}…ÕÑ½}ÁÕÍ¡}É•©•ÑÍ}ÝÉ½¹}•áÁ•Ñ•‘}½µµ¥Ð¡Í•±˜¤€´ø9½¹”è(€€€€€€€µ•ÍÍ…”€ôÍ•±˜¹ÁÉ•Á…É•}…ÕÑ½}¡…¹” ¤(€€€€€€€‘•¥Í¥½¸€ôÍ•±˜¹…ÕÑ½}Á±…¸¡µ•ÍÍ…”¤(€€€€€€€Í•±˜¹¥Ð¡Í•±˜¹É•Á¼°€‰…‘ˆ°€‰I5¹µˆ¤(€€€€€€€Í•±˜¹¥Ð¡Í•±˜¹É•Á¼°€‰½µµ¥Ðˆ°€ˆµˆ°ÍÑÈ¡µ•ÍÍ…”¤¤(€€€€€€€É•ÍÕ±Ð€ô¥Ñ}Á±…¸ (€€€€€€€€€€€Í•±˜¹É•Á¼°(€€€€€€€€€€€½Á•É…Ñ¥½¸ô‰ÁÕÍ ˆ°(€€€€€€€€€€€‘•±¥Ù•Éäô‰…ÕÑ¼ˆ°(€€€€€€€€€€€•áÁ•Ñ•‘}™¥¹•ÉÁÉ¥¹Ðõ‘•¥Í¥½¹l‰ÁÕÍ¡}Ñ…É•Ð‰ul‰™¥¹•ÉÁÉ¥¹Ð‰t°(€€€€€€€€€€€•áÁ•Ñ•‘}½µµ¥ÐôˆÀˆ€¨€ÐÀ°(€€€€€€€€¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…° ‰	1=-ˆ°É•ÍÕ±Ñl‰ÍÑ…ÑÕÌ‰t¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑQÉÕ” (€€€€€€€€€€€…¹ä ‰½¹±äÑ¡”¹•Ý±äÉ•…Ñ•½µµ¥Ðˆ¥¸É•…Í½¸™½ÈÉ•…Í½¸¥¸É•ÍÕ±Ñl‰É•…Í½¹Ì‰t¤(€€€€€€€€¤((€€€‘•˜Ñ•ÍÑ}…ÕÑ½}ÁÕÍ¡}ÍÑ½ÁÍ}½¹}™¥¹•ÉÁÉ¥¹Ñ}‘É¥™Ñ}…¹‘}­••ÁÍ}½µµ¥Ð¡Í•±˜¤€´ø9½¹”è(€€€€€€€µ•ÍÍ…”€ôÍ•±˜¹ÁÉ•Á…É•}…ÕÑ½}¡…¹” ¤(€€€€€€€‘•¥Í¥½¸€ôÍ•±˜¹…ÕÑ½}Á±…¸¡µ•ÍÍ…”¤(€€€€€€€Í•±˜¹¥Ð¡Í•±˜¹É•Á¼°€‰…‘ˆ°€‰I5¹µˆ¤(€€€€€€€Í•±˜¹¥Ð¡Í•±˜¹É•Á¼°€‰½µµ¥Ðˆ°€ˆµˆ°ÍÑÈ¡µ•ÍÍ…”¤¤(€€€€€€€½µµ¥Ñ}Í¡„€ôÍ•±˜¹¥Ð¡Í•±˜¹É•Á¼°€‰É•ØµÁ…ÉÍ”ˆ°€‰!ˆ¤¹ÍÑ‘½ÕÐ¹ÍÑÉ¥À ¤(€€€€€€€Í•±˜¹¥Ð (€€€€€€€€€€€Í•±˜¹É•Á¼°(€€€€€€€€€€€€‰½¹™¥œˆ°(€€€€€€€€€€€€‰É•µ½Ñ”¹½É¥¥¸¹ÁÕÍ¡ÕÉ°ˆ°(€€€€€€€€€€€€‰¡ÑÑÁÌè¼½•á…µÁ±”¹¥¹Ù…±¥½‘É¥™Ñ•¹¥Ðˆ°(€€€€€€€€¤(€€€€€€€É•ÍÕ±Ð€ô¥Ñ}Á±…¸ (€€€€€€€€€€€Í•±˜¹É•Á¼°(€€€€€€€€€€€½Á•É…Ñ¥½¸ô‰ÁÕÍ ˆ°(€€€€€€€€€€€‘•±¥Ù•Éäô‰…ÕÑ¼ˆ°(€€€€€€€€€€€•áÁ•Ñ•‘}™¥¹•ÉÁÉ¥¹Ðõ‘•¥Í¥½¹l‰ÁÕÍ¡}Ñ…É•Ð‰ul‰™¥¹•ÉÁÉ¥¹Ð‰t°(€€€€€€€€€€€•áÁ•Ñ•‘}½µµ¥Ðõ½µµ¥Ñ}Í¡„°(€€€€€€€€¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…° ‰	1=-ˆ°É•ÍÕ±Ñl‰ÍÑ…ÑÕÌ‰t¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑQÉÕ” (€€€€€€€€€€€…¹ä ‰¡…¹•…™Ñ•ÈÁÉ•™±¥¡Ðˆ¥¸É•…Í½¸™½ÈÉ•…Í½¸¥¸É•ÍÕ±Ñl‰É•…Í½¹Ì‰t¤(€€€€€€€€¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡½µµ¥Ñ}Í¡„°Í•±˜¹¥Ð¡Í•±˜¹É•Á¼°€‰É•ØµÁ…ÉÍ”ˆ°€‰!ˆ¤¹ÍÑ‘½ÕÐ¹ÍÑÉ¥À ¤¤((€€€‘•˜Ñ•ÍÑ}™…¥±•‘}…ÕÑ½}ÁÕÍ¡}­••ÁÍ}±½…±}½µµ¥Ð¡Í•±˜¤€´ø9½¹”è(€€€€€€€µ•ÍÍ…”€ôÍ•±˜¹ÁÉ•Á…É•}…ÕÑ½}¡…¹” ¤(€€€€€€€Í•±˜¹¥Ð (€€€€€€€€€€€Í•±˜¹É•Á¼°(€€€€€€€€€€€€‰½¹™¥œˆ°(€€€€€€€€€€€€‰É•µ½Ñ”¹½É¥¥¸¹ÕÉ°ˆ°(€€€€€€€€€€€€‰¡ÑÑÀè¼¼ÄÈÜ¸À¸À¸Äèä½Õ¹…Ù…¥±…‰±”¹¥Ðˆ°(€€€€€€€€¤(€€€€€€€‘•¥Í¥½¸€ôÍ•±˜¹…ÕÑ½}Á±…¸¡µ•ÍÍ…”¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡%M%=9}UQ=}UA1=°‘•¥Í¥½¹l‰‘•¥Í¥½¸‰t¤(€€€€€€€Í•±˜¹¥Ð¡Í•±˜¹É•Á¼°€‰…‘ˆ°€‰I5¹µˆ¤(€€€€€€€Í•±˜¹¥Ð¡Í•±˜¹É•Á¼°€‰½µµ¥Ðˆ°€ˆµˆ°ÍÑÈ¡µ•ÍÍ…”¤¤(€€€€€€€½µµ¥Ñ}Í¡„€ôÍ•±˜¹¥Ð¡Í•±˜¹É•Á¼°€‰É•ØµÁ…ÉÍ”ˆ°€‰!ˆ¤¹ÍÑ‘½ÕÐ¹ÍÑÉ¥À ¤(€€€€€€€ÁÕÍ¡}Á±…¸€ô¥Ñ}Á±…¸ (€€€€€€€€€€€Í•±˜¹É•Á¼°(€€€€€€€€€€€½Á•É…Ñ¥½¸ô‰ÁÕÍ ˆ°(€€€€€€€€€€€‘•±¥Ù•Éäô‰…ÕÑ¼ˆ°(€€€€€€€€€€€•áÁ•Ñ•‘}™¥¹•ÉÁÉ¥¹Ðõ‘•¥Í¥½¹l‰ÁÕÍ¡}Ñ…É•Ð‰ul‰™¥¹•ÉÁÉ¥¹Ð‰t°(€€€€€€€€€€€•áÁ•Ñ•‘}½µµ¥Ðõ½µµ¥Ñ}Í¡„°(€€€€€€€€¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…° ‰AMLˆ°ÁÕÍ¡}Á±…¹l‰ÍÑ…ÑÕÌ‰t°ÁÕÍ¡}Á±…¹l‰É•…Í½¹Ì‰t¤(€€€€€€€ÁÕÍ¡•€ôÍÕ‰ÁÉ½•ÍÌ¹ÉÕ¸ (€€€€€€€€€€€l(€€€€€€€€€€€€€€€€‰¥Ðˆ°(€€€€€€€€€€€€€€€€ˆµˆ°(€€€€€€€€€€€€€€€ÍÑÈ¡Í•±˜¹É•Á¼¤°(€€€€€€€€€€€€€€€€‰ÁÕÍ ˆ°(€€€€€€€€€€€€€€€€‰½É¥¥¸ˆ°(€€€€€€€€€€€€€€€€‰!éÉ•™Ì½¡•…‘Ì½™•…ÑÕÉ”½Ñ•ÍÐˆ°(€€€€€€€€€€€t°(€€€€€€€€€€€Ñ•áÐõQÉÕ”°(€€€€€€€€€€€•¹½‘¥¹œô‰ÕÑ˜´àˆ°(€€€€€€€€€€€•ÉÉ½ÉÌô‰É•Á±…”ˆ°(€€€€€€€€€€€…ÁÑÕÉ•}½ÕÑÁÕÐõQÉÕ”°(€€€€€€€€€€€¡•¬õ…±Í”°(€€€€€€€€€€€Ñ¥µ•½ÕÐôÄÔ°(€€€€€€€€¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ9½ÑÅÕ…° À°ÁÕÍ¡•¹É•ÑÕÉ¹½‘”¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡½µµ¥Ñ}Í¡„°Í•±˜¹¥Ð¡Í•±˜¹É•Á¼°€‰É•ØµÁ…ÉÍ”ˆ°€‰!ˆ¤¹ÍÑ‘½ÕÐ¹ÍÑÉ¥À ¤¤((€€€‘•˜Ñ•ÍÑ}½µµ¥Ñ}Á±…¹}‰±½­Í}ÍÑ…•‘}™¥±•Í}½ÕÑÍ¥‘•}•áÁ±¥¥Ñ}Í½Á”¡Í•±˜¤€´ø9½¹”è(€€€€€€€‘½Ì€ôÍ•±˜¹É•Á¼€¼€‰‘½Ìˆ(€€€€€€€‘½Ì¹µ­‘¥È ¤(€€€€€€€É•ÅÕ•ÍÑ•€ô‘½Ì€¼€‰¹½Ñ”¹µˆ(€€€€€€€É•ÅÕ•ÍÑ•¹ÝÉ¥Ñ•}Ñ•áÐ ‰¹½Ñ•q¸ˆ°•¹½‘¥¹œô‰ÕÑ˜´àˆ¤(€€€€€€€€¡Í•±˜¹É•Á¼€¼€‰I5¹µˆ¤¹ÝÉ¥Ñ•}Ñ•áÐ ‰Õ¹É•±…Ñ•ÍÑ…•¡…¹•q¸ˆ°•¹½‘¥¹œô‰ÕÑ˜´àˆ¤(€€€€€€€Í•±˜¹¥Ð¡Í•±˜¹É•Á¼°€‰…‘ˆ°€‰I5¹µˆ¤(€€€€€€€µ•ÍÍ…”€ôÍ•±˜¹É•Á¼€¼€‰µ•ÍÍ…”¹ÑáÐˆ(€€€€€€€Í¡ÕÑ¥°¹½Áå™¥±”¡%aQUI}I==P€¼€‰Ù…±¥µÅ‘´ÀÐÜµ‰Õœµ™¥à¹ÑáÐˆ°µ•ÍÍ…”¤(€€€€€€€É•ÍÕ±Ð€ô¥Ñ}Á±…¸ (€€€€€€€€€€€Í•±˜¹É•Á¼°(€€€€€€€€€€€½Á•É…Ñ¥½¸ô‰½µµ¥Ðˆ°(€€€€€€€€€€€‘•±¥Ù•Éäô‰½µµ¥Ðˆ°(€€€€€€€€€€€Á…Ñ¡Ìõl‰‘½Ì½¹½Ñ”¹µ‰t°(€€€€€€€€€€€µ•ÍÍ…•}™¥±”õµ•ÍÍ…”°(€€€€€€€€¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…° ‰	1=-ˆ°É•ÍÕ±Ñl‰ÍÑ…ÑÕÌ‰t¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑQÉÕ” (€€€€€€€€€€€…¹ä ‰ÍÑ…•Á…Ñ¡Ì…É”½ÕÑÍ¥‘”‘•±¥Ù•ÉäÍ½Á”ˆ¥¸É•…Í½¸™½ÈÉ•…Í½¸¥¸É•ÍÕ±Ñl‰É•…Í½¹Ì‰t¤(€€€€€€€€¤((€€€‘•˜Ñ•ÍÑ}ÁÉ½Ñ•Ñ•‘}‰É…¹¡}…¹‘}½¹™¥ÕÉ…Ñ¥½¹}‘É¥™Ñ}‰±½¬¡Í•±˜¤€´ø9½¹”è(€€€€€€€½É¥¥¹…°€ôÉ•Í½±Ù•}ÁÕÍ¡}Ñ…É•Ð¡Í•±˜¹É•Á¼¤(€€€€€€€Í•±˜¹¥Ð¡Í•±˜¹É•Á¼°€‰½¹™¥œˆ°€‰É•µ½Ñ”¹½É¥¥¸¹ÁÕÍ¡ÕÉ°ˆ°€‰¡ÑÑÁÌè¼½•á…µÁ±”¹¥¹Ù…±¥½¡…¹•¹¥Ðˆ¤(€€€€€€€‘É¥™Ð€ô¥Ñ}Á±…¸ (€€€€€€€€€€€Í•±˜¹É•Á¼°(€€€€€€€€€€€½Á•É…Ñ¥½¸ô‰ÁÕÍ ˆ°(€€€€€€€€€€€‘•±¥Ù•Éäô‰½µµ¥Ðµ…¹µÁÕÍ ˆ°(€€€€€€€€€€€•áÁ•Ñ•‘}™¥¹•ÉÁÉ¥¹Ðõ½É¥¥¹…±l‰™¥¹•ÉÁÉ¥¹Ð‰t°(€€€€€€€€¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‰±½…°€¹¥ÐÁÕÍ Ñ…É•Ð¡…¹•…™Ñ•ÈÁÉ•™±¥¡Ðˆ°‘É¥™Ñl‰É•…Í½¹Ì‰t¤((€€€€€€€Í•±˜¹¥Ð¡Í•±˜¹É•Á¼°€‰‰É…¹ ˆ°€ˆµ´ˆ°€‰µ…¥¸ˆ¤(€€€€€€€Í•±˜¹¥Ð¡Í•±˜¹É•Á¼°€‰½¹™¥œˆ°€‰‰É…¹ ¹µ…¥¸¹É•µ½Ñ”ˆ°€‰½É¥¥¸ˆ¤(€€€€€€€Í•±˜¹¥Ð¡Í•±˜¹É•Á¼°€‰½¹™¥œˆ°€‰‰É…¹ ¹µ…¥¸¹µ•É”ˆ°€‰É•™Ì½¡•…‘Ì½µ…¥¸ˆ¤(€€€€€€€ÁÉ½Ñ•Ñ•€ô¥Ñ}Á±…¸ (€€€€€€€€€€€Í•±˜¹É•Á¼°½Á•É…Ñ¥½¸ô‰ÁÕÍ ˆ°‘•±¥Ù•Éäô‰½µµ¥Ðµ…¹µÁÕÍ ˆ(€€€€€€€€¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑQÉÕ”¡…¹ä ‰ÁÉ½Ñ•Ñ•ˆ¥¸É•…Í½¸™½ÈÉ•…Í½¸¥¸ÁÉ½Ñ•Ñ•‘l‰É•…Í½¹Ì‰t¤¤((€€€‘•˜Ñ•ÍÑ}±¥¹­•‘}Ý½É­ÑÉ••}ÕÍ•Í}½µµ½¹}¥Ñ}‘¥É•Ñ½Éä¡Í•±˜¤€´ø9½¹”è(€€€€€€€±¥¹­•€ôÍ•±˜¹‰…Í”€¼€‰±¥¹­•ˆ(€€€€€€€Í•±˜¹¥Ð¡Í•±˜¹É•Á¼°€‰Ý½É­ÑÉ•”ˆ°€‰…‘ˆ°€ˆµˆˆ°€‰™•…ÑÕÉ”½±¥¹­•ˆ°ÍÑÈ¡±¥¹­•¤°€‰!ˆ¤(€€€€€€€Í•±˜¹¥Ð¡±¥¹­•°€‰½¹™¥œˆ°€‰‰É…¹ ¹™•…ÑÕÉ”½±¥¹­•¹É•µ½Ñ”ˆ°€‰½É¥¥¸ˆ¤(€€€€€€€Í•±˜¹¥Ð¡±¥¹­•°€‰½¹™¥œˆ°€‰‰É…¹ ¹™•…ÑÕÉ”½±¥¹­•¹µ•É”ˆ°€‰É•™Ì½¡•…‘Ì½™•…ÑÕÉ”½±¥¹­•ˆ¤(€€€€€€€Ñ…É•Ð€ôÉ•Í½±Ù•}ÁÕÍ¡}Ñ…É•Ð¡±¥¹­•¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ9½ÑÅÕ…°¡Ñ…É•Ñl‰¥Ñ}‘¥È‰t°Ñ…É•Ñl‰¥Ñ}½µµ½¹}‘¥È‰t¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑQÉÕ”¡Ñ…É•Ñl‰¥Ñ}½µµ½¹}‘¥È‰t¹•¹‘ÍÝ¥Ñ  ˆ¼¹¥Ðˆ¤¤(()¥˜}}¹…µ•}|€ôô€‰}}µ…¥¹}|ˆè(€€€Õ¹¥ÑÑ•ÍÐ¹µ…¥¸ ¤(