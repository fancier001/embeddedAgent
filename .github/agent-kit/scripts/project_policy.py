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
    ro÷Î:¶‰žËkºwµçY¥¹•ÉÁÉ¥¹ÐèÍÑÈð9½¹”€ô9½¹”°(€€€•áÁ•Ñ•‘}™¥¹•ÉÁÉ¥¹ÐèÍÑÈð9½¹”€ô9½¹”°(€€€•áÁ•Ñ•‘}½µµ¥ÐèÍÑÈð9½¹”€ô9½¹”°(¤€´ø5…ÁÁ¥¹mÍÑÈ°¹åtè(€€€É½½Ñ}Á…Ñ €ô}¹½Éµ…±¥é•‘}É½½Ð¡É½½Ð¤(€€€±½…‘•€ô±½…‘}µ…¹¥™•ÍÐ¡É½½Ñ}Á…Ñ ¤(€€€¥˜±½…‘•¥Ì9½¹”è(€€€€€€€É•ÑÕÉ¸}©Í½¹}É•ÍÕ±Ð ‰9=Q}=9%UIˆ°½Á•É…Ñ¥½¸õ½Á•É…Ñ¥½¸°É•…Í½¹Ìõmt¤(€€€±½…‘•‘}Á½±¥ä€ô±½…‘}Á½±¥ä¡É½½Ñ}Á…Ñ °±½…‘•¤(€€€…ÍÍ•ÉÐ±½…‘•‘}Á½±¥ä¥Ì¹½Ð9½¹”(€€€Á½±¥å}Á…Ñ °Á½±¥ä€ô±½…‘•‘}Á½±¥ä(€€€…ÕÑ½µ…Ñ¥½¸€ôÁ½±¥ä¹•Ð ‰…ÕÑ½µ…Ñ¥½¸ˆ°íô¤(€€€Í…™•Ñä€ôÁ½±¥ä¹•Ð ‰Í…™•Ñäˆ°íô¤(€€€É•…Í½¹Ìè±¥ÍÑmÍÑÉt€ômt(€€€Á½±¥å}É•±…Ñ¥Ù”€ôÁ½±¥å}Á…Ñ ¹É•±…Ñ¥Ù•}Ñ¼¡É½½Ñ}Á…Ñ ¤¹…Í}Á½Í¥à ¤(€€€¥˜Í…™•Ñä¹•Ð ‰É•ÅÕ¥É•}Ñ…Í­}…ÕÑ¡½É¥é…Ñ¥½¸ˆ¤¥Ì¹½ÐQÉÕ”è(€€€€€€€É•…Í½¹Ì¹…ÁÁ•¹ ‰Á½±¥äµÕÍÐÉ•ÅÕ¥É”ÕÉÉ•¹ÐQ…Í¬	É¥•˜…ÕÑ¡½É¥é…Ñ¥½¸ˆ¤(€€€¥˜Í…™•Ñä¹•Ð ‰•áÁ±¥¥Ñ}ÍÑ…¥¹œˆ¤¥Ì¹½ÐQÉÕ”è(€€€€€€€É•…Í½¹Ì¹…ÁÁ•¹ ‰Á½±¥äµÕÍÐÉ•ÅÕ¥É”•áÁ±¥¥ÐÍÑ…¥¹œˆ¤(€€€¥˜Í…™•Ñä¹•Ð ‰…±±½Ý}™½É•}ÁÕÍ ˆ¤¥Ì¹½Ð…±Í”è(€€€€€€€É•…Í½¹Ì¹…ÁÁ•¹ ‰Á½±¥äµÕÍÐ™½É‰¥™½É”ÁÕÍ ˆ¤(€€€¥˜‘•±¥Ù•Éä¹½Ð¥¸€ ‰½µµ¥Ðˆ°€‰½µµ¥Ðµ…¹µÁÕÍ ˆ°€‰…ÕÑ¼ˆ¤è(€€€€€€€É•…Í½¹Ì¹…ÁÁ•¹ ‰¥Ð•±¥Ù•Éä‘½•Ì¹½Ð…ÕÑ¡½É¥é”¥ÐÝÉ¥Ñ•Ìˆ¤((€€€É•Á½Í¥Ñ½Éä€ô}¥Ñ}É•Á½Í¥Ñ½Éä¡É½½Ñ}Á…Ñ ¤(€€€¡…¹•Ì€ô}¡…¹•‘}Á…Ñ¡Ì¡É½½Ñ}Á…Ñ ¤(€€€¡…¹•‘}½¹ÑÉ½±}Á…Ñ¡Ì€ôì(€€€€€€€€ˆ¹ÁÉ½©•Ð½ÁÉ½©•Ð¹åµ°ˆ°(€€€€€€€Á½±¥å}É•±…Ñ¥Ù”°(€€€ô€˜ì(€€€€€€€€©¡…¹•Íl‰Õ¹ÍÑ…•‰t°(€€€€€€€€©¡…¹•Íl‰ÍÑ…•‰t°(€€€€€€€€©¡…¹•Íl‰Õ¹ÑÉ…­•‰t°(€€€ô(€€€¥˜¡…¹•‘}½¹ÑÉ½±}Á…Ñ¡Ìè(€€€€€€€É•…Í½¹Ì¹…ÁÁ•¹ (€€€€€€€€€€€€‰Õ¹½µµ¥ÑÑ•‘•±¥Ù•Éä½¹ÑÉ½±Ì…¹¹½Ð…ÕÑ¡½É¥é”Ñ¡¥ÌÑ…Í¬è€ˆ(€€€€€€€€€€€€¬€ˆ°€ˆ¹©½¥¸¡Í½ÉÑ•¡¡…¹•‘}½¹ÑÉ½±}Á…Ñ¡Ì¤¤(€€€€€€€€¤(€€€¹½Éµ…±¥é•‘}Á…Ñ¡Ìè±¥ÍÑmÍÑÉt€ômt(€€€µ•ÍÍ…•}É•ÍÕ±Ðè5…ÁÁ¥¹mÍÑÈ°¹åtð9½¹”€ô9½¹”(€€€ÁÕÍ¡}Ñ…É•Ðè5…ÁÁ¥¹mÍÑÈ°¹åtð9½¹”€ô9½¹”(€€€½ÕÑ½¥¹}½µµ¥ÑÌè±¥ÍÑmÍÑÉt€ômt(€€€½ÕÑ½¥¹}Á…Ñ¡Ìè±¥ÍÑmÍÑÉt€ômt(€€€½µµ¥Ñ}½¹Ñ•¹Ðè5…ÁÁ¥¹mÍÑÈ°¹åtð9½¹”€ô9½¹”((€€€¥˜½Á•É…Ñ¥½¸€ôô€‰…ÕÑ¼ˆè(€€€€€€€¥˜‘•±¥Ù•Éä€„ô€‰…ÕÑ¼ˆè(€€€€€€€€€€€É…¥Í”A½±¥å%¹ÁÕÑÉÉ½È ‰…ÕÑ¼½Á•É…Ñ¥½¸É•ÅÕ¥É•Ì€´µ‘•±¥Ù•Éä…ÕÑ¼ˆ¤(€€€€€€€…ÑÕ…°€ôÍ•Ð¡¡…¹•Íl‰Õ¹ÍÑ…•‰t¤ðÍ•Ð¡¡…¹•Íl‰ÍÑ…•‰t¤ðÍ•Ð (€€€€€€€€€€€¡…¹•Íl‰Õ¹ÑÉ…­•‰t(€€€€€€€€¤(€€€€€€€¥˜¹½Ð…ÑÕ…°è(€€€€€€€€€€€É•ÑÕÉ¸}©Í½¹}É•ÍÕ±Ð (€€€€€€€€€€€€€€€€‰AMLˆ°(€€€€€€€€€€€€€€€½Á•É…Ñ¥½¸õ½Á•É…Ñ¥½¸°(€€€€€€€€€€€€€€€‘•±¥Ù•Éäõ‘•±¥Ù•Éä°(€€€€€€€€€€€€€€€‘•¥Í¥½¸õ%M%=9}9=}1%YId°(€€€€€€€€€€€€€€€‘•¥Í¥½¹}É•…Í½¹Ìõmt°(€€€€€€€€€€€€€€€Á½±¥äõÁ½±¥å}É•±…Ñ¥Ù”°(€€€€€€€€€€€€€€€É•Á½Í¥Ñ½Éäõì(€€€€€€€€€€€€€€€€€€€€‰É½½ÐˆèÉ•Á½Í¥Ñ½Éål‰É½½Ð‰t¹…Í}Á½Í¥à ¤°(€€€€€€€€€€€€€€€€€€€€‰¥Ñ}‘¥ÈˆèÉ•Á½Í¥Ñ½Éål‰¥Ñ}‘¥È‰t¹…Í}Á½Í¥à ¤°(€€€€€€€€€€€€€€€€€€€€‰¥Ñ}½µµ½¹}‘¥ÈˆèÉ•Á½Í¥Ñ½Éål‰¥Ñ}½µµ½¹}‘¥È‰t¹…Í}Á½Í¥à ¤°(€€€€€€€€€€€€€€€€€€€€‰ÕÉÉ•¹Ñ}‰É…¹ ˆèÉ•Á½Í¥Ñ½Éål‰‰É…¹ ‰t°(€€€€€€€€€€€€€€€ô°(€€€€€€€€€€€€€€€Á…Ñ¡Ìõmt°(€€€€€€€€€€€€€€€¡…¹•Ìõ¡…¹•Ì°(€€€€€€€€€€€€€€€µ•ÍÍ…”õ9½¹”°(€€€€€€€€€€€€€€€ÁÕÍ¡}Ñ…É•Ðõ9½¹”°(€€€€€€€€€€€€€€€¡•­Ìõì‰½µµ¥Ðˆèmt°€‰ÁÕÍ ˆèmuô°(€€€€€€€€€€€€¤(€€€€€€€¥˜µ•ÍÍ…•}™¥±”¥Ì9½¹”è(€€€€€€€€€€€É…¥Í”A½±¥å%¹ÁÕÑÉÉ½È (€€€€€€€€€€€€€€€€‰…ÕÑ¼½Á•É…Ñ¥½¸É•ÅÕ¥É•Ì€´µµ•ÍÍ…”µ™¥±”Ý¡•¸¡…¹•Ì•á¥ÍÐè€ˆ(€€€€€€€€€€€€€€€€¬€ˆ°€ˆ¹©½¥¸¡Í½ÉÑ•¡…ÑÕ…°¤¤(€€€€€€€€€€€€¤(€€€€€€€¹½Éµ…±¥é•‘}Á…Ñ¡Ì€ôm}É•Á½Í¥Ñ½Éå}Á…Ñ ¡Á…Ñ ¤™½ÈÁ…Ñ ¥¸Á…Ñ¡Ít(€€€€€€€¥˜¹½Ð¹½Éµ…±¥é•‘}Á…Ñ¡Ìè(€€€€€€€€€€€É…¥Í”A½±¥å%¹ÁÕÑÉÉ½È ‰…ÕÑ¼½Á•É…Ñ¥½¸É•ÅÕ¥É•Ì…Ð±•…ÍÐ½¹”€´µÁ…Ñ Ý¡•¸¡…¹•Ì•á¥ÍÐˆ¤(€€€€€€€¥˜•áÁ•Ñ•‘}½¹Ñ•¹Ñ}™¥¹•ÉÁÉ¥¹Ð¥Ì¹½Ð9½¹”…¹¹½ÐÉ”¹™Õ±±µ…Ñ  (€€€€€€€€€€€È‰lÀ´å„µ™µuìØÑôˆ°•áÁ•Ñ•‘}½¹Ñ•¹Ñ}™¥¹•ÉÁÉ¥¹Ð(€€€€€€€€¤è(€€€€€€€€€€€É…¥Í”A½±¥å%¹ÁÕÑÉÉ½È (€€€€€€€€€€€€€€€€ˆ´µ•áÁ•Ñ•µ½¹Ñ•¹Ðµ™¥¹•ÉÁÉ¥¹ÐµÕÍÐ‰”„€ØÐµ¡…É…Ñ•È¡•á…‘•¥µ…°‘¥•ÍÐˆ(€€€€€€€€€€€€¤(€€€€€€€µ•ÍÍ…•}É•ÍÕ±Ð€ôÙ…±¥‘…Ñ•}µ•ÍÍ…”¡É½½Ñ}Á…Ñ °µ•ÍÍ…•}™¥±”¤(€€€€€€€¥˜µ•ÍÍ…•}É•ÍÕ±Ñl‰ÍÑ…ÑÕÌ‰t€„ô€‰AMLˆè(€€€€€€€€€€€É•ÑÕÉ¸}©Í½¹}É•ÍÕ±Ð (€€€€€€€€€€€€€€€€‰	1=-ˆ°(€€€€€€€€€€€€€€€½Á•É…Ñ¥½¸õ½Á•É…Ñ¥½¸°(€€€€€€€€€€€€€€€‘•±¥Ù•Éäõ‘•±¥Ù•Éä°(€€€€€€€€€€€€€€€‘•¥Í¥½¸õ9½¹”°(€€€€€€€€€€€€€€€É•…Í½¹Ìõl‰½µµ¥Ðµ•ÍÍ…”Ù…±¥‘…Ñ¥½¸™…¥±•‰t°(€€€€€€€€€€€€€€€Á½±¥äõÁ½±¥å}É•±…Ñ¥Ù”°(€€€€€€€€€€€€€€€É•Á½Í¥Ñ½Éäõì(€€€€€€€€€€€€€€€€€€€€‰É½½ÐˆèÉ•Á½Í¥Ñ½Éål‰É½½Ð‰t¹…Í}Á½Í¥à ¤°(€€€€€€€€€€€€€€€€€€€€‰¥Ñ}‘¥ÈˆèÉ•Á½Í¥Ñ½Éål‰¥Ñ}‘¥È‰t¹…Í}Á½Í¥à ¤°(€€€€€€€€€€€€€€€€€€€€‰¥Ñ}½µµ½¹}‘¥ÈˆèÉ•Á½Í¥Ñ½Éål‰¥Ñ}½µµ½¹}‘¥È‰t¹…Í}Á½Í¥à ¤°(€€€€€€€€€€€€€€€€€€€€‰ÕÉÉ•¹Ñ}‰É…¹ ˆèÉ•Á½Í¥Ñ½Éål‰‰É…¹ ‰t°(€€€€€€€€€€€€€€€ô°(€€€€€€€€€€€€€€€Á…Ñ¡Ìõ¹½Éµ…±¥é•‘}Á…Ñ¡Ì°(€€€€€€€€€€€€€€€¡…¹•Ìõ¡…¹•Ì°(€€€€€€€€€€€€€€€µ•ÍÍ…”õµ•ÍÍ…•}É•ÍÕ±Ð°(€€€€€€€€€€€€€€€ÁÕÍ¡}Ñ…É•Ðõ9½¹”°(€€€€€€€€€€€€€€€¡•­Ìõì‰½µµ¥Ðˆèmt°€‰ÁÕÍ ˆèmuô°(€€€€€€€€€€€€¤(€€€€€€€½µµ¥Ñ}½¹Ñ•¹Ð€ô}½µµ¥Ñ}½¹Ñ•¹Ð¡É½½Ñ}Á…Ñ °¹½Éµ…±¥é•‘}Á…Ñ¡Ì°¡…¹•Ì¤(€€€€€€€ÕÉÉ•¹Ñ}½¹Ñ•¹Ñ}™¥¹•ÉÁÉ¥¹Ð€ôÍÑÈ¡½µµ¥Ñ}½¹Ñ•¹Ñl‰™¥¹•ÉÁÉ¥¹Ð‰t¤(€€€€€€€¥˜•áÁ•Ñ•‘}½¹Ñ•¹Ñ}™¥¹•ÉÁÉ¥¹Ð¥Ì9½¹”è(€€€€€€€€€€€½¹Ñ•¹Ñ}½¹™¥Éµ…Ñ¥½¹}ÍÑ…ÑÕÌ€ô€‰A9%9ˆ(€€€€€€€•±¥˜•áÁ•Ñ•‘}½¹Ñ•¹Ñ}™¥¹•ÉÁÉ¥¹Ð¹±½Ý•È ¤€„ôÕÉÉ•¹Ñ}½¹Ñ•¹Ñ}™¥¹•ÉÁÉ¥¹Ðè(€€€€€€€€€€€½¹Ñ•¹Ñ}½¹™¥Éµ…Ñ¥½¹}ÍÑ…ÑÕÌ€ô€‰MQ1ˆ(€€€€€€€•±Í”è(€€€€€€€€€€€½¹Ñ•¹Ñ}½¹™¥Éµ…Ñ¥½¹}ÍÑ…ÑÕÌ€ô€‰=9%I5ˆ((€€€€€€€‘•¥Í¥½¹}É•…Í½¹Ì€ô±¥ÍÐ¡É•…Í½¹Ì¤(€€€€€€€¥˜…ÕÑ½µ…Ñ¥½¸¹•Ð ‰½µµ¥Ðˆ¤¥Ì¹½ÐQÉÕ”è(€€€€€€€€€€€‘•¥Í¥½¹}É•…Í½¹Ì¹…ÁÁ•¹ ‰…ÕÑ½µ…Ñ¥Œ½µµ¥Ð¥Ì‘¥Í…‰±•ˆ¤(€€€€€€€¥˜…ÕÑ½µ…Ñ¥½¸¹•Ð ‰ÁÕÍ ˆ¤¥Ì¹½ÐQÉÕ”è(€€€€€€€€€€€‘•¥Í¥½¹}É•…Í½¹Ì¹…ÁÁ•¹ ‰…ÕÑ½µ…Ñ¥ŒÁÕÍ ¥Ì‘¥Í…‰±•ˆ¤(€€€€€€€É•ÅÕ•ÍÑ•€ôÍ•Ð¡¹½Éµ…±¥é•‘}Á…Ñ¡Ì¤(€€€€€€€µ¥ÍÍ¥¹œ€ôÍ½ÉÑ•¡É•ÅÕ•ÍÑ•€´…ÑÕ…°¤(€€€€€€€•áÑÉ„€ôÍ½ÉÑ•¡…ÑÕ…°€´É•ÅÕ•ÍÑ•¤(€€€€€€€¥˜µ¥ÍÍ¥¹œè(€€€€€€€€€€€‘•¥Í¥½¹}É•…Í½¹Ì¹…ÁÁ•¹ (€€€€€€€€€€€€€€€€‰É•ÅÕ•ÍÑ•Á…Ñ¡Ì¡…Ù”¹¼ÕÉÉ•¹Ð¡…¹•Ìè€ˆ€¬€ˆ°€ˆ¹©½¥¸¡µ¥ÍÍ¥¹œ¤(€€€€€€€€€€€€¤(€€€€€€€¥˜•áÑÉ„è(€€€€€€€€€€€‘•¥Í¥½¹}É•…Í½¹Ì¹…ÁÁ•¹ (€€€€€€€€€€€€€€€€‰ÕÉÉ•¹Ð¡…¹•Ì…É”½ÕÑÍ¥‘”…ÕÑ¼‘•±¥Ù•ÉäÍ½Á”è€ˆ€¬€ˆ°€ˆ¹©½¥¸¡•áÑÉ„¤(€€€€€€€€€€€€¤(€€€€€€€¥˜¡…¹•Íl‰ÍÑ…•‰tè(€€€€€€€€€€€‘•¥Í¥½¹}É•…Í½¹Ì¹…ÁÁ•¹ (€€€€€€€€€€€€€€€€‰¥¹‘•àµÕÍÐ‰”•µÁÑä‰•™½É”…ÕÑ¼‘•±¥Ù•Éäè€ˆ(€€€€€€€€€€€€€€€€¬€ˆ°€ˆ¹©½¥¸¡¡…¹•Íl‰ÍÑ…•‰t¤(€€€€€€€€€€€€¤(€€€€€€€‘•¥Í¥½¹}É•…Í½¹Ì¹•áÑ•¹¡}Á…Ñ¡}Á½±¥å}É•…Í½¹Ì¡¹½Éµ…±¥é•‘}Á…Ñ¡Ì°Á½±¥ä¤¤(€€€€€€€ÁÕÍ¡}Ñ…É•Ð°ÁÕÍ¡}É•…Í½¹Ì€ô}…ÕÑ½}ÁÕÍ¡}•±¥¥‰¥±¥Ñä (€€€€€€€€€€€É½½Ñ}Á…Ñ °É•Á½Í¥Ñ½Éä°Á½±¥ä(€€€€€€€€¤(€€€€€€€‘•¥Í¥½¹}É•…Í½¹Ì¹•áÑ•¹¡ÁÕÍ¡}É•…Í½¹Ì¤(€€€€€€€¥˜‘•¥Í¥½¹}É•…Í½¹Ìè(€€€€€€€€€€€‘•¥Í¥½¸€ô%M%=9}5MM}=91d(€€€€€€€•±¥˜½¹Ñ•¹Ñ}½¹™¥Éµ…Ñ¥½¹}ÍÑ…ÑÕÌ€„ô€‰=9%I5ˆè(€€€€€€€€€€€‘•¥Í¥½¸€ô%M%=9}=9%I5}UQ=}=9Q9P(€€€€€€€•±Í”è(€€€€€€€€€€€‘•¥Í¥½¸€ô%M%=9}UQ=}UA1=(€€€€€€€É•ÑÕÉ¸}©Í½¹}É•ÍÕ±Ð (€€€€€€€€€€€€‰AMLˆ°(€€€€€€€€€€€½Á•É…Ñ¥½¸õ½Á•É…Ñ¥½¸°(€€€€€€€€€€€‘•±¥Ù•Éäõ‘•±¥Ù•Éä°(€€€€€€€€€€€‘•¥Í¥½¸õ‘•¥Í¥½¸°(€€€€€€€€€€€‘•¥Í¥½¹}É•…Í½¹Ìõ‘•¥Í¥½¹}É•…Í½¹Ì°(€€€€€€€€€€€Á½±¥äõÁ½±¥å}É•±…Ñ¥Ù”°(€€€€€€€€€€€É•Á½Í¥Ñ½Éäõì(€€€€€€€€€€€€€€€€‰É½½ÐˆèÉ•Á½Í¥Ñ½Éål‰É½½Ð‰t¹…Í}Á½Í¥à ¤°(€€€€€€€€€€€€€€€€‰¥Ñ}‘¥ÈˆèÉ•Á½Í¥Ñ½Éål‰¥Ñ}‘¥È‰t¹…Í}Á½Í¥à ¤°(€€€€€€€€€€€€€€€€‰¥Ñ}½µµ½¹}‘¥ÈˆèÉ•Á½Í¥Ñ½Éål‰¥Ñ}½µµ½¹}‘¥È‰t¹…Í}Á½Í¥à ¤°(€€€€€€€€€€€€€€€€‰ÕÉÉ•¹Ñ}‰É…¹ ˆèÉ•Á½Í¥Ñ½Éål‰‰É…¹ ‰t°(€€€€€€€€€€€ô°(€€€€€€€€€€€Á…Ñ¡Ìõ¹½Éµ…±¥é•‘}Á…Ñ¡Ì°(€€€€€€€€€€€¡…¹•Ìõ¡…¹•Ì°(€€€€€€€€€€€µ•ÍÍ…”õµ•ÍÍ…•}É•ÍÕ±Ð°(€€€€€€€€€€€½µµ¥Ñ}½¹Ñ•¹Ðõ½µµ¥Ñ}½¹Ñ•¹Ð°(€€€€€€€€€€€½¹Ñ•¹Ñ}½¹™¥Éµ…Ñ¥½¸õì(€€€€€€€€€€€€€€€€‰É•ÅÕ¥É•ˆèQÉÕ”°(€€€€€€€€€€€€€€€€‰ÍÑ…ÑÕÌˆè½¹Ñ•¹Ñ}½¹™¥Éµ…Ñ¥½¹}ÍÑ…ÑÕÌ°(€€€€€€€€€€€€€€€€‰•áÁ•Ñ•‘}™¥¹•ÉÁÉ¥¹Ðˆè•áÁ•Ñ•‘}½¹Ñ•¹Ñ}™¥¹•ÉÁÉ¥¹Ð°(€€€€€€€€€€€€€€€€‰ÕÉÉ•¹Ñ}™¥¹•ÉÁÉ¥¹ÐˆèÕÉÉ•¹Ñ}½¹Ñ•¹Ñ}™¥¹•ÉÁÉ¥¹Ð°(€€€€€€€€€€€ô°(€€€€€€€€€€€ÁÕÍ¡}Ñ…É•ÐõÁÕÍ¡}Ñ…É•Ð°(€€€€€€€€€€€¡•­Ìõì(€€€€€€€€€€€€€€€€‰½µµ¥ÐˆèÁ½±¥ä¹•Ð ‰½µµ¥Ðˆ°íô¤¹•Ð ‰¡•­Ìˆ°mt¤°(€€€€€€€€€€€€€€€€‰ÁÕÍ ˆèÁ½±¥ä¹•Ð ‰ÁÕÍ ˆ°íô¤¹•Ð ‰¡•­Ìˆ°mt¤°(€€€€€€€€€€€ô°(€€€€€€€€¤((€€€¥˜½Á•É…Ñ¥½¸€ôô€‰½µµ¥Ðˆè(€€€€€€€¥˜‘•±¥Ù•Éä€ôô€‰…ÕÑ¼ˆè(€€€€€€€€€€€¥˜…ÕÑ½µ…Ñ¥½¸¹•Ð ‰½µµ¥Ðˆ¤¥Ì¹½ÐQÉÕ”è(€€€€€€€€€€€€€€€É•…Í½¹Ì¹…ÁÁ•¹ ‰…ÕÑ½µ…Ñ¥Œ½µµ¥Ð¥Ì‘¥Í…‰±•™½È…ÕÑ¼‘•±¥Ù•Éäˆ¤(€€€€€€€€€€€¥˜…ÕÑ½µ…Ñ¥½¸¹•Ð ‰ÁÕÍ ˆ¤¥Ì¹½ÐQÉÕ”è(€€€€€€€€€€€€€€€É•…Í½¹Ì¹…ÁÁ•¹ ‰…ÕÑ½µ…Ñ¥ŒÁÕÍ ¥Ì‘¥Í…‰±•™½È…ÕÑ¼‘•±¥Ù•Éäˆ¤(€€€€€€€¥˜µ•ÍÍ…•}™¥±”¥Ì9½¹”è(€€€€€€€€€€€É…¥Í”A½±¥å%¹ÁÕÑÉÉ½È ‰½µµ¥Ð½Á•É…Ñ¥½¸É•ÅÕ¥É•Ì€´µµ•ÍÍ…”µ™¥±”ˆ¤(€€€€€€€µ•ÍÍ…•}É•ÍÕ±Ð€ôÙ…±¥‘…Ñ•}µ•ÍÍ…”¡É½½Ñ}Á…Ñ °µ•ÍÍ…•}™¥±”¤(€€€€€€€¥˜µ•ÍÍ…•}É•ÍÕ±Ñl‰ÍÑ…ÑÕÌ‰t€„ô€‰AMLˆè(€€€€€€€€€€€É•…Í½¹Ì¹…ÁÁ•¹ ‰½µµ¥Ðµ•ÍÍ…”Ù…±¥‘…Ñ¥½¸™…¥±•ˆ¤(€€€€€€€¹½Éµ…±¥é•‘}Á…Ñ¡Ì€ôm}É•Á½Í¥Ñ½Éå}Á…Ñ ¡Á…Ñ ¤™½ÈÁ…Ñ ¥¸Á…Ñ¡Ít(€€€€€€€¥˜¹½Ð¹½Éµ…±¥é•‘}Á…Ñ¡Ìè(€€€€€€€€€€€É…¥Í”A½±¥å%¹ÁÕÑÉÉ½È ‰½µµ¥Ð½Á•É…Ñ¥½¸É•ÅÕ¥É•Ì…Ð±•…ÍÐ½¹”€´µÁ…Ñ ˆ¤(€€€€€€€É•…Í½¹Ì¹•áÑ•¹¡}Á…Ñ¡}Á½±¥å}É•…Í½¹Ì¡¹½Éµ…±¥é•‘}Á…Ñ¡Ì°Á½±¥ä¤¤(€€€€€€€…ÑÕ…°€ôÍ•Ð¡¡…¹•Íl‰Õ¹ÍÑ…•‰t¤ðÍ•Ð¡¡…¹•Íl‰ÍÑ…•‰t¤ðÍ•Ð¡¡…¹•Íl‰Õ¹ÑÉ…­•‰t¤(€€€€€€€µ¥ÍÍ¥¹œ€ôÍ½ÉÑ•¡Í•Ð¡¹½Éµ…±¥é•‘}Á…Ñ¡Ì¤€´…ÑÕ…°¤(€€€€€€€¥˜µ¥ÍÍ¥¹œè(€€€€€€€€€€€É•…Í½¹Ì¹…ÁÁ•¹ ‰É•ÅÕ•ÍÑ•Á…Ñ¡Ì¡…Ù”¹¼ÕÉÉ•¹Ð¡…¹•Ìè€ˆ€¬€ˆ°€ˆ¹©½¥¸¡µ¥ÍÍ¥¹œ¤¤(€€€€€€€½ÕÑÍ¥‘•}ÍÑ…•€ôÍ½ÉÑ•¡Í•Ð¡¡…¹•Íl‰ÍÑ…•‰t¤€´Í•Ð¡¹½Éµ…±¥é•‘}Á…Ñ¡Ì¤¤(€€€€€€€¥˜½ÕÑÍ¥‘•}ÍÑ…•è(€€€€€€€€€€€É•…Í½¹Ì¹…ÁÁ•¹ ‰ÍÑ…•Á…Ñ¡Ì…É”½ÕÑÍ¥‘”‘•±¥Ù•ÉäÍ½Á”è€ˆ€¬€ˆ°€ˆ¹©½¥¸¡½ÕÑÍ¥‘•}ÍÑ…•¤¤(€€€€€€€½µµ¥Ñ}½¹Ñ•¹Ð€ô}½µµ¥Ñ}½¹Ñ•¹Ð¡É½½Ñ}Á…Ñ °¹½Éµ…±¥é•‘}Á…Ñ¡Ì°¡…¹•Ì¤(€€€€€€€¡•­Ì€ôÁ½±¥ä¹•Ð ‰½µµ¥Ðˆ°íô¤¹•Ð ‰¡•­Ìˆ°mt¤(€€€•±¥˜½Á•É…Ñ¥½¸€ôô€‰ÁÕÍ ˆè(€€€€€€€¥˜‘•±¥Ù•Éä¹½Ð¥¸€ ‰½µµ¥Ðµ…¹µÁÕÍ ˆ°€‰…ÕÑ¼ˆ¤è(€€€€€€€€€€€É•…Í½¹Ì¹…ÁÁ•¹ ‰¥Ð•±¥Ù•Éä‘½•Ì¹½Ð…ÕÑ¡½É¥é”ÁÕÍ ˆ¤(€€€€€€€¥˜‘•±¥Ù•Éä€ôô€‰…ÕÑ¼ˆ…¹…ÕÑ½µ…Ñ¥½¸¹•Ð ‰ÁÕÍ ˆ¤¥Ì¹½ÐQÉÕ”è(€€€€€€€€€€€É•…Í½¹Ì¹…ÁÁ•¹ ‰…ÕÑ½µ…Ñ¥ŒÁÕÍ ¥Ì‘¥Í…‰±•™½È…ÕÑ¼‘•±¥Ù•Éäˆ¤(€€€€€€€ÁÕÍ¡}Ñ…É•Ð€ôÉ•Í½±Ù•}ÁÕÍ¡}Ñ…É•Ð¡É½½Ñ}Á…Ñ ¤(€€€€€€€É•…Í½¹Ì¹•áÑ•¹ (€€€€€€€€€€€}‰É…¹¡}Á½±¥å}É•…Í½¹Ì (€€€€€€€€€€€€€€€ÁÕÍ¡}Ñ…É•Ñl‰ÕÉÉ•¹Ñ}‰É…¹ ‰t°ÁÕÍ¡}Ñ…É•Ñl‰Ñ…É•Ñ}‰É…¹ ‰t°Á½±¥ä(€€€€€€€€€€€€¤(€€€€€€€€¤(€€€€€€€¥˜•áÁ•Ñ•‘}™¥¹•ÉÁÉ¥¹Ð…¹ÁÕÍ¡}Ñ…É•Ñl‰™¥¹•ÉÁÉ¥¹Ð‰t€„ô•áÁ•Ñ•‘}™¥¹•ÉÁÉ¥¹Ðè(€€€€€€€€€€€É•…Í½¹Ì¹…ÁÁ•¹ ‰±½…°€¹¥ÐÁÕÍ Ñ…É•Ð¡…¹•…™Ñ•ÈÁÉ•™±¥¡Ðˆ¤(€€€€€€€¥˜‘•±¥Ù•Éä€ôô€‰…ÕÑ¼ˆ…¹¹½Ð•áÁ•Ñ•‘}™¥¹•ÉÁÉ¥¹Ðè(€€€€€€€€€€€É•…Í½¹Ì¹…ÁÁ•¹ ‰…ÕÑ¼ÁÕÍ É•ÅÕ¥É•ÌÑ¡”½É¥¥¹…°ÁÉ•™±¥¡Ð™¥¹•ÉÁÉ¥¹Ðˆ¤(€€€€€€€¥˜‘•±¥Ù•Éä€ôô€‰…ÕÑ¼ˆ…¹¹½Ð•áÁ•Ñ•‘}½µµ¥Ðè(€€€€€€€€€€€É•…Í½¹Ì¹…ÁÁ•¹ ‰…ÕÑ¼ÁÕÍ É•ÅÕ¥É•ÌÑ¡”¹•Ý±äÉ•…Ñ•½µµ¥ÐM!ˆ¤(€€€€€€€¥˜•áÁ•Ñ•‘}½µµ¥Ð…¹¹½ÐÉ”¹™Õ±±µ…Ñ ¡È‰lÀ´å„µ™µuìÐÀ°ØÑôˆ°•áÁ•Ñ•‘}½µµ¥Ð¤è(€€€€€€€€€€€É…¥Í”A½±¥å%¹ÁÕÑÉÉ½È ˆ´µ•áÁ•Ñ•µ½µµ¥ÐµÕÍÐ‰”„™Õ±°¡•á…‘•¥µ…°½µµ¥ÐM!ˆ¤(€€€€€€€¥˜¡…¹•Íl‰ÍÑ…•‰tè(€€€€€€€€€€€É•…Í½¹Ì¹…ÁÁ•¹ ‰ÍÑ…•¡…¹•ÌÉ•µ…¥¸‰•™½É”ÁÕÍ è€ˆ€¬€ˆ°€ˆ¹©½¥¸¡¡…¹•Íl‰ÍÑ…•‰t¤¤(€€€€€€€€€€€É•…Í½¹Ì¹•áÑ•¹¡}Á…Ñ¡}Á½±¥å}É•…Í½¹Ì¡¡…¹•Íl‰ÍÑ…•‰t°Á½±¥ä¤¤(€€€€€€€ÕÁÍÑÉ•…´€ôÁÕÍ¡}Ñ…É•Ñl‰ÑÉ…­¥¹}É•˜‰t(€€€€€€€Ù•É¥™ä€ô}¥Ð (€€€€€€€€€€€É½½Ñ}Á…Ñ °(€€€€€€€€€€€€‰É•ØµÁ…ÉÍ”ˆ°(€€€€€€€€€€€€ˆ´µÙ•É¥™äˆ°(€€€€€€€€€€€€ˆ´µÅÕ¥•Ðˆ°(€€€€€€€€€€€ÕÁÍÑÉ•…´°(€€€€€€€€€€€…±±½Ý•‘}½‘•Ìô À°€Ä¤°(€€€€€€€€¤(€€€€€€€¥˜Ù•É¥™ä¹É•ÑÕÉ¹½‘”€„ô€Àè(€€€€€€€€€€€É•…Í½¹Ì¹…ÁÁ•¹ ‰½¹™¥ÕÉ•ÕÁÍÑÉ•…´ÑÉ…­¥¹œÉ•˜¥ÌÕ¹…Ù…¥±…‰±”±½…±±äˆ¤(€€€€€€€•±Í”è(€€€€€€€€€€€½ÕÑ½¥¹}½µµ¥ÑÌ€ôl(€€€€€€€€€€€€€€€±¥¹”(€€€€€€€€€€€€€€€™½È±¥¹”¥¸}¥Ð¡É½½Ñ}Á…Ñ °€‰É•Øµ±¥ÍÐˆ°€ˆ´µÉ•Ù•ÉÍ”ˆ°˜‰íÕÁÍÑÉ•…µô¸¹!ˆ¤¹ÍÑ‘½ÕÐ¹ÍÁ±¥Ñ±¥¹•Ì ¤(€€€€€€€€€€€€€€€¥˜±¥¹”(€€€€€€€€€€€t(€€€€€€€€€€€¥˜¹½Ð½ÕÑ½¥¹}½µµ¥ÑÌè(€€€€€€€€€€€€€€€É•…Í½¹Ì¹…ÁÁ•¹ ‰Ñ¡•É”…É”¹¼½ÕÑ½¥¹œ½µµ¥ÑÌˆ¤(€€€€€€€€€€€¥˜‘•±¥Ù•Éä€ôô€‰…ÕÑ¼ˆ…¹•áÁ•Ñ•‘}½µµ¥Ð…¹½ÕÑ½¥¹}½µµ¥ÑÌ€„ôl(€€€€€€€€€€€€€€€•áÁ•Ñ•‘}½µµ¥Ð¹±½Ý•È ¤(€€€€€€€€€€€tè(€€€€€€€€€€€€€€€É•…Í½¹Ì¹…ÁÁ•¹ (€€€€€€€€€€€€€€€€€€€€‰…ÕÑ¼ÁÕÍ ½ÕÑ½¥¹œ½µµ¥ÑÌµÕÍÐ½¹Ñ…¥¸½¹±äÑ¡”¹•Ý±äÉ•…Ñ•½µµ¥Ðˆ(€€€€€€€€€€€€€€€€¤(€€€€€€€€€€€½ÕÑ½¥¹}Á…Ñ¡Ì€ô}¹Õ±}Á…Ñ¡Ì (€€€€€€€€€€€€€€€}¥Ð¡É½½Ñ}Á…Ñ °€‰‘¥™˜ˆ°€ˆ´µ¹…µ”µ½¹±äˆ°€ˆµèˆ°˜‰íÕÁÍÑÉ•…µô¸¹!ˆ¤¹ÍÑ‘½ÕÐ(€€€€€€€€€€€€¤(€€€€€€€€€€€É•…Í½¹Ì¹•áÑ•¹¡}Á…Ñ¡}Á½±¥å}É•…Í½¹Ì¡½ÕÑ½¥¹}Á…Ñ¡Ì°Á½±¥ä¤¤(€€€€€€€¡•­Ì€ôÁ½±¥ä¹•Ð ‰ÁÕÍ ˆ°íô¤¹•Ð ‰¡•­Ìˆ°mt¤(€€€•±Í”è(€€€€€€€É…¥Í”A½±¥å%¹ÁÕÑÉÉ½È ‰½Á•É…Ñ¥½¸µÕÍÐ‰”…ÕÑ¼°½µµ¥Ð°½ÈÁÕÍ ˆ¤((€€€É•ÑÕÉ¸}©Í½¹}É•ÍÕ±Ð (€€€€€€€€‰AMLˆ¥˜¹½ÐÉ•…Í½¹Ì•±Í”€‰	1=-ˆ°(€€€€€€€½Á•É…Ñ¥½¸õ½Á•É…Ñ¥½¸°(€€€€€€€‘•±¥Ù•Éäõ‘•±¥Ù•Éä°(€€€€€€€É•…Í½¹ÌõÉ•…Í½¹Ì°(€€€€€€€Á½±¥äõÁ½±¥å}É•±…Ñ¥Ù”°(€€€€€€€É•Á½Í¥Ñ½Éäõì(€€€€€€€€€€€€‰É½½ÐˆèÉ•Á½Í¥Ñ½Éål‰É½½Ð‰t¹…Í}Á½Í¥à ¤°(€€€€€€€€€€€€‰¥Ñ}‘¥ÈˆèÉ•Á½Í¥Ñ½Éål‰¥Ñ}‘¥È‰t¹…Í}Á½Í¥à ¤°(€€€€€€€€€€€€‰¥Ñ}½µµ½¹}‘¥ÈˆèÉ•Á½Í¥Ñ½Éål‰¥Ñ}½µµ½¹}‘¥È‰t¹…Í}Á½Í¥à ¤°(€€€€€€€€€€€€‰ÕÉÉ•¹Ñ}‰É…¹ ˆèÉ•Á½Í¥Ñ½Éål‰‰É…¹ ‰t°(€€€€€€€ô°(€€€€€€€Á…Ñ¡Ìõ¹½Éµ…±¥é•‘}Á…Ñ¡Ì°(€€€€€€€¡…¹•Ìõ¡…¹•Ì°(€€€€€€€µ•ÍÍ…”õµ•ÍÍ…•}É•ÍÕ±Ð°(€€€€€€€ÁÕÍ¡}Ñ…É•ÐõÁÕÍ¡}Ñ…É•Ð°(€€€€€€€½ÕÑ½¥¹}½µµ¥ÑÌõ½ÕÑ½¥¹}½µµ¥ÑÌ°(€€€€€€€½ÕÑ½¥¹}Á…Ñ¡Ìõ½ÕÑ½¥¹}Á…Ñ¡Ì°(€€€€€€€½µµ¥Ñ}½¹Ñ•¹Ðõ½µµ¥Ñ}½¹Ñ•¹Ð°(€€€€€€€¡•­Ìõ¡•­Ì°(€€€€¤(()‘•˜}‰Õ¥±‘}Á…ÉÍ•È ¤€´ø…ÉÁ…ÉÍ”¹ÉÕµ•¹ÑA…ÉÍ•Èè(€€€Á…ÉÍ•È€ô…ÉÁ…ÉÍ”¹ÉÕµ•¹ÑA…ÉÍ•È¡‘•ÍÉ¥ÁÑ¥½¸õ}}‘½}|¤(€€€ÍÕ‰Á…ÉÍ•ÉÌ€ôÁ…ÉÍ•È¹…‘‘}ÍÕ‰Á…ÉÍ•ÉÌ¡‘•ÍÐô‰½µµ…¹ˆ°É•ÅÕ¥É•õQÉÕ”¤((€€€ÉÕ±•Ì€ôÍÕ‰Á…ÉÍ•ÉÌ¹…‘‘}Á…ÉÍ•È ‰ÉÕ±•Ìˆ°¡•±Àô‰É•Í½±Ù”…ÁÁ±¥…‰±”ÁÉ½©•ÐÉÕ±•Ìˆ¤(€€€ÉÕ±•Ì¹…‘‘}…ÉÕµ•¹Ð ˆ´µÉ½½Ðˆ°ÑåÁ”õA…Ñ °‘•™…Õ±ÐõA…Ñ ¹Ý ¤¤(€€€Í•±•Ñ¥½¸€ôÉÕ±•Ì¹…‘‘}µÕÑÕ…±±å}•á±ÕÍ¥Ù•}É½ÕÀ¡É•ÅÕ¥É•õQÉÕ”¤(€€€Í•±•Ñ¥½¸¹…‘‘}…ÉÕµ•¹Ð ˆ´µÁ…Ñ ˆ°…Ñ¥½¸ô‰…ÁÁ•¹ˆ°‘•ÍÐô‰Á…Ñ¡Ìˆ¤(€€€Í•±•Ñ¥½¸¹…‘‘}…ÉÕµ•¹Ð ˆ´µ…±°ˆ°…Ñ¥½¸ô‰ÍÑ½É•}ÑÉÕ”ˆ¤((€€€µ•ÍÍ…”€ôÍÕ‰Á…ÉÍ•ÉÌ¹…‘‘}Á…ÉÍ•È ‰µ•ÍÍ…”ˆ°¡•±Àô‰Ù…±¥‘…Ñ”½¹”½µÁ±•Ñ•½µµ¥Ðµ•ÍÍ…”ˆ¤(€€€µ•ÍÍ…”¹…‘‘}…ÉÕµ•¹Ð ˆ´µÉ½½Ðˆ°ÑåÁ”õA…Ñ °‘•™…Õ±ÐõA…Ñ ¹Ý ¤¤(€€€µ•ÍÍ…”¹…‘‘}…ÉÕµ•¹Ð ˆ´µ™¥±”ˆ°ÑåÁ”õA…Ñ °É•ÅÕ¥É•õQÉÕ”°‘•ÍÐô‰µ•ÍÍ…•}™¥±”ˆ¤((€€€Á±…¸€ôÍÕ‰Á…ÉÍ•ÉÌ¹…‘‘}Á…ÉÍ•È ‰¥ÐµÁ±…¸ˆ°¡•±Àô‰Á•É™½É´É•…µ½¹±ä¥Ð‘•±¥Ù•ÉäÁÉ•™±¥¡Ðˆ¤(€€€Á±…¸¹…‘‘}…ÉÕµ•¹Ð ˆ´µÉ½½Ðˆ°ÑåÁ”õA…Ñ °‘•™…Õ±ÐõA…Ñ ¹Ý ¤¤(€€€Á±…¸¹…‘‘}…ÉÕµ•¹Ð ˆ´µ½Á•É…Ñ¥½¸ˆ°¡½¥•Ìô ‰…ÕÑ¼ˆ°€‰½µµ¥Ðˆ°€‰ÁÕÍ ˆ¤°É•ÅÕ¥É•õQÉÕ”¤(€€€Á±…¸¹…‘‘}…ÉÕµ•¹Ð (€€€€€€€€ˆ´µ‘•±¥Ù•Éäˆ°¡½¥•Ìô ‰½µµ¥Ðˆ°€‰½µµ¥Ðµ…¹µÁÕÍ ˆ°€‰…ÕÑ¼ˆ¤°É•ÅÕ¥É•õQÉÕ”(€€€€¤(€€€Á±…¸¹…‘‘}…ÉÕµ•¹Ð ˆ´µÁ…Ñ ˆ°…Ñ¥½¸ô‰…ÁÁ•¹ˆ°‘•ÍÐô‰Á…Ñ¡Ìˆ°‘•™…Õ±Ðõmt¤(€€€Á±…¸¹…‘‘}…ÉÕµ•¹Ð ˆ´µµ•ÍÍ…”µ™¥±”ˆ°ÑåÁ”õA…Ñ ¤(€€€Á±…¸¹…‘‘}…ÉÕµ•¹Ð ˆ´µ•áÁ•Ñ•µ½¹Ñ•¹Ðµ™¥¹•ÉÁÉ¥¹Ðˆ¤(€€€Á±…¸¹…‘‘}…ÉÕµ•¹Ð ˆ´µ•áÁ•Ñ•µ™¥¹•ÉÁÉ¥¹Ðˆ¤(€€€Á±…¸¹…‘‘}…ÉÕµ•¹Ð ˆ´µ•áÁ•Ñ•µ½µµ¥Ðˆ¤(€€€É•ÑÕÉ¸Á…ÉÍ•È(()‘•˜µ…¥¸¡…ÉØèM•ÅÕ•¹•mÍÑÉtð9½¹”€ô9½¹”¤€´ø¥¹Ðè(€€€…ÉÌ€ô}‰Õ¥±‘}Á…ÉÍ•È ¤¹Á…ÉÍ•}…ÉÌ¡…ÉØ¤(€€€ÑÉäè(€€€€€€€¥˜…ÉÌ¹½µµ…¹€ôô€‰ÉÕ±•Ìˆè(€€€€€€€€€€€É•ÍÕ±Ð€ôÉ•Í½±Ù•}ÉÕ±•Ì¡…ÉÌ¹É½½Ð°…ÉÌ¹Á…Ñ¡Ì½Èmt°¥¹±Õ‘•}…±°õ…ÉÌ¹…±°¤(€€€€€€€•±¥˜…ÉÌ¹½µµ…¹€ôô€‰µ•ÍÍ…”ˆè(€€€€€€€€€€€É•ÍÕ±Ð€ôÙ…±¥‘…Ñ•}µ•ÍÍ…”¡…ÉÌ¹É½½Ð°…ÉÌ¹µ•ÍÍ…•}™¥±”¤(€€€€€€€•±Í”è(€€€€€€€€€€€É•ÍÕ±Ð€ô¥Ñ}Á±…¸ (€€€€€€€€€€€€€€€…ÉÌ¹É½½Ð°(€€€€€€€€€€€€€€€½Á•É…Ñ¥½¸õ…ÉÌ¹½Á•É…Ñ¥½¸°(€€€€€€€€€€€€€€€‘•±¥Ù•Éäõ…ÉÌ¹‘•±¥Ù•Éä°(€€€€€€€€€€€€€€€Á…Ñ¡Ìõ…ÉÌ¹Á…Ñ¡Ì°(€€€€€€€€€€€€€€€µ•ÍÍ…•}™¥±”õ…ÉÌ¹µ•ÍÍ…•}™¥±”°(€€€€€€€€€€€€€€€•áÁ•Ñ•‘}½¹Ñ•¹Ñ}™¥¹•ÉÁÉ¥¹Ðõ…ÉÌ¹•áÁ•Ñ•‘}½¹Ñ•¹Ñ}™¥¹•ÉÁÉ¥¹Ð°(€€€€€€€€€€€€€€€•áÁ•Ñ•‘}™¥¹•ÉÁÉ¥¹Ðõ…ÉÌ¹•áÁ•Ñ•‘}™¥¹•ÉÁÉ¥¹Ð°(€€€€€€€€€€€€€€€•áÁ•Ñ•‘}½µµ¥Ðõ…ÉÌ¹•áÁ•Ñ•‘}½µµ¥Ð°(€€€€€€€€€€€€¤(€€€•á•ÁÐA½±¥å%¹ÁÕÑÉÉ½È…Ì•áŒè(€€€€€€€ÁÉ¥¹Ð¡©Í½¸¹‘ÕµÁÌ¡}©Í½¹}É•ÍÕ±Ð ‰%9Y1%ˆ°•ÉÉ½ÈõÍÑÈ¡•áŒ¤¤°•¹ÍÕÉ•}…Í¥¤õ…±Í”¤¤(€€€€€€€É•ÑÕÉ¸a%Q}%9AUP(€€€•á•ÁÐ¥ÑI•…‘ÉÉ½È…Ì•áŒè(€€€€€€€ÁÉ¥¹Ð¡©Í½¸¹‘ÕµÁÌ¡}©Í½¹}É•ÍÕ±Ð ‰	1=-ˆ°É•…Í½¹ÌõmÍÑÈ¡•áŒ¥t¤°•¹ÍÕÉ•}…Í¥¤õ…±Í”¤¤(€€€€€€€É•ÑÕÉ¸a%Q}aQI90(€€€ÁÉ¥¹Ð¡©Í½¸¹‘ÕµÁÌ¡É•ÍÕ±Ð°•¹ÍÕÉ•}…Í¥¤õ…±Í”°¥¹‘•¹ÐôÈ¤¤(€€€É•ÑÕÉ¸a%Q}	1=-¥˜É•ÍÕ±Ñl‰ÍÑ…ÑÕÌ‰t€ôô€‰	1=-ˆ•±Í”€À(()¥˜}}¹…µ•}|€ôô€‰}}µ…¥¹}|ˆè(€€€É…¥Í”MåÍÑ•µá¥Ð¡µ…¥¸ ¤¤