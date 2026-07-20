from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

AGENT_KIT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AGENT_KIT_ROOT / "scripts"))

from validate_customizations import validate_repository


PROJECT_ROOT = AGENT_KIT_ROOT.parents[1]
FIXTURES = AGENT_KIT_ROOT / "tests" / "fixtures"


class CustomizationValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary_directory.cleanup)
        self.repo = Path(self._temporary_directory.name) / "repository"
        shutil.copytree(
            PROJECT_ROOT,
            self.repo,
            ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", "build"),
        )

    def diagnostics(self):
        return validate_repository(self.repo)

    def codes(self) -> set[str]:
        return {item.code for item in self.diagnostics()}

    def replace_profile(self, name: str) -> None:
        shutil.copyfile(
            FIXTURES / "profiles" / name,
            self.repo / ".github" / "embedded-project.yml",
        )

    def read_yaml(self, relative: str):
        return yaml.safe_load((self.repo / relative).read_text(encoding="utf-8"))

    def write_yaml(self, relative: str, value) -> None:
        (self.repo / relative).write_text(
            yaml.safe_dump(value, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
            newline="\n",
        )

    def install_negative_markdown(self, name: str) -> None:
        destination = self.repo / "docs" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(FIXTURES / "negative" / name, destination)

    def test_repository_configuration_is_valid(self) -> None:
        self.assertEqual([], self.diagnostics())

    def test_all_supported_product_forms_are_valid(self) -> None:
        for product_form in (
            "bare-metal",
            "rtos",
            "module-sdk",
            "embedded-linux",
            "hybrid",
        ):
            with self.subTest(product_form=product_form):
                self.replace_profile(f"{product_form}.yml")
                self.assertEqual([], self.diagnostics())

    def test_legacy_profile_without_application_paths_is_valid(self) -> None:
        profile_path = self.repo / ".github" / "embedded-project.yml"
        profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
        for key in ("application", "services", "middleware", "protocols"):
            profile["paths"].pop(key, None)
        profile_path.write_text(
            yaml.safe_dump(profile, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
            newline="\n",
        )
        self.assertEqual([], self.diagnostics())

    def test_missing_project_directory_is_accepted_for_legacy_projects(self) -> None:
        shutil.rmtree(self.repo / ".project")
        self.assertFalse(
            any(item.code.startswith("PROJECT_DIRECTORY") for item in self.diagnostics())
        )

    def test_existing_project_directory_requires_manifest(self) -> None:
        (self.repo / ".project" / "project.yml").unlink()
        codes = self.codes()
        self.assertIn("PROJECT_DIRECTORY_MISSING", codes)

    def test_invalid_project_directory_manifest_is_rejected(self) -> None:
        manifest = self.read_yaml(".project/project.yml")
        manifest["rules"] = []
        self.write_yaml(".project/project.yml", manifest)
        self.assertIn("PROJECT_DIRECTORY_SCHEMA", self.codes())

    def test_missing_and_outside_project_references_are_rejected(self) -> None:
        manifest = self.read_yaml(".project/project.yml")
        manifest["rules"][0]["path"] = "../README.md"
        manifest["git_policy"] = "git/missing.yml"
        self.write_yaml(".project/project.yml", manifest)
        diagnostics = self.diagnostics()
        project_references = [
            item for item in diagnostics if item.code == "PROJECT_REFERENCE"
        ]
        self.assertTrue(any("leaves .project" in item.message for item in project_references))
        self.assertTrue(any("is missing" in item.message for item in project_references))

    def test_missing_optional_project_constraint_is_accepted(self) -> None:
        manifest = self.read_yaml(".project/project.yml")
        manifest["rules"][1]["path"] = "rules/optional-local-rule.md"
        manifest["rules"][1]["required"] = False
        self.write_yaml(".project/project.yml", manifest)
        self.assertEqual([], self.diagnostics())

    def test_duplicate_project_rule_ids_are_rejected(self) -> None:
        manifest = self.read_yaml(".project/project.yml")
        manifest["rules"][1]["id"] = manifest["rules"][0]["id"]
        self.write_yaml(".project/project.yml", manifest)
        self.assertIn("PROJECT_RULE_ID", self.codes())

    def test_project_and_git_globs_must_be_repository_relative(self) -> None:
        manifest = self.read_yaml(".project/project.yml")
        manifest["rules"][0]["applies_to"] = ["../outside/**"]
        self.write_yaml(".project/project.yml", manifest)
        policy = self.read_yaml(".project/git/delivery.yml")
        policy["scope"]["allowed_paths"] = ["C:/outside/**"]
        self.write_yaml(".project/git/delivery.yml", policy)
        self.assertIn("PROJECT_GLOB", self.codes())

    def test_git_delivery_policy_preserves_authorization_and_force_safety(self) -> None:
        policy = self.read_yaml(".project/git/delivery.yml")
        policy["safety"]["require_task_authorization"] = False
        policy["safety"]["allow_force_push"] = True
        self.write_yaml(".project/git/delivery.yml", policy)
        diagnostics = self.diagnostics()
        policy_errors = [
            item for item in diagnostics if item.code == "GIT_POLICY_SCHEMA"
        ]
        self.assertTrue(
            any("require_task_authorization" in item.message for item in policy_errors)
        )
        self.assertTrue(any("allow_force_push" in item.message for item in policy_errors))

    def test_git_delivery_policy_rejects_push_target_overrides(self) -> None:
        policy = self.read_yaml(".project/git/delivery.yml")
        policy["extensions"] = {"provider": {"push-url": "https://unsafe.invalid"}}
        self.write_yaml(".project/git/delivery.yml", policy)
        self.assertIn("GIT_TARGET_OVERRIDE", self.codes())

    def test_commit_template_subject_and_field_order_are_strict(self) -> None:
        template = self.repo / ".project" / "git" / "commit.template"
        original = template.read_text(encoding="utf-8")
        template.write_text(
            original.replace(
                "<Project><Function block>: <Summary>",
                "<Project>: <Summary>",
            ),
            encoding="utf-8",
            newline="\n",
        )
        self.assertIn("COMMIT_TEMPLATE_SUBJECT", self.codes())
        template.write_text(
            original.replace("<Change Reason>:\n<Root Cause>:", "<Root Cause>:\n<Change Reason>:"),
            encoding="utf-8",
            newline="\n",
        )
        self.assertIn("COMMIT_TEMPLATE_ORDER", self.codes())

    def test_project_extension_namespaces_remain_extensible(self) -> None:
        manifest = self.read_yaml(".project/project.yml")
        manifest["extensions"] = {
            "example.vendor/tool": {"config": "rules/tool.yml", "enabled": True}
        }
        self.write_yaml(".project/project.yml", manifest)
        policy = self.read_yaml(".project/git/delivery.yml")
        policy["extensions"] = {"review-ticket": {"required": False}}
        self.write_yaml(".project/git/delivery.yml", policy)
        self.assertEqual([], self.diagnostics())

    def test_missing_agent_is_rejected(self) -> None:
        (self.repo / ".github" / "agents" / "doc-keeper.agent.md").unlink()
        self.assertIn("AGENT_SET", self.codes())

    def test_project_directory_contract_is_required_at_public_entry_points(self) -> None:
        for name in ("orchestrator.agent.md", "embedded-developer.agent.md"):
            agent = self.repo / ".github" / "agents" / name
            with self.subTest(agent=name):
                original = agent.read_text(encoding="utf-8")
                agent.write_text(
                    original.replace(".project/project.yml", ".project/REMOVED.yml"),
                    encoding="utf-8",
                    newline="\n",
                )
                self.assertIn("AGENT_BODY_CONTRACT", self.codes())
                agent.write_text(original, encoding="utf-8", newline="\n")

    def test_auto_delivery_contract_is_required_at_execution_entry_points(self) -> None:
        required = {
            "orchestrator.agent.md": (
                "`AUTO_DECIDE`",
                "`AUTO_COMMIT_AND_PUSH`",
                "`OUTPUT_COMMIT_MESSAGE`",
            ),
            "embedded-developer.agent.md": (
                "`SYNTHESIZE_METADATA`",
                "`CONFIRM_DELIVERY`",
                "`AUTO_DECIDE`",
                "`AUTO_COMMIT_AND_PUSH`",
                "`OUTPUT_COMMIT_MESSAGE`",
                "--expected-commit",
                "recommended default",
                "Jira ID is always user-supplied",
                "execute directly as the current EmbeddedDeveloper",
                "never delegate to yourself",
            ),
        }
        for name, markers in required.items():
            agent = self.repo / ".github" / "agents" / name
            original = agent.read_text(encoding="utf-8")
            for marker in markers:
                with self.subTest(agent=name, marker=marker):
                    agent.write_text(
                        original.replace(marker, "REMOVED_AUTO_DELIVERY_CONTRACT"),
                        encoding="utf-8",
                        newline="\n",
                    )
                    self.assertIn("AGENT_BODY_CONTRACT", self.codes())
            agent.write_text(original, encoding="utf-8", newline="\n")

    def test_missing_bug_resolver_agent_is_rejected(self) -> None:
        (self.repo / ".github" / "agents" / "bug-resolver.agent.md").unlink()
        self.assertIn("AGENT_SET", self.codes())

    def test_bug_resolver_behavior_contract_is_required(self) -> None:
        agent = self.repo / ".github" / "agents" / "bug-resolver.agent.md"
        original = agent.read_text(encoding="utf-8")
        for marker in (
            "DOCUMENT → DELIVERY → CLOSE",
            "GUIDE_SYMPTOMS",
            "CONFIRM_DIRECTION",
            "Usage Symptom Questions",
            "Usage Symptom Profile",
            "Direction Confirmation",
            "IDENTIFY_PROBLEM",
            "EVIDENCE_CHECK",
            "AWAIT_EVIDENCE",
            "`Git Delivery`",
            "`AUTO_DECIDE`",
            "Commit Delivery Confirmation",
            "recommended default",
            "Jira ID is always user-supplied",
            "separate complete delivery Task Brief",
        ):
            with self.subTest(marker=marker):
                agent.write_text(
                    original.replace(marker, "REMOVED_REQUIRED_BEHAVIOR"),
                    encoding="utf-8",
                    newline="\n",
                )
                self.assertIn("AGENT_BODY_CONTRACT", self.codes())
        agent.write_text(original, encoding="utf-8", newline="\n")

    def test_bug_prompts_require_delivery_contract(self) -> None:
        for name in ("analyze-bug.prompt.md", "analyze-log.prompt.md"):
            prompt = self.repo / ".github" / "prompts" / name
            original = prompt.read_text(encoding="utf-8")
            for marker in (
                "`Git Delivery`",
                "`DELIVERY`",
                "Commit Delivery Confirmation",
                "recommended default",
                "Jira ID is always user-supplied",
                "`AUTO_DECIDE`",
                "separate delivery Task Brief",
            ):
                with self.subTest(prompt=name, marker=marker):
                    prompt.write_text(
                        original.replace(marker, "REMOVED_DELIVERY_CONTRACT"),
                        encoding="utf-8",
                        newline="\n",
                    )
                    self.assertIn("PROMPT_BODY_CONTRACT", self.codes())
            prompt.write_text(original, encoding="utf-8", newline="\n")

    def test_extra_markdown_in_agents_directory_is_rejected(self) -> None:
        shutil.copyfile(
            FIXTURES / "negative" / "extra-agent.md",
            self.repo / ".github" / "agents" / "notes.md",
        )
        diagnostics = self.diagnostics()
        self.assertTrue(
            any(
                item.code == "AGENT_SET" and "notes.md" in item.message
                for item in diagnostics
            )
        )

    def test_invalid_agent_tools_reference_and_send_are_rejected(self) -> None:
        shutil.copyfile(
            FIXTURES / "negative" / "invalid-agent.agent.md",
            self.repo / ".github" / "agents" / "embedded-developer.agent.md",
        )
        codes = self.codes()
        self.assertIn("AGENT_TOOLS", codes)
        self.assertIn("AGENT_REFERENCE", codes)
        self.assertIn("HANDOFF_SEND", codes)

    def test_git_delivery_handoff_is_required_after_review_and_documentation(self) -> None:
        for name in (
            "bug-resolver.agent.md",
            "quality-reviewer.agent.md",
            "doc-keeper.agent.md",
        ):
            agent = self.repo / ".github" / "agents" / name
            original = agent.read_text(encoding="utf-8")
            with self.subTest(agent=name):
                agent.write_text(
                    original.replace(
                        "Git 提交交付 / Git Delivery",
                        "REMOVED_GIT_DELIVERY_HANDOFF",
                    ),
                    encoding="utf-8",
                    newline="\n",
                )
                self.assertIn("HANDOFF_DELIVERY", self.codes())
            agent.write_text(original, encoding="utf-8", newline="\n")

            for marker in (
                "recommended default",
                "user-supplied Jira ID",
                "generate every other commit field",
                "current input box",
                "execute directly as the current EmbeddedDeveloper",
                "never delegate to yourself",
            ):
                with self.subTest(agent=name, prompt_marker=marker):
                    agent.write_text(
                        original.replace(
                            marker,
                            "REMOVED_DELIVERY_DEFAULT_CONTRACT",
                            1,
                        ),
                        encoding="utf-8",
                        newline="\n",
                    )
                    self.assertIn("HANDOFF_DELIVERY", self.codes())
            agent.write_text(original, encoding="utf-8", newline="\n")

    def test_malformed_agent_yaml_is_rejected(self) -> None:
        shutil.copyfile(
            FIXTURES / "negative" / "malformed-agent.agent.md",
            self.repo / ".github" / "agents" / "embedded-developer.agent.md",
        )
        self.assertIn("FRONTMATTER_YAML", self.codes())

    def test_missing_skill_and_stale_prompt_reference_are_rejected(self) -> None:
        skill = self.repo / ".github" / "skills" / "misra-risk-review" / "SKILL.md"
        skill.unlink()
        prompt = self.repo / ".github" / "prompts" / "misra-review.prompt.md"
        prompt.write_text(
            prompt.read_text(encoding="utf-8").replace(
                "../skills/misra-risk-review/SKILL.md",
                "../skills/renamed-review/SKILL.md",
            ),
            encoding="utf-8",
            newline="\n",
        )
        codes = self.codes()
        self.assertIn("SKILL_SET", codes)
        self.assertIn("PROMPT_SKILL", codes)
        self.assertIn("LINK_MISSING", codes)

    def test_missing_analyze_bug_prompt_is_rejected(self) -> None:
        prompt = self.repo / ".github" / "prompts" / "analyze-bug.prompt.md"
        prompt.unlink()
        self.assertIn("PROMPT_SET", self.codes())

    def test_bug_prompt_must_route_to_bug_resolver(self) -> None:
        prompt = self.repo / ".github" / "prompts" / "analyze-bug.prompt.md"
        prompt.write_text(
            prompt.read_text(encoding="utf-8").replace(
                "agent: BugResolver",
                "agent: QualityReviewer",
            ),
            encoding="utf-8",
            newline="\n",
        )
        self.assertIn("PROMPT_AGENT", self.codes())

    def test_missing_required_skill_script_is_rejected(self) -> None:
        script = (
            self.repo
            / ".github"
            / "skills"
            / "misra-risk-review"
            / "scripts"
            / "normalize_sarif.py"
        )
        script.unlink()
        self.assertIn("SKILL_SCRIPT_SET", self.codes())

    def test_log_analysis_output_contract_is_required(self) -> None:
        skill = (
            self.repo
            / ".github"
            / "skills"
            / "firmware-log-analysis"
            / "SKILL.md"
        )
        original = skill.read_text(encoding="utf-8")
        for marker in (
            "GUIDE_SYMPTOMS",
            "CONFIRM_DIRECTION",
            "Usage Symptom Questions",
            "Usage Symptom Profile",
            "Direction Confirmation",
            "IDENTIFY_PROBLEM",
            "EVIDENCE_CHECK",
            "AWAIT_EVIDENCE",
            "Normalized Events",
        ):
            with self.subTest(marker=marker):
                skill.write_text(
                    original.replace(marker, "REMOVED_REQUIRED_BEHAVIOR"),
                    encoding="utf-8",
                    newline="\n",
                )
                self.assertIn("SKILL_BODY_CONTRACT", self.codes())
        skill.write_text(original, encoding="utf-8", newline="\n")

    def test_invalid_project_profile_is_rejected(self) -> None:
        shutil.copyfile(
            FIXTURES / "negative" / "invalid-profile.yml",
            self.repo / ".github" / "embedded-project.yml",
        )
        self.assertIn("PROFILE_SCHEMA", self.codes())

    def test_crlf_is_rejected(self) -> None:
        readme = self.repo / "README.md"
        text = readme.read_text(encoding="utf-8")
        readme.write_bytes(text.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))
        self.assertIn("TEXT_LF", self.codes())

    def test_missing_bilingual_section_is_rejected(self) -> None:
        self.install_negative_markdown("broken-bilingual.md")
        self.assertIn("BILINGUAL_SECTIONS", self.codes())

    def test_project_markdown_requires_bilingual_sections(self) -> None:
        shutil.copyfile(
            FIXTURES / "negative" / "broken-bilingual.md",
            self.repo / ".project" / "rules" / "broken-bilingual.md",
        )
        self.assertIn("BILINGUAL_SECTIONS", self.codes())

    def test_unresolved_todo_sync_in_prose_is_rejected(self) -> None:
        self.install_negative_markdown("todo-sync.md")
        self.assertIn("TODO_SYNC", self.codes())

    def test_broken_local_markdown_link_is_rejected(self) -> None:
        self.install_negative_markdown("broken-link.md")
        self.assertIn("LINK_MISSING", self.codes())

    def test_valid_local_markdown_anchors_are_accepted(self) -> None:
        docs = self.repo / "docs"
        shutil.copyfile(
            FIXTURES / "markdown" / "anchor-target.md",
            docs / "anchor-target.md",
        )
        shutil.copyfile(
            FIXTURES / "markdown" / "anchor-links-valid.md",
            docs / "anchor-links-valid.md",
        )
        self.assertEqual([], self.diagnostics())

    def test_missing_local_markdown_anchor_is_rejected(self) -> None:
        docs = self.repo / "docs"
        shutil.copyfile(
            FIXTURES / "markdown" / "anchor-target.md",
            docs / "anchor-target.md",
        )
        self.install_negative_markdown("broken-anchor.md")
        self.assertIn("LINK_ANCHOR_MISSING", self.codes())

    def test_documented_todo_sync_inside_code_is_allowed(self) -> None:
        readme = self.repo / "README.md"
        readme.write_text(
            readme.read_text(encoding="utf-8")
            + "\n<!-- The policy token is intentionally quoted: `TODO(sync)`. -->\n",
            encoding="utf-8",
            newline="\n",
        )
        self.assertNotIn("TODO_SYNC", self.codes())


if __name__ == "__main__":
    unittest.main()
