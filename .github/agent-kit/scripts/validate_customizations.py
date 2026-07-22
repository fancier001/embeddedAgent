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
        ("Bug åˆ†æä¸è§£å†³ / Diagnose and Resolve Bug", "BugResolver"),
        ("å®ç°å˜æ›´ / Implement", "EmbeddedDeveloper"),
        ("ç‹¬ç«‹è¯„å®¡ / Review", "QualityReviewer"),
        ("æ–‡æ¡£æ²‰æ·€ / Document", "DocKeeper"),
        ("æ‰§è¡Œä¸‹ä¸€æ­¥ / Next Action", "NextActionRouter"),
    ),
    "bug-resolver.agent.md": (
        ("å®æ–½ä¿®å¤ / Implement Fix", "EmbeddedDeveloper"),
        ("è´¨é‡è¯„ä¼° / Quality Assessment", "QualityReviewer"),
        ("è®°å½•ç»“è®º / Document Resolution", "DocKeeper"),
        ("Git æäº¤äº¤ä»˜ / Git Delivery", "EmbeddedDeveloper"),
        ("æ‰§è¡Œä¸‹ä¸€æ­¥ / Next Action", "NextActionRouter"),
    ),
    "embedded-developer.agent.md": (
        ("ç‹¬ç«‹è¯„å®¡ / Quality Review", "QualityReviewer"),
        ("æ–‡æ¡£åŒæ­¥ / Document Changes", "DocKeeper"),
        ("é—®é¢˜å·²è§£å†³ / Close Issue", "BugResolver"),
        ("æ‰§è¡Œä¸‹ä¸€æ­¥ / Next Action", "NextActionRouter"),
    ),
    "quality-reviewer.agent.md": (
        ("ä¿®å¤é—®é¢˜ / Fix Issues", "EmbeddedDeveloper"),
        ("æ²‰æ·€è´¨é‡ç»“è®º / Document Quality Findings", "DocKeeper"),
        ("Git æäº¤äº¤ä»˜ / Git Delivery", "EmbeddedDeveloper"),
        ("æ‰§è¡Œä¸‹ä¸€æ­¥ / Next Action", "NextActionRouter"),
    ),
    "doc-keeper.agent.md": (
        ("è¿”å›ç¼–æ’ / Resolve Conflict", "Orchestrator"),
        ("Git æäº¤äº¤ä»˜ / Git Delivery", "EmbeddedDeveloper"),
        ("æ‰§è¡Œä¸‹ä¸€æ­¥ / Next Action", "NextActionRouter"),
    ),
    "next-action-router.agent.md": (
        ("è¿”å›ç¼–æ’ / Return to Orchestrator", "Orchestrator"),
        ("è¿”å›é—®é¢˜è§£å†³ / Return to Bug Resolver", "BugResolver"),
        ("è¿”å›å®æ–½ / Return to Embedded Developer", "EmbeddedDeveloper"),
        ("è¿”å›è¯„å®¡ / Return to Quality Reviewer", "QualityReviewer"),
        ("è¿”å›æ–‡æ¡£ / Return to Doc Keeper", "DocKeeper"),
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
    "HANDOFF:<exact current-agent base-button label>",
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
NEXT_ACTION_HANDOFF_LABEL = "æ‰§è¡Œä¸‹ä¸€æ­¥ / Next Action"
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

GIT_DELIVERY_HANDOFF_LABEL = "Git æäº¤äº¤ä»˜ / Git Delivery"
CLOSE_ISSUE_HANDOFF_LABEL = "é—®é¢˜å·²è§£å†³ / Close Issue"
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
        }
    ),
    "bug-resolver.agent.md": frozenset(
        {
            ".github/agent-contracts.md",
            "CLOSE â†’ RESET â†’ INTAKE",
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
        }
    ),
    "doc-keeper.agent.md": frozenset(
        {
            ".github/agent-contracts.md",
            ".project/",
            "`RECEIVED`",
            "`REPORT`",
            "Documentation",
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
        "- Dispatch Target:",
        "- Input Required:",
        "- Required Input:",
        "- Reply Template:",
        "- Instruction:",
        "NEXT_ACTION_BUTTON",
        "CURRENT_INPUT",
        "HANDOFF:<exact current-agent base-button label>",
        "AGENT_CONTINUE",
        "EXTERNAL",
        "`ADJUST_CHANGESET`",
        "Change Confirmation: PENDING",
        "confirm changes and commit",
        "per-file `entries`",
        "`CONFIRM_PUSH`",
        "`MANUAL_PUSH`",
        "`START_NEW_ISSUE`",
        "NOT_RUN â€” Not required: <reason>",
        "`CONFIRM_COMMIT_CONTENT`",
        "--expected-content-fingerprint",
        "content_confirmation.status: CONFIRMED",
        "Commit Content Confirmation: PENDING",
        "è¿”å›ç¼–æ’ / Return to Orchestrator",
        "five static fallback handoffs",
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
    "$schema": "https://json-schema.org/draft/20×~ºêÚ$z{-®éÜj×¢–bæ÷B—6–ç7Fæ6R‡öÆ–7’ÂF–7B“ ¢&WGW&à¢÷fW'&–FUöÆö6F–öç3¢Æ—7E·7G%ÒÒµĞ ¢FVb6öÆÆV7Eö÷fW'&–FW2‡fÇVS¢ç’Â&Vf—ƒ¢7G"Ò""’ÓâæöæS ¢–b—6–ç7Fæ6R‡fÇVRÂF–7B“ ¢f÷"¶W’Â6†–ÆB–âfÇVRæ—FV×2‚“ ¢Æö6F–öâÒb'·&Vf—‡Òç¶¶W—Ò"–b&Vf—‚VÇ6R7G"†¶W’¢æ÷&ÖÆ—¦VBÒ7G"†¶W’’æÆ÷vW"‚’ç&WÆ6R‚"Ò"Â%ò"¢–bæ÷&ÖÆ—¦VB–âdõ$$”DDTåôt•EõD$tUEô´U•3 ¢÷fW'&–FUöÆö6F–öç2æVæB†Æö6F–öâ¢6öÆÆV7Eö÷fW'&–FW2†6†–ÆBÂÆö6F–öâ¢VÆ–b—6–ç7Fæ6R‡fÇVRÂÆ—7B“ ¢f÷"–æFW‚Â6†–ÆB–âVçVÖW&FR‡fÇVR“ ¢6öÆÆV7Eö÷fW'&–FW2†6†–ÆBÂb'·&Vf—‡Õ·¶–æFW‡ÕÒ" ¢6öÆÆV7Eö÷fW'&–FW2‡öÆ–7’¢f÷"Æö6F–öâ–â÷fW'&–FUöÆö6F–öç3 ¢6VÆbåöFB€¢F‚À¢$t•EõD$tUEôõdU%$”DR"À¢b'¶Æö6F–öçÒ×W7Bæ÷B÷fW'&–FR&VÖ÷FRÂU$ÂÂ÷"F&vWB&Vb"À¢¢f÷"6V7F–öâÂf–VÆG2–â€¢‚'66÷R"Â‚&ÆÆ÷vVE÷F‡2"Â&FVæ–VE÷F‡2"’’À¢‚'W6‚"Â‚&ÆÆ÷vVEö'&æ6†W2"Â'&÷FV7FVEö'&æ6†W2"’’À¢“ ¢6V7F–öå÷fÇVRÒöÆ–7’ævWB‡6V7F–öâ¢–bæ÷B—6–ç7Fæ6R‡6V7F–öå÷fÇVRÂF–7B“ ¢6öçF–çVP¢f÷"f–VÆB–âf–VÆG3 ¢fÇVW2Ò6V7F–öå÷fÇVRævWB†f–VÆB¢–bæ÷B—6–ç7Fæ6R‡fÇVW2ÂÆ—7B“ ¢6öçF–çVP¢f÷"–æFW‚ÂfÇVR–âVçVÖW&FR‡fÇVW2“ ¢–b—6–ç7Fæ6R‡fÇVRÂ7G"“ ¢6VÆbå÷fÆ–FFU÷&W÷6—F÷'•övÆö"€¢F‚ÂfÇVRÂb'·6V7F–öçÒç¶f–VÆGÕ·¶–æFW‡ÕÒ ¢¢6öÖÖ—BÒöÆ–7’ævWB‚&6öÖÖ—B"¢–bæ÷B—6–ç7Fæ6R†6öÖÖ—BÂF–7B“ ¢&WGW&à¢¦—&÷GFW&âÒ6öÖÖ—BævWB‚&¦—&÷GFW&â"¢–b—6–ç7Fæ6R†¦—&÷GFW&âÂ7G"“ ¢G'“ ¢&Ræ6ö×–ÆR†¦—&÷GFW&â¢W†6WB&RæW'&÷"2W†3 ¢6VÆbåöFB€¢F‚À¢$t•EõôÄ”5•ô¤•$õEDU$â"À¢b&6öÖÖ—Bæ¦—&÷GFW&â—2–çfÆ–C¢¶W†7Ò"À¢¢FV×ÆFRÒ6öÖÖ—BævWB‚'FV×ÆFR"¢–b—6–ç7Fæ6R‡FV×ÆFRÂ7G"“ ¢FV×ÆFU÷F‚Ò6VÆbå÷&ö¦V7E÷&VfW&Væ6R‡F‚ÂFV×ÆFR¢–bFV×ÆFU÷F‚—2æ÷BæöæS ¢6VÆbå÷fÆ–FFUö6öÖÖ—E÷FV×ÆFR‡FV×ÆFU÷F‚ ¢FVb÷fÆ–FFUö6öÖÖ—E÷FV×ÆFR‡6VÆbÂFƒ¢F‚’ÓâæöæS ¢FW‡BÒ6VÆbå÷&VE÷FW‡B‡F‚¢–bFW‡B—2æöæS ¢&WGW&à¢Æ–æW2Ò°¢Æ–æRç7G&—‚¢f÷"Æ–æR–âFW‡Bç7Æ—FÆ–æW2‚¢–bÆ–æRç7G&—‚’æBæ÷BÆ–æRæÇ7G&—‚’ç7F'G7v—F‚‚"2"¢Ğ¢–bæ÷BÆ–æW2÷"Æ–æW5³ÒÒ#Å&ö¦V7CãÄgVæ7F–öâ&Æö6³ã¢Å7VÖÖ'“â# ¢6VÆbåöFB€¢F‚À¢$4ôÔÔ•EõDTÕÄDUõ5T$¤T5B"À¢&f—'7BÆ–æR×W7B&RÅ&ö¦V7CãÄgVæ7F–öâ&Æö6³ã¢Å7VÖÖ'“â"À¢¢&WGW&à¢æÖW3¢Æ—7E·7G%ÒÒµĞ¢f÷"Æ–æR–âÆ–æW5³¥Ó ¢–bÆ–æRÓÒ#ÃÃÅFW7Bæ÷FW3ããâ# ¢æÖW2æVæB†Æ–æR¢6öçF–çVP¢ÖF6‚Ò&RægVÆÆÖF6‚‡"#Â…µãÃåÒ²“ã¢â¢"ÂÆ–æR¢–bÖF6‚—2æöæS ¢6VÆbåöFB€¢F‚À¢$4ôÔÔ•EõDTÕÄDUôÄ”äR"À¢b&–çfÆ–BFV×ÆFRÆ–æS¢¶Æ–æWÒ"À¢¢&WGW&à¢æÖW2æVæB†ÖF6‚æw&÷Wƒ’¢–bæÖW2ÒÆ—7B„4ôÔÔ•EõDTÕÄDUôd”TÄEôõ$DU"“ ¢6VÆbåöFB€¢F‚À¢$4ôÔÔ•EõDTÕÄDUôõ$DU""À¢'FV×ÆFRf–VÆG2&RÖ—76–ærÂVæ¶æ÷vâÂ÷"÷WBöb÷&FW""À¢¢VÆ–bGWÆR†Æ–æW5³c£•Ò’Ò4ôÔÔ•EõDTÕÄDUô•ôDTdTÅE3 ¢6VÆbåöFB€¢F‚À¢$4ôÔÔ•EõDTÕÄDUô•ôDTdTÅB"À¢$’FVfVÇG2×W7B&RâÂòÂòv—F‚öæR76RgFW"V6‚6öÆöâ"À¢ ¢FVb÷fÆ–FFU÷&ö¦V7EöF—&V7F÷'’‡6VÆb’ÓâæöæS ¢&ö¦V7EöF—"Ò6VÆbç&ö÷Bò"ç&ö¦V7B ¢–bæ÷B&ö¦V7EöF—"æW†—7G2‚“ ¢&WGW&à¢–bæ÷B&ö¦V7EöF—"æ—5öF—"‚“ ¢6VÆbåöFB€¢&ö¦V7EöF—"À¢%$ô¤T5EôD•$T5Dõ%•ô”ådÄ”B"À¢"ç&ö¦V7BW†—7G2'WB—2æ÷BF—&V7F÷'’"À¢¢&WGW&à¢F‚Ò&ö¦V7EöF—"ò'&ö¦V7Bç–ÖÂ ¢FW‡BÒ6VÆbå÷&VE÷FW‡B‡F‚’–bF‚æ—5öf–ÆR‚’VÇ6RæöæP¢–bFW‡B—2æöæS ¢–bæ÷BF‚æ—5öf–ÆR‚“ ¢6VÆbåöFB€¢F‚À¢%$ô¤T5EôD•$T5Dõ%•ôÔ•54”är"À¢'&ö¦V7Bç–ÖÂ—2&WV—&VBv†Vâç&ö¦V7BW†—7G2"À¢¢&WGW&à¢–bæ÷B‡&ö¦V7EöF—"ò%$TDÔRæÖB"’æ—5öf–ÆR‚“ ¢6VÆbåöFB€¢&ö¦V7EöF—"ò%$TDÔRæÖB"À¢%$ô¤T5EôD•$T5Dõ%•õ$TDÔR"À¢%$TDÔRæÖB—2&WV—&VBv†Vâç&ö¦V7BW†—7G2"À¢¢G'“ ¢Öæ–fW7BÒ–ÖÂç6fUöÆöB‡FW‡B¢W†6WB–ÖÂå”ÔÄW'&÷"2W†3 ¢6VÆbåöFB‡F‚Â%$ô¤T5EôD•$T5Dõ%•õ”ÔÂ"Âb&–çfÆ–B”ÔÃ¢¶W†7Ò"¢&WGW&à¢W'&÷'2Ò6÷'FVB€¢G&gC##%fÆ–FF÷"…$ô¤T5EôD•$T5Dõ%•õ44„TÔ’æ—FW%öW'&÷'2†Öæ–fW7B’À¢¶W“ÖÆÖ&FW'&÷#¢·7G"‡'B’f÷"'B–âW'&÷"æ'6öÇWFU÷F…ÒÀ¢¢f÷"W'&÷"–âW'&÷'3 ¢Æö6F–öâÒ"â"æ¦ö–â‡7G"‡'B’f÷"'B–âW'&÷"æ'6öÇWFU÷F‚’÷"#Ç&ö÷Câ ¢6VÆbåöFB‡F‚Â%$ô¤T5EôD•$T5Dõ%•õ44„TÔ"Âb'¶Æö6F–öçÓ¢¶W'&÷"æÖW76vWÒ"¢–bæ÷B—6–ç7Fæ6R†Öæ–fW7BÂF–7B“ ¢&WGW&à ¢6VVåö–G3¢6WE·7G%ÒÒ6WB‚¢'VÆW2ÒÖæ–fW7BævWB‚''VÆW2"¢–b—6–ç7Fæ6R‡'VÆW2ÂÆ—7B“ ¢f÷"–æFW‚Â'VÆR–âVçVÖW&FR‡'VÆW2“ ¢–bæ÷B—6–ç7Fæ6R‡'VÆRÂF–7B“ ¢6öçF–çVP¢'VÆUö–BÒ'VÆRævWB‚&–B"¢–b—6–ç7Fæ6R‡'VÆUö–BÂ7G"“ ¢–b'VÆUö–B–â6VVåö–G3 ¢6VÆbåöFB€¢F‚À¢%$ô¤T5Eõ%TÄUô”B"À¢b&GWÆ–6FR'VÆW2–C¢·'VÆUö–GÒ"À¢¢6VVåö–G2æFB‡'VÆUö–B¢&VfW&Væ6RÒ'VÆRævWB‚'F‚"¢–b—6–ç7Fæ6R‡&VfW&Væ6RÂ7G"“ ¢6VÆbå÷&ö¦V7E÷&VfW&Væ6R€¢F‚À¢&VfW&Væ6RÀ¢&WV—&VC×'VÆRævWB‚'&WV—&VB"’—2æ÷BfÇ6RÀ¢¢Æ–W5÷FòÒ'VÆRævWB‚&Æ–W5÷Fò"¢–b—6–ç7Fæ6R†Æ–W5÷FòÂÆ—7B“ ¢f÷"vÆö%ö–æFW‚ÂfÇVR–âVçVÖW&FR†Æ–W5÷Fò“ ¢–b—6–ç7Fæ6R‡fÇVRÂ7G"“ ¢6VÆbå÷fÆ–FFU÷&W÷6—F÷'•övÆö"€¢F‚À¢fÇVRÀ¢b''VÆW5·¶–æFW‡ÕÒæÆ–W5÷Fõ·¶vÆö%ö–æFW‡ÕÒ"À¢ ¢v—E÷öÆ–7’ÒÖæ–fW7BævWB‚&v—E÷öÆ–7’"¢–b—6–ç7Fæ6R†v—E÷öÆ–7’Â7G"“ ¢öÆ–7•÷F‚Ò6VÆbå÷&ö¦V7E÷&VfW&Væ6R‡F‚Âv—E÷öÆ–7’¢–böÆ–7•÷F‚—2æ÷BæöæS ¢6VÆbå÷fÆ–FFUöv—EöFVÆ—fW'•÷öÆ–7’‡öÆ–7•÷F‚ ¢FVböÖ&¶F÷våöf–ÆW2‡6VÆb’Óâ—FW&&ÆUµF…Ó ¢&VFÖRÒ6VÆbç&ö÷Bò%$TDÔRæÖB ¢–b&VFÖRæ—5öf–ÆR‚“ ¢––VÆB&VFÖP¢f÷"&6R–â€¢6VÆbç&ö÷Bò"æv—F‡V""À¢6VÆbç&ö÷Bò"ç&ö¦V7B"À¢6VÆbç&ö÷Bò&Fö72"À¢6VÆbç&ö÷Bò&W†×ÆW2"À¢“ ¢–bæ÷B&6Ræ—5öF—"‚“ ¢6öçF–çVP¢f÷"F‚–â&6Rç&vÆö"‚"¢æÖB"“ ¢&VÆF—fU÷'G2ÒF‚ç&VÆF—fU÷Fò‡6VÆbç&ö÷B’ç'G0¢–b€¢&VÆF—fU÷'G5³£%ÒÓÒ‚"æv—F‡V""Â&vVçBÖ¶—B"¢÷"ç’‡'B–â”täõ$TEôD•%2f÷"'B–â&VÆF—fU÷'G5³¢ÓÒ¢“ ¢6öçF–çVP¢––VÆBF€ ¢FVb÷fÆ–FFUö&–Æ–æwVÅöÖ&¶F÷vâ‡6VÆb’ÓâæöæS ¢f÷"F‚–â6÷'FVB‡6WB‡6VÆbåöÖ&¶F÷våöf–ÆW2‚’’“ ¢FW‡BÒ6VÆbå÷&VE÷FW‡B‡F‚¢–bFW‡B—2æöæS ¢6öçF–çVP¢6†–æW6RÒ$”Ä”äuTÅô4„”äU4Rç6V&6‚‡FW‡B¢VævÆ—6‚Ò$”Ä”äuTÅôTätÄ•4‚ç6V&6‚‡FW‡B¢–b6†–æW6R—2æöæR÷"VævÆ—6‚—2æöæS ¢6VÆbåöFB€¢F‚À¢$$”Ä”äuTÅõ4T5D”ôå2"À¢'&WV—&W2r22KŠŞihrò6†–æW6RrföÆÆ÷vVB'’r22VævÆ—6‚r"À¢¢VÆ–b6†–æW6Rç7F'B‚’ãÒVævÆ—6‚ç7F'B‚“ ¢6VÆbåöFB‡F‚Â$$”Ä”äuTÅôõ$DU""Â$6†–æW6R6V7F–öâ×W7B&V6VFRVævÆ—6‚"¢VÇ6S ¢6†–æW6Uö&öG’ÒFW‡E¶6†–æW6RæVæB‚’¢VævÆ—6‚ç7F'B‚•Òç7G&—‚¢VævÆ—6…ö&öG’ÒFW‡E¶VævÆ—6‚æVæB‚’¥Òç7G&—‚¢–bæ÷B6†–æW6Uö&öG’÷"æ÷BVævÆ—6…ö&öG“ ¢6VÆbåöFB‡F‚Â$$”Ä”äuTÅôTÕE’"Â&&÷F‚ÆæwVvR6V7F–öç2×W7B&RæöâÖV×G’" ¢&÷6RÒdTä4TEô4ôDRç7V"‚""ÂFW‡B¢&÷6RÒ”äÄ”äUô4ôDRç7V"‚""Â&÷6R¢–b&Rç6V&6‚‡"%DôDõÇ2¥Â‡7–æ5Â’"Â&÷6RÂfÆw3×&Rä”täõ$T44R“ ¢6VÆbåöFB‡F‚Â%DôDõõ5”ä2"Â'Vç&W6öÇfVBDôDò‡7–æ2’Ö&¶W"–â&÷6R" ¢FVböÖ&¶F÷våöæ6†÷'2‡6VÆbÂFƒ¢F‚’Óâ6WE·7G%ÒÂæöæS ¢""$6öÆÆV7BvVæW&FVB†VF–ær6ÇVw2æBW‡Æ–6—B…DÔÂæ6†÷'2â""  ¢66†Uö¶W’ÒF‚ç&W6öÇfR‚¢–b66†Uö¶W’–â6VÆbåöÖ&¶F÷våöæ6†÷%ö66†S ¢&WGW&â6VÆbåöÖ&¶F÷våöæ6†÷%ö66†U¶66†Uö¶W•Ğ¢FW‡BÒ6VÆbå÷&VE÷FW‡B‡F‚¢–bFW‡B—2æöæS ¢6VÆbåöÖ&¶F÷våöæ6†÷%ö66†U¶66†Uö¶W•ÒÒæöæP¢&WGW&âæöæP ¢6÷W&6RÒ÷v—F†÷WEög&öçFÖGFW"‡FW‡B¢6÷W&6RÒdTä4TEô4ôDRç7V"‚""Â6÷W&6R¢6÷W&6RÒ…DÔÅô4ôÔÔTåBç7V"‚""Â6÷W&6R¢Æ–æW2Ò6÷W&6Rç7Æ—FÆ–æW2‚¢æ6†÷'3¢6WE·7G%ÒÒ6WB‚¢æW‡E÷7Vff—ƒ¢F–7E·7G"Â–çEÒÒ·Ğ ¢FVbFEö†VF–ær††VF–æs¢7G"’ÓâæöæS ¢&6RÒöv—F‡V%ö†VF–æu÷6ÇVr††VF–ær¢–bæ÷B&6S ¢&WGW&à¢6æF–FFRÒ&6P¢7Vff—‚ÒæW‡E÷7Vff—‚ævWB†&6RÂ¢v†–ÆR6æF–FFR–âæ6†÷'3 ¢6æF–FFRÒb'¶&6WÒ×·7Vff—‡Ò ¢7Vff—‚³Ò¢æW‡E÷7Vff—…¶&6UÒÒ7Vff—€¢æ6†÷'2æFB†6æF–FFR ¢–æFW‚Ò ¢v†–ÆR–æFW‚ÂÆVâ†Æ–æW2“ ¢Æ–æRÒÆ–æW5¶–æFW…Ğ¢G‚ÒE…ô„TD”äræÖF6‚†Æ–æR¢–bG‚—2æ÷BæöæS ¢†VF–ærÒ&Rç7V"‡"%²ÇEÒ²2µ²ÇEÒ¢B"Â""ÂG‚æw&÷W‚'FW‡B"’¢FEö†VF–ær††VF–ær¢–æFW‚³Ò¢6öçF–çVP¢–b€¢Æ–æRç7G&—‚¢æB–æFW‚²ÂÆVâ†Æ–æW2¢æB4UDU…Eô„TD”äræÖF6‚†Æ–æW5¶–æFW‚²Ò’—2æ÷BæöæP¢“ ¢FEö†VF–ær†Æ–æRç7G&—‚’¢–æFW‚³Ò ¢6öçF–çVP¢–æFW‚³Ò ¢‡FÖÅ÷6÷W&6RÒ÷&WÆ6Uö–æÆ–æUö6öFR‡6÷W&6RÂ&W6W'fUö6öçFVçCÔfÇ6R¢f÷"ÖF6‚–â…DÔÅôU…Ä”4•Eôä4„õ"æf–æF—FW"†‡FÖÅ÷6÷W&6R“ ¢W‡Æ–6—BÒæW‡B‚†w&÷Wf÷"w&÷W–âÖF6‚æw&÷W2‚’–bw&÷W’Â""¢W‡Æ–6—BÒ‡FÖÂçVæW66R†W‡Æ–6—B’ç7G&—‚¢–bW‡Æ–6—C ¢æ6†÷'2æFB†W‡Æ–6—B ¢6VÆbåöÖ&¶F÷våöæ6†÷%ö66†U¶66†Uö¶W•ÒÒæ6†÷'0¢&WGW&âæ6†÷'0 ¢FVb÷fÆ–FFUöÖ&¶F÷våöÆ–æ·2‡6VÆb’ÓâæöæS ¢f÷"F‚–â6÷'FVB‡6WB‡6VÆbåöÖ&¶F÷våöf–ÆW2‚’’“ ¢FW‡BÒ6VÆbå÷&VE÷FW‡B‡F‚¢–bFW‡B—2æöæS ¢6öçF–çVP¢Æ–æµ÷6÷W&6RÒdTä4TEô4ôDRç7V"‚""ÂFW‡B¢Æ–æµ÷6÷W&6RÒ÷&WÆ6Uö–æÆ–æUö6öFR†Æ–æµ÷6÷W&6RÂ&W6W'fUö6öçFVçCÔfÇ6R¢f÷"ÖF6‚–âÔ$´DõtåôÄ”ä²æf–æF—FW"†Æ–æµ÷6÷W&6R“ ¢FW7F–æF–öâÒ†ÖF6‚æw&÷W‚&ævÆR"’÷"ÖF6‚æw&÷W‚'Æ–â"’÷"""’ç7G&—‚¢Æ÷vW&VBÒFW7F–æF–öâæÆ÷vW"‚¢–bæ÷BFW7F–æF–öã ¢6öçF–çVP¢–bÆ÷vW&VBç7F'G7v—F‚‚‚&‡GG¢òò"Â&‡GG3¢òò"Â&Ö–ÇFó¢"Â&FF¢"Â'g66öFS¢"’“ ¢6öçF–çVP¢–bFW7F–æF–öâç7F'G7v—F‚‚"G²"“ ¢6öçF–çVP¢F&vWBÂ6W&F÷"Â&uög&vÖVçBÒFW7F–æF–öâç'F—F–öâ‚"2"¢Æö6ÂÒVçV÷FR‡F&vWBç7Æ—B‚#ò"Â•³Ò¢6æF–FFRÒ€¢F€¢–bæ÷BÆö6À¢VÇ6R‡6VÆbç&ö÷BòÆö6ÂæÇ7G&—‚"ò"’¢–bÆö6Âç7F'G7v—F‚‚"ò"¢VÇ6R‡F‚ç&VçBòÆö6Â¢¢&W6öÇfVBÒ6æF–FFRç&W6öÇfR‚¢G'“ ¢&W6öÇfVBç&VÆF—fU÷Fò‡6VÆbç&ö÷B¢W†6WBfÇVTW'&÷# ¢6VÆbåöFB‡F‚Â$Ä”äµôõUE4”DR"Âb&Æ–æ²ÆVfW2&W÷6—F÷'“¢¶FW7F–æF–öçÒ"¢6öçF–çVP¢–bæ÷B&W6öÇfVBæW†—7G2‚“ ¢6VÆbåöFB‡F‚Â$Ä”äµôÔ•54”är"Âb&Æö6ÂÆ–æ²F&vWBFöW2æ÷BW†—7C¢¶FW7F–æF–öçÒ"¢6öçF–çVP¢–b€¢6W&F÷ ¢æB&uög&vÖVç@¢æBæ÷BÖF6‚æw&÷Wƒ’ç7F'G7v—F‚‚""¢æB&W6öÇfVBæ—5öf–ÆR‚¢æB&W6öÇfVBç7Vff—‚æÆ÷vW"‚’ÓÒ"æÖB ¢“ ¢g&vÖVçBÒVçV÷FR‡&uög&vÖVçB¢æ6†÷'2Ò6VÆbåöÖ&¶F÷våöæ6†÷'2‡&W6öÇfVB¢–bæ6†÷'2—2æ÷BæöæRæBg&vÖVçBæ÷B–âæ6†÷'3 ¢6VÆbåöFB€¢F‚À¢$Ä”äµôä4„õ%ôÔ•54”är"À¢b&Æö6ÂÖ&¶F÷vâæ6†÷"FöW2æ÷BW†—7C¢¶FW7F–æF–öçÒ"À¢  ¦FVbfÆ–FFU÷&W÷6—F÷'’‡&ö÷C¢F‚Â7G"’ÓâÆ—7E´F–væ÷7F–5Ó ¢""%V&Æ–2’W6VB'’Væ—BFW7G2æB–çFVw&F–öç2â""  ¢&WGW&â&W÷6—F÷'•fÆ–FF÷"‡&ö÷B’çfÆ–FFR‚  ¦FVbö'V–ÆE÷'6W"‚’Óâ&w'6Rä&wVÖVçE'6W# ¢'6W"Ò&w'6Rä&wVÖVçE'6W"†FW67&—F–öãÕõöFö5õò¢'6W"æFEö&wVÖVçB€¢"Ò×&ö÷B"À¢G—SÕF‚À¢FVfVÇCÕF‚…õöf–ÆUõò’ç&W6öÇfR‚’ç&VçG5³5ÒÀ¢†VÇÒ'&W÷6—F÷'’&ö÷B†FVfVÇG2FòF†R&VçBöbæv—F‡V"ò’"À¢¢'6W"æFEö&wVÖVçB€¢"ÒÖf÷&ÖB"À¢6†ö–6W3Ò‚'FW‡B"Â&§6öâ"’À¢FVfVÇCÒ'FW‡B"À¢FW7CÒ&÷WGWEöf÷&ÖB"À¢†VÇÒ&F–væ÷7F–2÷WGWBf÷&ÖB"À¢¢&WGW&â'6W   ¦FVbÖ–â†&wc¢6WVVæ6U·7G%ÒÂæöæRÒæöæR’Óâ–çC ¢&w2Òö'V–ÆE÷'6W"‚’ç'6Uö&w2†&wb¢F–væ÷7F–72ÒfÆ–FFU÷&W÷6—F÷'’†&w2ç&ö÷B¢–b&w2æ÷WGWEöf÷&ÖBÓÒ&§6öâ# ¢&–çB†§6öâæGV×2…¶6F–7B†—FVÒ’f÷"—FVÒ–âF–væ÷7F–75ÒÂVç7W&Uö66–“ÔfÇ6RÂ–æFVçCÓ"’¢VÆ–bF–væ÷7F–73 ¢f÷"—FVÒ–âF–væ÷7F–73 ¢&–çB†b'¶—FVÒçF‡Ó¢·¶—FVÒæ6öFWÕÒ¶—FVÒæÖW76vWÒ"¢&–çB†b%fÆ–FF–öâf–ÆVBv—F‚¶ÆVâ†F–væ÷7F–72—ÒF–væ÷7F–2‡2’â"Âf–ÆS×7—2ç7FFW'"¢VÇ6S ¢&–çB‚&VÖ&VFFVBÖ×VÇF’ÖvVçB6öæf–wW&F–öâ—2fÆ–Bâ"¢&WGW&â–bF–væ÷7F–72VÇ6R   ¦–bõöæÖUõòÓÒ%õöÖ–åõò# ¢&—6R7—7FVÔW†—B†Ö–â‚’