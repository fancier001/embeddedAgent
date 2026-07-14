---
name: Agent Kit Configuration Rules
applyTo: ".github/agents/**/*.agent.md,.github/prompts/**/*.prompt.md,.github/instructions/**/*.instructions.md,.github/skills/**/SKILL.md"
description: 五 Agent Kit 配置和最小权限规则 / Five-agent kit configuration and least-privilege rules
---

# Agent Kit Configuration Rules

> 中文：本文档采用固定双语结构。更新中文或英文内容时，必须同步更新另一部分，保持两部分语义一致。
>
> English: This document uses a fixed bilingual structure. When either the Chinese or English content is updated, the other section must be updated as well to keep both sections semantically aligned.

## 中文 / Chinese

- 只保留 `Orchestrator`、`BugResolver`、`EmbeddedDeveloper`、`QualityReviewer`、`DocKeeper` 五个 agent。
- 所有 agent 显式设置 `target: vscode`、`user-invocable: true` 和最小工具集；不固定模型，不使用已弃用的 `infer`。
- 只有 `Orchestrator` 和 `BugResolver` 可拥有 `agent` 工具与 `agents` allowlist；两个 manager 不得自动相互调用，`BugResolver` 仅可调用三个非委派 specialist，`EmbeddedDeveloper`、`QualityReviewer`、`DocKeeper` 不得嵌套委派。
- 所有 handoff 显式 `send: false`，正文不得把 handoff 描述成自动执行。
- Prompt 只负责输入和 agent 路由，不声明 `tools`，以继承目标 agent 权限。
- Skill 目录名必须与 `name` 一致、使用小写连字符；附属资源必须从 `SKILL.md` 直接链接。
- Frontmatter 之外的正文遵循完整中英双区结构。

## English

- Keep exactly five agents: `Orchestrator`, `BugResolver`, `EmbeddedDeveloper`, `QualityReviewer`, and `DocKeeper`.
- Every agent explicitly sets `target: vscode`, `user-invocable: true`, and a least-privilege tool list. Do not pin a model or use deprecated `infer`.
- Only `Orchestrator` and `BugResolver` may have the `agent` tool and an `agents` allowlist. The two managers must not auto-invoke each other. `BugResolver` may invoke only the three non-delegating specialists; `EmbeddedDeveloper`, `QualityReviewer`, and `DocKeeper` must not delegate recursively.
- Every handoff explicitly sets `send: false`, and body text must not describe handoffs as automatic execution.
- Prompts only capture input and route to an agent. They omit `tools` so they inherit the target agent's permissions.
- A Skill directory name matches its lowercase-hyphen `name`, and `SKILL.md` directly links every supporting resource.
- Body content after frontmatter follows the complete Chinese-English two-section structure.
