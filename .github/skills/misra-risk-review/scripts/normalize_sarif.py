#!/usr/bin/env python3
"""Normalize SARIF results into the shared high-signal finding shape."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


EXIT_OK = 0
EXIT_INPUT = 2
LEVEL_TO_SEVERITY = {"error": "MAJOR", "warning": "MINOR", "note": "MINOR", "none": "MINOR"}


class InputError(ValueError):
    """Raised when SARIF input is not usable."""


def load_sarif(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise InputError(f"cannot read SARIF {path}: {error}") from error
    if not isinstance(data, dict) or data.get("version") != "2.1.0":
        raise InputError("SARIF version must be 2.1.0")
    if not isinstance(data.get("runs"), list):
        raise InputError("SARIF runs must be a list")
    return data


def normalize(data: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    tools: list[str] = []
    for run_index, run in enumerate(data["runs"]):
        if not isinstance(run, dict):
            raise InputError(f"runs[{run_index}] must be an object")
        driver = run.get("tool", {}).get("driver", {}) if isinstance(run.get("tool"), dict) else {}
        tool_name = driver.get("name") if isinstance(driver, dict) else None
        if not isinstance(tool_name, str) or not tool_name.strip():
            raise InputError(f"runs[{run_index}].tool.driver.name is required")
        tools.append(tool_name)
        results = run.get("results")
        if not isinstance(results, list):
            raise InputError(f"runs[{run_index}].results must be a list")
        for result_index, result in enumerate(results):
            if not isinstance(result, dict):
                raise InputError(f"runs[{run_index}].results[{result_index}] must be an object")
            message = result.get("message")
            if not isinstance(message, dict):
                raise InputError(f"result {run_index}:{result_index} message is required")
            message_text = message.get("text") or message.get("markdown")
            if not isinstance(message_text, str) or not message_text.strip():
                raise InputError(f"result {run_index}:{result_index} message text is required")
            level = result.get("level", "warning")
            if level not in LEVEL_TO_SEVERITY:
                level = "warning"
            uri = None
            line = None
            locations = result.get("locations", [])
            if locations:
                if not isinstance(locations, list) or not isinstance(locations[0], dict):
                    raise InputError(f"result {run_index}:{result_index} locations are invalid")
                physical = locations[0].get("physicalLocation", {})
                if isinstance(physical, dict):
                    artifact = physical.get("artifactLocation", {})
                    region = physical.get("region", {})
                    if isinstance(artifact, dict):
                        uri = artifact.get("uri")
                    if isinstance(region, dict):
                        line = region.get("startLine")
            rule_id = result.get("ruleId")
            if rule_id is not None and not isinstance(rule_id, str):
                raise InputError(f"result {run_index}:{result_index} ruleId must be a string")
            fingerprints = result.get("partialFingerprints", {})
            if not isinstance(fingerprints, dict):
                raise InputError(f"result {run_index}:{result_index} fingerprints must be an object")
            findings.append(
                {
                    "severity": LEVEL_TO_SEVERITY[level],
                    "dimension": "Standards",
                    "location": {"uri": uri, "line": line},
                    "evidence": {
                        "tool": tool_name,
                        "sarif_level": level,
                        "rule_id": rule_id,
                        "fingerprints": fingerprints,
                        "run_index": run_index,
                        "result_index": result_index,
                    },
                    "rationale": message_text.strip(),
                    "recommendation": "Review the original tool result and project deviation policy.",
                    "confidence": "MEDIUM",
                    "risk_category": "UNCLASSIFIED" if rule_id is None else None,
                }
            )
    return {
        "status": "COMPLETE",
        "compliance_claim": False,
        "tools": sorted(set(tools)),
        "finding_count": len(findings),
        "findings": findings,
    }


def emit(result: dict[str, Any], output: Path | None) -> None:
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if output is None:
        sys.stdout.write(text)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        emit(normalize(load_sarif(args.input.resolve())), args.output.resolve() if args.output else None)
        return EXIT_OK
    except InputError as error:
        emit({"status": "FAILED", "error": str(error)}, args.output)
        return EXIT_INPUT


if __name__ == "__main__":
    raise SystemExit(main())
