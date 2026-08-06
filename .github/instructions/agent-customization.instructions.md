---
name: Agent Kit Configuration Rules
applyTo: ".github/agents/**/*.agent.md,.github/prompts/**/*.prompt.md,.github/instructions/**/*.instructions.md,.github/skills/**/SKILL.md,.project/**/*.md,.project/**/*.yml,.project/**/*.yaml"
description: Agent Kit 结构、权限和去重规则 / Agent Kit structure, permissions, and deduplication rules
---

# Agent Kit Configuration Rules

> 中文：本文档采用固定双语结构。更新中文或英文内容时，必须同步更新另一部分，保持两部分语义一致。
>
> English: This document uses a fixed bilingual structure. When either the Chinese or English content is updated, the other section must be updated as well to keep both sections semantically aligned.

## 中文 / Chinese

- `.github/agent-contracts.md` 是运行行为唯一事实源。Agent 只保留角色职责、权限、状态机和允许的 handoff；Prompt 只保留输入适配与路由；Skill 只保留专项步骤。不得复制完整共享契约。
- 保留五个业务 Agent（`Orchestrator`、`BugResolver`、`EmbeddedDeveloper`、`QualityReviewer`、`DocKeeper`）和一个隐藏 `NextActionRouter`。所有 Agent 显式使用 `target: vscode`、最小工具集且不固定模型。
- 只有两个 manager 和只读 Router 可拥有 `agent` 工具与 allowlist。两个 manager 不自动相互调用，specialist 不嵌套委派。
- 五个业务 Agent 可由用户调用；Router 使用 `user-invocable: false` 与 `disable-model-invocation: true`。基础 handoff 和 Router 返回入口为 `send: false`；业务 Agent 末尾的 `send: true` Next Action handoff 仅作人工恢复，不是默认自动入口。
- Handoff 的精确标签、顺序、目标、发送方式和安全提示由验证器检查。按钮只负责角色切换，不提供缺失输入，也不确认 Jira、修改内容、commit、push 或外部命令。
- 只有确实需要用户输入、外部动作或新增权限时才生成 Next Action，并显式使用 `Input Required: YES`、逐项 `Required Input` 和可复制 `Reply Template`。Agent 自己可继续的工作同轮执行，成功结果不生成 Next Action。
- 所有 Agent 在首次回复的第一个字符前先解析或传递 `Chat Language`。有 Latin-script 自然语言单词且无 Han 自然语言文本时必须使用 `en-US`，Jira ID 等标识符不得覆盖该结果。当该值为 `en` 或 `en-*` 时，发送前扫描完整草稿，出现 Agent 生成的 Han 字符必须丢弃并重新生成。`Dispatch Target` 只使用共享契约定义的纯 ASCII 稳定 ID。
- Next Action 在计算语义动作后必须按 `Chat Language` 独立渲染。`en` 或 `en-*` 块的所有生成字段值只使用英文词表和 ASCII 标点；出现 Han、CJK/全角标点、中文允许值或中文模板时必须丢弃并重新渲染整块。
- Prompt 不声明 `tools`，必须把 `${input:...}` 交给目标 Agent；需要 Skill 时直接链接其规范文件。
- Skill 目录名与小写连字符 `name` 一致，附属资源从 `SKILL.md` 直接链接；确定性脚本留在对应 Skill 的 `scripts/`。
- `.project/project.yml` 是项目级约束唯一入口；规则通过 `rules` 注册，Git policy 通过 `git_policy` 引用，集成扩展写入 `extensions`。Git policy 的 `workflow` 必须固定 `streamlined`、`new-or-worsened`、`risk-based`、`impact-based` 和 `once`。
- 运行实现留在 `.github/agent-kit/scripts/`；单元测试、fixtures、测试依赖和人工烟测统一留在 `tests/agent-kit/`，只在维护本工具包时通过 `--development` 校验，不得成为目标项目运行时隐式输入或交付门禁。
- Frontmatter 之外的 first-party Markdown 使用完整中英双区。

## English

- `.github/agent-contracts.md` is the single source of truth for runtime behavior. An Agent keeps only role responsibilities, permissions, its state machine, and allowed handoffs; a prompt keeps only input adaptation and routing; a Skill keeps only specialized steps. Never copy the complete shared contract.
- Keep five business Agents (`Orchestrator`, `BugResolver`, `EmbeddedDeveloper`, `QualityReviewer`, and `DocKeeper`) plus one hidden `NextActionRouter`. Every Agent explicitly uses `target: vscode`, a least-privilege tool set, and no pinned model.
- Only the two managers and the read-only Router may have the `agent` tool and an allowlist. The managers never auto-invoke each other, and specialists never delegate recursively.
- The five business Agents are user-invocable; the Router uses `user-invocable: false` and `disable-model-invocation: true`. Base handoffs and Router returns use `send: false`; the final `send: true` Next Action handoff on a business Agent is manual recovery only, not the default automatic entry.
- The validator checks exact handoff labels, order, targets, send behavior, and safety prompts. A button changes roles only; it supplies no missing input and confirms no Jira, change content, commit, push, or external command.
- Generate Next Action only for genuine user input, external work, or new authority, using `Input Required: YES` with itemized `Required Input` and a copy-ready `Reply Template`. Continue agent-owned work in the same run and omit Next Action from successful results.
- Every Agent resolves or preserves `Chat Language` before the first character of the first response. Latin-script natural-language words with no Han natural-language text require `en-US`; identifiers such as Jira IDs never override that result. For `en` or `en-*`, scan the complete draft before sending and discard/regenerate it when any agent-generated portion contains a Han-script character. `Dispatch Target` uses only the ASCII stable IDs defined by the shared contract.
- Render Next Action separately after computing the semantic action. For `en` or `en-*`, every generated field value uses English vocabulary and ASCII punctuation; Han, CJK/fullwidth punctuation, Chinese allowed values, or a Chinese template invalidates and rerenders the whole block.
- Prompts declare no `tools`, pass `${input:...}` to the target Agent, and directly link a required Skill specification.
- A Skill directory matches its lowercase-hyphen `name`, links supporting resources directly from `SKILL.md`, and keeps deterministic helpers in its own `scripts/` directory.
- `.project/project.yml` is the sole project-policy entry point. Register rules through `rules`, reference Git policy through `git_policy`, and place integration data under `extensions`. Git policy `workflow` must fix `streamlined`, `new-or-worsened`, `risk-based`, `impact-based`, and `once`.
- Runtime implementation remains in `.github/agent-kit/scripts/`. Unit tests, fixtures, test dependencies, and manual smoke tests remain together in `tests/agent-kit/`, are checked through `--development` only while maintaining this kit, and never become target-project runtime input or a delivery gate.
- First-party Markdown after frontmatter uses complete Chinese and English sections.
