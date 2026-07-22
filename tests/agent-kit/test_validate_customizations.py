from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

TEST_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = TEST_ROOT.parents[1]
sys.path.insert(0, str(PROJECT_ROOT / ".github" / "agent-kit" / "scripts"))

from validate_customizations import validate_repository


FIXTURES = TEST_ROOT / "fixtures"


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

    def test_test_assets_are_kept_outside_runtime_tree(self) -> None:
        legacy = self.repo / ".github" / "agent-kit" / "tests"
        legacy.mkdir(parents=True)
        (legacy / "test_legacy.py").write_text("pass\n", encoding="utf-8")
        self.assertIn("TEST_LAYOUT", self.codes())

        shutil.rmtree(legacy)
        (self.repo / "tests" / "agent-kit" / "requirements.txt").unlink()
        self.assertIn("REQUIRED_TEST_FILE", self.codes())

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

    def test_legacy_allowed_paths_are_accepted_but_non_authoritative(self) -> None:
        policy = self.read_yaml(".project/git/delivery.yml")
        policy["scope"]["allowed_paths"] = [".github/**", "docs/**"]
        self.write_yaml(".project/git/delivery.yml", policy)
        self.assertEqual([], self.diagnostics())

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
        template.write_text(
            original.replace("<AI-Tool-Scenario>: /", "<AI-Tool-Scenario>: N/A"),
            encoding="utf-8",
            newline="\n",
        )
        self.assertIn("COMMIT_TEMPLATE_AI_DEFAULT", self.codes())

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

    def test_manager_and_executor_state_contracts_are_required(self) -> None:
        required = {
            "orchestrator.agent.md": (
                ".github/agent-contracts.md",
                "`PREFLIGHT`",
                "`PLAN`",
                "`IMPLEMENT`",
                "`VERIFY`",
                "`REVIEW`",
                "`DOCUMENT`",
                "`DELIVERY`",
                "Task Change Baseline",
            ),
            "embedded-developer.agent.md": (
                ".github/agent-contracts.md",
                "project_policy.py",
                "`IMPLEMENT`",
                "`TEST`",
                "`BUILD`",
                "`REPORT`",
                "`LOAD_POLICY`",
                "`DETECT_COMMIT_SCOPE`",
                "`CONFIRM_DELIVERY`",
                "`AUTO_DECIDE`",
                "`CONFIRM_PUSH`",
                "Task Change Baseline",
            ),
        }
        for name, markers in required.items():
            agent = self.repo / ".github" / "agents" / name
            original = agent.read_text(encoding="utf-8")
            for marker in markers:
                with self.subTest(agent=name, marker=marker):
                    agent.write_text(
                        original.replace(marker, "REMOVED_ROLE_STATE_CONTRACT"),
                        encoding="utf-8",
                        newline="\n",
                    )
                    self.assertIn("AGENT_BODY_CONTRACT", self.codes())
            agent.write_text(original, encoding="utf-8", newline="\n")

    def test_specialist_role_contracts_are_required(self) -> None:
        required = {
            "quality-reviewer.agent.md": (
                ".github/agent-contracts.md",
                "Review Finding",
                "`BLOCKER`",
                "`MAJOR`",
                "`MINOR`",
                "`REPORT`",
            ),
            "doc-keeper.agent.md": (
                ".github/agent-contracts.md",
                ".project/",
                "`RECEIVED`",
                "`REPORT`",
                "Documentation",
            ),
        }
        for name, markers in required.items():
            agent = self.repo / ".github" / "agents" / name
            original = agent.read_text(encoding="utf-8")
            for marker in markers:
                with self.subTest(agent=name, marker=marker):
                    agent.write_text(
                        original.replace(marker, "REMOVED_SPECIALIST_CONTRACT"),
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
            ".github/agent-contracts.md",
            "CLOSE â†’ RESET â†’ INTAKE",
            "GUIDE_SYMPTOMS",
            "CONFIRM_DIRECTION",
            "Usage Symptom Questions",
            "Usage Symptom Profile",
            "Direction Confirmation",
            "IDENTIFY_PROBLEM",
            "EVIDENCE_CHECK",
            "AWAIT_EVIDENCE",
            "`PLAN_FIX`",
            "Task Change Baseline",
            "`Root Cause`",
        ):
            with self.subTest(marker=marker):
                agent.write_text(
                    original.replace(marker, "REMOVED_REQUIRED_BEHAVIOR"),
                    encoding="utf-8",
                    newline="\n",
                )
                self.assertIn("AGENT_BODY_CONTRACT", self.codes())
        agent.write_text(original, encoding="utf-8", newline="\n")

    def test_bug_prompts_reference_canonical_contract(self) -> None:
        for name in ("analyze-bug.prompt.md", "analyze-log.prompt.md"):
            prompt = self.repo / ".github" / "prompts" / name
            original = prompt.read_text(encoding="utf-8")
            for marker in (
                ".github/agent-contracts.md",
                "read-only by default",
                "does not duplicate",
            ):
                with self.subTest(prompt=name, marker=marker):
                    prompt.write_text(
                        original.replace(marker, "REMOVED_CANONICAL_REFERENCE"),
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

    def tes×½º¶‰žËkºwµçQ%¸ ‰ÍÕÁÁ±¥•Ì¹¼µ¥ÍÍ¥¹œ¥¹ÁÕÐˆ°¡…¹‘½™™l‰ÁÉ½µÁÐ‰t¤(€€€€€€€€€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ (€€€€€€€€€€€€€€€€€€€€‰½¹™¥ÉµÌ¹¼½µµ¥Ð°ÁÕÍ °½È•áÑ•É¹…°½µµ…¹ˆ°(€€€€€€€€€€€€€€€€€€€¡…¹‘½™™l‰ÁÉ½µÁÐ‰t°(€€€€€€€€€€€€€€€€¤((€€€€€€€…•¹Ð€ôÍ•±˜¹É•Á¼€¼€ˆ¹¥Ñ¡Õˆˆ€¼€‰…•¹ÑÌˆ€¼€‰½É¡•ÍÑÉ…Ñ½È¹…•¹Ð¹µˆ(€€€€€€€½É¥¥¹…°€ô…•¹Ð¹É•…‘}Ñ•áÐ¡•¹½‘¥¹œô‰ÕÑ˜´àˆ¤(€€€€€€€µÕÑ…Ñ¥½¹Ì€ô€ (€€€€€€€€€€€€ ‰…•¹Ðè9•áÑÑ¥½¹I½ÕÑ•Èˆ°€‰…•¹Ðèµ‰•‘‘•‘•Ù•±½Á•Èˆ¤°(€€€€€€€€€€€€ ˆ€€€Í•¹èÑÉÕ”ˆ°€ˆ€€€Í•¹è™…±Í”ˆ¤°(€€€€€€€€€€€€ ‰ÍÕÁÁ±¥•Ì¹¼µ¥ÍÍ¥¹œ¥¹ÁÕÐˆ°€‰ÍÕÁÁ±¥•Ì¥µÁ±¥¥Ð¥¹ÁÕÐˆ¤°(€€€€€€€€¤(€€€€€€€™½È½±°¹•Ü¥¸µÕÑ…Ñ¥½¹Ìè(€€€€€€€€€€€Ý¥Ñ Í•±˜¹ÍÕ‰Q•ÍÐ¡µÕÑ…Ñ¥½¸õ½±¤è(€€€€€€€€€€€€€€€…•¹Ð¹ÝÉ¥Ñ•}Ñ•áÐ (€€€€€€€€€€€€€€€€€€€½É¥¥¹…°¹É•Á±…”¡½±°¹•Ü°€Ä¤°(€€€€€€€€€€€€€€€€€€€•¹½‘¥¹œô‰ÕÑ˜´àˆ°(€€€€€€€€€€€€€€€€€€€¹•Ý±¥¹”ô‰q¸ˆ°(€€€€€€€€€€€€€€€€¤(€€€€€€€€€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‰!9=}9aQ}Q%=8ˆ°Í•±˜¹½‘•Ì ¤¤(€€€€€€€…•¹Ð¹ÝÉ¥Ñ•}Ñ•áÐ¡½É¥¥¹…°°•¹½‘¥¹œô‰ÕÑ˜´àˆ°¹•Ý±¥¹”ô‰q¸ˆ¤((€€€‘•˜Ñ•ÍÑ}¹•áÑ}…Ñ¥½¹}É½ÕÑ•É}¥Í}¡¥‘‘•¹}…¹‘}µ¥¹¥µ…°¡Í•±˜¤€´ø9½¹”è(€€€€€€€É½ÕÑ•È€ôÍ•±˜¹É•Á¼€¼€ˆ¹¥Ñ¡Õˆˆ€¼€‰…•¹ÑÌˆ€¼€‰¹•áÐµ…Ñ¥½¸µÉ½ÕÑ•È¹…•¹Ð¹µˆ(€€€€€€€½É¥¥¹…°€ôÉ½ÕÑ•È¹É•…‘}Ñ•áÐ¡•¹½‘¥¹œô‰ÕÑ˜´àˆ¤(€€€€€€€™É½¹Ñµ…ÑÑ•È€ôå…µ°¹Í…™•}±½…¡½É¥¥¹…°¹ÍÁ±¥Ð ˆ´´µq¸ˆ°€È¥lÅt¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…° ‰9•áÑÑ¥½¹I½ÕÑ•Èˆ°™É½¹Ñµ…ÑÑ•Él‰¹…µ”‰t¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%Ì¡™É½¹Ñµ…ÑÑ•Él‰ÕÍ•Èµ¥¹Ù½…‰±”‰t°…±Í”¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%Ì¡™É½¹Ñµ…ÑÑ•Él‰‘¥Í…‰±”µµ½‘•°µ¥¹Ù½…Ñ¥½¸‰t°QÉÕ”¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡l‰…•¹Ðˆ°€‰É•…ˆ°€‰Í•…É ‰t°™É½¹Ñµ…ÑÑ•Él‰Ñ½½±Ì‰t¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…° (€€€€€€€€€€€l(€€€€€€€€€€€€€€€€‰=É¡•ÍÑÉ…Ñ½Èˆ°(€€€€€€€€€€€€€€€€‰	ÕI•Í½±Ù•Èˆ°(€€€€€€€€€€€€€€€€‰µ‰•‘‘•‘•Ù•±½Á•Èˆ°(€€€€€€€€€€€€€€€€‰EÕ…±¥ÑåI•Ù¥•Ý•Èˆ°(€€€€€€€€€€€€€€€€‰½-••Á•Èˆ°(€€€€€€€€€€€t°(€€€€€€€€€€€™É½¹Ñµ…ÑÑ•Él‰…•¹ÑÌ‰t°(€€€€€€€€¤(€€€€€€€•áÁ•Ñ•‘}¡…¹‘½™™Ì€ô€ (€€€€€€€€€€€€ ‹¢þS–n{žò[š:H€¼I•ÑÕÉ¸Ñ¼=É¡•ÍÑÉ…Ñ½Èˆ°€‰=É¡•ÍÑÉ…Ñ½Èˆ¤°(€€€€€€€€€€€€ ‹¢þS–n{¦^»¦Šc¢ž–Ì€¼I•ÑÕÉ¸Ñ¼	ÕœI•Í½±Ù•Èˆ°€‰	ÕI•Í½±Ù•Èˆ¤°(€€€€€€€€€€€€ ‹¢þS–n{–º{šZô€¼I•ÑÕÉ¸Ñ¼µ‰•‘‘••Ù•±½Á•Èˆ°€‰µ‰•‘‘•‘•Ù•±½Á•Èˆ¤°(€€€€€€€€€€€€ ‹¢þS–n{¢¾–º„€¼I•ÑÕÉ¸Ñ¼EÕ…±¥ÑäI•Ù¥•Ý•Èˆ°€‰EÕ…±¥ÑåI•Ù¥•Ý•Èˆ¤°(€€€€€€€€€€€€ ‹¢þS–n{šZš†Œ€¼I•ÑÕÉ¸Ñ¼½Œ-••Á•Èˆ°€‰½-••Á•Èˆ¤°(€€€€€€€€¤(€€€€€€€¡…¹‘½™™Ì€ô™É½¹Ñµ…ÑÑ•Él‰¡…¹‘½™™Ì‰t(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…° (€€€€€€€€€€€•áÁ•Ñ•‘}¡…¹‘½™™Ì°(€€€€€€€€€€€ÑÕÁ±” ¡¥Ñ•µl‰±…‰•°‰t°¥Ñ•µl‰…•¹Ð‰t¤™½È¥Ñ•´¥¸¡…¹‘½™™Ì¤°(€€€€€€€€¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑQÉÕ”¡…±°¡¥Ñ•µl‰Í•¹‰t¥Ì…±Í”™½È¥Ñ•´¥¸¡…¹‘½™™Ì¤¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑQÉÕ” (€€€€€€€€€€€…±° (€€€€€€€€€€€€€€€€‰I•Ù…±¥‘…Ñ”Ñ¡”±…Ñ•ÍÐÕ¹¥ÅÕ”9•áÐÑ¥½¸ˆ¥¸¥Ñ•µl‰ÁÉ½µÁÐ‰t(€€€€€€€€€€€€€€€…¹€‰ÍÕÁÁ±¥•Ì¹¼µ¥ÍÍ¥¹œ¥¹ÁÕÐˆ¥¸¥Ñ•µl‰ÁÉ½µÁÐ‰t(€€€€€€€€€€€€€€€…¹€‰½¹™¥ÉµÌ¹¼½µµ¥Ð°ÁÕÍ °½È•áÑ•É¹…°½µµ…¹ˆ(€€€€€€€€€€€€€€€¥¸¥Ñ•µl‰ÁÉ½µÁÐ‰t(€€€€€€€€€€€€€€€™½È¥Ñ•´¥¸¡…¹‘½™™Ì(€€€€€€€€€€€€¤(€€€€€€€€¤((€€€€€€€µÕÑ…Ñ¥½¹Ì€ô€ (€€€€€€€€€€€€ ‰ÕÍ•Èµ¥¹Ù½…‰±”è™…±Í”ˆ°€‰ÕÍ•Èµ¥¹Ù½…‰±”èÑÉÕ”ˆ°€‰9Q}%9Y=	1ˆ¤°(€€€€€€€€€€€€ (€€€€€€€€€€€€€€€€‰Ñ½½±Ìèl…•¹Ðœ°€É•…œ°€Í•…É tˆ°(€€€€€€€€€€€€€€€€‰Ñ½½±Ìèl…•¹Ðœ°€É•…œ°€Í•…É œ°€•á•ÕÑ”tˆ°(€€€€€€€€€€€€€€€€‰9Q}Q==1Lˆ°(€€€€€€€€€€€€¤°(€€€€€€€€€€€€ (€€€€€€€€€€€€€€€€‰…Ðµ½ÍÐ•¥¡Ð½¹Í•ÕÑ¥Ù”…Ñ¥½¹Ìˆ°(€€€€€€€€€€€€€€€€‰Ý¥Ñ¡½ÕÐ„ÑÉ…¹Í¥Ñ¥½¸±¥µ¥Ðˆ°(€€€€€€€€€€€€€€€€‰9Q}	=e}=9QIPˆ°(€€€€€€€€€€€€¤°(€€€€€€€€€€€€ (€€€€€€€€€€€€€€€€‹¢þS–n{žò[š:H€¼I•ÑÕÉ¸Ñ¼=É¡•ÍÑÉ…Ñ½Èˆ°(€€€€€€€€€€€€€€€€‰I5=Y}I=UQI}11	,ˆ°(€€€€€€€€€€€€€€€€‰!9=}	M1%9ˆ°(€€€€€€€€€€€€¤°(€€€€€€€€€€€€ (€€€€€€€€€€€€€€€€ˆ€€€Í•¹è™…±Í”ˆ°(€€€€€€€€€€€€€€€€ˆ€€€Í•¹èÑÉÕ”ˆ°(€€€€€€€€€€€€€€€€‰!9=}I=UQI}11	,ˆ°(€€€€€€€€€€€€¤°(€€€€€€€€€€€€ (€€€€€€€€€€€€€€€€‰ÍÕÁÁ±¥•Ì¹¼µ¥ÍÍ¥¹œ¥¹ÁÕÐˆ°(€€€€€€€€€€€€€€€€‰ÍÕÁÁ±¥•Ì¥µÁ±¥¥Ð¥¹ÁÕÐˆ°(€€€€€€€€€€€€€€€€‰!9=}I=UQI}11	,ˆ°(€€€€€€€€€€€€¤°(€€€€€€€€¤(€€€€€€€™½È½±°¹•Ü°½‘”¥¸µÕÑ…Ñ¥½¹Ìè(€€€€€€€€€€€Ý¥Ñ Í•±˜¹ÍÕ‰Q•ÍÐ¡µÕÑ…Ñ¥½¸õ½±¤è(€€€€€€€€€€€€€€€É½ÕÑ•È¹ÝÉ¥Ñ•}Ñ•áÐ (€€€€€€€€€€€€€€€€€€€½É¥¥¹…°¹É•Á±…”¡½±°¹•Ü°€Ä¤°(€€€€€€€€€€€€€€€€€€€•¹½‘¥¹œô‰ÕÑ˜´àˆ°(€€€€€€€€€€€€€€€€€€€¹•Ý±¥¹”ô‰q¸ˆ°(€€€€€€€€€€€€€€€€¤(€€€€€€€€€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸¡½‘”°Í•±˜¹½‘•Ì ¤¤(€€€€€€€É½ÕÑ•È¹ÝÉ¥Ñ•}Ñ•áÐ¡½É¥¥¹…°°•¹½‘¥¹œô‰ÕÑ˜´àˆ°¹•Ý±¥¹”ô‰q¸ˆ¤((€€€€€€€™½Èµ…É­•È¥¸€ ‰%¹ÁÕÐI•ÅÕ¥É•ˆ°€‰I•Á±äQ•µÁ±…Ñ”ˆ¤è(€€€€€€€€€€€Ý¥Ñ Í•±˜¹ÍÕ‰Q•ÍÐ¡É•ÅÕ¥É•‘}¥¹ÁÕÑ}µ…É­•Èõµ…É­•È¤è(€€€€€€€€€€€€€€€É½ÕÑ•È¹ÝÉ¥Ñ•}Ñ•áÐ (€€€€€€€€€€€€€€€€€€€½É¥¥¹…°¹É•Á±…”¡µ…É­•È°€‰I5=Y}%9AUQ}=9QIPˆ¤°(€€€€€€€€€€€€€€€€€€€•¹½‘¥¹œô‰ÕÑ˜´àˆ°(€€€€€€€€€€€€€€€€€€€¹•Ý±¥¹”ô‰q¸ˆ°(€€€€€€€€€€€€€€€€¤(€€€€€€€€€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‰9Q}	=e}=9QIPˆ°Í•±˜¹½‘•Ì ¤¤(€€€€€€€É½ÕÑ•È¹ÝÉ¥Ñ•}Ñ•áÐ¡½É¥¥¹…°°•¹½‘¥¹œô‰ÕÑ˜´àˆ°¹•Ý±¥¹”ô‰q¸ˆ¤((€€€‘•˜Ñ•ÍÑ}¥Ñ}‘•±¥Ù•Éå}¡…¹‘½™™}¥Í}É•ÅÕ¥É•‘}…™Ñ•É}É•Ù¥•Ý}…¹‘}‘½Õµ•¹Ñ…Ñ¥½¸¡Í•±˜¤€´ø9½¹”è(€€€€€€€™½È¹…µ”¥¸€ (€€€€€€€€€€€€‰‰ÕœµÉ•Í½±Ù•È¹…•¹Ð¹µˆ°(€€€€€€€€€€€€‰ÅÕ…±¥ÑäµÉ•Ù¥•Ý•È¹…•¹Ð¹µˆ°(€€€€€€€€€€€€‰‘½Œµ­••Á•È¹…•¹Ð¹µˆ°(€€€€€€€€¤è(€€€€€€€€€€€…•¹Ð€ôÍ•±˜¹É•Á¼€¼€ˆ¹¥Ñ¡Õˆˆ€¼€‰…•¹ÑÌˆ€¼¹…µ”(€€€€€€€€€€€½É¥¥¹…°€ô…•¹Ð¹É•…‘}Ñ•áÐ¡•¹½‘¥¹œô‰ÕÑ˜´àˆ¤(€€€€€€€€€€€Ý¥Ñ Í•±˜¹ÍÕ‰Q•ÍÐ¡…•¹Ðõ¹…µ”¤è(€€€€€€€€€€€€€€€…•¹Ð¹ÝÉ¥Ñ•}Ñ•áÐ (€€€€€€€€€€€€€€€€€€€½É¥¥¹…°¹É•Á±…” (€€€€€€€€€€€€€€€€€€€€€€€€‰¥Ðƒš>C’ê“’ê“’î`€¼¥Ð•±¥Ù•Éäˆ°(€€€€€€€€€€€€€€€€€€€€€€€€‰I5=Y}%Q}1%YIe}!9=ˆ°(€€€€€€€€€€€€€€€€€€€€¤°(€€€€€€€€€€€€€€€€€€€•¹½‘¥¹œô‰ÕÑ˜´àˆ°(€€€€€€€€€€€€€€€€€€€¹•Ý±¥¹”ô‰q¸ˆ°(€€€€€€€€€€€€€€€€¤(€€€€€€€€€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‰!9=}1%YIdˆ°Í•±˜¹½‘•Ì ¤¤(€€€€€€€€€€€…•¹Ð¹ÝÉ¥Ñ•}Ñ•áÐ¡½É¥¥¹…°°•¹½‘¥¹œô‰ÕÑ˜´àˆ°¹•Ý±¥¹”ô‰q¸ˆ¤((€€€€€€€€€€€™½Èµ…É­•È¥¸€ (€€€€€€€€€€€€€€€€‰É•½µµ•¹‘•‘•™…Õ±Ðˆ°(€€€€€€€€€€€€€€€€‰ÕÍ•ÈµÍÕÁÁ±¥•)¥É„%ˆ°(€€€€€€€€€€€€€€€€‰•¹•É…Ñ”•Ù•Éä½Ñ¡•È½µµ¥Ð™¥•±ˆ°(€€€€€€€€€€€€€€€€‰ÕÉÉ•¹Ð¥¹ÁÕÐ‰½àˆ°(€€€€€€€€€€€€€€€€‰•á•ÕÑ”‘¥É•Ñ±ä…ÌÑ¡”ÕÉÉ•¹Ðµ‰•‘‘•‘•Ù•±½Á•Èˆ°(€€€€€€€€€€€€€€€€‰¹•Ù•È‘•±•…Ñ”Ñ¼å½ÕÉÍ•±˜ˆ°(€€€€€€€€€€€€€€€€‰Q…Í¬¡…¹”	…Í•±¥¹”ˆ°(€€€€€€€€€€€€€€€€‰Q…Í¬¡…¹”1•‘•Èˆ°(€€€€€€€€€€€€€€€€‰QQ}=55%Q}M=Aˆ°(€€€€€€€€€€€€€€€€‰½µµ¥Ð½¹Ñ•¹Ðˆ°(€€€€€€€€€€€€€€€€‰)UMQ}!9MPˆ°(€€€€€€€€€€€€€€€€‰¡…¹”½¹™¥Éµ…Ñ¥½¸èA9%9ˆ°(€€€€€€€€€€€€€€€€‰=9%I5}AUM ˆ°(€€€€€€€€€€€€€€€€‰59U1}AUM ˆ°(€€€€€€€€€€€€¤è(€€€€€€€€€€€€€€€Ý¥Ñ Í•±˜¹ÍÕ‰Q•ÍÐ¡…•¹Ðõ¹…µ”°ÁÉ½µÁÑ}µ…É­•Èõµ…É­•È¤è(€€€€€€€€€€€€€€€€€€€…•¹Ð¹ÝÉ¥Ñ•}Ñ•áÐ (€€€€€€€€€€€€€€€€€€€€€€€½É¥¥¹…°¹É•Á±…” (€€€€€€€€€€€€€€€€€€€€€€€€€€€µ…É­•È°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€‰I5=Y}1%YIe}U1Q}=9QIPˆ°(€€€€€€€€€€€€€€€€€€€€€€€€¤°(€€€€€€€€€€€€€€€€€€€€€€€•¹½‘¥¹œô‰ÕÑ˜´àˆ°(€€€€€€€€€€€€€€€€€€€€€€€¹•Ý±¥¹”ô‰q¸ˆ°(€€€€€€€€€€€€€€€€€€€€¤(€€€€€€€€€€€€€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‰!9=}1%YIdˆ°Í•±˜¹½‘•Ì ¤¤(€€€€€€€€€€€…•¹Ð¹ÝÉ¥Ñ•}Ñ•áÐ¡½É¥¥¹…°°•¹½‘¥¹œô‰ÕÑ˜´àˆ°¹•Ý±¥¹”ô‰q¸ˆ¤((€€€‘•˜Ñ•ÍÑ}Í¡…É•‘}½¹ÑÉ…Ñ}É•ÅÕ¥É•Í}¡…¹•}½¹™¥Éµ…Ñ¥½¹}…¹‘}…‘©ÕÍÑµ•¹Ð¡Í•±˜¤€´ø9½¹”è(€€€€€€€½¹ÑÉ…Ð€ôÍ•±˜¹É•Á¼€¼€ˆ¹¥Ñ¡Õˆˆ€¼€‰…•¹Ðµ½¹ÑÉ…ÑÌ¹µˆ(€€€€€€€½É¥¥¹…°€ô½¹ÑÉ…Ð¹É•…‘}Ñ•áÐ¡•¹½‘¥¹œô‰ÕÑ˜´àˆ¤(€€€€€€€™½Èµ…É­•È¥¸€ (€€€€€€€€€€€€ˆŒŒ9•áÐÑ¥½¸ˆ°(€€€€€€€€€€€€‰)UMQ}!9MQ€ˆ°(€€€€€€€€€€€€‰¡…¹”½¹™¥Éµ…Ñ¥½¸èA9%9ˆ°(€€€€€€€€€€€€‰½¹™¥É´¡…¹•Ì…¹½µµ¥Ðˆ°(€€€€€€€€€€€€‰Á•Èµ™¥±”•¹ÑÉ¥•Í€ˆ°(€€€€€€€€€€€€‰=9%I5}AUM!€ˆ°(€€€€€€€€€€€€‰59U1}AUM!€ˆ°(€€€€€€€€€€€€‰MQIQ}9]}%MMU€ˆ°(€€€€€€€€€€€€ˆ´U$I½ÕÑ”èˆ°(€€€€€€€€€€€€ˆ´¥ÍÁ…Ñ Q…É•Ðèˆ°(€€€€€€€€€€€€ˆ´%¹ÁÕÐI•ÅÕ¥É•èˆ°(€€€€€€€€€€€€ˆ´I•ÅÕ¥É•%¹ÁÕÐèˆ°(€€€€€€€€€€€€ˆ´I•Á±äQ•µÁ±…Ñ”èˆ°(€€€€€€€€€€€€ˆ´%¹ÍÑÉÕÑ¥½¸èˆ°(€€€€€€€€€€€€‰AI=Y%}Y%9€ˆ°(€€€€€€€€€€€€‰9aQ}Q%=9}	UQQ=8ˆ°(€€€€€€€€€€€€‰!9=èñ•á…ÐÕÉÉ•¹Ðµ…•¹Ð‰…Í”µ‰ÕÑÑ½¸±…‰•°øˆ°(€€€€€€€€€€€€‰9Q}=9Q%9Uˆ°(€€€€€€€€€€€€‰9=Q}IU8ƒŠP9½ÐÉ•ÅÕ¥É•è€ñÉ•…Í½¸øˆ°(€€€€€€€€€€€€‰=9%I5}=55%Q}=9Q9Q€ˆ°(€€€€€€€€€€€€ˆ´µ•áÁ•Ñ•µ½¹Ñ•¹Ðµ™¥¹•ÉÁÉ¥¹Ðˆ°(€€€€€€€€€€€€‰½¹Ñ•¹Ñ}½¹™¥Éµ…Ñ¥½¸¹ÍÑ…ÑÕÌè=9%I5ˆ°(€€€€€€€€€€€€‰½µµ¥Ð½¹Ñ•¹Ð½¹™¥Éµ…Ñ¥½¸èA9%9ˆ°(€€€€€€€€€€€€‹¢þS–n{žò[š:H€¼I•ÑÕÉ¸Ñ¼=É¡•ÍÑÉ…Ñ½Èˆ°(€€€€€€€€€€€€‰™¥Ù”ÍÑ…Ñ¥Œ™…±±‰…¬¡…¹‘½™™Ìˆ°(€€€€€€€€¤è(€€€€€€€€€€€Ý¥Ñ Í•±˜¹ÍÕ‰Q•ÍÐ¡µ…É­•Èõµ…É­•È¤è(€€€€€€€€€€€€€€€½¹ÑÉ…Ð¹ÝÉ¥Ñ•}Ñ•áÐ (€€€€€€€€€€€€€€€€€€€½É¥¥¹…°¹É•Á±…”¡µ…É­•È°€‰I5=Y}M!I}=9QIPˆ¤°(€€€€€€€€€€€€€€€€€€€•¹½‘¥¹œô‰ÕÑ˜´àˆ°(€€€€€€€€€€€€€€€€€€€¹•Ý±¥¹”ô‰q¸ˆ°(€€€€€€€€€€€€€€€€¤(€€€€€€€€€€€€€€€Í•±˜¹…ÍÍ•ÉÑQÉÕ” (€€€€€€€€€€€€€€€€€€€…¹ä¡½‘”¹ÍÑ…ÉÑÍÝ¥Ñ  ‰M!I}=9QIPˆ¤™½È½‘”¥¸Í•±˜¹½‘•Ì ¤¤(€€€€€€€€€€€€€€€€¤(€€€€€€€½¹ÑÉ…Ð¹ÝÉ¥Ñ•}Ñ•áÐ¡½É¥¥¹…°°•¹½‘¥¹œô‰ÕÑ˜´àˆ°¹•Ý±¥¹”ô‰q¸ˆ¤((€€€‘•˜Ñ•ÍÑ}±½Í•}¥ÍÍÕ•}¡…¹‘½™™}¥Í}É•ÅÕ¥É•‘}…™Ñ•É}‘•±¥Ù•Éä¡Í•±˜¤€´ø9½¹”è(€€€€€€€…•¹Ð€ôÍ•±˜¹É•Á¼€¼€ˆ¹¥Ñ¡Õˆˆ€¼€‰…•¹ÑÌˆ€¼€‰•µ‰•‘‘•µ‘•Ù•±½Á•È¹…•¹Ð¹µˆ(€€€€€€€½É¥¥¹…°€ô…•¹Ð¹É•…‘}Ñ•áÐ¡•¹½‘¥¹œô‰ÕÑ˜´àˆ¤(€€€€€€€…•¹Ð¹ÝÉ¥Ñ•}Ñ•áÐ (€€€€€€€€€€€½É¥¥¹…°¹É•Á±…” (€€€€€€€€€€€€€€€€‹¦^»¦Šc–ÞË¢ž–Ì€¼±½Í”%ÍÍÕ”ˆ°(€€€€€€€€€€€€€€€€‰I5=Y}1=M}%MMU}!9=ˆ°(€€€€€€€€€€€€¤°(€€€€€€€€€€€•¹½‘¥¹œô‰ÕÑ˜´àˆ°(€€€€€€€€€€€¹•Ý±¥¹”ô‰q¸ˆ°(€€€€€€€€¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‰!9=}1=M}%MMUˆ°Í•±˜¹½‘•Ì ¤¤((€€€€€€€™½Èµ…É­•È¥¸€ (€€€€€€€€€€€€‰I•¡•¬ˆ°(€€€€€€€€€€€€‰É•Á…¥Èˆ°(€€€€€€€€€€€€‰Í•±•Ñ•¥Ð‘•±¥Ù•Éäˆ°(€€€€€€€€€€€€‰±•…È¥ÍÍÕ”µ±•Ù•°ÍÑ…Ñ”ˆ°(€€€€€€€€€€€€‰™É•Í ¥ÍÍÕ”%9Q-ˆ°(€€€€€€€€€€€€‰½Ñ¡•ÉÝ¥Í”É•ÑÕÉ¸	1=-ˆ°(€€€€€€€€€€€€‰9•áÐÑ¥½¸ˆ°(€€€€€€€€¤è(€€€€€€€€€€€Ý¥Ñ Í•±˜¹ÍÕ‰Q•ÍÐ¡ÁÉ½µÁÑ}µ…É­•Èõµ…É­•È¤è(€€€€€€€€€€€€€€€…•¹Ð¹ÝÉ¥Ñ•}Ñ•áÐ (€€€€€€€€€€€€€€€€€€€½É¥¥¹…°¹É•Á±…” (€€€€€€€€€€€€€€€€€€€€€€€µ…É­•È°(€€€€€€€€€€€€€€€€€€€€€€€€‰I5=Y}1=M}%MMU}=9QIPˆ°(€€€€€€€€€€€€€€€€€€€€¤°(€€€€€€€€€€€€€€€€€€€•¹½‘¥¹œô‰ÕÑ˜´àˆ°(€€€€€€€€€€€€€€€€€€€¹•Ý±¥¹”ô‰q¸ˆ°(€€€€€€€€€€€€€€€€¤(€€€€€€€€€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‰!9=}1=M}%MMUˆ°Í•±˜¹½‘•Ì ¤¤(€€€€€€€…•¹Ð¹ÝÉ¥Ñ•}Ñ•áÐ¡½É¥¥¹…°°•¹½‘¥¹œô‰ÕÑ˜´àˆ°¹•Ý±¥¹”ô‰q¸ˆ¤((€€€‘•˜Ñ•ÍÑ}µ…±™½Éµ•‘}…•¹Ñ}å…µ±}¥Í}É•©•Ñ•¡Í•±˜¤€´ø9½¹”è(€€€€€€€Í¡ÕÑ¥°¹½Áå™¥±” (€€€€€€€€€€€%aQUIL€¼€‰¹•…Ñ¥Ù”ˆ€¼€‰µ…±™½Éµ•µ…•¹Ð¹…•¹Ð¹µˆ°(€€€€€€€€€€€Í•±˜¹É•Á¼€¼€ˆ¹¥Ñ¡Õˆˆ€¼€‰…•¹ÑÌˆ€¼€‰•µ‰•‘‘•µ‘•Ù•±½Á•È¹…•¹Ð¹µˆ°(€€€€€€€€¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‰I=9Q5QQI}e50ˆ°Í•±˜¹½‘•Ì ¤¤((€€€‘•˜Ñ•ÍÑ}µ¥ÍÍ¥¹}Í­¥±±}…¹‘}ÍÑ…±•}ÁÉ½µÁÑ}É•™•É•¹•}…É•}É•©•Ñ•¡Í•±˜¤€´ø9½¹”è(€€€€€€€Í­¥±°€ôÍ•±˜¹É•Á¼€¼€ˆ¹¥Ñ¡Õˆˆ€¼€‰Í­¥±±Ìˆ€¼€‰µ¥ÍÉ„µÉ¥Í¬µÉ•Ù¥•Üˆ€¼€‰M-%10¹µˆ(€€€€€€€Í­¥±°¹Õ¹±¥¹¬ ¤(€€€€€€€ÁÉ½µÁÐ€ôÍ•±˜¹É•Á¼€¼€ˆ¹¥Ñ¡Õˆˆ€¼€‰ÁÉ½µÁÑÌˆ€¼€‰µ¥ÍÉ„µÉ•Ù¥•Ü¹ÁÉ½µÁÐ¹µˆ(€€€€€€€ÁÉ½µÁÐ¹ÝÉ¥Ñ•}Ñ•áÐ (€€€€€€€€€€€ÁÉ½µÁÐ¹É•…‘}Ñ•áÐ¡•¹½‘¥¹œô‰ÕÑ˜´àˆ¤¹É•Á±…” (€€€€€€€€€€€€€€€€ˆ¸¸½Í­¥±±Ì½µ¥ÍÉ„µÉ¥Í¬µÉ•Ù¥•Ü½M-%10¹µˆ°(€€€€€€€€€€€€€€€€ˆ¸¸½Í­¥±±Ì½É•¹…µ•µÉ•Ù¥•Ü½M-%10¹µˆ°(€€€€€€€€€€€€¤°(€€€€€€€€€€€•¹½‘¥¹œô‰ÕÑ˜´àˆ°(€€€€€€€€€€€¹•Ý±¥¹”ô‰q¸ˆ°(€€€€€€€€¤(€€€€€€€½‘•Ì€ôÍ•±˜¹½‘•Ì ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‰M-%11}MPˆ°½‘•Ì¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‰AI=5AQ}M-%10ˆ°½‘•Ì¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‰1%9-}5%MM%9ˆ°½‘•Ì¤((€€€‘•˜Ñ•ÍÑ}µ¥ÍÍ¥¹}…¹…±åé•}‰Õ}ÁÉ½µÁÑ}¥Í}É•©•Ñ•¡Í•±˜¤€´ø9½¹”è(€€€€€€€ÁÉ½µÁÐ€ôÍ•±˜¹É•Á¼€¼€ˆ¹¥Ñ¡Õˆˆ€¼€‰ÁÉ½µÁÑÌˆ€¼€‰…¹…±åé”µ‰Õœ¹ÁÉ½µÁÐ¹µˆ(€€€€€€€ÁÉ½µÁÐ¹Õ¹±¥¹¬ ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‰AI=5AQ}MPˆ°Í•±˜¹½‘•Ì ¤¤((€€€‘•˜Ñ•ÍÑ}‰Õ}ÁÉ½µÁÑ}µÕÍÑ}É½ÕÑ•}Ñ½}‰Õ}É•Í½±Ù•È¡Í•±˜¤€´ø9½¹”è(€€€€€€€ÁÉ½µÁÐ€ôÍ•±˜¹É•Á¼€¼€ˆ¹¥Ñ¡Õˆˆ€¼€‰ÁÉ½µÁÑÌˆ€¼€‰…¹…±åé”µ‰Õœ¹ÁÉ½µÁÐ¹µˆ(€€€€€€€ÁÉ½µÁÐ¹ÝÉ¥Ñ•}Ñ•áÐ (€€€€€€€€€€€ÁÉ½µÁÐ¹É•…‘}Ñ•áÐ¡•¹½‘¥¹œô‰ÕÑ˜´àˆ¤¹É•Á±…” (€€€€€€€€€€€€€€€€‰…•¹Ðè	ÕI•Í½±Ù•Èˆ°(€€€€€€€€€€€€€€€€‰…•¹ÐèEÕ…±¥ÑåI•Ù¥•Ý•Èˆ°(€€€€€€€€€€€€¤°(€€€€€€€€€€€•¹½‘¥¹œô‰ÕÑ˜´àˆ°(€€€€€€€€€€€¹•Ý±¥¹”ô‰q¸ˆ°(€€€€€€€€¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‰AI=5AQ}9Pˆ°Í•±˜¹½‘•Ì ¤¤((€€€‘•˜Ñ•ÍÑ}µ¥ÍÍ¥¹}É•ÅÕ¥É•‘}Í­¥±±}ÍÉ¥ÁÑ}¥Í}É•©•Ñ•¡Í•±˜¤€´ø9½¹”è(€€€€€€€ÍÉ¥ÁÐ€ô€ (€€€€€€€€€€€Í•±˜¹É•Á¼(€€€€€€€€€€€€¼€ˆ¹¥Ñ¡Õˆˆ(€€€€€€€€€€€€¼€‰Í­¥±±Ìˆ(€€€€€€€€€€€€¼€‰µ¥ÍÉ„µÉ¥Í¬µÉ•Ù¥•Üˆ(€€€€€€€€€€€€¼€‰ÍÉ¥ÁÑÌˆ(€€€€€€€€€€€€¼€‰¹½Éµ…±¥é•}Í…É¥˜¹Áäˆ(€€€€€€€€¤(€€€€€€€ÍÉ¥ÁÐ¹Õ¹±¥¹¬ ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‰M-%11}MI%AQ}MPˆ°Í•±˜¹½‘•Ì ¤¤((€€€‘•˜Ñ•ÍÑ}±½}…¹…±åÍ¥Í}½ÕÑÁÕÑ}½¹ÑÉ…Ñ}¥Í}É•ÅÕ¥É•¡Í•±˜¤€´ø9½¹”è(€€€€€€€Í­¥±°€ô€ (€€€€€€€€€€€Í•±˜¹É•Á¼(€€€€€€€€€€€€¼€ˆ¹¥Ñ¡Õˆˆ(€€€€€€€€€€€€¼€‰Í­¥±±Ìˆ(€€€€€€€€€€€€¼€‰™¥ÉµÝ…É”µ±½œµ…¹…±åÍ¥Ìˆ(€€€€€€€€€€€€¼€‰M-%10¹µˆ(€€€€€€€€¤(€€€€€€€½É¥¥¹…°€ôÍ­¥±°¹É•…‘}Ñ•áÐ¡•¹½‘¥¹œô‰ÕÑ˜´àˆ¤(€€€€€€€™½Èµ…É­•È¥¸€ (€€€€€€€€€€€€‰U%}Me5AQ=5Lˆ°(€€€€€€€€€€€€‰=9%I5}%IQ%=8ˆ°(€€€€€€€€€€€€‰UÍ…”MåµÁÑ½´EÕ•ÍÑ¥½¹Ìˆ°(€€€€€€€€€€€€‰UÍ…”MåµÁÑ½´AÉ½™¥±”ˆ°(€€€€€€€€€€€€‰¥É•Ñ¥½¸½¹™¥Éµ…Ñ¥½¸ˆ°(€€€€€€€€€€€€‰%9Q%e}AI=	14ˆ°(€€€€€€€€€€€€‰Y%9}!,ˆ°(€€€€€€€€€€€€‰]%Q}Y%9ˆ°(€€€€€€€€€€€€‰9½Éµ…±¥é•Ù•¹ÑÌˆ°(€€€€€€€€¤è(€€€€€€€€€€€Ý¥Ñ Í•±˜¹ÍÕ‰Q•ÍÐ¡µ…É­•Èõµ…É­•È¤è(€€€€€€€€€€€€€€€Í­¥±°¹ÝÉ¥Ñ•}Ñ•áÐ (€€€€€€€€€€€€€€€€€€€½É¥¥¹…°¹É•Á±…”¡µ…É­•È°€‰I5=Y}IEU%I}	!Y%=Hˆ¤°(€€€€€€€€€€€€€€€€€€€•¹½‘¥¹œô‰ÕÑ˜´àˆ°(€€€€€€€€€€€€€€€€€€€¹•Ý±¥¹”ô‰q¸ˆ°(€€€€€€€€€€€€€€€€¤(€€€€€€€€€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‰M-%11}	=e}=9QIPˆ°Í•±˜¹½‘•Ì ¤¤(€€€€€€€Í­¥±°¹ÝÉ¥Ñ•}Ñ•áÐ¡½É¥¥¹…°°•¹½‘¥¹œô‰ÕÑ˜´àˆ°¹•Ý±¥¹”ô‰q¸ˆ¤((€€€‘•˜Ñ•ÍÑ}¥¹Ù…±¥‘}ÁÉ½©•Ñ}ÁÉ½™¥±•}¥Í}É•©•Ñ•¡Í•±˜¤€´ø9½¹”è(€€€€€€€Í¡ÕÑ¥°¹½Áå™¥±” (€€€€€€€€€€€%aQUIL€¼€‰¹•…Ñ¥Ù”ˆ€¼€‰¥¹Ù…±¥µÁÉ½™¥±”¹åµ°ˆ°(€€€€€€€€€€€Í•±˜¹É•Á¼€¼€ˆ¹¥Ñ¡Õˆˆ€¼€‰•µ‰•‘‘•µÁÉ½©•Ð¹åµ°ˆ°(€€€€€€€€¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‰AI=%1}M!5ˆ°Í•±˜¹½‘•Ì ¤¤((€€€‘•˜Ñ•ÍÑ}É±™}¥Í}É•©•Ñ•¡Í•±˜¤€´ø9½¹”è(€€€€€€€É•…‘µ”€ôÍ•±˜¹É•Á¼€¼€‰I5¹µˆ(€€€€€€€Ñ•áÐ€ôÉ•…‘µ”¹É•…‘}Ñ•áÐ¡•¹½‘¥¹œô‰ÕÑ˜´àˆ¤(€€€€€€€É•…‘µ”¹ÝÉ¥Ñ•}‰åÑ•Ì¡Ñ•áÐ¹É•Á±…” ‰qÉq¸ˆ°€‰q¸ˆ¤¹É•Á±…” ‰q¸ˆ°€‰qÉq¸ˆ¤¹•¹½‘” ‰ÕÑ˜´àˆ¤¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‰QaQ}1ˆ°Í•±˜¹½‘•Ì ¤¤((€€€‘•˜Ñ•ÍÑ}µ¥ÍÍ¥¹}‰¥±¥¹Õ…±}Í•Ñ¥½¹}¥Í}É•©•Ñ•¡Í•±˜¤€´ø9½¹”è(€€€€€€€Í•±˜¹¥¹ÍÑ…±±}¹•…Ñ¥Ù•}µ…É­‘½Ý¸ ‰‰É½­•¸µ‰¥±¥¹Õ…°¹µˆ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‰	%1%9U1}MQ%=9Lˆ°Í•±˜¹½‘•Ì ¤¤((€€€‘•˜Ñ•ÍÑ}ÁÉ½©•Ñ}µ…É­‘½Ý¹}É•ÅÕ¥É•Í}‰¥±¥¹Õ…±}Í•Ñ¥½¹Ì¡Í•±˜¤€´ø9½¹”è(€€€€€€€Í¡ÕÑ¥°¹½Áå™¥±” (€€€€€€€€€€€%aQUIL€¼€‰¹•…Ñ¥Ù”ˆ€¼€‰‰É½­•¸µ‰¥±¥¹Õ…°¹µˆ°(€€€€€€€€€€€Í•±˜¹É•Á¼€¼€ˆ¹ÁÉ½©•Ðˆ€¼€‰ÉÕ±•Ìˆ€¼€‰‰É½­•¸µ‰¥±¥¹Õ…°¹µˆ°(€€€€€€€€¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‰	%1%9U1}MQ%=9Lˆ°Í•±˜¹½‘•Ì ¤¤((€€€‘•˜Ñ•ÍÑ}Õ¹É•Í½±Ù•‘}Ñ½‘½}Íå¹}¥¹}ÁÉ½Í•}¥Í}É•©•Ñ•¡Í•±˜¤€´ø9½¹”è(€€€€€€€Í•±˜¹¥¹ÍÑ…±±}¹•…Ñ¥Ù•}µ…É­‘½Ý¸ ‰Ñ½‘¼µÍå¹Œ¹µˆ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‰Q==}Me9ˆ°Í•±˜¹½‘•Ì ¤¤((€€€‘•˜Ñ•ÍÑ}‰É½­•¹}±½…±}µ…É­‘½Ý¹}±¥¹­}¥Í}É•©•Ñ•¡Í•±˜¤€´ø9½¹”è(€€€€€€€Í•±˜¹¥¹ÍÑ…±±}¹•…Ñ¥Ù•}µ…É­‘½Ý¸ ‰‰É½­•¸µ±¥¹¬¹µˆ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‰1%9-}5%MM%9ˆ°Í•±˜¹½‘•Ì ¤¤((€€€‘•˜Ñ•ÍÑ}Ù…±¥‘}±½…±}µ…É­‘½Ý¹}…¹¡½ÉÍ}…É•}…•ÁÑ•¡Í•±˜¤€´ø9½¹”è(€€€€€€€‘½Ì€ôÍ•±˜¹É•Á¼€¼€‰‘½Ìˆ(€€€€€€€Í¡ÕÑ¥°¹½Áå™¥±” (€€€€€€€€€€€%aQUIL€¼€‰µ…É­‘½Ý¸ˆ€¼€‰…¹¡½ÈµÑ…É•Ð¹µˆ°(€€€€€€€€€€€‘½Ì€¼€‰…¹¡½ÈµÑ…É•Ð¹µˆ°(€€€€€€€€¤(€€€€€€€Í¡ÕÑ¥°¹½Áå™¥±” (€€€€€€€€€€€%aQUIL€¼€‰µ…É­‘½Ý¸ˆ€¼€‰…¹¡½Èµ±¥¹­ÌµÙ…±¥¹µˆ°(€€€€€€€€€€€‘½Ì€¼€‰…¹¡½Èµ±¥¹­ÌµÙ…±¥¹µˆ°(€€€€€€€€¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑÅÕ…°¡mt°Í•±˜¹‘¥…¹½ÍÑ¥Ì ¤¤((€€€‘•˜Ñ•ÍÑ}µ¥ÍÍ¥¹}±½…±}µ…É­‘½Ý¹}…¹¡½É}¥Í}É•©•Ñ•¡Í•±˜¤€´ø9½¹”è(€€€€€€€‘½Ì€ôÍ•±˜¹É•Á¼€¼€‰‘½Ìˆ(€€€€€€€Í¡ÕÑ¥°¹½Áå™¥±” (€€€€€€€€€€€%aQUIL€¼€‰µ…É­‘½Ý¸ˆ€¼€‰…¹¡½ÈµÑ…É•Ð¹µˆ°(€€€€€€€€€€€‘½Ì€¼€‰…¹¡½ÈµÑ…É•Ð¹µˆ°(€€€€€€€€¤(€€€€€€€Í•±˜¹¥¹ÍÑ…±±}¹•…Ñ¥Ù•}µ…É­‘½Ý¸ ‰‰É½­•¸µ…¹¡½È¹µˆ¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ%¸ ‰1%9-}9!=I}5%MM%9ˆ°Í•±˜¹½‘•Ì ¤¤((€€€‘•˜Ñ•ÍÑ}‘½Õµ•¹Ñ•‘}Ñ½‘½}Íå¹}¥¹Í¥‘•}½‘•}¥Í}…±±½Ý•¡Í•±˜¤€´ø9½¹”è(€€€€€€€É•…‘µ”€ôÍ•±˜¹É•Á¼€¼€‰I5¹µˆ(€€€€€€€É•…‘µ”¹ÝÉ¥Ñ•}Ñ•áÐ (€€€€€€€€€€€É•…‘µ”¹É•…‘}Ñ•áÐ¡•¹½‘¥¹œô‰ÕÑ˜´àˆ¤(€€€€€€€€€€€€¬€‰q¸ð„´´Q¡”Á½±¥äÑ½­•¸¥Ì¥¹Ñ•¹Ñ¥½¹…±±äÅÕ½Ñ•èQ=<¡Íå¹Œ¥€¸€´´ùq¸ˆ°(€€€€€€€€€€€•¹½‘¥¹œô‰ÕÑ˜´àˆ°(€€€€€€€€€€€¹•Ý±¥¹”ô‰q¸ˆ°(€€€€€€€€¤(€€€€€€€Í•±˜¹…ÍÍ•ÉÑ9½Ñ%¸ ‰Q==}Me9ˆ°Í•±˜¹½‘•Ì ¤¤(()¥˜}}¹…µ•}|€ôô€‰}}µ…¥¹}|ˆè(€€€Õ¹¥ÑÑ•ÍÐ¹µ…¥¸ ¤(