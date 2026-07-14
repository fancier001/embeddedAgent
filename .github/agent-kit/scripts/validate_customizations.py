#!/usr/bin/env python3
"""Validate the embedded-multi-agent repository customizations.

The validator intentionally checks product invariants rather than only parsing
YAML.  It is suitable for local preflight checks and CI on Python 3.10+.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import unquote

try:
    import yaml
    from jsonschema import Draft202012Validator
except ImportError as exc:  # pragma: no cover - exercised by the CLI environment
    print(
        "Missing validation dependencies. Run "
        "'python -m pip install -r .github/agent-kit/requirements-dev.txt'.",
        file=sys.stderr,
    )
    raise SystemExit(2) from exc


EXPECTED_AGENTS: Mapping[str, Mapping[str, Any]] = {
    "orchestrator.agent.md": {
        "name": "Orchestrator",
        "tools": ["agent", "read", "search"],
        "agents": ["EmbeddedDeveloper", "QualityReviewer", "DocKeeper"],
        "handoffs": ["BugResolver", "EmbeddedDeveloper", "QualityReviewer", "DocKeeper"],
        "disable-model-invocation": True,
    },
    "bug-resolver.agent.md": {
        "name": "BugResolver",
        "tools": ["agent", "read", "search", "execute"],
        "agents": ["EmbeddedDeveloper", "QualityReviewer", "DocKeeper"],
        "disable-model-invocation": False,
        "handoffs": ["EmbeddedDeveloper", "QualityReviewer", "DocKeeper"],
    },
    "embedded-developer.agent.md": {
        "name": "EmbeddedDeveloper",
        "tools": ["edit", "read", "search", "execute"],
        "disable-model-invocation": False,
        "handoffs": ["QualityReviewer", "DocKeeper"],
    },
    "quality-reviewer.agent.md": {
        "name": "QualityReviewer",
        "tools": ["read", "search", "execute"],
        "disable-model-invocation": False,
        "handoffs": ["EmbeddedDeveloper", "DocKeeper"],
    },
    "doc-keeper.agent.md": {
        "name": "DocKeeper",
        "tools": ["read", "search", "edit", "web"],
        "disable-model-invocation": False,
        "handoffs": ["Orchestrator"],
    },
}

EXPECTED_PROMPTS: Mapping[str, Mapping[str, str]] = {
    "new-driver.prompt.md": {
        "name": "new-driver",
        "agent": "Orchestrator",
        "skill": "embedded-driver-development",
        "input": "driver_request",
    },
    "analyze-log.prompt.md": {
        "name": "analyze-log",
        "agent": "BugResolver",
        "skill": "firmware-log-analysis",
        "input": "log_input",
    },
    "analyze-bug.prompt.md": {
        "name": "analyze-bug",
        "agent": "BugResolver",
        "input": "bug_input",
    },
    "misra-review.prompt.md": {
        "name": "misra-review",
        "agent": "QualityReviewer",
        "skill": "misra-risk-review",
        "input": "review_target",
    },
    "verify-change.prompt.md": {
        "name": "verify-change",
        "agent": "Orchestrator",
        "skill": "embedded-change-verification",
        "input": "change_target",
    },
    "implement-feature.prompt.md": {
        "name": "implement-feature",
        "agent": "Orchestrator",
        "skill": "embedded-application-development",
        "input": "feature_request",
    },
}

EXPECTED_SKILLS = frozenset(
    spec["skill"] for spec in EXPECTED_PROMPTS.values() if "skill" in spec
)
EXPECTED_SKILL_SCRIPTS: Mapping[str, frozenset[str]] = {
    "embedded-application-development": frozenset({"validate_traceability.py"}),
    "embedded-change-verification": frozenset({"profile_gates.py"}),
    "firmware-log-analysis": frozenset({"artifact_evidence.py"}),
    "misra-risk-review": frozenset({"normalize_sarif.py"}),
}
REQUIRED_AGENT_BODY_MARKERS: Mapping[str, frozenset[str]] = {
    "bug-resolver.agent.md": frozenset(
        {
            "GUIDE_SYMPTOMS",
            "CONFIRM_DIRECTION",
            "IDENTIFY_PROBLEM",
            "EVIDENCE_CHECK",
            "AWAIT_EVIDENCE",
            "## Usage Symptom Questions",
            "## Usage Symptom Profile",
            "Direction Confirmation",
            "## Problem Identification",
            "## Evidence Request",
        }
    ),
}
REQUIRED_SKILL_BODY_MARKERS: Mapping[str, frozenset[str]] = {
    "firmware-log-analysis": frozenset(
        {
            "GUIDE_SYMPTOMS",
            "CONFIRM_DIRECTION",
            "IDENTIFY_PROBLEM",
            "EVIDENCE_CHECK",
            "AWAIT_EVIDENCE",
            "Usage Symptom Questions",
            "Usage Symptom Profile",
            "Direction Confirmation",
            "Normalized Events",
            "Anomalies and Correlations",
            "Next Evidence Needed",
        }
    ),
}
KNOWN_AGENT_NAMES = frozenset(spec["name"] for spec in EXPECTED_AGENTS.values())
REQUIRED_PRODUCT_FILES = (
    ".github/agent-contracts.md",
    ".github/copilot-instructions.md",
    ".github/instructions/c-code.instructions.md",
    ".github/instructions/markdown-bilingual.instructions.md",
)

AGENT_FRONTMATTER_FIELDS = frozenset(
    {
        "name",
        "description",
        "tools",
        "agents",
        "handoffs",
        "target",
        "user-invocable",
        "disable-model-invocation",
    }
)
PROMPT_FRONTMATTER_FIELDS = frozenset(
    {"name", "description", "agent", "argument-hint"}
)
SKILL_FRONTMATTER_FIELDS = frozenset(
    {
        "name",
        "description",
        "user-invocable",
        "disable-model-invocation",
        "license",
        "compatibility",
        "metadata",
    }
)

PRODUCT_FORMS = [
    "auto",
    "bare-metal",
    "rtos",
    "module-sdk",
    "embedded-linux",
    "hybrid",
]
AUTO_OR_STRING = {"type": "string", "minLength": 1}
AUTO_OR_STRING_LIST = {
    "oneOf": [
        AUTO_OR_STRING,
        {"type": "array", "items": AUTO_OR_STRING, "minItems": 1, "uniqueItems": True},
    ]
}

PROJECT_PROFILE_SCHEMA: Mapping[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version",
        "kit_version",
        "product_form",
        "target",
        "toolchain",
        "paths",
        "commands",
        "artifacts",
        "safety",
        "misra",
        "documentation",
        "product_form_focus",
    ],
    "properties": {
        "schema_version": {"const": 1},
        "kit_version": {"type": "string", "pattern": r"^\d+\.\d+\.\d+$"},
        "product_form": {"enum": PRODUCT_FORMS},
        "target": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "mcu_soc",
                "chip_part_number",
                "board",
                "silicon_revision",
                "board_revision",
                "rtos",
                "datasheet",
            ],
            "properties": {
                "mcu_soc": AUTO_OR_STRING,
                "chip_part_number": AUTO_OR_STRING,
                "board": AUTO_OR_STRING,
                "silicon_revision": AUTO_OR_STRING,
                "board_revision": AUTO_OR_STRING,
                "rtos": AUTO_OR_STRING,
                "datasheet": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["document_id", "revision", "path_or_url"],
                    "properties": {
                        "document_id": AUTO_OR_STRING,
                        "revision": AUTO_OR_STRING,
                        "path_or_url": AUTO_OR_STRING,
                    },
                },
            },
        },
        "toolchain": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "compiler",
                "compiler_version",
                "c_standard",
                "build_system",
                "cross_compile_prefix",
            ],
            "properties": {
                "compiler": AUTO_OR_STRING,
                "compiler_version": AUTO_OR_STRING,
                "c_standard": AUTO_OR_STRING,
                "build_system": AUTO_OR_STRING,
                "cross_compile_prefix": AUTO_OR_STRING,
            },
        },
        "paths": {
            "type": "object",
            "additionalProperties": False,
            "required": ["source", "drivers", "tests", "docs", "vendor", "generated"],
            "properties": {
                "source": AUTO_OR_STRING_LIST,
                "drivers": AUTO_OR_STRING_LIST,
                "application": AUTO_OR_STRING_LIST,
                "services": AUTO_OR_STRING_LIST,
                "middleware": AUTO_OR_STRING_LIST,
                "protocols": AUTO_OR_STRING_LIST,
                "tests": AUTO_OR_STRING_LIST,
                "docs": AUTO_OR_STRING_LIST,
                "vendor": AUTO_OR_STRING_LIST,
                "generated": AUTO_OR_STRING_LIST,
            },
        },
        "commands": {
            "type": "object",
            "additionalProperties": False,
            "required": ["configure", "build", "test", "static_analysis", "hardware"],
            "properties": {
                "configure": AUTO_OR_STRING,
                "build": AUTO_OR_STRING,
                "test": AUTO_OR_STRING,
                "static_analysis": AUTO_OR_STRING,
                "hardware": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["flash", "erase", "fuse", "reset", "hil"],
                    "properties": {
                        action: {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["command", "enabled", "requires_explicit_approval"],
                            "properties": {
                                "command": AUTO_OR_STRING,
                                "enabled": {"const": False},
                                "requires_explicit_approval": {"const": True},
                            },
                        }
                        for action in ("flash", "erase", "fuse", "reset", "hil")
                    },
                },
            },
        },
        "artifacts": {
            "type": "object",
            "additionalProperties": False,
            "required": ["elf", "map", "logs", "static_analysis_reports"],
            "properties": {
                "elf": AUTO_OR_STRING_LIST,
                "map": AUTO_OR_STRING_LIST,
                "logs": AUTO_OR_STRING_LIST,
                "static_analysis_reports": AUTO_OR_STRING_LIST,
            },
        },
        "misra": {
            "type": "object",
            "additionalProperties": False,
            "required": ["standard", "version", "deviations", "compliance_claim_allowed"],
            "properties": {
                "standard": AUTO_OR_STRING,
                "version": AUTO_OR_STRING,
                "deviations": AUTO_OR_STRING,
                "compliance_claim_allowed": {"const": False},
            },
        },
        "documentation": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "language_policy",
                "chinese_section",
                "english_section",
                "todo_sync_allowed_at_release",
            ],
            "properties": {
                "language_policy": {"const": "bilingual-full"},
                "chinese_section": {"const": "## 中文 / Chinese"},
                "english_section": {"const": "## English"},
                "todo_sync_allowed_at_release": {"const": False},
            },
        },
        "safety": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "preserve_dirty_worktree",
                "allow_destructive_git",
                "allow_automatic_dependency_install",
                "allow_physical_hardware_access",
            ],
            "properties": {
                "preserve_dirty_worktree": {"const": True},
                "allow_destructive_git": {"const": False},
                "allow_automatic_dependency_install": {"const": False},
                "allow_physical_hardware_access": {"const": False},
            },
        },
        "product_form_focus": {
            "type": "object",
            "additionalProperties": False,
            "required": ["bare-metal", "rtos", "module-sdk", "embedded-linux", "hybrid"],
            "properties": {
                form: {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                    "minItems": 1,
                    "uniqueItems": True,
                }
                for form in ("bare-metal", "rtos", "module-sdk", "embedded-linux", "hybrid")
            },
        },
    },
}

TEXT_EXTENSIONS = {
    ".c",
    ".h",
    ".json",
    ".md",
    ".py",
    ".txt",
    ".yaml",
    ".yml",
}
TEXT_FILENAMES = {"CMakeLists.txt", "Makefile"}
IGNORED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "build",
    "generated",
    "node_modules",
    "vendor",
}

FRONTMATTER_END = re.compile(r"\n---[ \t]*\n")
BILINGUAL_CHINESE = re.compile(r"^## 中文 / Chinese[ \t]*$", re.MULTILINE)
BILINGUAL_ENGLISH = re.compile(r"^## English[ \t]*$", re.MULTILINE)
FENCED_CODE = re.compile(r"^(```|~~~).*?^\1[ \t]*$", re.MULTILINE | re.DOTALL)
INLINE_CODE = re.compile(
    r"(?<!`)(?P<ticks>`+)(?!`)(?P<body>[^\n]*?)(?<!`)(?P=ticks)(?!`)"
)
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
ATX_HEADING = re.compile(r"^[ ]{0,3}#{1,6}(?:[ \t]+|$)(?P<text>.*)$")
SETEXT_HEADING = re.compile(r"^[ ]{0,3}(?:=+|-+)[ \t]*$")
INLINE_LINK_LABEL = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
REFERENCE_LINK_LABEL = re.compile(r"!?\[([^\]]*)\]\[[^\]]*\]")
HTML_EXPLICIT_ANCHOR = re.compile(
    r"<[A-Za-z][^>]*\s(?:id|name)\s*=\s*(?:\"([^\"]+)\"|'([^']+)'|([^\s\"'=<>`]+))",
    re.IGNORECASE,
)
MARKDOWN_LINK = re.compile(
    r"!?\[[^\]]*\]\((?:<(?P<angle>[^>]+)>|(?P<plain>[^\s)]+))(?:\s+['\"][^'\"]*['\"])?\)"
)


def _replace_inline_code(text: str, *, preserve_content: bool) -> str:
    """Remove code spans, or unwrap their content when building heading slugs."""

    replacement = (lambda match: match.group("body")) if preserve_content else ""
    return INLINE_CODE.sub(replacement, text)


def _without_frontmatter(text: str) -> str:
    """Remove leading YAML frontmatter so it cannot become a Setext heading."""

    if not text.startswith("---\n"):
        return text
    match = FRONTMATTER_END.search(text, 4)
    return text[match.end() :] if match is not None else text


def _github_heading_slug(heading: str) -> str:
    """Return the common GitHub/VS Code slug for one Markdown heading."""

    value = _replace_inline_code(heading, preserve_content=True)
    value = INLINE_LINK_LABEL.sub(r"\1", value)
    value = REFERENCE_LINK_LABEL.sub(r"\1", value)
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value).strip().lower()

    kept: list[str] = []
    for character in value:
        category = unicodedata.category(character)
        if character.isspace():
            kept.append(" ")
        elif character in "-_" or character.isalnum() or category.startswith("M"):
            kept.append(character)
    return re.sub(r"\s+", "-", "".join(kept))


@dataclass(frozen=True, order=True)
class Diagnostic:
    """A stable, testable validation diagnostic."""

    path: str
    code: str
    message: str


class RepositoryValidator:
    """Validate one repository root and return all detected problems."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()
        self.diagnostics: list[Diagnostic] = []
        self._text_cache: dict[Path, str | None] = {}
        self._markdown_anchor_cache: dict[Path, set[str] | None] = {}

    def validate(self) -> list[Diagnostic]:
        if not self.root.is_dir():
            self._add(self.root, "ROOT_MISSING", "repository root is not a directory")
            return self.diagnostics

        self._validate_text_hygiene()
        self._validate_required_files()
        self._validate_agents()
        self._validate_skills()
        self._validate_prompts()
        self._validate_profile()
        self._validate_bilingual_markdown()
        self._validate_markdown_links()
        return sorted(set(self.diagnostics))

    def _relative(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.root).as_posix()
        except ValueError:
            return str(path)

    def _add(self, path: Path, code: str, message: str) -> None:
        self.diagnostics.append(Diagnostic(self._relative(path), code, message))

    def _read_text(self, path: Path) -> str | None:
        if path in self._text_cache:
            return self._text_cache[path]
        try:
            raw = path.read_bytes()
        except OSError as exc:
            self._add(path, "FILE_READ", str(exc))
            self._text_cache[path] = None
            return None
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            self._add(path, "TEXT_UTF8", f"not valid UTF-8: {exc}")
            self._text_cache[path] = None
            return None
        if text.startswith("\ufeff"):
            self._add(path, "TEXT_BOM", "UTF-8 BOM is not allowed")
            text = text.removeprefix("\ufeff")
        if "\r" in text:
            self._add(path, "TEXT_LF", "use LF line endings; CR or CRLF was found")
        self._text_cache[path] = text
        return text

    def _iter_files(self) -> Iterable[Path]:
        for path in self.root.rglob("*"):
            if not path.is_file():
                continue
            try:
                relative_parts = path.relative_to(self.root).parts
            except ValueError:
                continue
            if any(part in IGNORED_DIRS for part in relative_parts[:-1]):
                continue
            yield path

    def _iter_text_files(self) -> Iterable[Path]:
        for path in self._iter_files():
            if path.suffix.lower() in TEXT_EXTENSIONS or path.name in TEXT_FILENAMES:
                yield path

    def _validate_text_hygiene(self) -> None:
        for path in self._iter_text_files():
            self._read_text(path)

    def _validate_required_files(self) -> None:
        for relative in REQUIRED_PRODUCT_FILES:
            path = self.root / relative
            if not path.is_file():
                self._add(path, "REQUIRED_FILE", "required product file is missing")

    def _frontmatter(self, path: Path) -> tuple[dict[str, Any] | None, str]:
        text = self._read_text(path)
        if text is None:
            return None, ""
        if not text.startswith("---\n"):
            self._add(path, "FRONTMATTER_MISSING", "file must start with YAML frontmatter")
            return None, text
        match = FRONTMATTER_END.search(text, 4)
        if match is None:
            self._add(path, "FRONTMATTER_END", "frontmatter closing delimiter is missing")
            return None, text
        source = text[4 : match.start()]
        try:
            value = yaml.safe_load(source)
        except yaml.YAMLError as exc:
            self._add(path, "FRONTMATTER_YAML", f"invalid YAML: {exc}")
            return None, text[match.end() :]
        if not isinstance(value, dict):
            self._add(path, "FRONTMATTER_TYPE", "frontmatter must be a YAML mapping")
            return None, text[match.end() :]
        return value, text[match.end() :]

    def _check_frontmatter_fields(
        self, path: Path, data: Mapping[str, Any], allowed: frozenset[str]
    ) -> None:
        unknown = sorted(set(data) - allowed)
        if unknown:
            self._add(
                path,
                "FRONTMATTER_FIELD",
                f"unsupported frontmatter field(s): {', '.join(unknown)}",
            )
        if "model" in data:
            self._add(path, "MODEL_PINNED", "agent kit must not pin a model")

    def _validate_agents(self) -> None:
        agents_dir = self.root / ".github" / "agents"
        # VS Code treats every Markdown file in .github/agents as an agent.  The
        # product therefore rejects even a harmless-looking notes.md instead of
        # limiting this check to the conventional *.agent.md suffix.
        found = {path.name for path in agents_dir.glob("*.md")} if agents_dir.is_dir() else set()
        expected = set(EXPECTED_AGENTS)
        if found != expected:
            missing = sorted(expected - found)
            extra = sorted(found - expected)
            detail = []
            if missing:
                detail.append(f"missing: {', '.join(missing)}")
            if extra:
                detail.append(f"unexpected: {', '.join(extra)}")
            self._add(agents_dir, "AGENT_SET", "; ".join(detail) or "agent set differs")

        for filename, spec in EXPECTED_AGENTS.items():
            path = agents_dir / filename
            if not path.is_file():
                continue
            data, body = self._frontmatter(path)
            if data is None:
                continue
            self._check_frontmatter_fields(path, data, AGENT_FRONTMATTER_FIELDS)
            for required in ("name", "description", "tools", "target", "user-invocable", "disable-model-invocation"):
                if required not in data:
                    self._add(path, "AGENT_REQUIRED", f"missing required field: {required}")
            if data.get("name") != spec["name"]:
                self._add(path, "AGENT_NAME", f"name must be {spec['name']!r}")
            if not isinstance(data.get("description"), str) or not data.get("description", "").strip():
                self._add(path, "AGENT_DESCRIPTION", "description must be a non-empty string")
            if data.get("tools") != spec["tools"]:
                self._add(path, "AGENT_TOOLS", f"tools must be exactly {spec['tools']!r}")
            if data.get("target") != "vscode":
                self._add(path, "AGENT_TARGET", "target must be 'vscode'")
            if data.get("user-invocable") is not True:
                self._add(path, "AGENT_INVOCABLE", "user-invocable must be true")
            if data.get("disable-model-invocation") is not spec["disable-model-invocation"]:
                self._add(
                    path,
                    "AGENT_MODEL_INVOCATION",
                    "disable-model-invocation does not match the five-agent policy",
                )

            if "agents" in spec:
                if data.get("agents") != spec["agents"]:
                    self._add(
                        path,
                        "AGENT_ALLOWLIST",
                        f"agents must be exactly {spec['agents']!r}",
                    )
            elif "agents" in data:
                self._add(
                    path,
                    "AGENT_NESTING",
                    "non-delegating specialists must not declare an agents allowlist",
                )

            for marker in sorted(REQUIRED_AGENT_BODY_MARKERS.get(filename, frozenset())):
                if marker not in body:
                    self._add(
                        path,
                        "AGENT_BODY_CONTRACT",
                        f"agent body must contain behavior marker {marker!r}",
                    )

            handoffs = data.get("handoffs", [])
            if not isinstance(handoffs, list):
                self._add(path, "HANDOFF_TYPE", "handoffs must be a list")
                continue
            actual_targets = [
                handoff.get("agent")
                for handoff in handoffs
                if isinstance(handoff, dict)
            ]
            if actual_targets != spec["handoffs"]:
                self._add(
                    path,
                    "HANDOFF_SET",
                    f"handoff agents must be exactly {spec['handoffs']!r}",
                )
            for index, handoff in enumerate(handoffs):
                location = f"handoffs[{index}]"
                if not isinstance(handoff, dict):
                    self._add(path, "HANDOFF_TYPE", f"{location} must be a mapping")
                    continue
                required_handoff = {"label", "agent", "prompt", "send"}
                missing = required_handoff - set(handoff)
                if missing:
                    self._add(
                        path,
                        "HANDOFF_REQUIRED",
                        f"{location} missing: {', '.join(sorted(missing))}",
                    )
                if handoff.get("agent") not in KNOWN_AGENT_NAMES:
                    self._add(
                        path,
                        "AGENT_REFERENCE",
                        f"{location} references unknown agent {handoff.get('agent')!r}",
                    )
                if handoff.get("send") is not False:
                    self._add(path, "HANDOFF_SEND", f"{location}.send must be false")

    def _validate_skills(self) -> None:
        skills_dir = self.root / ".github" / "skills"
        found = (
            {path.parent.name for path in skills_dir.glob("*/SKILL.md")}
            if skills_dir.is_dir()
            else set()
        )
        if found != EXPECTED_SKILLS:
            missing = sorted(EXPECTED_SKILLS - found)
            extra = sorted(found - EXPECTED_SKILLS)
            details = []
            if missing:
                details.append(f"missing: {', '.join(missing)}")
            if extra:
                details.append(f"unexpected: {', '.join(extra)}")
            self._add(skills_dir, "SKILL_SET", "; ".join(details) or "skill set differs")

        for name in sorted(EXPECTED_SKILLS):
            path = skills_dir / name / "SKILL.md"
            if not path.is_file():
                continue
            data, body = self._frontmatter(path)
            if data is None:
                continue
            self._check_frontmatter_fields(path, data, SKILL_FRONTMATTER_FIELDS)
            if data.get("name") != name:
                self._add(path, "SKILL_NAME", f"name must match directory: {name!r}")
            if not isinstance(data.get("description"), str) or not data.get("description", "").strip():
                self._add(path, "SKILL_DESCRIPTION", "description must be a non-empty string")
            if data.get("user-invocable") is not False:
                self._add(path, "SKILL_INVOCABLE", "user-invocable must be false")
            if "context" in data:
                self._add(path, "SKILL_CONTEXT", "experimental context: fork is not supported")

            for marker in sorted(REQUIRED_SKILL_BODY_MARKERS.get(name, frozenset())):
                if marker not in body:
                    self._add(
                        path,
                        "SKILL_BODY_CONTRACT",
                        f"skill body must contain behavior marker {marker!r}",
                    )

            expected_scripts = EXPECTED_SKILL_SCRIPTS.get(name, frozenset())
            scripts_dir = path.parent / "scripts"
            found_scripts = (
                {script.name for script in scripts_dir.glob("*.py")}
                if scripts_dir.is_dir()
                else set()
            )
            if found_scripts != expected_scripts:
                missing_scripts = sorted(expected_scripts - found_scripts)
                extra_scripts = sorted(found_scripts - expected_scripts)
                details = []
                if missing_scripts:
                    details.append(f"missing: {', '.join(missing_scripts)}")
                if extra_scripts:
                    details.append(f"unexpected: {', '.join(extra_scripts)}")
                self._add(
                    scripts_dir,
                    "SKILL_SCRIPT_SET",
                    "; ".join(details) or "skill script set differs",
                )

    def _validate_prompts(self) -> None:
        prompts_dir = self.root / ".github" / "prompts"
        found = {path.name for path in prompts_dir.glob("*.prompt.md")} if prompts_dir.is_dir() else set()
        expected = set(EXPECTED_PROMPTS)
        if found != expected:
            missing = sorted(expected - found)
            extra = sorted(found - expected)
            details = []
            if missing:
                details.append(f"missing: {', '.join(missing)}")
            if extra:
                details.append(f"unexpected: {', '.join(extra)}")
            self._add(prompts_dir, "PROMPT_SET", "; ".join(details) or "prompt set differs")

        for filename, spec in EXPECTED_PROMPTS.items():
            path = prompts_dir / filename
            if not path.is_file():
                continue
            data, body = self._frontmatter(path)
            if data is None:
                continue
            self._check_frontmatter_fields(path, data, PROMPT_FRONTMATTER_FIELDS)
            for required in ("name", "description", "agent", "argument-hint"):
                if required not in data:
                    self._add(path, "PROMPT_REQUIRED", f"missing required field: {required}")
            if data.get("name") != spec["name"]:
                self._add(path, "PROMPT_NAME", f"name must be {spec['name']!r}")
            if data.get("agent") != spec["agent"]:
                self._add(path, "PROMPT_AGENT", f"agent must be {spec['agent']!r}")
            if not isinstance(data.get("description"), str) or not data.get("description", "").strip():
                self._add(path, "PROMPT_DESCRIPTION", "description must be a non-empty string")
            if not isinstance(data.get("argument-hint"), str) or not data.get("argument-hint", "").strip():
                self._add(path, "PROMPT_ARGUMENT", "argument-hint must be a non-empty string")

            if "skill" in spec:
                skill_path = f"../skills/{spec['skill']}/SKILL.md"
                if skill_path not in body:
                    self._add(
                        path,
                        "PROMPT_SKILL",
                        f"prompt must link to its canonical skill: {skill_path}",
                    )
            input_marker = "${input:" + spec["input"] + "}"
            if input_marker not in body:
                self._add(
                    path,
                    "PROMPT_INPUT",
                    f"prompt must use input key {spec['input']!r}",
                )

    def _validate_profile(self) -> None:
        path = self.root / ".github" / "embedded-project.yml"
        text = self._read_text(path) if path.is_file() else None
        if text is None:
            if not path.is_file():
                self._add(path, "PROFILE_MISSING", "project profile is required")
            return
        try:
            profile = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            self._add(path, "PROFILE_YAML", f"invalid YAML: {exc}")
            return
        errors = sorted(
            Draft202012Validator(PROJECT_PROFILE_SCHEMA).iter_errors(profile),
            key=lambda error: [str(part) for part in error.absolute_path],
        )
        for error in errors:
            location = ".".join(str(part) for part in error.absolute_path) or "<root>"
            self._add(path, "PROFILE_SCHEMA", f"{location}: {error.message}")

    def _markdown_files(self) -> Iterable[Path]:
        readme = self.root / "README.md"
        if readme.is_file():
            yield readme
        for base in (self.root / ".github", self.root / "docs", self.root / "examples"):
            if not base.is_dir():
                continue
            for path in base.rglob("*.md"):
                relative_parts = path.relative_to(self.root).parts
                if (
                    relative_parts[:2] == (".github", "agent-kit")
                    or any(part in IGNORED_DIRS for part in relative_parts[:-1])
                ):
                    continue
                yield path

    def _validate_bilingual_markdown(self) -> None:
        for path in sorted(set(self._markdown_files())):
            text = self._read_text(path)
            if text is None:
                continue
            chinese = BILINGUAL_CHINESE.search(text)
            english = BILINGUAL_ENGLISH.search(text)
            if chinese is None or english is None:
                self._add(
                    path,
                    "BILINGUAL_SECTIONS",
                    "requires '## 中文 / Chinese' followed by '## English'",
                )
            elif chinese.start() >= english.start():
                self._add(path, "BILINGUAL_ORDER", "Chinese section must precede English")
            else:
                chinese_body = text[chinese.end() : english.start()].strip()
                english_body = text[english.end() :].strip()
                if not chinese_body or not english_body:
                    self._add(path, "BILINGUAL_EMPTY", "both language sections must be non-empty")

            prose = FENCED_CODE.sub("", text)
            prose = INLINE_CODE.sub("", prose)
            if re.search(r"TODO\s*\(sync\)", prose, flags=re.IGNORECASE):
                self._add(path, "TODO_SYNC", "unresolved TODO(sync) marker in prose")

    def _markdown_anchors(self, path: Path) -> set[str] | None:
        """Collect generated heading slugs and explicit HTML anchors."""

        cache_key = path.resolve()
        if cache_key in self._markdown_anchor_cache:
            return self._markdown_anchor_cache[cache_key]
        text = self._read_text(path)
        if text is None:
            self._markdown_anchor_cache[cache_key] = None
            return None

        source = _without_frontmatter(text)
        source = FENCED_CODE.sub("", source)
        source = HTML_COMMENT.sub("", source)
        lines = source.splitlines()
        anchors: set[str] = set()
        next_suffix: dict[str, int] = {}

        def add_heading(heading: str) -> None:
            base = _github_heading_slug(heading)
            if not base:
                return
            candidate = base
            suffix = next_suffix.get(base, 1)
            while candidate in anchors:
                candidate = f"{base}-{suffix}"
                suffix += 1
            next_suffix[base] = suffix
            anchors.add(candidate)

        index = 0
        while index < len(lines):
            line = lines[index]
            atx = ATX_HEADING.match(line)
            if atx is not None:
                heading = re.sub(r"[ \t]+#+[ \t]*$", "", atx.group("text"))
                add_heading(heading)
                index += 1
                continue
            if (
                line.strip()
                and index + 1 < len(lines)
                and SETEXT_HEADING.match(lines[index + 1]) is not None
            ):
                add_heading(line.strip())
                index += 2
                continue
            index += 1

        html_source = _replace_inline_code(source, preserve_content=False)
        for match in HTML_EXPLICIT_ANCHOR.finditer(html_source):
            explicit = next((group for group in match.groups() if group), "")
            explicit = html.unescape(explicit).strip()
            if explicit:
                anchors.add(explicit)

        self._markdown_anchor_cache[cache_key] = anchors
        return anchors

    def _validate_markdown_links(self) -> None:
        for path in sorted(set(self._markdown_files())):
            text = self._read_text(path)
            if text is None:
                continue
            link_source = FENCED_CODE.sub("", text)
            link_source = _replace_inline_code(link_source, preserve_content=False)
            for match in MARKDOWN_LINK.finditer(link_source):
                destination = (match.group("angle") or match.group("plain") or "").strip()
                lowered = destination.lower()
                if not destination:
                    continue
                if lowered.startswith(("http://", "https://", "mailto:", "data:", "vscode:")):
                    continue
                if destination.startswith("${"):
                    continue
                target, separator, raw_fragment = destination.partition("#")
                local = unquote(target.split("?", 1)[0])
                candidate = (
                    path
                    if not local
                    else (self.root / local.lstrip("/"))
                    if local.startswith("/")
                    else (path.parent / local)
                )
                resolved = candidate.resolve()
                try:
                    resolved.relative_to(self.root)
                except ValueError:
                    self._add(path, "LINK_OUTSIDE", f"link leaves repository: {destination}")
                    continue
                if not resolved.exists():
                    self._add(path, "LINK_MISSING", f"local link target does not exist: {destination}")
                    continue
                if (
                    separator
                    and raw_fragment
                    and not match.group(0).startswith("!")
                    and resolved.is_file()
                    and resolved.suffix.lower() == ".md"
                ):
                    fragment = unquote(raw_fragment)
                    anchors = self._markdown_anchors(resolved)
                    if anchors is not None and fragment not in anchors:
                        self._add(
                            path,
                            "LINK_ANCHOR_MISSING",
                            f"local Markdown anchor does not exist: {destination}",
                        )


def validate_repository(root: Path | str) -> list[Diagnostic]:
    """Public API used by unit tests and integrations."""

    return RepositoryValidator(root).validate()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[3],
        help="repository root (defaults to the parent of .github/)",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        dest="output_format",
        help="diagnostic output format",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    diagnostics = validate_repository(args.root)
    if args.output_format == "json":
        print(json.dumps([asdict(item) for item in diagnostics], ensure_ascii=False, indent=2))
    elif diagnostics:
        for item in diagnostics:
            print(f"{item.path}: [{item.code}] {item.message}")
        print(f"Validation failed with {len(diagnostics)} diagnostic(s).", file=sys.stderr)
    else:
        print("embedded-multi-agent configuration is valid.")
    return 1 if diagnostics else 0


if __name__ == "__main__":
    raise SystemExit(main())
