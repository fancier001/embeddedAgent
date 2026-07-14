# Embedded Project Copilot Instructions

> 中文：本文档采用固定双语结构。更新中文或英文内容时，必须同步更新另一部分，保持两部分语义一致。
>
> English: This document uses a fixed bilingual structure. When either the Chinese or English content is updated, the other section must be updated as well to keep both sections semantically aligned.

## 中文 / Chinese

### 上下文入口

- 开始任务前读取 [项目画像](embedded-project.yml) 和 [Agent 公共契约](agent-contracts.md)。
- 项目画像中的显式事实优先；字段为 `auto` 时，再从 README、CI、Make/CMake、VS Code tasks、相邻模块和现有测试中探测。
- 如果项目画像与仓库实际状态冲突，报告配置漂移并停止依赖该冲突事实，不静默改写画像或仓库。

### 现有工程优先

- 复用项目已经采用的 C 标准、目录、命名、HAL、错误码、日志、构建和测试体系。
- C99、`src/`、`drivers/`、`test/` 和 `docs/` 只作为空白工程的回退默认值，不覆盖成熟工程约定。
- 保持最小任务范围，不重构无关代码，不覆盖或丢弃用户已有修改。
- vendor、generated 和第三方文件默认只读；除非用户明确授权，不在这些路径内生成修改。

### 应用逻辑

- 应用功能先明确状态、事件、合法转换、时间、重试、取消、幂等、恢复、兼容性和资源所有权，再实现最小垂直切片。
- 优先使用 host test、fake clock、fake service 和表驱动状态转换；需求标为 `covered` 时必须同时提供实现、测试和证据。

### Bug 诊断

- 用户要求理解、分析或修复 Bug 时，交给 `BugResolver` 使用 `bug-analysis` 建立只读诊断；日志/崩溃/ELF/MAP 场景同时使用 `fault-analysis` 辅助模式。
- BugResolver 先输出结构化 `Problem Identification`，基于事实识别问题类别、疑似子系统、观察严重度、触发条件、复现性、影响范围和证据置信度；不得把问题分类当作根因结论。
- 保留原始错误，区分现象、报错位置、触发条件和根因；追踪相关调用、状态、数据所有权、配置、依赖、版本与 baseline。
- 每个假设必须记录支持证据、反证、置信度和最小验证动作。只有因果链成立且主要替代解释被排除时才确认根因；否则返回 `INSUFFICIENT_EVIDENCE` 和精确的缺失材料。
- 缺少关键材料时，先搜索仓库并完成所有安全初判，再用一张 `Evidence Request` 表集中请求无法自行取得的最小资料；在补充前暂停根因确认和 Developer 委派，补充后不得重复索取。
- 日志分析覆盖 bare-metal、RTOS、模组 SDK、Embedded Linux 和 hybrid；保留原始行/偏移与时钟域，没有可靠时间基准时不得伪造统一时间或跨域顺序。
- 分析请求不修改代码。用户明确要求修复后，由 `BugResolver` 将已确认根因或可证伪的高置信假设交给 `EmbeddedDeveloper`，并调用 `QualityReviewer` 做独立质量评估。

### 嵌入式安全边界

- 禁止臆造寄存器地址、位定义、引脚、电气特性、时序和芯片行为。缺少匹配型号/revision 的资料时，使用无数值符号占位或返回 `BLOCKED`。
- MMIO 访问按项目 HAL 或寄存器定义处理。`volatile` 只解决特定编译器可见性问题，不代表原子性、内存顺序或 ISR/任务同步。
- 跨字节序数据必须显式打包/解包，不依赖未定义的结构体布局、位域顺序或未对齐指针访问。
- 未获明确授权不得执行 flash、erase、fuse、reset、设备电源控制、HIL、发布或外部部署命令。
- 不执行破坏性 Git 命令，不静默安装依赖，不运行与任务无关的格式化、代码生成或迁移。

### 证据与完成标准

- 每个子任务使用公共契约中的 `Task Brief`，每个结果使用统一 Agent Report。
- 命令证据包含实际命令、退出码和关键输出；未执行的验证标记为 `NOT_RUN` 并说明原因。
- 将既有 baseline 失败与本次变更新增失败分开，不把缺失工具、未运行测试或启发式检查写成通过。
- MISRA 的模型审查仅称为风险筛查；只有匹配的标准版本、deviation 配置和工具报告才能支持合规结论。
- 硬件事实引用本地受控资料或官方/供应商来源，并记录器件型号、文档编号、revision 和页码或 URL。

### 五 Agent 协作

- `Orchestrator` 是默认通用交付入口；它不编辑文件或执行命令，Bug 请求通过人工 handoff 或专用 prompt 切换到 BugResolver。
- `BugResolver` 专门编排 Bug 诊断与解决，可运行只读诊断命令并调用开发、质量评估和文档角色，但不直接修改文件；两个 manager 不自动相互调用。
- `EmbeddedDeveloper` 是唯一常规功能代码修改者，并负责构建和测试证据。
- `QualityReviewer` 只做独立质量评估，不负责 Bug 根因分析，也不修改功能代码。
- `DocKeeper` 维护 README、`docs/`、项目画像和明确授权的非行为性注释，不修改功能行为。
- 自动 subagent 委派与用户点击的 handoff 是不同机制；handoff 不代表任务已经自动提交或执行。

### 双语协作

- 用户未指定语言时，聊天输出可以使用中英双语标签；用户指定单一语言时遵循用户要求。
- first-party 团队 Markdown 使用完整双区结构：先 `## 中文 / Chinese`，后 `## English`。
- 文件名、路径、标识符、命令、寄存器名、日志和编译器原始输出保持原文。

## English

### Context Entry Points

- Read the [project profile](embedded-project.yml) and [shared agent contract](agent-contracts.md) before starting a task.
- Explicit facts in the project profile take precedence. When a field is `auto`, discover it from the README, CI, Make/CMake files, VS Code tasks, neighboring modules, and existing tests.
- If the profile conflicts with the repository, report configuration drift and stop relying on the conflicting fact. Do not silently rewrite either the profile or repository.

### Existing Project First

- Reuse the project's established C standard, layout, naming, HAL, error codes, logging, build, and test systems.
- C99, `src/`, `drivers/`, `test/`, and `docs/` are fallback defaults for a greenfield project only; they do not override a mature repository.
- Keep the task scope minimal, avoid unrelated refactors, and preserve all existing user changes.
- Treat vendor, generated, and third-party files as read-only unless the user explicitly authorizes changes there.

### Application Logic

- Before implementation, define states, events, legal transitions, timing, retries, cancellation, idempotency, recovery, compatibility, and resource ownership; then deliver the smallest vertical slice.
- Prefer host tests, fake clocks, fake services, and table-driven transitions. A `covered` requirement must include implementation, tests, and evidence.

### Bug Diagnosis

- When the user asks to understand, analyze, or fix a bug, give it to `BugResolver` to establish a read-only diagnosis in `bug-analysis` mode. Add `fault-analysis` for log/crash/ELF/MAP cases.
- BugResolver emits a structured Problem Identification first, using facts to classify the problem, suspected subsystem, observed severity, trigger, reproducibility, affected scope, and evidence confidence. Classification is not a root-cause conclusion.
- Preserve the original error and distinguish symptom, reporting location, trigger, and root cause. Trace related calls, states, data ownership, configuration, dependencies, versions, and baseline.
- Every hypothesis records supporting evidence, counter-evidence, confidence, and the smallest validation action. Confirm root cause only when the causal chain holds and main alternatives are excluded; otherwise return `INSUFFICIENT_EVIDENCE` with exact missing material.
- When critical material is missing, search the repository and finish every safe preliminary step before requesting the smallest unavailable evidence set once through an Evidence Request table. Pause root-cause confirmation and Developer delegation until it arrives, and never request supplied evidence twice.
- Log analysis covers bare-metal, RTOS, module SDK, Embedded Linux, and hybrid systems. Preserve original lines/offsets and clock domains; never invent a unified time or cross-domain order without reliable timing evidence.
- Analysis requests do not modify code. Only after the user explicitly asks for a fix may `BugResolver` give a confirmed root cause or falsifiable high-confidence hypothesis to `EmbeddedDeveloper`, followed by independent `QualityReviewer` assessment.

### Embedded Safety Boundaries

- Never invent register addresses, bit definitions, pins, electrical characteristics, timing, or chip behavior. Without documentation matching the exact device and revision, use symbolic placeholders without values or return `BLOCKED`.
- Access MMIO through the project's HAL or register definitions. `volatile` addresses specific compiler-visibility concerns; it does not provide atomicity, memory ordering, or ISR/task synchronization.
- Explicitly pack and unpack cross-endian data. Do not rely on undefined struct layout, bit-field ordering, or unaligned pointer access.
- Do not run flash, erase, fuse, reset, device power-control, HIL, release, or external deployment commands without explicit authorization.
- Do not use destructive Git commands, silently install dependencies, or run unrelated formatting, code generation, or migrations.

### Evidence and Completion

- Use the shared contract's `Task Brief` for every delegated task and the common Agent Report for every result.
- Command evidence includes the exact command, exit code, and relevant output. Mark unexecuted checks as `NOT_RUN` and explain why.
- Separate pre-existing baseline failures from regressions introduced by the change. Never present missing tools, unexecuted tests, or heuristic checks as passing.
- Describe model-based MISRA work as risk screening only. A compliance claim requires a matching standard edition, deviation configuration, and tool report.
- Cite hardware facts from controlled local documents or official/vendor sources, recording the device, document number, revision, and page or URL.

### Five-Agent Collaboration

- `Orchestrator` is the default general-delivery entry point; it does not edit files or run commands, and bug requests transition to BugResolver through a manual handoff or dedicated prompt.
- `BugResolver` exclusively orchestrates bug diagnosis and resolution. It may run read-only diagnostic commands and invoke development, quality-assessment, and documentation roles, but it does not edit files directly; the two managers never auto-invoke each other.
- `EmbeddedDeveloper` is the sole routine functional-code writer and supplies build and test evidence.
- `QualityReviewer` performs independent quality assessment only; it neither diagnoses bug root causes nor modifies functional code.
- `DocKeeper` maintains the README, `docs/`, the project profile, and explicitly authorized non-behavioral comments without changing functional behavior.
- Automatic subagent delegation and user-selected handoffs are different mechanisms. A handoff does not mean a task was automatically submitted or executed.

### Bilingual Collaboration

- When the user does not specify a language, chat output may use bilingual labels. Follow an explicit single-language request.
- First-party team Markdown uses two complete sections: `## 中文 / Chinese` first, followed by `## English`.
- Keep file names, paths, identifiers, commands, register names, logs, and raw compiler output unchanged.
