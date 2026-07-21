---
name: Agent Kit Configuration Rules
applyTo: ".github/agents/**/*.agent.md,.github/prompts/**/*.prompt.md,.github/instructions/**/*.instructions.md,.github/skills/**/SKILL.md,.project/**/*.md,.project/**/*.yml,.project/**/*.yaml"
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
- BugResolver 及 `firmware-log-analysis` 必须保留 `GUIDE_SYMPTOMS`、按需 `CONFIRM_DIRECTION`、`Usage Symptom Questions`、`Usage Symptom Profile` 和 `Direction Confirmation` 契约；使用现象问题不得与证据材料请求混用。
- BugResolver 的授权修复闭环必须保留 `DOCUMENT → DELIVERY → CLOSE → RESET → INTAKE`、显式 `Git Delivery` 传递、遗漏选择时的一次性询问，以及用单独交付 Task Brief 调用 `EmbeddedDeveloper` 的规则；BugResolver 不得直接执行 Git 写操作。
- `BugResolver`、`QualityReviewer` 和 `DocKeeper` 必须各自保留一个标签为 `Git 提交交付 / Git Delivery`、目标为 `EmbeddedDeveloper`、`send: false` 的 handoff，保证人工角色切换后仍有可见交付入口。
- `EmbeddedDeveloper` 必须保留一个标签为 `问题已解决 / Close Issue`、目标为 `BugResolver`、`send: false` 的 handoff；BugResolver 必须在实际闭环前重新核对门禁与交付结果。
- Git Delivery handoff 必须建议 `commit` 为待确认默认值，只要求用户主动提供 Jira ID 并确认/修正；其余 commit 字段由 Agent 从本次修改证据生成。推荐默认值不得替代授权，`commit-and-push`/`auto` 不得默认。
- Handoff 已切换到 EmbeddedDeveloper 后，用户在当前输入框确认；当前 Developer 必须直接执行交付，不得自我委派、声称还要委派 EmbeddedDeveloper，或等待另一个 commit handoff 按钮。
- 所有 agent 的正文必须保留动态结构化 `## Next Action` 契约，包括规范 Action ID、`UI Route`、固定选择优先级和输入/handoff/Agent 继续/外部/终态五类路由。handoff 路由必须引用当前 Agent frontmatter 的精确现有按钮标签，不得动态创建、隐藏或改序按钮。`commit-and-push` 在 commit 后使用 `CONFIRM_PUSH` 二次确认，`auto` 保持自动；auto push 失败使用 `MANUAL_PUSH`，问题闭环后使用 `START_NEW_ISSUE`。所有 commit 模式确认前必须有 Documentation=`PASS` 或带 `Not required: <reason>` 的 `NOT_RUN`。
- 可选的 `.project/project.yml` 是项目级约束唯一入口；规范文件必须通过 `rules` 注册，Git policy 必须通过 `git_policy` 引用。结构化扩展数据放入 `extensions`。
- Git policy 不得保存 remote、URL 或目标 ref，也不得用 `scope.allowed_paths` 决定 commit 内容；旧字段只能兼容解析。必须保留 `Task Change Baseline → DETECT_COMMIT_SCOPE → Commit Content`、逐文件 state/增删统计/摘要/excluded paths/fingerprint、`Change Confirmation: PENDING` 和 `ADJUST_CHANGESET` 重新验证/独立评审循环，以及当前任务显式授权、`denied_paths`、精确暂存和禁止 force push 的安全不变量。`automation` 只约束 `auto`，启用它不能单独构成授权，关闭它也不得阻塞已通过 `CONFIRM_COMMIT`/`CONFIRM_PUSH` 的操作。
- Frontmatter 之外的正文遵循完整中英双区结构。

## English

- Keep exactly five agents: `Orchestrator`, `BugResolver`, `EmbeddedDeveloper`, `QualityReviewer`, and `DocKeeper`.
- Every agent explicitly sets `target: vscode`, `user-invocable: true`, and a least-privilege tool list. Do not pin a model or use deprecated `infer`.
- Only `Orchestrator` and `BugResolver` may have the `agent` tool and an `agents` allowlist. The two managers must not auto-invoke each other. `BugResolver` may invoke only the three non-delegating specialists; `EmbeddedDeveloper`, `QualityReviewer`, and `DocKeeper` must not delegate recursively.
- Every handoff explicitly sets `send: false`, and body text must not describe handoffs as automatic execution.
- Prompts only capture input and route to an agent. They omit `tools` so they inherit the target agent's permissions.
- A Skill directory name matches its lowercase-hyphen `name`, and `SKILL.md` directly links every supporting resource.
- BugResolver and `firmware-log-analysis` retain the `GUIDE_SYMPTOMS`, conditional `CONFIRM_DIRECTION`, Usage Symptom Questions, Usage Symptom Profile, and Direction Confirmation contracts. Usage-symptom questions never mix with evidence-material requests.
- An authorized BugResolver repair loop retains `DOCUMENT → DELIVERY → CLOSE → RESET → INTAKE`, explicit `Git Delivery` propagation, a single prompt when the choice was omitted, and delegation to `EmbeddedDeveloper` through a separate delivery Task Brief. BugResolver never performs Git writes directly.
- `BugResolver`, `QualityReviewer`, and `DocKeeper` each retain one `Git 提交交付 / Git Delivery` handoff targeting `EmbeddedDeveloper` with `send: false`, so delivery remains visible after manual role transitions.
- `EmbeddedDeveloper` retains one `问题已解决 / Close Issue` handoff targeting `BugResolver` with `send: false`; BugResolver rechecks gates and delivery before closing.
- A Git Delivery handoff proposes `commit` as a recommended default pending confirmation, asks only for the user-supplied Jira ID plus confirmation/corrections, and generates every other commit field from this change's evidence. The recommendation never replaces authorization, and `commit-and-push`/`auto` are never defaults.
- After the handoff has switched to EmbeddedDeveloper, the user confirms in the current input box and the current Developer executes delivery directly. It never delegates to itself, says it will delegate to EmbeddedDeveloper, or waits for another commit handoff button.
- Every agent body retains the dynamic structured `## Next Action` contract, including a canonical Action ID, `UI Route`, fixed selection priority, and typed-input/handoff/agent-continuation/external/terminal routing. A handoff route names an exact existing button label from the current agent frontmatter and never dynamically creates, hides, or reorders buttons. `commit-and-push` uses `CONFIRM_PUSH` after commit, `auto` remains automatic, failed auto push uses `MANUAL_PUSH`, and issue closure uses `START_NEW_ISSUE`. Every commit mode requires Documentation=`PASS` or `NOT_RUN` with `Not required: <reason>` before confirmation.
- Optional `.project/project.yml` is the sole project-level constraint entry point. Register rule files through `rules`, reference Git policy through `git_policy`, and place structured extension data under `extensions`.
- Git policy never stores a remote, URL, or target ref and never determines commit content through `scope.allowed_paths`; the legacy field is compatibility-only. Retain `Task Change Baseline → DETECT_COMMIT_SCOPE → Commit Content`, per-file state/added-deleted counts/summary/excluded paths/fingerprint, `Change Confirmation: PENDING`, the `ADJUST_CHANGESET` re-verification/independent-review loop, explicit current-task authorization, `denied_paths`, exact staging, and no-force-push safety. `automation` gates only `auto`: enabling it never authorizes a write by itself, and disabling it never blocks an operation already authorized through `CONFIRM_COMMIT`/`CONFIRM_PUSH`.
- Body content after frontmatter follows the complete Chinese-English two-section structure.
