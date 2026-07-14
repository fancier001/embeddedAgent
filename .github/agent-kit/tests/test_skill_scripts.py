from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


AGENT_KIT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = AGENT_KIT_ROOT.parents[1]
SKILLS = PROJECT_ROOT / ".github" / "skills"
SARIF_FIXTURES = AGENT_KIT_ROOT / "tests" / "fixtures" / "sarif"


def run_script(
    path: Path,
    *arguments: str,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    process_environment = os.environ.copy()
    process_environment.update(environment or {})
    return subprocess.run(
        [sys.executable, str(path), *arguments],
        check=False,
        env=process_environment,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


class SkillScriptTests(unittest.TestCase):
    def test_traceability_example_is_complete(self) -> None:
        script = SKILLS / "embedded-application-development" / "scripts" / "validate_traceability.py"
        matrix = PROJECT_ROOT / "examples" / "minimal-firmware" / "requirements" / "network-reconnect.yml"
        completed = run_script(script, "--input", str(matrix), "--root", str(PROJECT_ROOT))
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual("COMPLETE", result["status"])
        self.assertEqual(3, result["counts"]["covered"])

    def test_traceability_partial_returns_insufficient_evidence(self) -> None:
        source = PROJECT_ROOT / "examples" / "minimal-firmware" / "requirements" / "network-reconnect.yml"
        data = yaml.safe_load(source.read_text(encoding="utf-8"))
        data["requirements"][0]["status"] = "partial"
        with tempfile.TemporaryDirectory() as directory:
            matrix = Path(directory) / "partial.yml"
            matrix.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8", newline="\n")
            script = SKILLS / "embedded-application-development" / "scripts" / "validate_traceability.py"
            completed = run_script(script, "--input", str(matrix), "--root", str(PROJECT_ROOT))
        self.assertEqual(3, completed.returncode)
        self.assertEqual("INSUFFICIENT_EVIDENCE", json.loads(completed.stdout)["status"])

    def test_traceability_stdout_remains_utf8_with_legacy_console_encoding(self) -> None:
        script = SKILLS / "embedded-application-development" / "scripts" / "validate_traceability.py"
        matrix = PROJECT_ROOT / "examples" / "minimal-firmware" / "requirements" / "network-reconnect.yml"
        completed = run_script(
            script,
            "--input",
            str(matrix),
            "--root",
            str(PROJECT_ROOT),
            environment={"PYTHONIOENCODING": "cp1252"},
        )
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual("COMPLETE", result["status"])
        self.assertTrue(any(item["statement_cn"] for item in result["requirements"]))

    def test_profile_plan_never_executes_or_includes_hardware(self) -> None:
        script = SKILLS / "embedded-change-verification" / "scripts" / "profile_gates.py"
        profile = PROJECT_ROOT / ".github" / "embedded-project.yml"
        completed = run_script(script, "plan", "--profile", str(profile))
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        result = json.loads(completed.stdout)
        self.assertFalse(result["executes_commands"])
        self.assertEqual({"configure", "build", "test", "static_analysis"}, {gate["name"] for gate in result["gates"]})
        self.assertEqual({"flash", "erase", "fuse", "reset", "hil"}, {gate["name"] for gate in result["excluded_hardware"]})

    def test_profile_report_requires_pass_evidence(self) -> None:
        profile_data = yaml.safe_load(
            (PROJECT_ROOT / ".github" / "embedded-project.yml").read_text(encoding="utf-8")
        )
        profile_data["commands"]["build"] = "cmake --build build"
        report = {
            "gates": [
                {"name": name, "command": profile_data["commands"][name], "status": "PASS" if name == "build" else "NOT_RUN", "exit_code": 0 if name == "build" else None, "evidence": [], "reason": None if name == "build" else "profile value is auto"}
                for name in ("configure", "build", "test", "static_analysis")
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = root / "profile.yml"
            report_path = root / "report.json"
            profile.write_text(yaml.safe_dump(profile_data, allow_unicode=True), encoding="utf-8", newline="\n")
            report_path.write_text(json.dumps(report), encoding="utf-8", newline="\n")
            script = SKILLS / "embedded-change-verification" / "scripts" / "profile_gates.py"
            completed = run_script(script, "validate-report", "--profile", str(profile), "--input", str(report_path))
        self.assertEqual(3, completed.returncode)
        self.assertIn("PASS requires exit_code 0 and evidence", completed.stdout)

    def test_profile_report_rejects_hardware_gate(self) -> None:
        profile = PROJECT_ROOT / ".github" / "embedded-project.yml"
        report = {
            "gates": [
                {
                    "name": "flash",
                    "command": "program-device",
                    "status": "PASS",
                    "exit_code": 0,
                    "evidence": ["must never be accepted"],
                }
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "report.json"
            report_path.write_text(json.dumps(report), encoding="utf-8", newline="\n")
            script = SKILLS / "embedded-change-verification" / "scripts" / "profile_gates.py"
            completed = run_script(
                script,
                "validate-report",
                "--profile",
                str(profile),
                "--input",
                str(report_path),
            )
        self.assertEqual(2, completed.returncode)
        self.assertIn("forbidden or unknown gate", completed.stdout)

    def test_sarif_normalization_preserves_tool_evidence(self) -> None:
        script = SKILLS / "misra-risk-review" / "scripts" / "normalize_sarif.py"
        completed = run_script(script, "--input", str(SARIF_FIXTURES / "valid.sarif"))
        self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
        finding = json.loads(completed.stdout)["findings"][0]
        self.assertEqual("C-RISK-001", finding["evidence"]["rule_id"])
        self.assertEqual("src/example.c", finding["location"]["uri"])
        self.assertFalse(json.loads(completed.stdout)["compliance_claim"])

    def test_sarif_missing_required_message_is_rejected(self) -> None:
        script = SKILLS / "misra-risk-review" / "scripts" / "normalize_sarif.py"
        completed = run_script(script, "--input", str(SARIF_FIXTURES / "missing-message.sarif"))
        self.assertEqual(2, completed.returncode)

    def test_sarif_unknown_rule_is_not_invented(self) -> None:
        script = SKILLS / "misra-risk-review" / "scripts" / "normalize_sarif.py"
        completed = run_script(script, "--input", str(SARIF_FIXTURES / "unknown-rule.sarif"))
        self.assertEqual(0, completed.returncode)
        finding = json.loads(completed.stdout)["findings"][0]
        self.assertIsNone(finding["evidence"]["rule_id"])
        self.assertEqual("UNCLASSIFIED", finding["risk_category"])

    def test_artifact_mismatch_stops_before_symbolization(self) -> None:
        script = SKILLS / "firmware-log-analysis" / "scripts" / "artifact_evidence.py"
        specification = importlib.util.spec_from_file_location("artifact_evidence", script)
        self.assertIsNotNone(specification)
        module = importlib.util.module_from_spec(specification)
        assert specification is not None and specification.loader is not None
        specification.loader.exec_module(module)
        identity = {
            "artifact": "firmware.elf",
            "build_id": "abcdef",
            "elf_sha256": "0" * 64,
            "symbol": "handler",
            "symbol_address": "0x1000",
        }
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "mismatch.log"
            log.write_text(
                "artifact=other.elf\nbuild_id=123456\nsymbol=handler\npc=0x1000\nevidence=test\n",
                encoding="utf-8",
                newline="\n",
            )
            _, gaps = module.match_log(identity, log)
        self.assertTrue(any("artifact mismatch" in gap for gap in gaps))
        self.assertTrue(any("build ID mismatch" in gap for gap in gaps))


if __name__ == "__main__":
    unittest.main()
