#!/usr/bin/env python3
"""Resolve project rules and perform read-only commit/push policy preflight."""

from __future__ import annotations

import argparse
import copy
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit

try:
    import yaml
except ImportError as exc:  # pragma: no cover - exercised by CLI environments
    print(
        "Missing validation dependency PyYAML. Run "
        "'python -m pip install -r tests/agent-kit/requirements.txt'.",
        file=sys.stderr,
    )
    raise SystemExit(2) from exc


EXIT_INPUT = 2
EXIT_BLOCKED = 3
EXIT_EXTERNAL = 4
DECISION_AUTO_UPLOAD = "AUTO_COMMIT_AND_PUSH"
DECISION_CONFIRM_AUTO_CONTENT = "CONFIRM_COMMIT_CONTENT"
DECISION_MESSAGE_ONLY = "OUTPUT_COMMIT_MESSAGE"
DECISION_NO_DELIVERY = "NO_DELIVERY"
PROJECT_POLICY_REQUIRED = "PROJECT_POLICY_REQUIRED"
FORBIDDEN_PUSH_KEYS = frozenset(
    {"remote", "url", "push_url", "pushurl", "target_branch", "target_ref"}
)
SUBJECT_PATTERN = re.compile(r"^<([^<>]+)><([^<>]+)>:\s+(.+?)$")
FIELD_PATTERN = re.compile(r"^<([^<>]+)>:\s?(.*)$")
PLACEHOLDER_PATTERN = re.compile(r"<[^<>]+>")
TEST_MARKER = "<<<Test Notes>>>"
PRE_JIRA_FIELDS = ("Change Type", "Change Reason", "Root Cause", "Solution")
POST_JIRA_FIELDS = (
    "AI-Tool-Used",
    "AI-Tool-Scenario",
    "AI-Tool-Detail",
    "Affected Function Name",
    "Applicable Project",
    "RN",
    "RN description",
    TEST_MARKER,
    "Test-Proposal",
    "Stress-Test",
    "HW-Test",
)
TEMPLATE_FIELD_ORDER = (*PRE_JIRA_FIELDS, "Jira ID", *POST_JIRA_FIELDS)
TEMPLATE_AI_DEFAULTS = (
    "<AI-Tool-Used>: N",
    "<AI-Tool-Scenario>: /",
    "<AI-Tool-Detail>: /",
)


class PolicyInputError(ValueError):
    """Raised for malformed policy input or unsafe references."""


class GitReadError(RuntimeError):
    """Raised when repository-local Git evidence cannot be read."""


@dataclass(frozen=True)
class ParsedField:
    name: str
    value: str
    details: tuple[str, ...]
    line: int

    @property
    def detail_text(self) -> str:
        return "\n".join(part for part in (self.value, *self.details) if part).strip()


def _json_result(status: str, **items: Any) -> dict[str, Any]:
    return {"status": status, **items}


def _project_policy_required(operation: str) -> dict[str, Any]:
    message = (
        ".project/project.yml and its referenced Git delivery policy are required "
        f"for {operation}; Git delivery is fail-closed"
    )
    return _json_result(
        "BLOCKED",
        code=PROJECT_POLICY_REQUIRED,
        reasons=[message],
        errors=[
            {
                "code": PROJECT_POLICY_REQUIRED,
                "line": 1,
                "message": message,
            }
        ],
    )


def _normalized_root(root: Path | str) -> Path:
    candidate = Path(root).resolve()
    if not candidate.is_dir():
        raise PolicyInputError(f"repository root is not a directory: {candidate}")
    return candidate


def _repository_path(value: str) -> str:
    normalized = value.strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if (
        not normalized
        or normalized.startswith(("/", "\\"))
        or "\\" in normalized
        or re.match(r"^[A-Za-z]:", normalized)
        or any(part in ("", ".", "..") for part in normalized.split("/"))
    ):
        raise PolicyInputError(
            f"path must be repository-relative and use '/': {value!r}"
        )
    return normalized


def _project_file(project_dir: Path, reference: str) -> Path:
    if not isinstance(reference, str) or not reference or "\\" in reference:
        raise PolicyInputError(f"invalid .project reference: {reference!r}")
    candidate = (project_dir / reference).resolve()
    try:
        candidate.relative_to(project_dir.resolve())
    except ValueError as exc:
        raise PolicyInputError(f"reference leaves .project: {reference}") from exc
    return candidate


def _matches(path: str, pattern: str) -> bool:
    path_parts = tuple(path.split("/"))
    pattern_parts = tuple(pattern.split("/"))

    @lru_cache(maxsize=None)
    def visit(pattern_index: int, path_index: int) -> bool:
        if pattern_index == len(pattern_parts):
            return path_index == len(path_parts)
        segment = pattern_parts[pattern_index]
        if segment == "**":
            return visit(pattern_index + 1, path_index) or (
                path_index < len(path_parts) and visit(pattern_index, path_index + 1)
            )
        return (
            path_index < len(path_parts)
            and fnmatch.fnmatchcase(path_parts[path_index], segment)
            and visit(pattern_index + 1, path_index + 1)
        )

    return visit(0, 0)


def _yaml_mapping(path: Path) -> Mapping[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise PolicyInputError(f"cannot read YAML {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise PolicyInputError(f"YAML must be a mapping: {path}")
    return data


def _mapping_keys(
    value: Any,
    *,
    label: str,
    required: set[str],
    allowed: set[str],
) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise PolicyInputError(f"{label} must be a mapping")
    missing = sorted(required - set(value))
    unknown = sorted(set(value) - allowed)
    if missing:
        raise PolicyInputError(f"{label} is missing: {', '.join(missing)}")
    if unknown:
        raise PolicyInputError(f"{label} contains unknown fields: {', '.join(unknown)}")
    return value


def _string_list(value: Any, *, label: str, allow_empty: bool = False) -> list[str]:
    if (
        not isinstance(value, list)
        or (not value and not allow_empty)
        or not all(isinstance(item, str) and item for item in value)
    ):
        qualifier = "" if allow_empty else "non-empty "
        raise PolicyInputError(f"{label} must be a {qualifier}string list")
    return value


def _validate_manifest(manifest: Mapping[str, Any]) -> None:
    _mapping_keys(
        manifest,
        label="project manifest",
        required={"schema_version", "project", "rules", "git_policy", "extensions"},
        allowed={"schema_version", "project", "rules", "git_policy", "extensions"},
    )
    if manifest.get("schema_version") != 1:
        raise PolicyInputError("project manifest schema_version must be 1")
    project = _mapping_keys(
        manifest.get("project"),
        label="project manifest project",
        required={"primary", "aliases"},
        allowed={"primary", "aliases"},
    )
    if not isinstance(project.get("primary"), str) or not project["primary"]:
        raise PolicyInputError("project.primary must be a non-empty string")
    aliases = _string_list(
        project.get("aliases"), label="project.aliases", allow_empty=True
    )
    if len(aliases) != len(set(aliases)):
        raise PolicyInputError("project.aliases must be unique")
    if not isinstance(manifest.get("rules"), list):
        raise PolicyInputError("project manifest rules must be a list")
    seen_ids: set[str] = set()
    for index, raw_rule in enumerate(manifest["rules"]):
        rule = _mapping_keys(
            raw_rule,
            label=f"rules[{index}]",
            required={"id", "path", "applies_to", "required"},
            allowed={"id", "path", "applies_to", "required"},
        )
        if not isinstance(rule.get("id"), str) or not rule["id"]:
            raise PolicyInputError(f"rules[{index}].id must be a non-empty string")
        if rule["id"] in seen_ids:
            raise PolicyInputError(f"duplicate rule id: {rule['id']}")
        seen_ids.add(rule["id"])
        if not isinstance(rule.get("path"), str):
            raise PolicyInputError(f"rules[{index}].path must be a string")
        _string_list(rule.get("applies_to"), label=f"rules[{index}].applies_to")
        if not isinstance(rule.get("required"), bool):
            raise PolicyInputError(f"rules[{index}].required must be boolean")
    if not isinstance(manifest.get("git_policy"), str):
        raise PolicyInputError("project manifest git_policy must be a path")
    if not isinstance(manifest.get("extensions"), dict):
        raise PolicyInputError("project manifest extensions must be a mapping")


def load_manifest(root: Path | str) -> tuple[Path, Mapping[str, Any]] | None:
    root_path = _normalized_root(root)
    project_dir = root_path / ".project"
    if not project_dir.exists():
        return None
    if not project_dir.is_dir():
        raise PolicyInputError(".project exists but is not a directory")
    manifest_path = project_dir / "project.yml"
    if not manifest_path.is_file():
        raise PolicyInputError(".project/project.yml is required when .project exists")
    manifest = _yaml_mapping(manifest_path)
    _validate_manifest(manifest)
    return manifest_path, manifest


def _forbidden_push_key_paths(value: Any, prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            location = f"{prefix}.{key}" if prefix else str(key)
            normalized = str(key).lower().replace("-", "_")
            if normalized in FORBIDDEN_PUSH_KEYS:
                found.append(location)
            found.extend(_forbidden_push_key_paths(child, location))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_forbidden_push_key_paths(child, f"{prefix}[{index}]"))
    return found


def load_policy(
    root: Path | str, manifest_data: tuple[Path, Mapping[str, Any]] | None = None
) -> tuple[Path, Mapping[str, Any]] | None:
    loaded = manifest_data if manifest_data is not None else load_manifest(root)
    if loaded is None:
        return None
    manifest_path, manifest = loaded
    policy_path = _project_file(manifest_path.parent, manifest["git_policy"])
    if not policy_path.is_file():
        raise PolicyInputError(f"Git policy is missing: {manifest['git_policy']}")
    policy = _yaml_mapping(policy_path)
    forbidden = _forbidden_push_key_paths(policy)
    if forbidden:
        raise PolicyInputError(
            "Git policy must not define push target overrides: " + ", ".join(forbidden)
        )
    _validate_policy(policy, manifest_path.parent)
    return policy_path, policy


def _validate_template(path: Path) -> None:
    try:
        lines = [
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
    except (OSError, UnicodeError) as exc:
        raise PolicyInputError(f"cannot read commit template {path}: {exc}") from exc
    if not lines or lines[0] != "<Project><Function block>: <Summary>":
        raise PolicyInputError(
            "commit template subject must be <Project><Function block>: <Summary>"
        )
    names: list[str] = []
    for line in lines[1:]:
        if line == TEST_MARKER:
            names.append(TEST_MARKER)
            continue
        match = FIELD_PATTERN.fullmatch(line)
        if match is None:
            raise PolicyInputError(f"invalid commit template line: {line}")
        names.append(match.group(1))
    if names != list(TEMPLATE_FIELD_ORDER):
        raise PolicyInputError("commit template fields are missing, unknown, or out of order")
    if tuple(lines[6:9]) != TEMPLATE_AI_DEFAULTS:
        raise PolicyInputError(
            "commit template AI defaults must be N, /, / with one space after each colon"
        )


def _validate_policy(policy: Mapping[str, Any], project_dir: Path) -> None:
    _mapping_keys(
        policy,
        label="Git policy",
        required={
            "schema_version",
            "automation",
            "scope",
            "commit",
            "push",
            "safety",
            "extensions",
        },
        allowed={
            "schema_version",
            "automation",
            "scope",
            "commit",
            "push",
            "safety",
            "extensions",
        },
    )
    if policy.get("schema_version") != 1:
        raise PolicyInputError("Git policy schema_version must be 1")
    automation = _mapping_keys(
        policy.get("automation"),
        label="automation",
        required={"commit", "push"},
        allowed={"commit", "push"},
    )
    if not all(isinstance(automation.get(key), bool) for key in ("commit", "push")):
        raise PolicyInputError("automation.commit and automation.push must be boolean")
    scope = _mapping_keys(
        policy.get("scope"),
        label="scope",
        required={"denied_paths"},
        allowed={"allowed_paths", "denied_paths"},
    )
    for key in ("allowed_paths", "denied_paths"):
        if key not in scope:
            continue
        patterns = _string_list(scope.get(key), label=f"scope.{key}")
        for pattern in patterns:
            _repository_path(pattern)
    commit = _mapping_keys(
        policy.get("commit"),
        label="commit",
        required={
            "template",
            "change_types",
            "jira_pattern",
            "ai_scenarios",
            "checks",
        },
        allowed={
            "template",
            "change_types",
            "jira_pattern",
            "ai_scenarios",
            "checks",
        },
    )
    if not isinstance(commit.get("template"), str):
        raise PolicyInputError("commit.template must be a path")
    template_path = _project_file(project_dir, commit["template"])
    if not template_path.is_file():
        raise PolicyInputError(f"commit template is missing: {commit['template']}")
    _validate_template(template_path)
    _string_list(commit.get("change_types"), label="commit.change_types")
    _string_list(commit.get("ai_scenarios"), label="commit.ai_scenarios")
    _string_list(commit.get("checks"), label="commit.checks", allow_empty=True)
    if not isinstance(commit.get("jira_pattern"), str):
        raise PolicyInputError("commit.jira_pattern must be a string")
    try:
        re.compile(commit["jira_pattern"])
    except re.error as exc:
        raise PolicyInputError(f"invalid commit.jira_pattern: {exc}") from exc
    push = _mapping_keys(
        policy.get("push"),
        label="push",
        required={"allowed_branches", "protected_branches", "checks"},
        allowed={"allowed_branches", "protected_branches", "checks"},
    )
    for key in ("allowed_branches", "protected_branches"):
        _string_list(push.get(key), label=f"push.{key}")
    _string_list(push.get("checks"), label="push.checks", allow_empty=True)
    safety = _mapping_keys(
        policy.get("safety"),
        label="safety",
        required={
            "require_task_authorization",
            "explicit_staging",
            "allow_force_push",
        },
        allowed={
            "require_task_authorization",
            "explicit_staging",
            "allow_force_push",
        },
    )
    if not all(isinstance(safety.get(key), bool) for key in safety):
        raise PolicyInputError("all safety values must be boolean")
    if not isinstance(policy.get("extensions"), dict):
        raise PolicyInputError("Git policy extensions must be a mapping")


def resolve_rules(
    root: Path | str, task_paths: Sequence[str], *, include_all: bool = False
) -> Mapping[str, Any]:
    root_path = _normalized_root(root)
    loaded = load_manifest(root_path)
    if loaded is None:
        return _json_result(
            "NOT_CONFIGURED", task_paths=[], all=include_all, rules=[], git_policy=None
        )
    manifest_path, manifest = loaded
    load_policy(root_path, loaded)
    normalized_paths = [] if include_all else [_repository_path(path) for path in task_paths]
    if not include_all and not normalized_paths:
        raise PolicyInputError("provide at least one task path or use --all")

    resolved: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, entry in enumerate(manifest["rules"]):
        if not isinstance(entry, dict):
            raise PolicyInputError(f"rules[{index}] must be a mapping")
        rule_id = entry.get("id")
        reference = entry.get("path")
        patterns = entry.get("applies_to")
        required = entry.get("required")
        if not isinstance(rule_id, str) or not rule_id:
            raise PolicyInputError(f"rules[{index}].id is invalid")
        if rule_id in seen_ids:
            raise PolicyInputError(f"duplicate rule id: {rule_id}")
        seen_ids.add(rule_id)
        if not isinstance(patterns, list) or not patterns or not all(
            isinstance(pattern, str) and pattern for pattern in patterns
        ):
            raise PolicyInputError(
                f"rules[{index}].applies_to must be a non-empty string list"
            )
        normalized_patterns = [_repository_path(pattern) for pattern in patterns]
        if not isinstance(required, bool):
            raise PolicyInputError(f"rules[{index}].required is invalid")
        matched = (
            normalized_patterns
            if include_all
            else [
                pattern
                for pattern in normalized_patterns
                if any(_matches(path, pattern) for path in normalized_paths)
            ]
        )
        if not matched:
            continue
        rule_path = _project_file(manifest_path.parent, reference)
        if not rule_path.is_file():
            if required:
                raise PolicyInputError(f"required rule is missing: {reference}")
            continue
        resolved.append(
            {
                "id": rule_id,
                "path": rule_path.relative_to(root_path).as_posix(),
                "required": required,
                "matched_patterns": matched,
            }
        )
    policy_path = _project_file(manifest_path.parent, manifest["git_policy"])
    return _json_result(
        "PASS",
        task_paths=normalized_paths,
        all=include_all,
        rules=resolved,
        git_policy=policy_path.relative_to(root_path).as_posix(),
    )


def _message_entries(text: str) -> tuple[dict[str, str], list[ParsedField], list[dict[str, Any]]]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    errors: list[dict[str, Any]] = []
    first = next((index for index, line in enumerate(lines) if line.strip()), None)
    if first is None:
        return {}, [], [{"code": "EMPTY_MESSAGE", "line": 1, "message": "message is empty"}]
    subject_match = SUBJECT_PATTERN.fullmatch(lines[first].strip())
    subject: dict[str, str] = {}
    if subject_match is None:
        errors.append(
            {
                "code": "SUBJECT_FORMAT",
                "line": first + 1,
                "message": "subject must be <Project><Function block>: <Summary>",
            }
        )
    else:
        subject = {
            "project": subject_match.group(1).strip(),
            "function_block": subject_match.group(2).strip(),
            "summary": subject_match.group(3).strip(),
        }

    mutable: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for index in range(first + 1, len(lines)):
        raw = lines[index]
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == TEST_MARKER:
            current = {"name": TEST_MARKER, "value": "", "details": [], "line": index + 1}
            mutable.append(current)
            continue
        match = FIELD_PATTERN.fullmatch(stripped)
        if match is not None:
            current = {
                "name": match.group(1),
                "value": match.group(2).strip(),
                "details": [],
                "line": index + 1,
            }
            mutable.append(current)
            continue
        if raw[:1].isspace() and current is not None and current["name"] != TEST_MARKER:
            current["details"].append(stripped)
            continue
        errors.append(
            {
                "code": "UNKNOWN_LINE",
                "line": index + 1,
                "message": f"unrecognized non-indented line: {stripped}",
            }
        )
    entries = [
        ParsedField(item["name"], item["value"], tuple(item["details"]), item["line"])
        for item in mutable
    ]
    return subject, entries, errors


def _field_map(entries: Sequence[ParsedField]) -> dict[str, list[ParsedField]]:
    result: dict[str, list[ParsedField]] = {}
    for entry in entries:
        result.setdefault(entry.name, []).append(entry)
    return result


def _conditional_yn(
    entry: ParsedField | None,
    name: str,
    errors: list[dict[str, Any]],
    *,
    y_requires_detail: bool,
    n_requires_detail: bool,
) -> None:
    if entry is None:
        return
    match = re.fullmatch(r"([YN])(?:\s+(.*))?", entry.value.strip())
    if match is None:
        errors.append(
            {
                "code": "YN_VALUE",
                "line": entry.line,
                "message": f"{name} must start with Y or N",
            }
        )
        return
    value = match.group(1).upper()
    details = [match.group(2) or "", *entry.details]
    has_detail = bool("\n".join(details).strip())
    if value == "Y" and y_requires_detail and not has_detail:
        errors.append(
            {
                "code": "DETAIL_REQUIRED",
                "line": entry.line,
                "message": f"{name}=Y requires steps",
            }
        )
    if value == "N" and n_requires_detail and not has_detail:
        errors.append(
            {
                "code": "RATIONALE_REQUIRED",
                "line": entry.line,
                "message": f"{name}=N requires a rationale",
            }
        )


def validate_message(root: Path | str, message_path: Path | str) -> Mapping[str, Any]:
    root_path = _normalized_root(root)
    loaded = load_manifest(root_path)
    if loaded is None:
        return _project_policy_required("commit message validation")
    manifest_path, manifest = loaded
    loaded_policy = load_policy(root_path, loaded)
    assert loaded_policy is not None
    policy_path, policy = loaded_policy
    message_file = Path(message_path).resolve()
    if not message_file.is_file():
        raise PolicyInputError(f"message file is missing: {message_file}")
    try:
        text = message_file.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise PolicyInputError(f"cannot read message file: {exc}") from exc

    subject, entries, errors = _message_entries(text)
    names = [entry.name for entry in entries]
    jira_count = names.count("Jira ID")
    collapsed = [name for name in names if name != "Jira ID"]
    expected = [*PRE_JIRA_FIELDS, *POST_JIRA_FIELDS]
    if jira_count < 1:
        errors.append({"code": "JIRA_REQUIRED", "line": 1, "message": "at least one Jira ID is required"})
    if collapsed != expected:
        errors.append(
            {
                "code": "FIELD_ORDER",
                "line": 1,
                "message": "fields are missing, unknown, duplicated, or out of order",
            }
        )
    elif names[: len(PRE_JIRA_FIELDS)] != list(PRE_JIRA_FIELDS):
        errors.append({"code": "FIELD_ORDER", "line": 1, "message": "Jira ID rows must follow Solution"})
    else:
        first_jira = len(PRE_JIRA_FIELDS)
        if names[first_jira : first_jira + jira_count] != ["Jira ID"] * jira_count:
            errors.append({"code": "FIELD_ORDER", "line": 1, "message": "Jira ID rows must be consecutive"})

    fields = _field_map(entries)
    singleton: dict[str, ParsedField | None] = {
        name: values[0] if len(values) == 1 else None
        for name, values in fields.items()
        if name != "Jira ID"
    }
    project_config = manifest.get("project", {})
    primary = project_config.get("primary") if isinstance(project_config, dict) else None
    aliases = project_config.get("aliases", []) if isinstance(project_config, dict) else []
    if subject:
        for key, value in subject.items():
            placeholder_values = {
                "project": "Project",
                "function_block": "Function block",
                "summary": "Summary",
            }
            if (
                not value
                or PLACEHOLDER_PATTERN.search(value)
                or value == placeholder_values[key]
            ):
                errors.append({"code": "SUBJECT_PLACEHOLDER", "line": 1, "message": f"subject {key} is empty or a placeholder"})
        if isinstance(primary, str) and primary != "auto":
            allowed_projects = {primary, *(item for item in aliases if isinstance(item, str))}
            if subject.get("project") not in allowed_projects:
                errors.append({"code": "PROJECT_MISMATCH", "line": 1, "message": "subject project is not configured in project.yml"})

    required_fields = (
        "Change Type",
        "Change Reason",
        "Root Cause",
        "Solution",
        "AI-Tool-Used",
        "AI-Tool-Scenario",
        "AI-Tool-Detail",
        "Affected Function Name",
        "Applicable Project",
        "RN",
        "RN description",
        "Test-Proposal",
        "Stress-Test",
        "HW-Test",
    )
    for name in required_fields:
        entry = singleton.get(name)
        if entry is None:
            continue
        if not entry.detail_text or PLACEHOLDER_PATTERN.search(entry.detail_text):
            errors.append({"code": "FIELD_VALUE", "line": entry.line, "message": f"{name} is empty or contains a placeholder"})

    commit_policy = policy.get("commit", {}) if isinstance(policy, dict) else {}
    change_types = commit_policy.get("change_types", []) if isinstance(commit_policy, dict) else []
    change_entry = singleton.get("Change Type")
    change_type = change_entry.value if change_entry else ""
    if change_entry and change_type not in change_types:
        errors.append({"code": "CHANGE_TYPE", "line": change_entry.line, "message": f"Change Type must be one of {change_types!r}"})
    root_cause = singleton.get("Root Cause")
    if root_cause:
        if change_type == "bug fix" and root_cause.detail_text.upper() == "N/A":
            errors.append({"code": "ROOT_CAUSE", "line": root_cause.line, "message": "bug fix requires a real Root Cause"})
        if change_type == "new requirements" and root_cause.detail_text.upper() != "N/A":
            errors.append({"code": "ROOT_CAUSE", "line": root_cause.line, "message": "new requirements must use N/A for Root Cause"})

    jira_pattern = commit_policy.get("jira_pattern", "") if isinstance(commit_policy, dict) else ""
    try:
        compiled_jira = re.compile(jira_pattern)
    except (re.error, TypeError) as exc:
        raise PolicyInputError(f"invalid commit.jira_pattern: {exc}") from exc
    for jira in fields.get("Jira ID", []):
        if not compiled_jira.fullmatch(jira.value):
            errors.append({"code": "JIRA_FORMAT", "line": jira.line, "message": f"invalid Jira ID: {jira.value!r}"})
    jira_entries = fields.get("Jira ID", [])
    for previous, current in zip(jira_entries, jira_entries[1:]):
        if current.line != previous.line + 1:
            errors.append(
                {
                    "code": "JIRA_CONTIGUOUS",
                    "line": current.line,
                    "message": "multiple Jira ID rows must be contiguous",
                }
            )

    ai_used = singleton.get("AI-Tool-Used")
    ai_scenario = singleton.get("AI-Tool-Scenario")
    ai_detail = singleton.get("AI-Tool-Detail")
    if ai_used and ai_used.value not in ("Y", "N"):
        errors.append({"code": "AI_USED", "line": ai_used.line, "message": "AI-Tool-Used must be Y or N"})
    elif ai_used and ai_scenario and ai_detail:
        if ai_used.value == "N":
            if ai_scenario.detail_text != "/" or ai_detail.detail_text != "/":
                errors.append({"code": "AI_CONDITION", "line": ai_used.line, "message": "AI-Tool-Used=N requires Scenario and Detail to be /"})
        else:
            allowed_scenarios = commit_policy.get("ai_scenarios", [])
            selected = ai_scenario.value.strip()
            if selected not in allowed_scenarios:
                errors.append({"code": "AI_SCENARIO", "line": ai_scenario.line, "message": f"invalid AI scenario: {selected!r}"})
            if not ai_detail.detail_text or ai_detail.detail_text in ("N/A", "/"):
                errors.append({"code": "AI_DETAIL", "line": ai_detail.line, "message": "AI-Tool-Used=Y requires usage detail"})

    rn = singleton.get("RN")
    rn_description = singleton.get("RN description")
    if rn and rn.value not in ("Y", "N"):
        errors.append({"code": "RN_VALUE", "line": rn.line, "message": "RN must be Y or N"})
    elif rn and rn_description:
        if rn.value == "Y" and rn_description.detail_text in ("", "N/A"):
            errors.append({"code": "RN_DESCRIPTION", "line": rn_description.line, "message": "RN=Y requires RN description"})
        if rn.value == "N" and rn_description.detail_text != "N/A":
            errors.append({"code": "RN_DESCRIPTION", "line": rn_description.line, "message": "RN=N requires RN description to be N/A"})

    _conditional_yn(singleton.get("Test-Proposal"), "Test-Proposal", errors, y_requires_detail=True, n_requires_detail=True)
    _conditional_yn(singleton.get("Stress-Test"), "Stress-Test", errors, y_requires_detail=True, n_requires_detail=False)
    _conditional_yn(singleton.get("HW-Test"), "HW-Test", errors, y_requires_detail=True, n_requires_detail=False)

    template_ref = commit_policy.get("template") if isinstance(commit_policy, dict) else None
    template_path = _project_file(manifest_path.parent, template_ref)
    if not template_path.is_file():
        raise PolicyInputError(f"commit template is missing: {template_ref}")
    return _json_result(
        "PASS" if not errors else "BLOCKED",
        subject=subject,
        jira_ids=[entry.value for entry in fields.get("Jira ID", [])],
        errors=errors,
        template=template_path.relative_to(root_path).as_posix(),
        policy=policy_path.relative_to(root_path).as_posix(),
    )


def _git_environment() -> dict[str, str]:
    environment = dict(os.environ)
    for key in list(environment):
        if key.startswith("GIT_CONFIG") or key in {
            "GIT_DIR",
            "GIT_WORK_TREE",
            "GIT_COMMON_DIR",
        }:
            environment.pop(key, None)
    return environment


def _git(root: Path, *arguments: str, allowed_codes: tuple[int, ...] = (0,)) -> subprocess.CompletedProcess[str]:
    completed: subprocess.CompletedProcess[str] | None = None
    for _attempt in range(3):
        completed = subprocess.run(
            ["git", "-C", str(root), *arguments],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            env=_git_environment(),
        )
        if completed.returncode in allowed_codes:
            return completed
    assert completed is not None
    detail = completed.stderr.strip() or completed.stdout.strip() or "Git read failed"
    raise GitReadError(
        f"git {' '.join(arguments)} exited {completed.returncode}: {detail}"
    )


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(str(left.resolve())) == os.path.normcase(str(right.resolve()))


def _git_repository(root: Path) -> dict[str, Any]:
    top = Path(_git(root, "rev-parse", "--show-toplevel").stdout.strip()).resolve()
    if not _same_path(top, root):
        raise GitReadError(f"--root is not the current Git repository root: {top}")
    git_dir_raw = _git(root, "rev-parse", "--git-dir").stdout.strip()
    common_raw = _git(root, "rev-parse", "--git-common-dir").stdout.strip()
    git_dir = (root / git_dir_raw).resolve() if not Path(git_dir_raw).is_absolute() else Path(git_dir_raw).resolve()
    common_dir = (root / common_raw).resolve() if not Path(common_raw).is_absolute() else Path(common_raw).resolve()
    if not git_dir.exists() or not common_dir.exists():
        raise GitReadError("Git metadata directory is missing")
    branch = _git(root, "symbolic-ref", "--quiet", "--short", "HEAD", allowed_codes=(0, 1)).stdout.strip()
    if not branch:
        raise GitReadError("detached HEAD is not eligible for automatic Git delivery")
    return {
        "root": top,
        "git_dir": git_dir,
        "git_common_dir": common_dir,
        "branch": branch,
    }


def _local_config_values(root: Path, key: str) -> tuple[list[str], str | None]:
    values_result = _git(
        root,
        "config",
        "--local",
        "--no-includes",
        "--get-all",
        key,
        allowed_codes=(0, 1),
    )
    values = [line for line in values_result.stdout.splitlines() if line]
    origin_result = _git(
        root,
        "config",
        "--local",
        "--no-includes",
        "--show-origin",
        "--get-all",
        key,
        allowed_codes=(0, 1),
    )
    origins = []
    for line in origin_result.stdout.splitlines():
        if not line:
            continue
        origins.append(line.split("\t", 1)[0].split(" ", 1)[0])
    origin = origins[0] if origins and len(set(origins)) == 1 else None
    return values, origin


def _one_local_value(root: Path, key: str) -> tuple[str, str | None]:
    values, origin = _local_config_values(root, key)
    if len(values) != 1:
        raise GitReadError(f"local Git config {key} must have exactly one value")
    if origin is None:
        raise GitReadError(f"local Git config {key} has no unique source evidence")
    return values[0], origin


def _redact_url(value: str) -> str:
    if "://" in value:
        try:
            parsed = urlsplit(value)
            hostname = parsed.hostname or ""
            port = parsed.port
        except ValueError:
            scheme = value.split("://", 1)[0]
            return f"{scheme}://***"
        if port is not None:
            hostname = f"{hostname}:{port}"
        if parsed.username is not None or parsed.password is not None:
            hostname = f"***@{hostname}"
        query = "***" if parsed.query else ""
        fragment = "***" if parsed.fragment else ""
        return urlunsplit((parsed.scheme, hostname, parsed.path, query, fragment))
    if re.match(r"^[^/@\s]+@[^:\s]+:.+$", value):
        return "***@" + value.split("@", 1)[1]
    return value


def resolve_push_target(root: Path | str) -> Mapping[str, Any]:
    root_path = _normalized_root(root)
    repository = _git_repository(root_path)
    branch = repository["branch"]
    remote, remote_origin = _one_local_value(root_path, f"branch.{branch}.remote")
    merge_ref, merge_origin = _one_local_value(root_path, f"branch.{branch}.merge")
    if (
        not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", remote)
        or ".." in remote
        or "@{" in remote
    ):
        raise GitReadError("branch remote must name one configured remote")
    if not merge_ref.startswith("refs/heads/") or merge_ref == "refs/heads/":
        raise GitReadError("branch merge target must be one refs/heads/... ref")
    if _git(root_path, "check-ref-format", merge_ref, allowed_codes=(0, 1)).returncode != 0:
        raise GitReadError("branch merge target is not a valid Git ref")
    push_urls, push_origin = _local_config_values(root_path, f"remote.{remote}.pushurl")
    url_key = f"remote.{remote}.pushurl"
    if not push_urls:
        push_urls, push_origin = _local_config_values(root_path, f"remote.{remote}.url")
        url_key = f"remote.{remote}.url"
    if len(push_urls) != 1:
        raise GitReadError(f"local Git config must provide exactly one {url_key}")
    if push_origin is None:
        raise GitReadError(f"local Git config {url_key} has no unique source evidence")
    target_branch = merge_ref.removeprefix("refs/heads/")
    tracking_ref = f"refs/remotes/{remote}/{target_branch}"
    evidence = {
        "root": repository["root"].as_posix(),
        "git_dir": repository["git_dir"].as_posix(),
        "git_common_dir": repository["git_common_dir"].as_posix(),
        "current_branch": branch,
        "remote": remote,
        "push_url": _redact_url(push_urls[0]),
        "target_ref": merge_ref,
        "target_branch": target_branch,
        "tracking_ref": tracking_ref,
        "config_sources": {
            f"branch.{branch}.remote": remote_origin,
            f"branch.{branch}.merge": merge_origin,
            url_key: push_origin,
        },
    }
    fingerprint_source = copy.deepcopy(evidence)
    fingerprint_source["push_url"] = push_urls[0]
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_source, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return {**evidence, "fingerprint": fingerprint}


def _nul_paths(output: str) -> list[str]:
    return [_repository_path(item) for item in output.split("\0") if item]


def _changed_paths(root: Path) -> dict[str, list[str]]:
    unstaged = _nul_paths(_git(root, "diff", "--name-only", "-z").stdout)
    staged = _nul_paths(_git(root, "diff", "--cached", "--name-only", "-z").stdout)
    untracked = _nul_paths(
        _git(root, "ls-files", "--others", "--exclude-standard", "-z").stdout
    )
    return {
        "unstaged": sorted(set(unstaged)),
        "staged": sorted(set(staged)),
        "untracked": sorted(set(untracked)),
    }


def _path_policy_reasons(paths: Sequence[str], policy: Mapping[str, Any]) -> list[str]:
    scope = policy.get("scope", {})
    denied = scope.get("denied_paths", []) if isinstance(scope, dict) else []
    reasons: list[str] = []
    for path in paths:
        if any(_matches(path, pattern) for pattern in denied):
            reasons.append(f"path is denied: {path}")
    return reasons


def _path_change_statistics(
    root: Path, path: str, states: Sequence[str]
) -> dict[str, Any]:
    """Summarize the current worktree version of one path relative to HEAD."""
    candidate = root.joinpath(*path.split("/"))
    if "untracked" in states:
        if candidate.is_file() and not candidate.is_symlink():
            added = 0
            has_data = False
            last_byte = b""
            with candidate.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    if b"\0" in chunk:
                        return {"added": None, "deleted": None, "binary": True}
                    has_data = True
                    added += chunk.count(b"\n")
                    last_byte = chunk[-1:]
            if has_data and last_byte != b"\n":
                added += 1
            return {
                "added": added,
                "deleted": 0,
                "binary": False,
            }
        if candidate.is_symlink():
            return {"added": 1, "deleted": 0, "binary": False}
    result = _git(
        root,
        "diff",
        "--numstat",
        "HEAD",
        "--",
        path,
        allowed_codes=(0, 128),
    )
    if result.returncode == 128:
        if candidate.is_file() and not candidate.is_symlink():
            data = candidate.read_bytes()
            if b"\0" in data:
                return {"added": None, "deleted": None, "binary": True}
            return {
                "added": len(data.decode("utf-8", errors="replace").splitlines()),
                "deleted": 0,
                "binary": False,
            }
        if candidate.is_symlink():
            return {"added": 1, "deleted": 0, "binary": False}
        return {"added": 0, "deleted": 0, "binary": False}

    added = 0
    deleted = 0
    binary = False
    for line in result.stdout.splitlines():
        columns = line.split("\t", 2)
        if len(columns) < 2:
            continue
        if columns[0] == "-" or columns[1] == "-":
            binary = True
            continue
        try:
            added += int(columns[0])
            deleted += int(columns[1])
        except ValueError:
            continue
    if binary:
        return {"added": None, "deleted": None, "binary": True}
    return {"added": added, "deleted": deleted, "binary": False}


def _commit_content(
    root: Path, paths: Sequence[str], changes: Mapping[str, Sequence[str]]
) -> dict[str, Any]:
    selected = set(paths)
    all_changes = {
        path
        for state in ("staged", "unstaged", "untracked")
        for path in changes.get(state, [])
    }
    digest = hashlib.sha256()
    ordered = sorted(selected)
    entries: list[dict[str, Any]] = []
    for path in ordered:
        states = [
            state
            for state in ("staged", "unstaged", "untracked")
            if path in changes.get(state, [])
        ]
        entries.append(
            {
                "path": path,
                "states": states,
                **_path_change_statistics(root, path, states),
            }
        )
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        candidate = root.joinpath(*path.split("/"))
        if candidate.is_symlink():
            digest.update(b"SYMLINK\0")
            digest.update(os.readlink(candidate).encode("utf-8", errors="surrogateescape"))
        elif candidate.is_file():
            digest.update(b"FILE\0")
            digest.update(str(candidate.stat().st_mode & 0o111).encode("ascii"))
            digest.update(b"\0")
            with candidate.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
        elif candidate.is_dir():
            digest.update(b"DIRECTORY\0")
            nested_head = _git(
                candidate,
                "rev-parse",
                "--verify",
                "HEAD",
                allowed_codes=(0, 128),
            )
            digest.update(
                nested_head.stdout.strip().encode("ascii", errors="replace")
                if nested_head.returncode == 0
                else b"NO_NESTED_HEAD"
            )
        else:
            digest.update(b"MISSING")
        digest.update(b"\0")
    return {
        "paths": sorted(selected),
        "staged": sorted(selected & set(changes.get("staged", []))),
        "unstaged": sorted(selected & set(changes.get("unstaged", []))),
        "untracked": sorted(selected & set(changes.get("untracked", []))),
        "entries": entries,
        "excluded_paths": sorted(all_changes - selected),
        "fingerprint": digest.hexdigest(),
    }


def _branch_policy_reasons(
    current: str, target: str, policy: Mapping[str, Any]
) -> list[str]:
    push = policy.get("push", {})
    allowed = push.get("allowed_branches", []) if isinstance(push, dict) else []
    protected = push.get("protected_branches", []) if isinstance(push, dict) else []
    reasons: list[str] = []
    for label, branch in (("current", current), ("target", target)):
        if not any(_matches(branch, pattern) for pattern in allowed):
            reasons.append(f"{label} branch is not allowed: {branch}")
        if any(_matches(branch, pattern) for pattern in protected):
            reasons.append(f"{label} branch is protected: {branch}")
    return reasons


def _tracking_ref_sha(root: Path, push_target: Mapping[str, Any]) -> str | None:
    result = _git(
        root,
        "rev-parse",
        "--verify",
        "--quiet",
        push_target["tracking_ref"],
        allowed_codes=(0, 1),
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _auto_push_eligibility(
    root: Path,
    repository: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> tuple[Mapping[str, Any] | None, list[str]]:
    reasons: list[str] = []
    try:
        push_target = resolve_push_target(root)
    except GitReadError as exc:
        return None, [str(exc)]
    reasons.extend(
        _branch_policy_reasons(
            push_target["current_branch"], push_target["target_branch"], policy
        )
    )
    tracking_sha = _tracking_ref_sha(root, push_target)
    if tracking_sha is None:
        reasons.append("configured upstream tracking ref is unavailable locally")
    else:
        head_sha = _git(root, "rev-parse", "HEAD").stdout.strip()
        if head_sha != tracking_sha:
            reasons.append(
                "current HEAD must exactly match the upstream tracking ref before auto delivery"
            )
    if push_target["current_branch"] != repository["branch"]:
        reasons.append("current branch changed during auto preflight")
    return push_target, reasons


def git_plan(
    root: Path | str,
    *,
    operation: str,
    delivery: str,
    paths: Sequence[str] = (),
    message_file: Path | str | None = None,
    expected_content_fingerprint: str | None = None,
    expected_fingerprint: str | None = None,
    expected_commit: str | None = None,
) -> Mapping[str, Any]:
    root_path = _normalized_root(root)
    loaded = load_manifest(root_path)
    if loaded is None:
        return {
            **_project_policy_required(f"Git {operation} preflight"),
            "operation": operation,
            "delivery": delivery,
        }
    loaded_policy = load_policy(root_path, loaded)
    assert loaded_policy is not None
    policy_path, policy = loaded_policy
    automation = policy.get("automation", {})
    safety = policy.get("safety", {})
    reasons: list[str] = []
    policy_relative = policy_path.relative_to(root_path).as_posix()
    if safety.get("require_task_authorization") is not True:
        reasons.append("policy must require current Task Brief authorization")
    if safety.get("explicit_staging") is not True:
        reasons.append("policy must require explicit staging")
    if safety.get("allow_force_push") is not False:
        reasons.append("policy must forbid force push")
    if delivery not in ("commit", "commit-and-push", "auto"):
        reasons.append("Git Delivery does not authorize Git writes")

    repository = _git_repository(root_path)
    changes = _changed_paths(root_path)
    changed_control_paths = {
        ".project/project.yml",
        policy_relative,
    } & {
        *changes["unstaged"],
        *changes["staged"],
        *changes["untracked"],
    }
    if changed_control_paths:
        reasons.append(
            "uncommitted delivery controls cannot authorize this task: "
            + ", ".join(sorted(changed_control_paths))
        )
    normalized_paths: list[str] = []
    message_result: Mapping[str, Any] | None = None
    push_target: Mapping[str, Any] | None = None
    outgoing_commits: list[str] = []
    outgoing_paths: list[str] = []
    commit_content: Mapping[str, Any] | None = None
    content_confirmation: Mapping[str, Any] | None = None

    if operation == "auto":
        if delivery != "auto":
            raise PolicyInputError("auto operation requires --delivery auto")
        actual = set(changes["unstaged"]) | set(changes["staged"]) | set(
            changes["untracked"]
        )
        if not actual:
            return _json_result(
                "PASS",
                operation=operation,
                delivery=delivery,
                decision=DECISION_NO_DELIVERY,
                decision_reasons=[],
                policy=policy_relative,
                repository={
                    "root": repository["root"].as_posix(),
                    "git_dir": repository["git_dir"].as_posix(),
                    "git_common_dir": repository["git_common_dir"].as_posix(),
                    "current_branch": repository["branch"],
                },
                paths=[],
                changes=changes,
                message=None,
                push_target=None,
                checks={"commit": [], "push": []},
            )
        if message_file is None:
            raise PolicyInputError(
                "auto operation requires --message-file when changes exist: "
                + ", ".join(sorted(actual))
            )
        normalized_paths = [_repository_path(path) for path in paths]
        if not normalized_paths:
            raise PolicyInputError("auto operation requires at least one --path when changes exist")
        if expected_content_fingerprint is not None and not re.fullmatch(
            r"[0-9a-fA-F]{64}", expected_content_fingerprint
        ):
            raise PolicyInputError(
                "--expected-content-fingerprint must be a 64-character hexadecimal digest"
            )
        message_result = validate_message(root_path, message_file)
        if message_result["status"] != "PASS":
            return _json_result(
                "BLOCKED",
                operation=operation,
                delivery=delivery,
                decision=None,
                reasons=["commit message validation failed"],
                policy=policy_relative,
                repository={
                    "root": repository["root"].as_posix(),
                    "git_dir": repository["git_dir"].as_posix(),
                    "git_common_dir": repository["git_common_dir"].as_posix(),
                    "current_branch": repository["branch"],
                },
                paths=normalized_paths,
                changes=changes,
                message=message_result,
                push_target=None,
                checks={"commit": [], "push": []},
            )
        commit_content = _commit_content(root_path, normalized_paths, changes)
        current_content_fingerprint = str(commit_content["fingerprint"])
        if expected_content_fingerprint is None:
            content_confirmation_status = "PENDING"
        elif expected_content_fingerprint.lower() != current_content_fingerprint:
            content_confirmation_status = "STALE"
        else:
            content_confirmation_status = "CONFIRMED"

        decision_reasons = list(reasons)
        if automation.get("commit") is not True:
            decision_reasons.append("automatic commit is disabled")
        if automation.get("push") is not True:
            decision_reasons.append("automatic push is disabled")
        requested = set(normalized_paths)
        missing = sorted(requested - actual)
        extra = sorted(actual - requested)
        if missing:
            decision_reasons.append(
                "requested paths have no current changes: " + ", ".join(missing)
            )
        if extra:
            decision_reasons.append(
                "current changes are outside auto delivery scope: " + ", ".join(extra)
            )
        if changes["staged"]:
            decision_reasons.append(
                "index must be empty before auto delivery: "
                + ", ".join(changes["staged"])
            )
        decision_reasons.extend(_path_policy_reasons(normalized_paths, policy))
        push_target, push_reasons = _auto_push_eligibility(
            root_path, repository, policy
        )
        decision_reasons.extend(push_reasons)
        if decision_reasons:
            decision = DECISION_MESSAGE_ONLY
        elif content_confirmation_status != "CONFIRMED":
            decision = DECISION_CONFIRM_AUTO_CONTENT
        else:
            decision = DECISION_AUTO_UPLOAD
        return _json_result(
            "PASS",
            operation=operation,
            delivery=delivery,
            decision=decision,
            decision_reasons=decision_reasons,
            policy=policy_relative,
            repository={
                "root": repository["root"].as_posix(),
                "git_dir": repository["git_dir"].as_posix(),
                "git_common_dir": repository["git_common_dir"].as_posix(),
                "current_branch": repository["branch"],
            },
            paths=normalized_paths,
            changes=changes,
            message=message_result,
            commit_content=commit_content,
            content_confirmation={
                "required": True,
                "status": content_confirmation_status,
                "expected_fingerprint": expected_content_fingerprint,
                "current_fingerprint": current_content_fingerprint,
            },
            push_target=push_target,
            checks={
                "commit": policy.get("commit", {}).get("checks", []),
                "push": policy.get("push", {}).get("checks", []),
            },
        )

    if operation == "commit":
        if delivery == "auto":
            if automation.get("commit") is not True:
                reasons.append("automatic commit is disabled for auto delivery")
            if automation.get("push") is not True:
                reasons.append("automatic push is disabled for auto delivery")
        if message_file is None:
            raise PolicyInputError("commit operation requires --message-file")
        message_result = validate_message(root_path, message_file)
        if message_result["status"] != "PASS":
            reasons.append("commit message validation failed")
        normalized_paths = [_repository_path(path) for path in paths]
        if not normalized_paths:
            raise PolicyInputError("commit operation requires at least one --path")
        reasons.extend(_path_policy_reasons(normalized_paths, policy))
        actual = set(changes["unstaged"]) | set(changes["staged"]) | set(changes["untracked"])
        missing = sorted(set(normalized_paths) - actual)
        if missing:
            reasons.append("requested paths have no current changes: " + ", ".join(missing))
        outside_staged = sorted(set(changes["staged"]) - set(normalized_paths))
        if outside_staged:
            reasons.append("staged paths are outside delivery scope: " + ", ".join(outside_staged))
        commit_content = _commit_content(root_path, normalized_paths, changes)
        checks = policy.get("commit", {}).get("checks", [])
    elif operation == "push":
        if delivery not in ("commit-and-push", "auto"):
            reasons.append("Git Delivery does not authorize push")
        if delivery == "auto" and automation.get("push") is not True:
            reasons.append("automatic push is disabled for auto delivery")
        push_target = resolve_push_target(root_path)
        reasons.extend(
            _branch_policy_reasons(
                push_target["current_branch"], push_target["target_branch"], policy
            )
        )
        if expected_fingerprint and push_target["fingerprint"] != expected_fingerprint:
            reasons.append("local .git push target changed after preflight")
        if delivery == "auto" and not expected_fingerprint:
            reasons.append("auto push requires the original preflight fingerprint")
        if delivery == "auto" and not expected_commit:
            reasons.append("auto push requires the newly created commit SHA")
        if expected_commit and not re.fullmatch(r"[0-9a-fA-F]{40,64}", expected_commit):
            raise PolicyInputError("--expected-commit must be a full hexadecimal commit SHA")
        if changes["staged"]:
            reasons.append("staged changes remain before push: " + ", ".join(changes["staged"]))
            reasons.extend(_path_policy_reasons(changes["staged"], policy))
        upstream = push_target["tracking_ref"]
        verify = _git(
            root_path,
            "rev-parse",
            "--verify",
            "--quiet",
            upstream,
            allowed_codes=(0, 1),
        )
        if verify.returncode != 0:
            reasons.append("configured upstream tracking ref is unavailable locally")
        else:
            outgoing_commits = [
                line
                for line in _git(root_path, "rev-list", "--reverse", f"{upstream}..HEAD").stdout.splitlines()
                if line
            ]
            if not outgoing_commits:
                reasons.append("there are no outgoing commits")
            if delivery == "auto" and expected_commit and outgoing_commits != [
                expected_commit.lower()
            ]:
                reasons.append(
                    "auto push outgoing commits must contain only the newly created commit"
                )
            outgoing_paths = _nul_paths(
                _git(root_path, "diff", "--name-only", "-z", f"{upstream}..HEAD").stdout
            )
            reasons.extend(_path_policy_reasons(outgoing_paths, policy))
        checks = policy.get("push", {}).get("checks", [])
    else:
        raise PolicyInputError("operation must be auto, commit, or push")

    return _json_result(
        "PASS" if not reasons else "BLOCKED",
        operation=operation,
        delivery=delivery,
        reasons=reasons,
        policy=policy_relative,
        repository={
            "root": repository["root"].as_posix(),
            "git_dir": repository["git_dir"].as_posix(),
            "git_common_dir": repository["git_common_dir"].as_posix(),
            "current_branch": repository["branch"],
        },
        paths=normalized_paths,
        changes=changes,
        message=message_result,
        push_target=push_target,
        outgoing_commits=outgoing_commits,
        outgoing_paths=outgoing_paths,
        commit_content=commit_content,
        content_confirmation=content_confirmation,
        checks=checks,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    rules = subparsers.add_parser("rules", help="resolve applicable project rules")
    rules.add_argument("--root", type=Path, default=Path.cwd())
    selection = rules.add_mutually_exclusive_group(required=True)
    selection.add_argument("--path", action="append", dest="paths")
    selection.add_argument("--all", action="store_true")

    message = subparsers.add_parser("message", help="validate one completed commit message")
    message.add_argument("--root", type=Path, default=Path.cwd())
    message.add_argument("--file", type=Path, required=True, dest="message_file")

    plan = subparsers.add_parser("git-plan", help="perform read-only Git delivery preflight")
    plan.add_argument("--root", type=Path, default=Path.cwd())
    plan.add_argument("--operation", choices=("auto", "commit", "push"), required=True)
    plan.add_argument(
        "--delivery", choices=("commit", "commit-and-push", "auto"), required=True
    )
    plan.add_argument("--path", action="append", dest="paths", default=[])
    plan.add_argument("--message-file", type=Path)
    plan.add_argument("--expected-content-fingerprint")
    plan.add_argument("--expected-fingerprint")
    plan.add_argument("--expected-commit")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "rules":
            result = resolve_rules(args.root, args.paths or [], include_all=args.all)
        elif args.command == "message":
            result = validate_message(args.root, args.message_file)
        else:
            result = git_plan(
                args.root,
                operation=args.operation,
                delivery=args.delivery,
                paths=args.paths,
                message_file=args.message_file,
                expected_content_fingerprint=args.expected_content_fingerprint,
                expected_fingerprint=args.expected_fingerprint,
                expected_commit=args.expected_commit,
            )
    except PolicyInputError as exc:
        print(json.dumps(_json_result("INVALID", error=str(exc)), ensure_ascii=False))
        return EXIT_INPUT
    except GitReadError as exc:
        print(json.dumps(_json_result("BLOCKED", reasons=[str(exc)]), ensure_ascii=False))
        return EXIT_EXTERNAL
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return EXIT_BLOCKED if result["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
