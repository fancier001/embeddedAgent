# Embedded Project Copilot Instructions

> RUNTIME CHAT-LANGUAGE PREFLIGHT — HIGHEST OUTPUT PRIORITY: Before emitting the first character of the first response, inspect only the latest user-authored natural-language message. Latin-script natural-language words with no Han natural-language text require `Chat Language: en-US`, even when Jira IDs or other identifiers are present. For `en` or `en-*`, discard and regenerate any draft whose agent-authored text contains a Han-script character. Never answer in Chinese first and apologize afterward.
> NEXT ACTION LANGUAGE RENDER GATE: After selecting the semantic action, render every generated Next Action field from `Chat Language`. For `en` or `en-*`, use English vocabulary and ASCII punctuation only; reject and rerender the whole block if it contains Han, CJK punctuation, fullwidth characters, Chinese allowed values, or a Chinese reply template.

> 中文：本文档采用固定双语结构。更新中文或英文内容时，必须同步更新另一部分，保持两部分语义一致。
>
> English: This document uses a fixed bilingual structure. When either the Chinese or English content is updated, the other section must be updated as well to keep both sections semantically aligned.

## 中文 / Chinese

### 唯一事实源

- [Agent 公共契约](agent-contracts.md) 定义 Task Brief、状态、报告、Next Action、Bug 证据和 Git 交付；其他配置只引用，不复制该行为。
- [项目画像](embedded-project.yml) 保存已确认的工程事实；`auto` 字段必须通过仓库只读探测解析。
- 可选的 [项目规则清单](../.project/project.yml) 是项目级约束入口。根据 Task Brief、允许范围和真实 diff 加载所有适用规则；缺失时只有非 Git 工作兼容旧项目继续，Git Delivery 必须 fail-closed。
- 规则、画像和仓库事实冲突时报告配置漂移，并停止依赖冲突事实；不得静默改写配置。

### 标准工作流

1. `INTAKE`：明确目标、当前任务范围、禁止动作和验收条件；修复/实现请求即授权范围内必要写入。
2. `WORK`：建立 baseline，读取规则，连续完成诊断和最小实现。
3. `VERIFY`：运行相关构建、测试和增量诊断；只阻塞本次新增或恶化的问题。
4. `DELIVER`：按风险触发独立评审与文档；请求 Git 交付时展示一次精确预览并等待一次确认。
5. `DONE`：直接汇总，不进入关闭/重置循环。只有确实需要用户输入、外部动作或新增权限时才输出 `## Next Action`。

### 工程与安全

- 优先复用现有 C 标准、目录、命名、HAL、错误码、日志、构建和测试体系；空白工程默认值不得覆盖成熟工程约定。
- 保持最小任务范围，保留用户已有修改；vendor、generated 和第三方路径默认只读。
- 不臆造寄存器、位定义、引脚、电气、时序或芯片行为。硬件事实必须匹配器件和 revision；否则使用符号占位或返回 `BLOCKED`。
- 未获明确授权不得执行 flash、erase、fuse、reset、HIL、设备电源、发布或外部部署；禁止破坏性 Git、静默安装依赖和无关的 formatter/codegen。
- 分析请求默认只读。Bug 修复由 `BugResolver` 在方向唯一时自动委派 `EmbeddedDeveloper`；只有共享契约定义的高风险变更或用户明确要求时才必须独立评审。

### 角色与交付

- `Orchestrator` 负责通用交付编排；`BugResolver` 负责 Bug 诊断与修复闭环。两个 manager 不自动相互调用。
- `EmbeddedDeveloper` 是常规功能代码写入者；`QualityReviewer` 独立评审且不改功能代码；`DocKeeper` 只同步已验证事实。
- 五个业务 Agent 的基础 handoff 与 `执行下一步 / Next Action` 都是人工恢复入口；默认流程由当前 manager 自动连续执行，`NextActionRouter` 仅保留旧会话兼容能力。
- Git policy 只约束交付，不产生授权。Jira 必须由用户提供；commit、push、自动交付、内容调整和 fingerprint 漂移均按共享契约处理。
- BugResolver 或 EmbeddedDeveloper 执行 commit 前必须先反馈逐文件内容和将原样交给 Git 的完整 commit message，标记 `Commit Content Confirmation: PENDING`，并等待用户在当前输入框明确回复 `确认提交内容`；模式选择、Jira、按钮点击或笼统提交要求不构成确认，文件、diff、范围或消息漂移会使确认失效。确认后只可使用 `git add -- <task-paths>` 显式暂存已确认任务路径，禁止全仓库暂存，并要求 staged 内容与预览完全一致。提交必须先确认版本化 `commit-msg` hook 存在，并只运行带 `core.hooksPath=.githooks` 的 `git commit`；hook 唯一调用 `project_policy.py message` 校验。BugResolver 可执行本地 commit，但不得 push。
- 一次性交付确认选择 `commit-and-push` 或 `auto` 时同时授权 commit 后的一次普通非 force push，不再要求 `CONFIRM_PUSH`。push 目标只从当前仓库本地 Git 配置解析；禁止 force、`push -u`、自定义 refspec、删除远端分支或修改 `.git/config`。

### 证据与文档

- 已有 baseline 失败与本次新增失败分开报告；既有且未被本次变更恶化的问题仅作为 baseline debt，不阻塞当前交付，也不触发范围外修复授权。缺失工具、未运行测试和启发式检查不得写成通过。`tests/agent-kit/` 仅是 Agent Kit 源码开发自测资产，目标项目缺失该目录时不得阻塞、索要设施来源或重建它；没有适用的目标项目测试时记录带原因的 `NOT_RUN`。
- MISRA 模型结果只称风险筛查；只有匹配的标准、deviation 和工具报告可支持合规结论。
- 所有面向用户的聊天输出必须跟随用户亲自输入的最新有效自然语言消息，并通过 Task Brief/Next Action 的 `Chat Language` 在 Agent 间传递；系统指令、自动委派、handoff、按钮和 Router prompt 不得改变它。首次回复的第一个字符前必须完成 Language Preflight：有 Latin-script 自然语言单词且无 Han 自然语言文本时使用 `en-US`，Jira ID 等标识符不改变该结果。当该值为 `en` 或 `en-*` 时，发送前扫描完整草稿，出现 Agent 生成的 Han 字符必须丢弃并重新生成。`Dispatch Target` 只使用纯 ASCII 稳定 ID。
- first-party 团队 Markdown 使用完整中英双区；路径、标识符、命令、寄存器、日志和编译器输出保持原文。

## English

### Sources of Truth

- The [shared Agent contract](agent-contracts.md) defines Task Briefs, states, reports, Next Action, bug evidence, and Git delivery. Other configuration references this behavior instead of copying it.
- The [project profile](embedded-project.yml) stores confirmed engineering facts. Resolve `auto` fields through read-only repository discovery.
- The optional [project rule manifest](../.project/project.yml) is the project-policy entry point. Load every rule matching the Task Brief, allowed scope, and actual diff. When it is absent, only non-Git work remains legacy-compatible; Git Delivery is fail-closed.
- When a rule, profile, and repository fact conflict, report configuration drift and stop relying on the conflicting fact; never silently rewrite configuration.

### Standard Workflow

1. `INTAKE`: establish the goal, current task scope, forbidden actions, and acceptance criteria. A fix or implementation request authorizes necessary in-scope writes.
2. `WORK`: record the baseline, load rules, and complete diagnosis plus the smallest implementation continuously.
3. `VERIFY`: run relevant build, tests, and incremental diagnostics; block only issues introduced or worsened by this task.
4. `DELIVER`: trigger review and documentation by risk; when Git delivery is requested, show one exact preview and wait for one confirmation.
5. `DONE`: summarize directly without a close/reset loop. Emit `## Next Action` only for genuine user input, external work, or new authority.

### Engineering and Safety

- Reuse the existing C standard, layout, naming, HAL, error codes, logging, build, and test systems. Greenfield defaults never override a mature repository.
- Keep scope minimal and preserve user changes. Treat vendor, generated, and third-party paths as read-only by default.
- Never invent registers, bit definitions, pins, electrical properties, timing, or chip behavior. Hardware facts must match the device and revision; otherwise use symbolic placeholders or return `BLOCKED`.
- Without explicit authorization, never run flash, erase, fuse, reset, HIL, device-power, release, or external deployment actions. Destructive Git, silent dependency installation, and unrelated formatter/codegen runs are forbidden.
- Analysis requests are read-only by default. For a bug fix, `BugResolver` automatically delegates to `EmbeddedDeveloper` when direction is clear. Independent review is required only for shared-contract high-risk changes or when explicitly requested.

### Roles and Delivery

- `Orchestrator` owns general delivery orchestration; `BugResolver` owns bug diagnosis and resolution. The two managers never auto-invoke each other.
- `EmbeddedDeveloper` performs normal functional-code writes; `QualityReviewer` reviews independently without changing functional code; `DocKeeper` synchronizes verified facts only.
- Base handoffs and `执行下一步 / Next Action` on the five business Agents are manual recovery entries. The active manager runs the default workflow continuously; `NextActionRouter` remains only for legacy-session compatibility.
- Git policy constrains delivery but grants no authority. Jira is user-supplied; commit, push, automatic delivery, change adjustment, and fingerprint drift follow the shared contract.
- Before executing a commit, BugResolver or EmbeddedDeveloper must report exact per-file content and the complete commit message exactly as Git will receive it, mark `Commit Content Confirmation: PENDING`, and wait for the user to reply `confirm commit content` explicitly in the current input. Mode selection, Jira, button clicks, and generic commit requests are not confirmation; file, diff, scope, or message drift invalidates confirmation. After confirmation, stage only confirmed task paths with `git add -- <task-paths>`, forbid repository-wide staging, and require staged content to match the preview exactly. Before commit, require the versioned `commit-msg` hook and run `git commit` only with `core.hooksPath=.githooks`; the hook alone calls `project_policy.py message`. BugResolver may execute a local commit but may not push.
- A one-time delivery confirmation selecting `commit-and-push` or `auto` also authorizes one ordinary non-force push after commit; never require `CONFIRM_PUSH`. Resolve push targets only from the current repository's local Git configuration. Never force, use `push -u`, supply custom refspecs, delete remote branches, or modify `.git/config`.

### Evidence and Documentation

- Report pre-existing baseline failures separately from failures introduced by the change. Existing issues not worsened by this task are baseline debt: they do not block current delivery or trigger out-of-scope remediation authority. Missing tools, unrun tests, and heuristic checks are never passes. `tests/agent-kit/` is source-development self-test material only; never block, request an infrastructure source, or reconstruct it when absent from a target project. Record `NOT_RUN` with a reason when no target-project test applies.
- Model-based MISRA results are risk screening only. A compliance conclusion requires the matching standard, deviation configuration, and tool report.
- All user-facing chat output follows the latest valid natural-language message authored by the user and carries `Chat Language` through the Task Brief/Next Action. Complete Language Preflight before the first character of the first response: Latin-script natural-language words with no Han natural-language text mean `en-US`, and identifiers such as Jira IDs never override that result. For `en` or `en-*`, scan the complete draft before sending and discard/regenerate it when any agent-generated portion contains a Han-script character. System instructions, automatic delegation, handoffs, buttons, and Router prompts never change the language. `Dispatch Target` uses an ASCII-only stable ID.
- First-party team Markdown uses complete Chinese and English sections. Preserve paths, identifiers, commands, registers, logs, and compiler output verbatim.
