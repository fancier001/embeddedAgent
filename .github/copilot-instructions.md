# Embedded Project Copilot Instructions

> 中文：本文档采用固定双语结构。更新中文或英文内容时，必须同步更新另一部分，保持两部分语义一致。
>
> English: This document uses a fixed bilingual structure. When either the Chinese or English content is updated, the other section must be updated as well to keep both sections semantically aligned.

## 中文 / Chinese

### 唯一事实源

- [Agent 公共契约](agent-contracts.md) 定义 Task Brief、状态、报告、Next Action、Bug 证据和 Git 交付；其他配置只引用，不复制该行为。
- [项目画像](embedded-project.yml) 保存已确认的工程事实；`auto` 字段必须通过仓库只读探测解析。
- 可选的 [项目规则清单](../.project/project.yml) 是项目级约束入口。根据 Task Brief、允许范围和真实 diff 加载所有适用规则；缺失时兼容旧项目继续。
- 规则、画像和仓库事实冲突时报告配置漂移，并停止依赖冲突事实；不得静默改写配置。

### 标准工作流

1. 明确用户目标、授权范围、禁止动作和验收条件。
2. 建立 baseline，读取共享契约、项目画像和适用项目规则。
3. 选择一个负责 Agent；Prompt 只适配输入，Skill 只提供专项流程。
4. 完成最小范围工作，保留真实命令、退出码、关键输出和未运行项。
5. 按共享契约完成独立评审、必要文档、可选 Git 交付和唯一 `## Next Action`。

### 工程与安全

- 优先复用现有 C 标准、目录、命名、HAL、错误码、日志、构建和测试体系；空白工程默认值不得覆盖成熟工程约定。
- 保持最小任务范围，保留用户已有修改；vendor、generated 和第三方路径默认只读。
- 不臆造寄存器、位定义、引脚、电气、时序或芯片行为。硬件事实必须匹配器件和 revision；否则使用符号占位或返回 `BLOCKED`。
- 未获明确授权不得执行 flash、erase、fuse、reset、HIL、设备电源、发布或外部部署；禁止破坏性 Git、静默安装依赖和无关的 formatter/codegen。
- 分析请求默认只读。Bug 修复必须由 `BugResolver` 确认证据方向，再委派 `EmbeddedDeveloper`，随后独立评审。

### 角色与交付

- `Orchestrator` 负责通用交付编排；`BugResolver` 负责 Bug 诊断与修复闭环。两个 manager 不自动相互调用。
- `EmbeddedDeveloper` 是常规功能代码写入者；`QualityReviewer` 独立评审且不改功能代码；`DocKeeper` 只同步已验证事实。
- 五个业务 Agent 的基础 handoff 是人工恢复入口；唯一自动入口是末尾 `执行下一步 / Next Action`，由只读 `NextActionRouter` 按共享契约路由。
- Git policy 只约束交付，不产生授权。Jira 必须由用户提供；commit、push、自动交付、内容调整和 fingerprint 漂移均按共享契约处理。
- push 目标只从当前仓库本地 Git 配置解析；禁止 force、`push -u`、自定义 refspec、删除远端分支或修改 `.git/config`。

### 证据与文档

- 已有 baseline 失败与本次新增失败分开报告；缺失工具、未运行测试和启发式检查不得写成通过。
- MISRA 模型结果只称风险筛查；只有匹配的标准、deviation 和工具报告可支持合规结论。
- first-party 团队 Markdown 使用完整中英双区；路径、标识符、命令、寄存器、日志和编译器输出保持原文。

## English

### Sources of Truth

- The [shared Agent contract](agent-contracts.md) defines Task Briefs, states, reports, Next Action, bug evidence, and Git delivery. Other configuration references this behavior instead of copying it.
- The [project profile](embedded-project.yml) stores confirmed engineering facts. Resolve `auto` fields through read-only repository discovery.
- The optional [project rule manifest](../.project/project.yml) is the project-policy entry point. Load every rule matching the Task Brief, allowed scope, and actual diff; continue in legacy-compatible mode when it is absent.
- When a rule, profile, and repository fact conflict, report configuration drift and stop relying on the conflicting fact; never silently rewrite configuration.

### Standard Workflow

1. Establish the user's goal, authorized scope, forbidden actions, and acceptance criteria.
2. Record the baseline and read the shared contract, project profile, and applicable project rules.
3. Select one owning Agent. A prompt only adapts input, and a Skill only supplies a specialized procedure.
4. Complete the smallest scoped work while preserving real commands, exit codes, key output, and unrun items.
5. Use the shared contract to close independent review, required documentation, optional Git delivery, and exactly one `## Next Action`.

### Engineering and Safety

- Reuse the existing C standard, layout, naming, HAL, error codes, logging, build, and test systems. Greenfield defaults never override a mature repository.
- Keep scope minimal and preserve user changes. Treat vendor, generated, and third-party paths as read-only by default.
- Never invent registers, bit definitions, pins, electrical properties, timing, or chip behavior. Hardware facts must match the device and revision; otherwise use symbolic placeholders or return `BLOCKED`.
- Without explicit authorization, never run flash, erase, fuse, reset, HIL, device-power, release, or external deployment actions. Destructive Git, silent dependency installation, and unrelated formatter/codegen runs are forbidden.
- Analysis requests are read-only by default. A bug fix requires `BugResolver` to establish the evidence direction, delegate to `EmbeddedDeveloper`, and obtain independent review.

### Roles and Delivery

- `Orchestrator` owns general delivery orchestration; `BugResolver` owns bug diagnosis and resolution. The two managers never auto-invoke each other.
- `EmbeddedDeveloper` performs normal functional-code writes; `QualityReviewer` reviews independently without changing functional code; `DocKeeper` synchronizes verified facts only.
- Base handoffs on the five business Agents are manual recovery entries. The only automatic entry is the final `执行下一步 / Next Action`, routed by the read-only `NextActionRouter` under the shared contract.
- Git policy constrains delivery but grants no authority. Jira is user-supplied; commit, push, automatic delivery, change adjustment, and fingerprint drift follow the shared contract.
- Resolve push targets only from the current repository's local Git configuration. Never force, use `push -u`, supply custom refspecs, delete remote branches, or modify `.git/config`.

### Evidence and Documentation

- Report pre-existing baseline failures separately from failures introduced by the change. Missing tools, unrun tests, and heuristic checks are never passes.
- Model-based MISRA results are risk screening only. A compliance conclusion requires the matching standard, deviation configuration, and tool report.
- First-party team Markdown uses complete Chinese and English sections. Preserve paths, identifiers, commands, registers, logs, and compiler output verbatim.
