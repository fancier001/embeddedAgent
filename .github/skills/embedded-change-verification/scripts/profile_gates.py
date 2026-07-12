#!/usr/bin/env python3
"""Plan safe host gates and validate their evidence report without executing commands."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml


EXIT_OK = 0
EXIT_INPUT = 2
EXIT_INSUFFICIENT_EVIDENCE = 3
HOST_GATES = ("configure", "build", "test", "static_analysis")
REPORT_STATUSES = {"PASS", "FAIL", "BLOCKED", "NOT_RUN"}


class InputError(ValueError):
    """Raised for invalid profile or report data."""


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise InputError(f"cannot read profile {path}: {error}") from error
    if not isinstance(data, dict) or not isinstance(data.get("commands"), dict):
        raise InputError("profile commands must be a mapping")
    return data


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise InputError(f"cannot read report {path}: {error}") from error
    if not isinstance(data, dict):
        raise InputError("report root must be an object")
    return data


def plan(profile: dict[str, Any]) -> dict[str, Any]:
    commands = profile["commands"]
    gates: list[dict[str, Any]] = []
    for name in HOST_GATES:
        command = commands.get(name, "auto")
        if not isinstance(command, str) or not command.strip():
            raise InputError(f"commands.{name} must be a non-empty string")
        configured = command != "auto"
        gates.append(
            {
                "name": name,
                "command": command,
                "status": "PLANNED" if configured else "NOT_RUN",
                "reason": None if configured else "profile value is auto",
            }
        )
    hardware = commands.get("hardware", {})
    if not isinstance(hardware, dict):
        raise InputError("commands.hardware must be a mapping")
    return {
        "status": "COMPLETE",
        "executes_commands": False,
        "gates": gates,
        "excluded_hardware": [
            {"name": name, "status": "FORBIDDEN", "reason": "physical hardware gate"}
            for name in sorted(hardware)
        ],
    }


def validate_report(profile: dict[str, Any], report: dict[str, Any]) -> tuple[dict[str, Any], int]:
    raw_gates = report.get("gates")
    if not isinstance(raw_gates, list):
        raise InputError("report.gates must be a list")
    by_name: dict[str, dict[str, Any]] = {}
    gaps: list[str] = []
    for index, gate in enumerate(raw_gates):
        if not isinstance(gate, dict):
            raise InputError(f"report.gates[{index}] must be an object")
        name = gate.get("name")
        if name not in HOST_GATES:
            raise InputError(f"report contains forbidden or unknown gate: {name!r}")
        if name in by_name:
            raise InputError(f"duplicate gate: {name}")
        status = gate.get("status")
        if status not in REPORT_STATUSES:
            raise InputError(f"gate {name} has invalid status: {status!r}")
        command = gate.get("command")
        expected_command = profile["commands"].get(name, "auto")
        if command != expected_command:
            raise InputError(f"gate {name} command does not match the project profile")
        evidence = gate.get("evidence", [])
        if not isinstance(evidence, list) or any(
            not isinstance(item, str) or not item.strip() for item in evidence
        ):
            raise InputError(f"gate {name} evidence must be a string list")
        exit_code = gate.get("exit_code")
        reason = gate.get("reason")
        if status == "PASS" and (exit_code != 0 or not evidence):
            gaps.append(f"{name}: PASS requires exit_code 0 and evidence")
        if status == "FAIL" and (not isinstance(exit_code, int) or exit_code == 0):
            gaps.append(f"{name}: FAIL requires a non-zero integer exit_code")
        if status in {"BLOCKED", "NOT_RUN"} and (
            not isinstance(reason, str) or not reason.strip()
        ):
            gaps.append(f"{name}: {status} requires a reason")
        if expected_command == "auto" and status != "NOT_RUN":
            gaps.append(f"{name}: profile value auto must be NOT_RUN")
        if expected_command != "auto" and status != "PASS":
            gaps.append(f"{name}: configured required gate is {status}")
        by_name[name] = gate

    for name in HOST_GATES:
        if name not in by_name:
            gaps.append(f"{name}: gate missing from report")
    exit_code = EXIT_OK if not gaps else EXIT_INSUFFICIENT_EVIDENCE
    return {
        "status": "COMPLETE" if exit_code == EXIT_OK else "INSUFFICIENT_EVIDENCE",
        "gates": [by_name[name] for name in HOST_GATES if name in by_name],
        "evidence_gaps": gaps,
        "executes_commands": False,
    }, exit_code


def emit(result: dict[str, Any], output: Path | None) -> None:
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if output is None:
        sys.stdout.write(text)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)
    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("--profile", required=True, type=Path)
    plan_parser.add_argument("--output", type=Path)
    report_parser = subparsers.add_parser("validate-report")
    report_parser.add_argument("--profile", required=True, type=Path)
    report_parser.add_argument("--input", required=True, type=Path)
    report_parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        profile = load_yaml(args.profile.resolve())
        if args.mode == "plan":
            result, exit_code = plan(profile), EXIT_OK
        else:
            result, exit_code = validate_report(profile, load_json(args.input.resolve()))
        emit(result, args.output.resolve() if args.output else None)
        return exit_code
    except InputError as error:
        emit({"status": "FAILED", "error": str(error)}, args.output)
        return EXIT_INPUT


if __name__ == "__main__":
    raise SystemExit(main())
