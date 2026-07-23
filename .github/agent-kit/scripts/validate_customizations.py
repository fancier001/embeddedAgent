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
        "'python -m pip install -r tests/agent-kit/requirements.txt'.",
        file=sys.stderr,
    )
    raise SystemExit(2) from exc


EXPECTED_AGENTS: Mapping[str, Mapping[str, Any]] = {
    "orchestrator.agent.md": {
        "name": "Orchestrator",
        "tools": ["agent", "read", "search"],
        "agents": ["EmbeddedDeveloper", "QualityReviewer", "DocKeeper"],
        "handoffs": ["BugResolver", "EmbeddedDeveloper", "QualityReviewer", "DocKeeper", "NextActionRouter"],
        "user-invocable": True,
        "disable-model-invocation": True,
    },
    "bug-resolver.agent.md": {
        "name": "BugResolver",
        "tools": ["agent", "read", "search", "execute"],
        "agents": ["EmbeddedDeveloper", "QualityReviewer", "DocKeeper"],
        "handoffs": ["EmbeddedDeveloper", "QualityReviewer", "DocKeeper", "EmbeddedDeveloper", "NextActionRouter"],
        "user-invocable": True,
        "disable-model-invocation": False,
    },
    "embedded-developer.agent.md": {
        "name": "EmbeddedDeveloper",
        "tools": ["edit", "read", "search", "execute"],
        "handoffs": ["QualityReviewer", "DocKeeper", "BugResolver", "NextActionRouter"],
        "user-invocable": True,
        "disable-model-invocation": False,
    },
    "quality-reviewer.agent.md": {
        "name": "QualityReviewer",
        "tools": ["read", "search", "execute"],
        "handoffs": ["EmbeddedDeveloper", "DocKeeper", "EmbeddedDeveloper", "NextActionRouter"],
        "user-invocable": True,
        "disable-model-invocation": False,
    },
    "doc-keeper.agent.md": {
        "name": "DocKeeper",
        "tools": ["read", "search", "edit", "web"],
        "handoffs": ["Orchestrator", "EmbeddedDeveloper", "NextActionRouter"],
        "user-invocable": True,
        "disable-model-invocation": False,
    },
    "next-action-router.agent.md": {
        "name": "NextActionRouter",
        "tools": ["agent", "read", "search"],
        "agents": ["Orchestrator", "BugResolver", "EmbeddedDeveloper", "QualityReviewer", "DocKeeper"],
        "handoffs": ["Orchestrator", "BugResolver", "EmbeddedDeveloper", "QualityReviewer", "DocKeeper"],
        "user-invocable": False,
        "disable-model-invocation": True,
    },
}
EXPECTED_HANDOFFS: Mapping[str, tuple[tuple[str, str], ...]] = {
    "orchestrator.agent.md": (
        ("Bug 分析与解决 / Diagnose and Resolve Bug", "BugResolver"),
        ("实现变更 / Implement", "EmbeddedDeveloper"),
        ("独立评审 / Review", "QualityReviewer"),
        ("文档沉淀 / Document", "DocKeeper"),
        ("执行下一步 / Next Action", "NextActionRouter"),
    ),
    "bug-resolver.agent.md": (
        ("实施修复 / Implement Fix", "EmbeddedDeveloper"),
        ("质量评估 / Quality Assessment", "QualityReviewer"),
        ("记录结论 / Document Resolution", "DocKeeper"),
        ("Git 提交交付 / Git Delivery", "EmbeddedDeveloper"),
        ("执行下一步 / Next Action", "NextActionRouter"),
    ),
    "embedded-developer.agent.md": (
        ("独立评审 / Quality Review", "QualityReviewer"),
        ("文档同步 / Document Changes", "DocKeeper"),
        ("问题已解决 / Close Issue", "BugResolver"),
        ("执行下一步 / Next Action", "NextActionRouter"),
    ),
    "quality-reviewer.agent.md": (
        ("修复问题 / Fix Issues", "EmbeddedDeveloper"),
        ("沉淀质量结论 / Document Quality Findings", "DocKeeper"),
        ("Git 提交交付 / Git Delivery", "EmbeddedDeveloper"),
        ("执行下一步 / Next Action", "NextActionRouter"),
    ),
    "doc-keeper.agent.md": (
        ("返回编排 / Resolve Conflict", "Orchestrator"),
        ("Git 提交交付 / Git Delivery", "EmbeddedDeveloper"),
        ("执行下一步 / Next Action", "NextActionRouter"),
    ),
    "next-action-router.agent.md": (
        ("返回编排 / Return to Orchestrator", "Orchestrator"),
        ("返回问题解决 / Return to Bug Resolver", "BugResolver"),
        ("返回实施 / Return to Embedded Developer", "EmbeddedDeveloper"),
        ("返回评审 / Return to Quality Reviewer", "QualityReviewer"),
        ("返回文档 / Return to Doc Keeper", "DocKeeper"),
    ),
}
NEXT_ACTION_IDS = (
    "CONFIRM_DIRECTION",
    "PROVIDE_EVIDENCE",
    "IMPLEMENT_FIX",
    "FIX_FINDINGS",
    "QUALITY_REVIEW",
    "DOCUMENT_CHANGES",
    "GIT_DELIVERY",
    "CONFIRM_COMMIT",
    "ADJUST_CHANGESET",
    "CONFIRM_PUSH",
    "MANUAL_PUSH",
    "CLOSE_ISSUE",
    "START_NEW_ISSUE",
    "NONE",
)
NEXT_ACTION_ROUTES = (
    "NEXT_ACTION_BUTTON",
    "CURRENT_INPUT",
    "EXTERNAL",
    "NONE",
)
NEXT_ACTION_DISPATCH_TARGETS = (
    "HANDOFF:ORCHESTRATOR",
    "HANDOFF:BUG_RESOLVER",
    "HANDOFF:EMBEDDED_DEVELOPER",
    "HANDOFF:QUALITY_REVIEWER",
    "HANDOFF:DOC_KEEPER",
    "AGENT_CONTINUE",
    "NONE",
)

BUSINESS_AGENT_FILES = frozenset(
    {
        "orchestrator.agent.md",
        "bug-resolver.agent.md",
        "embedded-developer.agent.md",
        "quality-reviewer.agent.md",
        "doc-keeper.agent.md",
    }
)
NEXT_ACTION_HANDOFF_LABEL = "执行下一步 / Next Action"
NEXT_ACTION_HANDOFF_AGENT = "NextActionRouter"
NEXT_ACTION_SOURCE_AGENTS = {
    "orchestrator.agent.md": "Orchestrator",
    "bug-resolver.agent.md": "BugResolver",
    "embedded-developer.agent.md": "EmbeddedDeveloper",
    "quality-reviewer.agent.md": "QualityReviewer",
    "doc-keeper.agent.md": "DocKeeper",
}
NEXT_ACTION_HANDOFF_PROMPT_MARKERS = (
    "Source Agent:",
    "latest unique structured Next Action",
    "safe routing or role transition only",
    "supplies no missing input",
    "confirms no commit, push, or external command",
)
ROUTER_AGENT_FILE = "next-action-router.agent.md"
ROUTER_FALLBACK_PROMPT_MARKERS = (
    "Manually return from NextActionRouter",
    "Revalidate the latest unique Next Action",
    "otherwise return BLOCKED",
    "supplies no missing input",
    "confirms no commit, push, or external command",
)

GIT_DELIVERY_HANDOFF_LABEL = "Git 提交交付 / Git Delivery"
CLOSE_ISSUE_HANDOFF_LABEL = "问题已解决 / Close Issue"
GIT_DELIVERY_HANDOFF_AGENTS = frozenset(
    {"bug-resolver.agent.md", "quality-reviewer.agent.md", "doc-keeper.agent.md"}
)
GIT_DELIVERY_HANDOFF_PROMPT_MARKERS = (
    "recommended default",
    "user-supplied Jira ID",
    "generate every other commit field",
    "current input box",
    "execute directly as the current EmbeddedDeveloper",
    "never delegate to yourself",
    "Task Change Baseline",
    "Task Change Ledger",
    "DETECT_COMMIT_SCOPE",
    "Commit Content",
    "ADJUST_CHANGESET",
    "Change Confirmation: PENDING",
    "CONFIRM_PUSH",
    "MANUAL_PUSH",
)
CLOSE_ISSUE_HANDOFF_PROMPT_MARKERS = (
    "Recheck",
    "repair",
    "selected Git delivery",
    "clear issue-level state",
    "fresh issue INTAKE",
    "otherwise return BLOCKED",
    "Next Action",
)

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
    "orchestrator.agent.md": frozenset(
        {
            ".github/agent-contracts.md",
            ".project/project.yml",
            "`PREFLIGHT`",
            "`PLAN`",
            "`IMPLEMENT`",
            "`VERIFY`",
            "`REVIEW`",
            "`DOCUMENT`",
            "`DELIVERY`",
            "Task Change Baseline",
            "Chat Language",
            "CHAT LANGUAGE OUTPUT GATE",
            "FIRST-RESPONSE PRECHECK",
            "NEXT ACTION LANGUAGE RENDER GATE",
        }
    ),
    "bug-resolver.agent.md": frozenset(
        {
            ".github/agent-contracts.md",
            "CLOSE → RESET → INTAKE",
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
            "`PLAN_FIX`",
            "Task Change Baseline",
            "`Root Cause`",
            "Chat Language",
            "CHAT LANGUAGE OUTPUT GATE",
            "FIRST-RESPONSE PRECHECK",
            "NEXT ACTION LANGUAGE RENDER GATE",
        }
    ),
    "embedded-developer.agent.md": frozenset(
        {
            ".github/agent-contracts.md",
            ".project/project.yml",
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
            "Chat Language",
            "CHAT LANGUAGE OUTPUT GATE",
            "FIRST-RESPONSE PRECHECK",
            "NEXT ACTION LANGUAGE RENDER GATE",
        }
    ),
    "quality-reviewer.agent.md": frozenset(
        {
            ".github/agent-contracts.md",
            "Review Finding",
            "`BLOCKER`",
            "`MAJOR`",
            "`MINOR`",
            "`REPORT`",
            "Chat Language",
            "CHAT LANGUAGE OUTPUT GATE",
            "FIRST-RESPONSE PRECHECK",
            "NEXT ACTION LANGUAGE RENDER GATE",
        }
    ),
    "doc-keeper.agent.md": frozenset(
        {
            ".github/agent-contracts.md",
            ".project/",
            "`RECEIVED`",
            "`REPORT`",
            "Documentation",
            "Chat Language",
            "CHAT LANGUAGE OUTPUT GATE",
            "FIRST-RESPONSE PRECHECK",
            "NEXT ACTION LANGUAGE RENDER GATE",
        }
    ),
    "next-action-router.agent.md": frozenset(
        {
            "Source Agent",
            "latest unique complete `## Next Action`",
            "NEXT_ACTION_BUTTON",
            "Dispatch Target",
            "CURRENT_INPUT",
            "Input Required",
            "Reply Template",
            "EXTERNAL",
            "at most eight consecutive actions",
            "never confirms Jira",
            "no edit or command-execution capability",
            "five static `send: false` return handoffs",
            "Chat Language",
            "CHAT LANGUAGE OUTPUT GATE",
            "FIRST-RESPONSE PRECHECK",
            "NEXT ACTION LANGUAGE RENDER GATE",
        }
    ),
}
REQUIRED_PROMPT_BODY_MARKERS: Mapping[str, frozenset[str]] = {
    "analyze-bug.prompt.md": frozenset(
        {
            ".github/agent-contracts.md",
            "read-only by default",
            "does not duplicate",
        }
    ),
    "analyze-log.prompt.md": frozenset(
        {
            ".github/agent-contracts.md",
            "read-only by default",
            "does not duplicate",
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
    ".github/agent-kit/scripts/project_policy.py",
)
REQUIRED_TEST_FILES = (
    "tests/agent-kit/requirements.txt",
    "tests/agent-kit/test_project_policy.py",
    "tests/agent-kit/test_skill_scripts.py",
    "tests/agent-kit/test_validate_customizations.py",
    "tests/agent-kit/manual/vscode-smoke-test.md",
)
REQUIRED_SHARED_CONTRACT_MARKERS = frozenset(
    {
        "## Next Action",
        "- UI Route:",
        "- Chat Language:",
        "- Dispatch Target:",
        "- Input Required:",
        "- Required Input:",
        "- Reply Template:",
        "- Instruction:",
        "NEXT_ACTION_BUTTON",
        "CURRENT_INPUT",
        "HANDOFF:QUALITY_REVIEWER",
        "AGENT_CONTINUE",
        "EXTERNAL",
        "`ADJUST_CHANGESET`",
        "Change Confirmation: PENDING",
        "confirm changes and commit",
        "per-file `entries`",
        "`CONFIRM_PUSH`",
        "`MANUAL_PUSH`",
        "`START_NEW_ISSUE`",
        "NOT_RUN — Not required: <reason>",
        "`CONFIRM_COMMIT_CONTENT`",
        "--expected-content-fingerprint",
        "content_confirmation.status: CONFIRMED",
        "Commit Content Confirmation: PENDING",
        "返回编排 / Return to Orchestrator",
        "five static fallback handoffs",
        "在输出首个字符之前",
        "Before emitting the first character",
        "Latin-script natural-language words",
        "discard the draft and regenerate",
        "handoff prompt、按钮、Router prompt",
        "handoff prompts, buttons, Router prompts",
        "zero Han-script characters",
        "Never copy a bilingual button label",
        "Next Action has a separate language-rendering gate",
        "no Han, CJK punctuation, or fullwidth characters",
        "the `START_NEW_ISSUE` values above are mandatory",
    }
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

PROJECT_DIRECTORY_SCHEMA: Mapping[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": ["schema_version", "project", "rules", "git_policy", "extensions"],
    "properties": {
        "schema_version": {"const": 1},
        "project": {
            "type": "object",
            "additionalProperties": False,
            "required": ["primary", "aliases"],
            "properties": {
                "primary": {"type": "string", "minLength": 1},
                "aliases": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                    "uniqueItems": True,
                },
            },
        },
        "rules": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "path", "applies_to", "required"],
                "properties": {
                    "id": {
                        "type": "string",
                        "pattern": r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
                    },
                    "path": {"type": "string", "pattern": r"^.+\.md$"},
                    "applies_to": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1},
                        "minItems": 1,
                        "uniqueItems": True,
                    },
                    "required": {"type": "boolean"},
                },
            },
            "minItems": 1,
        },
        "git_policy": {"type": "string", "pattern": r"^.+\.ya?ml$"},
        # Project-owned integrations may add namespaced data without changing
        # the core loader contract or the validator schema.
        "extensions": {"type": "object", "additionalProperties": True},
    },
}

PATH_GLOB_LIST: Mapping[str, Any] = {
    "type": "array",
    "items": {"type": "string", "minLength": 1},
    "uniqueItems": True,
}
NON_EMPTY_PATH_GLOB_LIST: Mapping[str, Any] = {
    **PATH_GLOB_LIST,
    "minItems": 1,
}

GIT_DELIVERY_POLICY_SCHEMA: Mapping[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version",
        "automation",
        "scope",
        "commit",
        "push",
        "safety",
        "extensions",
    ],
    "properties": {
        "schema_version": {"const": 1},
        "automation": {
            "type": "object",
            "additionalProperties": False,
            "required": ["commit", "push"],
            "properties": {
                "commit": {"type": "boolean"},
                "push": {"type": "boolean"},
            },
        },
        "scope": {
            "type": "object",
            "additionalProperties": False,
            "required": ["denied_paths"],
            "properties": {
                "allowed_paths": NON_EMPTY_PATH_GLOB_LIST,
                "denied_paths": NON_EMPTY_PATH_GLOB_LIST,
            },
        },
        "commit": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "template",
                "change_types",
                "jira_pattern",
                "ai_scenarios",
                "checks",
            ],
            "properties": {
                "template": {"type": "string", "pattern": r"^.+$"},
                "change_types": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                    "minItems": 1,
                    "uniqueItems": True,
                },
                "jira_pattern": {"type": "string", "minLength": 1},
                "ai_scenarios": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                    "minItems": 1,
                    "uniqueItems": True,
                },
                "checks": PATH_GLOB_LIST,
            },
        },
        "push": {
            "type": "object",
            "additionalProperties": False,
            "required": ["allowed_branches", "protected_branches", "checks"],
            "properties": {
                "allowed_branches": NON_EMPTY_PATH_GLOB_LIST,
                "protected_branches": NON_EMPTY_PATH_GLOB_LIST,
                "checks": PATH_GLOB_LIST,
            },
        },
        "safety": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "require_task_authorization",
                "explicit_staging",
                "allow_force_push",
            ],
            "properties": {
                "require_task_authorization": {"const": True},
                "explicit_staging": {"const": True},
                "allow_force_push": {"const": False},
            },
        },
        "extensions": {"type": "object", "additionalProperties": True},
    },
}

FORBIDDEN_GIT_TARGET_KEYS = frozenset(
    {"remote", "url", "push_url", "pushurl", "target_branch", "target_ref"}
)
COMMIT_TEMPLATE_FIELD_ORDER = (
    "Change Type",
    "Change Reason",
    "Root Cause",
    "Solution",
    "Jira ID",
    "AI-Tool-Used",
    "AI-Tool-Scenario",
    "AI-Tool-Detail",
    "Affected Function Name",
    "Applicable Project",
    "RN",
    "RN description",
    "<<<Test Notes>>>",
    "Test-Proposal",
    "Stress-Test",
    "HW-Test",
)
COMMIT_TEMPLATE_AI_DEFAULTS = (
    "<AI-Tool-Used>: N",
    "<AI-Tool-Scenario>: /",
    "<AI-Tool-Detail>: /",
)

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
        self._validate_shared_contract()
        self._validate_agents()
        self._validate_skills()
        self._validate_prompts()
        self._validate_profile()
        self._validate_project_directory()
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
        for relative in REQUIRED_TEST_FILES:
            path = self.root / relative
            if not path.is_file():
                self._add(path, "REQUIRED_TEST_FILE", "required test file is missing")
        legacy_tests = self.root / ".github" / "agent-kit" / "tests"
        legacy_requirements = self.root / ".github" / "agent-kit" / "requirements-dev.txt"
        if legacy_tests.exists() or legacy_requirements.exists():
            self._add(
                self.root / ".github" / "agent-kit",
                "TEST_LAYOUT",
                "test assets belong under tests/agent-kit, outside the runtime tree",
            )

    def _validate_shared_contract(self) -> None:
        path = self.root / ".github" / "agent-contracts.md"
        if not path.is_file():
            return
        text = self._read_text(path)
        if text is None:
            return
        for marker in sorted(REQUIRED_SHARED_CONTRACT_MARKERS):
            if marker not in text:
                self._add(
                    path,
                    "SHARED_CONTRACT",
                    f"shared contract must contain behavior marker {marker!r}",
                )
        for action in NEXT_ACTION_IDS:
            marker = f"`{action}`"
            if marker not in text:
                self._add(
                    path,
                    "SHARED_CONTRACT_ACTION",
                    f"shared contract must define canonical action {action!r}",
                )
        for route in NEXT_ACTION_ROUTES:
            if route not in text:
                self._add(
                    path,
                    "SHARED_CONTRACT_ROUTE",
                    f"shared contract must define UI route {route!r}",
                )
        for target in NEXT_ACTION_DISPATCH_TARGETS:
            if target not in text:
                self._add(
                    path,
                    "SHARED_CONTRACT_DISPATCH",
                    f"shared contract must define dispatch target {target!r}",
                )

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
            elif re.match(r"^[\x00-\x7f]+ / [^\x00-\x7f]", data["description"]) is None:
                self._add(
                    path,
                    "AGENT_DESCRIPTION_LANGUAGE_ORDER",
                    "description must place the English text before the bilingual separator",
                )
            if data.get("tools") != spec["tools"]:
                self._add(path, "AGENT_TOOLS", f"tools must be exactly {spec['tools']!r}")
            if data.get("target") != "vscode":
                self._add(path, "AGENT_TARGET", "target must be 'vscode'")
            if data.get("user-invocable") is not spec["user-invocable"]:
                self._add(
                    path,
                    "AGENT_INVOCABLE",
                    f"user-invocable must be {spec['user-invocable']!r}",
                )
            if data.get("disable-model-invocation") is not spec["disable-model-invocation"]:
                self._add(
                    path,
                    "AGENT_MODEL_INVOCATION",
                    "disable-model-invocation does not match the six-agent policy",
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
            actual_handoffs = tuple(
                (handoff.get("label"), handoff.get("agent"))
                for handoff in handoffs
                if isinstance(handoff, dict)
            )
            if actual_handoffs != EXPECTED_HANDOFFS[filename]:
                self._add(
                    path,
                    "HANDOFF_BASELINE",
                    "handoff labels, order, and targets must remain exactly the base set",
                )
            if filename in BUSINESS_AGENT_FILES:
                next_handoffs = [
                    handoff
                    for handoff in handoffs
                    if isinstance(handoff, dict)
                    and handoff.get("label") == NEXT_ACTION_HANDOFF_LABEL
                ]
                expected_source = NEXT_ACTION_SOURCE_AGENTS[filename]
                if (
                    len(next_handoffs) != 1
                    or handoffs[-1] is not next_handoffs[0]
                    or next_handoffs[0].get("agent") != NEXT_ACTION_HANDOFF_AGENT
                    or next_handoffs[0].get("send") is not True
                    or not isinstance(next_handoffs[0].get("prompt"), str)
                    or f"Source Agent: {expected_source}" not in next_handoffs[0]["prompt"]
                    or any(
                        marker not in next_handoffs[0]["prompt"]
                        for marker in NEXT_ACTION_HANDOFF_PROMPT_MARKERS
                    )
                ):
                    self._add(
                        path,
                        "HANDOFF_NEXT_ACTION",
                        "must append exactly one safe send:true Next Action handoff to NextActionRouter",
                    )
            if filename == ROUTER_AGENT_FILE:
                if (
                    len(handoffs) != 5
                    or any(
                        not isinstance(handoff, dict)
                        or handoff.get("send") is not False
                        or not isinstance(handoff.get("prompt"), str)
                        or any(
                            marker not in handoff["prompt"]
                            for marker in ROUTER_FALLBACK_PROMPT_MARKERS
                        )
                        for handoff in handoffs
                    )
                ):
                    self._add(
                        path,
                        "HANDOFF_ROUTER_FALLBACK",
                        "Router must expose exactly five safe send:false fallback handoffs",
                    )
            if filename in GIT_DELIVERY_HANDOFF_AGENTS:
                delivery_handoffs = [
                    handoff
                    for handoff in handoffs
                    if isinstance(handoff, dict)
                    and handoff.get("label") == GIT_DELIVERY_HANDOFF_LABEL
                ]
                if (
                    len(delivery_handoffs) != 1
                    or delivery_handoffs[0].get("agent") != "EmbeddedDeveloper"
                    or not isinstance(delivery_handoffs[0].get("prompt"), str)
                    or any(
                        marker not in delivery_handoffs[0]["prompt"]
                        for marker in GIT_DELIVERY_HANDOFF_PROMPT_MARKERS
                    )
                ):
                    self._add(
                        path,
                        "HANDOFF_DELIVERY",
                        "must expose exactly one Git Delivery handoff to EmbeddedDeveloper",
                    )
            if filename == "embedded-developer.agent.md":
                close_handoffs = [
                    handoff
                    for handoff in handoffs
                    if isinstance(handoff, dict)
                    and handoff.get("label") == CLOSE_ISSUE_HANDOFF_LABEL
                ]
                if (
                    len(close_handoffs) != 1
                    or close_handoffs[0].get("agent") != "BugResolver"
                    or not isinstance(close_handoffs[0].get("prompt"), str)
                    or any(
                        marker not in close_handoffs[0]["prompt"]
                        for marker in CLOSE_ISSUE_HANDOFF_PROMPT_MARKERS
                    )
                ):
                    self._add(
                        path,
                        "HANDOFF_CLOSE_ISSUE",
                        "must expose exactly one Close Issue handoff to BugResolver",
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
                extra = set(handoff) - required_handoff
                if extra:
                    self._add(
                        path,
                        "HANDOFF_FIELDS",
                        f"{location} has unsupported fields: {', '.join(sorted(extra))}",
                    )
                if handoff.get("agent") not in KNOWN_AGENT_NAMES:
                    self._add(
                        path,
                        "AGENT_REFERENCE",
                        f"{location} references unknown agent {handoff.get('agent')!r}",
                    )
                is_next_action = (
                    filename in BUSINESS_AGENT_FILES
                    and index == len(handoffs) - 1
                    and handoff.get("label") == NEXT_ACTION_HANDOFF_LABEL
                    and handoff.get("agent") == NEXT_ACTION_HANDOFF_AGENT
                )
                expected_send = True if is_next_action else False
                if handoff.get("send") is not expected_send:
                    self._add(
                        path,
                        "HANDOFF_SEND",
                        f"{location}.send must be {expected_send!r}",
                    )

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
            elif re.match(r"^[\x00-\x7f]+ / [^\x00-\x7f]", data["description"]) is None:
                self._add(
                    path,
                    "PROMPT_DESCRIPTION_LANGUAGE_ORDER",
                    "description must place the English text before the bilingual separator",
                )
            if not isinstance(data.get("argument-hint"), str) or not data.get("argument-hint", "").strip():
                self._add(path, "PROMPT_ARGUMENT", "argument-hint must be a non-empty string")

            for marker in sorted(REQUIRED_PROMPT_BODY_MARKERS.get(filename, frozenset())):
                if marker not in body:
                    self._add(
                        path,
                        "PROMPT_BODY_CONTRACT",
                        f"prompt body must contain behavior marker {marker!r}",
                    )

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

    def _project_reference(
        self, owner: Path, reference: str, *, required: bool = True
    ) -> Path | None:
        project_dir = (self.root / ".project").resolve()
        if "\\" in reference:
            self._add(owner, "PROJECT_REFERENCE", f"use '/' in project reference: {reference}")
            return None
        candidate = (project_dir / reference).resolve()
        try:
            candidate.relative_to(project_dir)
        except ValueError:
            self._add(owner, "PROJECT_REFERENCE", f"reference leaves .project: {reference}")
            return None
        if not candidate.is_file():
            if required:
                self._add(
                    owner, "PROJECT_REFERENCE", f"referenced file is missing: {reference}"
                )
            return None
        return candidate

    def _validate_repository_glob(self, owner: Path, value: str, location: str) -> None:
        if (
            not value
            or value.startswith(("/", "\\"))
            or "\\" in value
            or re.match(r"^[A-Za-z]:", value)
            or any(part == ".." for part in value.split("/"))
        ):
            self._add(
                owner,
                "PROJECT_GLOB",
                f"{location} must be a repository-relative '/' glob: {value!r}",
            )

    def _validate_git_delivery_policy(self, path: Path) -> None:
        text = self._read_text(path)
        if text is None:
            return
        try:
            policy = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            self._add(path, "GIT_POLICY_YAML", f"invalid YAML: {exc}")
            return
        errors = sorted(
            Draft202012Validator(GIT_DELIVERY_POLICY_SCHEMA).iter_errors(policy),
            key=lambda error: [str(part) for part in error.absolute_path],
        )
        for error in errors:
            location = ".".join(str(part) for part in error.absolute_path) or "<root>"
            self._add(path, "GIT_POLICY_SCHEMA", f"{location}: {error.message}")
        if not isinstance(policy, dict):
            return
        override_locations: list[str] = []

        def collect_overrides(value: Any, prefix: str = "") -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    location = f"{prefix}.{key}" if prefix else str(key)
                    normalized = str(key).lower().replace("-", "_")
                    if normalized in FORBIDDEN_GIT_TARGET_KEYS:
                        override_locations.append(location)
                    collect_overrides(child, location)
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    collect_overrides(child, f"{prefix}[{index}]")

        collect_overrides(policy)
        for location in override_locations:
            self._add(
                path,
                "GIT_TARGET_OVERRIDE",
                f"{location} must not override a remote, URL, or target ref",
            )
        for section, fields in (
            ("scope", ("allowed_paths", "denied_paths")),
            ("push", ("allowed_branches", "protected_branches")),
        ):
            section_value = policy.get(section)
            if not isinstance(section_value, dict):
                continue
            for field in fields:
                values = section_value.get(field)
                if not isinstance(values, list):
                    continue
                for index, value in enumerate(values):
                    if isinstance(value, str):
                        self._validate_repository_glob(
                            path, value, f"{section}.{field}[{index}]"
                        )
        commit = policy.get("commit")
        if not isinstance(commit, dict):
            return
        jira_pattern = commit.get("jira_pattern")
        if isinstance(jira_pattern, str):
            try:
                re.compile(jira_pattern)
            except re.error as exc:
                self._add(
                    path,
                    "GIT_POLICY_JIRA_PATTERN",
                    f"commit.jira_pattern is invalid: {exc}",
                )
        template = commit.get("template")
        if isinstance(template, str):
            template_path = self._project_reference(path, template)
            if template_path is not None:
                self._validate_commit_template(template_path)

    def _validate_commit_template(self, path: Path) -> None:
        text = self._read_text(path)
        if text is None:
            return
        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        if not lines or lines[0] != "<Project><Function block>: <Summary>":
            self._add(
                path,
                "COMMIT_TEMPLATE_SUBJECT",
                "first line must be <Project><Function block>: <Summary>",
            )
            return
        names: list[str] = []
        for line in lines[1:]:
            if line == "<<<Test Notes>>>":
                names.append(line)
                continue
            match = re.fullmatch(r"<([^<>]+)>:.*", line)
            if match is None:
                self._add(
                    path,
                    "COMMIT_TEMPLATE_LINE",
                    f"invalid template line: {line}",
                )
                return
            names.append(match.group(1))
        if names != list(COMMIT_TEMPLATE_FIELD_ORDER):
            self._add(
                path,
                "COMMIT_TEMPLATE_ORDER",
                "template fields are missing, unknown, or out of order",
            )
        elif tuple(lines[6:9]) != COMMIT_TEMPLATE_AI_DEFAULTS:
            self._add(
                path,
                "COMMIT_TEMPLATE_AI_DEFAULT",
                "AI defaults must be N, /, / with one space after each colon",
            )

    def _validate_project_directory(self) -> None:
        project_dir = self.root / ".project"
        if not project_dir.exists():
            return
        if not project_dir.is_dir():
            self._add(
                project_dir,
                "PROJECT_DIRECTORY_INVALID",
                ".project exists but is not a directory",
            )
            return
        path = project_dir / "project.yml"
        text = self._read_text(path) if path.is_file() else None
        if text is None:
            if not path.is_file():
                self._add(
                    path,
                    "PROJECT_DIRECTORY_MISSING",
                    "project.yml is required when .project exists",
                )
            return
        if not (project_dir / "README.md").is_file():
            self._add(
                project_dir / "README.md",
                "PROJECT_DIRECTORY_README",
                "README.md is required when .project exists",
            )
        try:
            manifest = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            self._add(path, "PROJECT_DIRECTORY_YAML", f"invalid YAML: {exc}")
            return
        errors = sorted(
            Draft202012Validator(PROJECT_DIRECTORY_SCHEMA).iter_errors(manifest),
            key=lambda error: [str(part) for part in error.absolute_path],
        )
        for error in errors:
            location = ".".join(str(part) for part in error.absolute_path) or "<root>"
            self._add(path, "PROJECT_DIRECTORY_SCHEMA", f"{location}: {error.message}")
        if not isinstance(manifest, dict):
            return

        seen_ids: set[str] = set()
        rules = manifest.get("rules")
        if isinstance(rules, list):
            for index, rule in enumerate(rules):
                if not isinstance(rule, dict):
                    continue
                rule_id = rule.get("id")
                if isinstance(rule_id, str):
                    if rule_id in seen_ids:
                        self._add(
                            path,
                            "PROJECT_RULE_ID",
                            f"duplicate rules id: {rule_id}",
                        )
                    seen_ids.add(rule_id)
                reference = rule.get("path")
                if isinstance(reference, str):
                    self._project_reference(
                        path,
                        reference,
                        required=rule.get("required") is not False,
                    )
                applies_to = rule.get("applies_to")
                if isinstance(applies_to, list):
                    for glob_index, value in enumerate(applies_to):
                        if isinstance(value, str):
                            self._validate_repository_glob(
                                path,
                                value,
                                f"rules[{index}].applies_to[{glob_index}]",
                            )

        git_policy = manifest.get("git_policy")
        if isinstance(git_policy, str):
            policy_path = self._project_reference(path, git_policy)
            if policy_path is not None:
                self._validate_git_delivery_policy(policy_path)

    def _markdown_files(self) -> Iterable[Path]:
        readme = self.root / "README.md"
        if readme.is_file():
            yield readme
        for base in (
            self.root / ".github",
            self.root / ".project",
            self.root / "docs",
            self.root / "examples",
        ):
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
