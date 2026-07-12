# Four-Agent Collaboration Contract

> 中文：本文档采用固定双语结构。更新中文或英文内容时，必须同步更新另一部分，保持两部分语义一致。
>
> English: This document uses a fixed bilingual structure. When either the Chinese or English content is updated, the other section must be updated as well to keep both sections semantically aligned.

## 中文 / Chinese

### 目的与适用范围

本文档是 `Orchestrator`、`EmbeddedDeveloper`、`QualityReviewer`、`DocKeeper` 的共享输入、输出和安全契约。四个 Agent 开始工作前必须读取本文件与 `.github/embedded-project.yml`；角色文件只定义专属行为，不得降低本契约要求。

规则优先级如下：

1. 用户在当前任务中的明确要求和授权。
2. 目标仓库的真实代码、构建、CI、文档和硬件证据。
3. `.github/embedded-project.yml` 中非 `auto` 的已确认配置。
4. 对 `auto` 字段的只读探测结果。
5. 仅用于空白工程的模板默认建议。

若画像与仓库事实冲突，报告“配置漂移”，不得静默选择一方或改写工程以迎合画像。

### Task Brief 输入契约

每次自动委派或人工 handoff 都必须形成自包含的 Task Brief。未知值写 `Unknown` 并说明它是否阻塞；不得依赖“上文”“同前”或未转交的会话记忆。

```md
## Task Brief

- Goal: <单一可验证目标>
- Scope: <允许检查或变更的文件、模块、接口>
- Out of Scope: <明确排除的工作>
- Product Context: <product_form、MCU/SoC、RTOS、工具链、固件/硬件/文档 revision>
- Inputs and Evidence: <需求、issue、diff、日志、ELF/MAP、datasheet、baseline>
- Allowed Changes: <可写路径和允许的变更类型；只读任务写 None>
- Forbidden Actions: <禁止命令、禁止路径、禁止硬件动作和数据边界>
- Verification Commands: <命令、工作目录、配置；未知时写 Discover safely>
- Acceptance Criteria: <可以独立判断 PASS/FAIL 的条件>
- Documentation Requirement: <None，或触发原因、受众、文档类型与路径>
```

Task Brief 规则：

- `Goal` 必须聚焦一个交付结果；大任务拆成有依赖顺序的垂直切片。
- `Allowed Changes` 是写权限上限，不是建议范围。未列出的 tracked 文件不得修改。
- `Forbidden Actions` 必须继承本契约安全边界；Task Brief 不能授权超出用户意图的高风险动作。
- `Verification Commands` 中的 flash/HIL 配置只描述能力，不构成执行授权。
- 缺少会改变 API、硬件值、数据格式或安全策略的输入时，执行者必须返回 `BLOCKED`。

### 产品形态契约

`product_form` 的已配置值为：

- `bare-metal`：重点检查 MMIO、ISR、原子性、时序、栈、启动/异常和低功耗流程。
- `rtos`：重点检查 task/ISR 边界、优先级、同步、死锁、优先级反转、heap、超时和对象生命周期。
- `module-sdk`：重点检查 API/URC、状态机、网络生命周期、重连、日志和向后兼容。
- `embedded-linux`：重点检查 POSIX、线程/进程、交叉编译、系统接口、信号、文件描述符和资源回收。
- `hybrid`：组合所有实际相关的检查，并将证据/finding 绑定到明确运行域。

应用功能必须把状态、事件、时间、重试/取消、幂等、恢复和资源所有权写入 `Inputs and Evidence` 或 `Acceptance Criteria`，并在结果证据中提供需求追踪矩阵。矩阵中的 `covered` 必须同时关联实现、测试和证据。

默认模板可使用 `auto` 表示尚未配置。Agent 必须从 README、构建/CI、依赖、入口和相邻模块只读探测，并在报告中声明推断与置信度；不能确定时返回所需证据，不得猜测。

### 状态契约

任务级 `Status` 只能是：

| 状态 | 含义 |
|---|---|
| `COMPLETE` | 所有必需验收条件和门禁均有证据且为 `PASS`。 |
| `CONDITIONAL` | 用户已明确接受报告中列出的具体剩余风险；未获得接受前不得使用。 |
| `BLOCKED` | 缺少产品决策、资料、工具、权限或硬件授权，当前无法安全继续。 |
| `FAILED` | 已执行验证失败，或两轮返工后仍有 BLOCKER/MAJOR/必需门禁失败。 |
| `INSUFFICIENT_EVIDENCE` | 仅供评审与故障分析使用：证据不足以判断范围、产物匹配、finding 或根因。 |

验证门 `Gate` 只能是：

| 门状态 | 含义 |
|---|---|
| `PASS` | 已执行且有可复查证据满足条件。 |
| `FAIL` | 已执行并证明不满足条件。 |
| `BLOCKED` | 因缺资料、工具、权限或决定而无法执行。 |
| `NOT_RUN` | 未执行；必须说明原因和影响，永远不等于通过。 |

必需门为 `FAIL` 时任务为 `FAILED`，为 `BLOCKED` 时任务为 `BLOCKED`。必需门为 `NOT_RUN` 时不得返回 `COMPLETE`。

### Result Report 输出契约

每个 Agent 的最终结果使用以下结构；无内容的字段写 `None`，不可删除：

```md
## Result Report

- Status: COMPLETE | CONDITIONAL | BLOCKED | FAILED | INSUFFICIENT_EVIDENCE
- Summary: <结论优先的简短摘要>
- Files/APIs: <读取或修改的关键文件；新增/变化的接口>
- Commands and Exit Codes: <工作目录、完整命令、退出码；未运行写 None>
- Evidence: <diff、测试、构建、日志、产物 ID、官方资料 revision/page>
- Assumptions: <推断、置信度和确认方式>
- Risks: <剩余风险、影响和所有者>
- Next Steps: <最小下一步；完成时可写 None>

| Quality Gate | Result | Evidence / Reason |
|---|---|---|
| Scope/Acceptance | PASS/FAIL/BLOCKED/NOT_RUN | ... |
| Build | PASS/FAIL/BLOCKED/NOT_RUN | ... |
| Tests | PASS/FAIL/BLOCKED/NOT_RUN | ... |
| Static Analysis | PASS/FAIL/BLOCKED/NOT_RUN | ... |
| Independent Review | PASS/FAIL/BLOCKED/NOT_RUN | ... |
| Documentation | PASS/FAIL/BLOCKED/NOT_RUN | ... |
| Hardware Evidence | PASS/FAIL/BLOCKED/NOT_RUN | ... |
```

只列与任务有关的证据，但门表行不得省略；不适用的门使用 `NOT_RUN` 并写 `Not required: <reason>`。命令证据必须包含退出码，构建产物尽量包含路径、version/build ID 与配置。

### Review Finding 契约

`QualityReviewer` 的每条 finding 必须使用：

```md
### <Severity>: <简短标题>

- Dimension: Spec | Standards | Spec, Standards
- Location: <file:line、symbol 或 log offset>
- Evidence: <可复查事实>
- Rationale: <触发条件、失败机制和影响>
- Recommendation: <最小修复或下一项证据>
- Confidence: HIGH | MEDIUM | LOW
```

Evidence 与 Hypothesis 必须分开。MISRA 默认是风险筛查；缺少已配置标准版本、deviation 与实际工具证据时，不得声称合规或虚构规则号。

### 编排与写入所有权

- `Orchestrator` 是唯一自动委派者，只读且不执行命令。
- `EmbeddedDeveloper` 是唯一常规功能代码写入者，也负责相关测试和必要构建配置。
- `QualityReviewer` 只读源码；`execute` 仅用于只读 Git、非源码改写的构建/测试诊断、静态分析和符号化。
- `DocKeeper` 只可写 `docs/`、根 README、`.github/embedded-project.yml` 和明确授权的非行为性代码注释。
- 任何工作树写入必须串行。无依赖只读评审可以并行；并行结果由 Orchestrator 去重并保留证据来源。
- 自动 subagent 委派用于闭环；frontmatter handoff 是 `send: false` 的人工切换，不得被描述为自动继续。
- Developer/Reviewer 返工最多两轮；超过限制仍有 BLOCKER/MAJOR 或必需门失败，返回 `FAILED`。

仅在公共 API、架构、硬件假设、操作流程或已确认根因变化时触发 DocKeeper。文档必须完整双语，发布前不得保留同步占位标记。

### 安全与证据边界

- 保护 dirty worktree，禁止破坏性 Git、覆盖无关改动、无关重构、静默安装依赖和未经授权的源码改写工具。
- 未获得用户针对当前任务的明确授权，禁止 flash、erase、fuse、reset、板卡上电、HIL、连接/控制真实设备或其他物理硬件动作。画像中的命令永远不构成授权。
- 不得虚构寄存器、地址、位值、引脚、时钟、时序、电气约束、revision、测试结果、标准规则号或来源。
- 私有源码、客户数据、凭据、内部 URL 和未脱敏日志不得上传或放入 Web 查询。DocKeeper 的 Web 仅限官方公开资料。
- `volatile` 只提供编译器可见性，不保证原子性、互斥或内存顺序；并发设计必须使用平台适用的同步机制。
- 证据必须可追溯到文件/行、命令/退出码、日志偏移、产物 ID 或官方文档编号/revision/page。无法追溯的结论必须标为 assumption/hypothesis。

## English

### Purpose and Scope

This document is the shared input, output, and safety contract for `Orchestrator`, `EmbeddedDeveloper`, `QualityReviewer`, and `DocKeeper`. Every agent must read this file and `.github/embedded-project.yml` before work. Role files define specialist behavior and cannot weaken this contract.

Rule precedence is:

1. Explicit user requirements and authorization for the current task.
2. Actual source, build, CI, documentation, and hardware evidence in the target repository.
3. Confirmed non-`auto` values in `.github/embedded-project.yml`.
4. Read-only discovery for `auto` fields.
5. Template suggestions used only for an empty project.

When the profile conflicts with repository truth, report “configuration drift”; never silently choose a side or rewrite the project to match the profile.

### Task Brief Input Contract

Every automatic delegation or manual handoff must produce a self-contained Task Brief. Write `Unknown` for missing values and state whether they block work; never depend on “above,” “same as before,” or conversation memory that was not handed over.

```md
## Task Brief

- Goal: <one verifiable outcome>
- Scope: <files, modules, and interfaces allowed for inspection or change>
- Out of Scope: <explicitly excluded work>
- Product Context: <product_form, MCU/SoC, RTOS, toolchain, firmware/hardware/document revision>
- Inputs and Evidence: <requirements, issue, diff, logs, ELF/MAP, datasheet, baseline>
- Allowed Changes: <writable paths and allowed change types; None for read-only tasks>
- Forbidden Actions: <forbidden commands/paths, hardware actions, and data boundary>
- Verification Commands: <commands, working directory, configuration; Discover safely when unknown>
- Acceptance Criteria: <conditions that independently determine PASS/FAIL>
- Documentation Requirement: <None, or trigger, audience, document type, and path>
```

Task Brief rules:

- `Goal` targets one deliverable outcome; split large work into ordered vertical slices.
- `Allowed Changes` is the maximum write authority, not a suggested scope. Do not modify unlisted tracked files.
- `Forbidden Actions` inherits this contract's safety boundary. A Task Brief cannot authorize high-risk action beyond user intent.
- A configured flash/HIL command in `Verification Commands` describes capability and is not execution authorization.
- If missing input would change an API, hardware value, data format, or safety policy, the worker must return `BLOCKED`.

### Product-Form Contract

Configured `product_form` values are:

- `bare-metal`: focus on MMIO, ISR, atomicity, timing, stack, startup/exception, and low-power flows.
- `rtos`: focus on task/ISR boundaries, priority, synchronization, deadlock, priority inversion, heap, timeouts, and object lifetime.
- `module-sdk`: focus on API/URC behavior, state machines, network lifecycle, reconnection, logging, and backward compatibility.
- `embedded-linux`: focus on POSIX, threads/processes, cross-compilation, system interfaces, signals, file descriptors, and resource cleanup.
- `hybrid`: combine all relevant checks and bind each evidence item/finding to an execution domain.

Application features record states, events, timing, retry/cancellation, idempotency, recovery, and resource ownership under `Inputs and Evidence` or `Acceptance Criteria`, and include a requirement traceability matrix in result evidence. Every `covered` row must link implementation, tests, and evidence.

The default template may use `auto` for an unconfigured value. Agents must discover it read-only from README, build/CI, dependencies, entry points, and neighboring modules, then report the inference and confidence. When it cannot be determined, request evidence rather than guessing.

### Status Contract

Task-level `Status` is one of:

| Status | Meaning |
|---|---|
| `COMPLETE` | Every required acceptance criterion and gate has evidence and is `PASS`. |
| `CONDITIONAL` | The user explicitly accepted the specific residual risks listed in the report; never use before acceptance. |
| `BLOCKED` | A product decision, source, tool, permission, or hardware authorization is missing, so work cannot safely continue. |
| `FAILED` | Executed verification failed, or BLOCKER/MAJOR/required gate failures remain after two rework rounds. |
| `INSUFFICIENT_EVIDENCE` | Review and fault analysis only: evidence cannot establish scope, artifact match, a finding, or root cause. |

Verification `Gate` is one of:

| Gate Status | Meaning |
|---|---|
| `PASS` | Executed with reproducible evidence satisfying the condition. |
| `FAIL` | Executed and proven not to satisfy the condition. |
| `BLOCKED` | Could not execute because a source, tool, permission, or decision is missing. |
| `NOT_RUN` | Not executed; the reason and impact are mandatory, and it never means pass. |

A required `FAIL` gate makes the task `FAILED`; a required `BLOCKED` gate makes it `BLOCKED`. A required `NOT_RUN` gate prevents `COMPLETE`.

### Result Report Output Contract

Every agent final result uses this structure. Write `None` instead of removing an empty field:

```md
## Result Report

- Status: COMPLETE | CONDITIONAL | BLOCKED | FAILED | INSUFFICIENT_EVIDENCE
- Summary: <conclusion-first summary>
- Files/APIs: <key files read or changed; new/changed interfaces>
- Commands and Exit Codes: <working directory, full command, exit code; None when not run>
- Evidence: <diff, tests, build, logs, artifact ID, official source revision/page>
- Assumptions: <inference, confidence, and confirmation method>
- Risks: <residual risk, impact, and owner>
- Next Steps: <smallest next action; may be None when complete>

| Quality Gate | Result | Evidence / Reason |
|---|---|---|
| Scope/Acceptance | PASS/FAIL/BLOCKED/NOT_RUN | ... |
| Build | PASS/FAIL/BLOCKED/NOT_RUN | ... |
| Tests | PASS/FAIL/BLOCKED/NOT_RUN | ... |
| Static Analysis | PASS/FAIL/BLOCKED/NOT_RUN | ... |
| Independent Review | PASS/FAIL/BLOCKED/NOT_RUN | ... |
| Documentation | PASS/FAIL/BLOCKED/NOT_RUN | ... |
| Hardware Evidence | PASS/FAIL/BLOCKED/NOT_RUN | ... |
```

Include only task-relevant evidence, but do not omit gate rows. Use `NOT_RUN` with `Not required: <reason>` for an inapplicable gate. Command evidence includes exit codes; build artifacts should include path, version/build ID, and configuration when available.

### Review Finding Contract

Every `QualityReviewer` finding uses:

```md
### <Severity>: <short title>

- Dimension: Spec | Standards | Spec, Standards
- Location: <file:line, symbol, or log offset>
- Evidence: <reproducible fact>
- Rationale: <trigger, failure mechanism, and impact>
- Recommendation: <smallest fix or next evidence>
- Confidence: HIGH | MEDIUM | LOW
```

Evidence and Hypothesis must remain separate. MISRA is risk screening by default; without a configured standard version, deviation record, and actual tool evidence, do not claim compliance or invent rule numbers.

### Orchestration and Write Ownership

- `Orchestrator` is the only automatic delegator; it is read-only and does not execute commands.
- `EmbeddedDeveloper` is the only routine functional-code writer and owns related tests and necessary build configuration.
- `QualityReviewer` reads source only; `execute` is restricted to read-only Git, non-source-rewriting build/test diagnostics, static analysis, and symbolization.
- `DocKeeper` may write only `docs/`, the root README, `.github/embedded-project.yml`, and explicitly authorized non-behavioral code comments.
- Serialize every working-tree write. Independent read-only reviews may run in parallel; Orchestrator deduplicates results while preserving evidence provenance.
- Automatic subagent delegation drives the closed loop; frontmatter handoff is a manual `send: false` transition and must not be described as automatic continuation.
- Allow at most two Developer/Reviewer rework rounds. Return `FAILED` if BLOCKER/MAJOR findings or required gate failures remain.

Invoke DocKeeper only when a public API, architecture, hardware assumption, operating procedure, or confirmed root cause changed. Documentation must be fully bilingual and contain no synchronization placeholder at release.

### Safety and Evidence Boundary

- Preserve the dirty worktree. No destructive Git, unrelated overwrite/refactor, silent dependency installation, or unauthorized source-rewriting tools.
- Without explicit user authorization for the current task, do not flash, erase, fuse, reset, power a board, run HIL, connect/control a physical device, or perform other physical-hardware actions. Commands in the profile never constitute authorization.
- Never fabricate registers, addresses, bit values, pins, clocks, timing, electrical constraints, revisions, test results, standards rule numbers, or sources.
- Never upload or place private source, customer data, credentials, internal URLs, or unsanitized logs in Web queries. DocKeeper Web access is restricted to public official sources.
- `volatile` provides compiler visibility only and does not guarantee atomicity, mutual exclusion, or memory ordering; concurrency design requires platform-appropriate synchronization.
- Evidence must trace to a file/line, command/exit code, log offset, artifact ID, or official document identifier/revision/page. Anything untraceable must be labeled as an assumption or hypothesis.
