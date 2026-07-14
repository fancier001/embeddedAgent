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

    def test_missing_agent_is_rejected(self) -> None:
        (self.repo / ".github" / "agents" / "doc-keeper.agent.md").unlink()
        self.assertIn("AGENT_SET", self.codes())

    def test_missing_bug_resolver_agent_is_rejected(self) -> None:
        (self.repo / ".github" / "agents" / "bug-resolver.agent.md").unlink()
        self.assertIn("AGENT_SET", self.codes())

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
