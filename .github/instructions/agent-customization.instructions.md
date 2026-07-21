---
name: Agent Kit Configuration Rules
applyTo: ".github/agents/**/*.agent.md,.github/prompts/**/*.prompt.md,.github/instructions/**/*.instructions.md,.github/skills/**/SKILL.md,.project/**/*.md,.project/**/*.yml,.project/**/*.yaml"
description: 五业务 Agent 加隐藏 Router 的配置和最小权限规则 / Five business agents plus hidden Router configuration and least-privilege rules
---

# Agent Kit Configuration Rules

> 中文：本文档采用固定双语结构。更新中文或英文内容时，必须同步更新另一部分，保持两部分语义一致。
>
> English: This document uses a fixed bilingual structure. When either the Chinese or English content is updated, the other section must be updated as well to keep both sections semantically aligned.

## 中文 / Chinese

- 保留五个业务 agent（`Orchestrator`、`BugResolver`、`EmbeddedDeveloper`、`QualityReviewer`、`DocKeeper`）和一个隐藏的 `NextActionRouter`。
- 所有 agent 显式设置 `target: vscode` 和最小工具集；五个业务 Agent 为 `user-invocable: true`，Router 为 `user-invocable:false` 且 `disable-model-invocation:true`；不固定模型，不使用已弃用的 `infer`。
- 只有 `Orchestrator`、`BugResolver` 和只读 Router 可拥有 `agent` 工具与 `agents` allowlist；两个 manager 不得自动相互调用，三个 specialist 不得嵌套委派。
- 业务基础 handoff 和 Router 返回 handoff 显式 `send:false`；每个业务 Agent 仅末尾统一 `执行下一步 / Next Action` 使用 `send:true`。
- Prompt 只负责输入和 agent 路由，不声明 `tools`，以继承目标 agent 权限。
- Skill 目录名必须与 `name` 一致、使用小写连字符；附属资源必须从 `SKILL.md` 直接链接。
- BugResolver 及 `firmware-log-analysis` 必须保留 `GUIDE_SYMPTOMS`、按需 `CONFIRM_DIRECTION`、`Usage Symptom Questions`、`Usage Symptom Profile` 和 `Direction Confirmation` 契约；使用现象问题不得与证据材料请求混用。
- BugResolver 的授权修复闭环必须保留 `DOCUMENT → DELIVERY → CLOSE → RESET → INTAKE`、显式 `Git Delivery` 传递、遗漏选择时的一次性询问，以及用单独交付 Task Brief 调用 `EmbeddedDeveloper` 的规则；BugResolver 不得直接执行 Git 写操作。
- `BugResolver`、`QualityReviewer` 和 `DocKeeper` 必须各自保留一个标签为 `Git 提交交付 / Git Delivery`、目标为 `EmbeddedDeveloper`、`send: false` 的 handoff，保证人工角色切换后仍有可见交付入口。
- `EmbeddedDeveloper` 必须保留一个标签为 `问题已解决 / Close Issue`、目标为 `BugResolver`、`send: false` 的 handoff；BugResolver 必须在实际闭环前重新核对门禁与交付结果。
- Git Delivery handoff 必须建议 `commit` 为待确认默认值，只要求用户主动提供 Jira ID 并确认/修正；其余 commit 字段由 Agent 从本次修改证据生成。推荐默认值不得替代授权，`commit-and-push`/`auto` 不得默认。
- Handoff 已切换到 EmbeddedDeveloper 后，用户在当前输入框确认；当前 Developer 必须直接执行交付，不得自我委派、声称还要委派 EmbeddedDeveloper，或等待另一个 commit handoff 按钮。
- 所有业务 Agent 正文必须保留完整动态 `## Next Action` 契约及 `UI Route`、`Dispatch Target`、`Instruction`。原基础按钮标签、相对顺序、目标和 `send:false` 不变；末尾只追加一个 `执行下一步 / Next Action`，目标隐藏 Router 且 `send:true`。Router 自身必须按固定顺序保留五个目标为业务 Agent 的 `send:false` 静态返回按钮，防止切换后 footer 为空；这些按钮只供恢复。角色切换使用 `NEXT_ACTION_BUTTON + HANDOFF:<精确基础按钮标签>`；CURRENT_INPUT/EXTERNAL/NONE 的 Dispatch Target 均为 NONE，按钮点击不得代替输入或 Git 授权。
- 可选的 `.project/project.yml` 是项目级约束唯一入口；规范文件必须通过 `rules` 注册，Git policy 必须通过 `git_policy` 引用。结构化扩展数据放入 `extensions`。
- Git policy 不得保存 remote、URL 或目标 ref，也不得用 `scope.allowed_paths` 决定 commit 内容；旧字段只能兼容解析。必须保留 `Task Change Baseline → DETECT_COMMIT_SCOPE → Commit Content`、逐文件证据、`Change Confirmation: PENDING` 和 `ADJUST_CHANGESET` 循环。自动 commit 前，auto 还必须保留 `Commit Content Confirmation: PENDING → --expected-content-fingerprint → content_confirmation.status: CONFIRMED` 门禁；缺失或漂移返回 `CONFIRM_COMMIT_CONTENT`，不得写 Git。
- Frontmatter 之外的正文遵循完整中英双区结构。

## English

- Keep five business agents (`Orchestrator`, `BugResolver`, `EmbeddedDeveloper`, `QualityReviewer`, and `DocKeeper`) plus one hidden `NextActionRouter`.
- Every agent sets `target: vscode` and a least-privilege tool list. The five business agents use `user-invocable: true`; the Router uses `user-invocable:false` and `disable-model-invocation:true`. Do not pin a model or use deprecated `infer`.
- Only `Orchestrator`, `BugResolver`, and the read-only Router may have the `agent` tool and an `agents` allowlist. The two managers never auto-invoke each other, and the three specialists never delegate recursively.
- Business base handoffs and Router returns use `send:false`; only the final unified `执行下一步 / Next Action` on each business agent uses `send:true`.
- Prompts only capture input and route to an agent. They omit `tools` so they inherit the target agent's permissions.
- A Skill directory name matches its lowercase-hyphen `name`, and `SKILL.md` directly links every supporting resource.
- BugResolver and `firmware-log-analysis` retain the `GUIDE_SYMPTOMS`, conditional `CONFIRM_DIRECTION`, Usage Symptom Questions, Usage Symptom Profile, and Direction Confirmation contracts. Usage-symptom questions never mix with evidence-material requests.
- An authorized BugResolver repair loop retains `DOCUMENT → DELIVERY → CLOSE → RESET → INTAKE`, explicit `Git Delivery` propagation, a single prompt when the choice was omitted, and delegation to `EmbeddedDeveloper` through a separate delivery Task Brief. BugResolver never performs Git writes directly.
- `BugResolver`, `QualityReviewer`, and `DocKeeper` each retain one `Git 提交交付 / Git Delivery` handoff targeting `EmbeddedDeveloper` with `send: false`, so delivery remains visible after manual role transitions.
- `EmbeddedDeveloper` retains one `问题已解决 / Close Issue` handoff targeting `BugResolver` with `send: false`; BugResolver rechecks gates and delivery before closing.
- A Git Delivery handoff proposes `commit` as a recommended default pending confirmation, asks only for the user-supplied Jira ID plus confirmation/corrections, and generates every other commit field from this change's evidence. The recommendation never replaces authorization, and `commit-and-push`/`auto` are never defaults.
- After the handoff has switched to EmbeddedDeveloper, the user confirms in the current input box and the current Developer executes delivery directly. It never delegates to itself, says it will delegate to EmbeddedDeveloper, or waits for another commit handoff button.
- Every business-agent body retains the complete dynamic `## Next Action` contract with `UI Route`, `Dispatch Target`, and `Instruction`. Existing base labels, relative order, targets, and `send:false` remain unchanged; append exactly one `send:true` `执行下一步 / Next Action` targeting the hidden Router. The Router itself retains five ordered `send:false` static returns to the business agents so the footer never becomes empty; they are recovery entries only. Role transitions use `NEXT_ACTION_BUTTON + HANDOFF:<exact base-button label>`; CURRENT_INPUT/EXTERNAL/NONE use Dispatch Target NONE, and a button click never replaces input or Git authorization.
- Optional `.project/project.yml` is the sole project-level constraint entry point. Register rule files through `rules`, reference Git policy through `git_policy`, and place structured extension data under `extensions`.
- Git policy never stores a remote, URL, or target ref and never determines commit content through `scope.allowed_paths`; the legacy field is compatibility-only. Retain `Task Change Baseline → DETECT_COMMIT_SCOPE → Commit Content`, per-file evidence, `Change Confirmation: PENDING`, and the `ADJUST_CHANGESET` loop. Before automatic commit, auto also retains `Commit Content Confirmation: PENDING → --expected-content-fingerprint → content_confirmation.status: CONFIRMED`; missing or stale confirmation returns `CONFIRM_COMMIT_CONTENT` with no Git write.
- Body content after frontmatter follows the complete Chinese-English two-section structure.
