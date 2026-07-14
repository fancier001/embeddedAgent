#!/usr/bin/env python3
"""Validate an embedded application requirement traceability matrix."""

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
STATUSES = {"covered", "partial", "missing", "not-applicable"}


class InputError(ValueError):
    """Raised when the matrix is malformed."""


def nonempty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InputError(f"{field} must be a non-empty string")
    return value.strip()


def load_matrix(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise InputError(f"cannot read matrix {path}: {error}") from error
    if not isinstance(data, dict):
        raise InputError("matrix root must be a mapping")
    if data.get("schema_version") != 1:
        raise InputError("schema_version must be 1")
    nonempty(data.get("feature"), "feature")
    requirements = data.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        raise InputError("requirements must be a non-empty list")
    return data


def resolve_repo_path(root: Path, raw: str, field: str) -> Path:
    candidate = (root / raw).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise InputError(f"{field} leaves repository: {raw}") from error
    return candidate


def validate_matrix(data: dict[str, Any], root: Path) -> tuple[dict[str, Any], int]:
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    evidence_gaps: list[str] = []

    for index, raw in enumerate(data["requirements"]):
        prefix = f"requirements[{index}]"
        if not isinstance(raw, dict):
            raise InputError(f"{prefix} must be a mapping")
        requirement_id = nonempty(raw.get("id"), f"{prefix}.id")
        if requirement_id in seen:
            raise InputError(f"duplicate requirement id: {requirement_id}")
        seen.add(requirement_id)
        statement_cn = nonempty(raw.get("statement_cn"), f"{prefix}.statement_cn")
        statement_en = nonempty(raw.get("statement_en"), f"{prefix}.statement_en")
        status = raw.get("status")
        if status not in STATUSES:
            raise InputError(
                f"{prefix}.status must be one of: {', '.join(sorted(STATUSES))}"
            )

        implementations = raw.get("implementation", [])
        tests = raw.get("tests", [])
        evidence = raw.get("evidence", [])
        if not isinstance(implementations, list) or not isinstance(tests, list):
            raise InputError(f"{prefix}.implementation and .tests must be lists")
        if not isinstance(evidence, list):
            raise InputError(f"{prefix}.evidence must be a list")

        normalized_implementation: list[dict[str, str]] = []
        for item_index, item in enumerate(implementations):
            if not isinstance(item, dict):
                raise InputError(f"{prefix}.implementation[{item_index}] must be a mapping")
            raw_path = nonempty(item.get("path"), f"{prefix}.implementation[{item_index}].path")
            symbol = nonempty(item.get("symbol"), f"{prefix}.implementation[{item_index}].symbol")
            resolved = resolve_repo_path(root, raw_path, f"{prefix}.implementation[{item_index}].path")
            if not resolved.is_file():
                evidence_gaps.append(f"{requirement_id}: implementation path missing: {raw_path}")
            normalized_implementation.append({"path": raw_path, "symbol": symbol})

        normalized_tests: list[dict[str, str]] = []
        for test_index, item in enumerate(tests):
            if not isinstance(item, dict):
                raise InputError(f"{prefix}.tests[{test_index}] must be a mapping")
            normalized_tests.append(
                {
                    "name": nonempty(item.get("name"), f"{prefix}.tests[{test_index}].name"),
                    "command": nonempty(item.get("command"), f"{prefix}.tests[{test_index}].command"),
                }
            )

        normalized_evidence = [
            nonempty(item, f"{prefix}.evidence[{evidence_index}]")
            for evidence_index, item in enumerate(evidence)
        ]
        if status == "covered" and (
            not normalized_implementation or not normalized_tests or not normalized_evidence
        ):
            evidence_gaps.append(
                f"{requirement_id}: covered requires implementation, tests, and evidence"
            )
        elif status in {"partial", "missing"}:
            evidence_gaps.append(f"{requirement_id}: status is {status}")
        elif status == "not-applicable" and not normalized_evidence:
            evidence_gaps.append(f"{requirement_id}: not-applicable requires rationale evidence")

        normalized.append(
            {
                "id": requirement_id,
                "statement_cn": statement_cn,
                "statement_en": statement_en,
                "implementation": normalized_implementation,
                "tests": normalized_tests,
                "evidence": normalized_evidence,
                "status": status,
            }
        )

    counts = {status: 0 for status in sorted(STATUSES)}
    for item in normalized:
        counts[item["status"]] += 1
    exit_code = EXIT_OK if not evidence_gaps else EXIT_INSUFFICIENT_EVIDENCE
    result = {
        "status": "COMPLETE" if exit_code == EXIT_OK else "INSUFFICIENT_EVIDENCE",
        "feature": data["feature"],
        "counts": counts,
        "requirements": normalized,
        "evidence_gaps": evidence_gaps,
    }
    return result, exit_code


def emit(result: dict[str, Any], output: Path | None) -> None:
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if output is None:
        sys.stdout.buffer.write(text.encode("utf-8"))
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        data = load_matrix(args.input.resolve())
        result, exit_code = validate_matrix(data, args.root.resolve())
        emit(result, args.output.resolve() if args.output else None)
        return exit_code
    except InputError as error:
        emit({"status": "FAILED", "error": str(error)}, args.output)
        return EXIT_INPUT


if __name__ == "__main__":
    raise SystemExit(main())
