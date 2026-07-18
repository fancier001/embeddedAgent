# Five-Agent Collaboration Contract

> 中文：本文档采用固定双语结构。更新中文或英文内容时，必须同步更新另一部分，保持两部分语义一致。
>
> English: This document uses a fixed bilingual structure. When either the Chinese or English content is updated, the other section must be updated as well to keep both sections semantically aligned.

## 中文 / Chinese

### 目的与适用范围

本文档是 `Orchestrator`、`BugResolver`、`EmbeddedDeveloper`、`QualityReviewer`、`DocKeeper` 的共享输入、输出和安全契约。五个 Agent 开始工作前必须读取本文件与 `.github/embedded-project.yml`，并发现可选的 `.project/project.yml`；存在时加载当前任务路径适用的项目规则，缺失时按旧项目兼容流程继续。角色文件只定义专属行为，不得降低本契约要求。

规则优先级如下：

1. 用户在当前任务中的明确要求和授权。
2. 目标仓库的真实代码、构建、CI、文档和硬件证据。
3. 可选 `.project/project.yml` 注册且与当前任务路径匹配的项目规则。
4. `.github/embedded-project.yml` 中非 `auto` 的已确认配置。
5. 对 `auto` 字段的只读探测结果。
6. 仅用于空白工程的模板默认建议。

Agent 使用 Task Brief 的 `Scope`、`Allowed Changes` 和当前真实 diff 匹配每条规则的 `applies_to`；适用且 `required: true` 的规则必须读取。若项目规则或画像与仓库事实冲突，报告“配置漂移”，不得静默选择一方或改写工程以迎合配置。

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
- Git Delivery: <none | commit | commit-and-push | auto>
```

Task Brief 规则：

- `Goal` 必须聚焦一个交付结果；大任务拆成有依赖顺序的垂直切片。
- `Allowed Changes` 是写权限上限，不是建议范围。未列出的 tracked 文件不得修改。
- `Forbidden Actions` 必须继承本契约安全边界；Task Brief 不能授权超出用户意图的高风险动作。
- `Verification Commands` 中的 flash/HIL 配置只描述能力，不构成执行授权。
- `Git Delivery` 只接受 `none`、`commit`、`commit-and-push`、`auto`；不接受 remote、URL、目标分支或 refspec。`none` 时不得 commit 或 push；`auto` 是本轮自动 commit+push 的明确授权，但 policy 不能替代该授权。
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

### Usage Symptom Guidance 输出契约

`BugResolver` 在问题识别和根因分析前，必须先把用户如何使用、执行了什么以及观察到什么规范化。输入缺少会影响方向的现象时，使用以下表格集中引导；首轮最多 5 个问题：

```md
## Usage Symptom Questions

| Priority | Question | Why It Matters | Example Answer |
|---|---|---|---|
| REQUIRED_FOR_DIRECTION/HELPFUL | ... | ... | ... |
```

问题依次优先覆盖用户目标/实际场景、从正常到异常的操作序列、预期/实际行为、频率/规律/触发窗口/边界条件，以及软件/固件/硬件版本、最后正常/首次异常版本、影响和恢复方式。只询问当前输入没有回答的高信息量问题；完整输入不得重复提问。用户可回答 `Unknown`，非关键未知项不得阻塞分析。只有回答产生新矛盾或新方向歧义时，允许最多一组不重复的补充问题。

每次分析都维护以下规范化结果；缺失字段写 `Unknown`：

```md
## Usage Symptom Profile

- User Goal / Scenario: <用户要完成的目标及真实使用场景>
- Operation Sequence: <从正常状态到异常发生的操作和事件顺序>
- Expected Behavior: <用户或需求定义的预期>
- Actual Behavior: <可观察实际现象和原始错误>
- Frequency / Pattern: <频率、规律、持续时间和触发窗口>
- Preconditions / Boundary Conditions: <前置状态、负载、网络、电源、时序和边界值>
- Environment / Revision: <软件、固件、硬件、配置和工具链版本>
- Last Known Good / First Known Bad: <最后正常与首次异常版本或时间>
- Impact / Scope: <受影响设备、用户、功能和严重影响>
- Recovery / Workaround: <自动/人工恢复方式和已知规避方法>
- Direction Confirmation: CONFIRMED | NOT_REQUIRED | PENDING
```

当现象可能指向两个以上模块或根因路径、预期/实际不明确或输入相互矛盾时，将方向标记为 `PENDING`，输出一句 `Current Understanding`、具体的 `Possible Directions`，并请求用户确认或纠正。确认前不得进入深入调用链追踪、根因确认或 Developer 委派。方向明确时使用 `NOT_REQUIRED` 并直接继续；用户确认后使用 `CONFIRMED`。

`Usage Symptom Questions` 只采集使用现象。日志、版本清单、配置、ELF/MAP、dump 等材料只能通过 `Evidence Request` 索取，两类请求不得混用。

### Problem Identification 输出契约

`BugResolver` 必须在 Usage Symptom Profile 的方向为 `CONFIRMED` 或 `NOT_REQUIRED` 后、Bug Analysis 之前输出以下结构。字段缺失时写 `Unknown`，不得用假设填空：

```md
## Problem Identification

- Usage Symptom Basis: <引用 Usage Symptom Profile 中支持当前方向的已确认事实>
- Problem Statement: <仅基于已观察事实的一句话问题定义>
- Category: 功能/状态机 | 崩溃/异常 | 内存 | 并发/时序 | 资源 | 硬件/I/O | 协议/网络 | 配置/构建/版本 | 性能/功耗 | 其他/未知
- Suspected Subsystem: <受影响模块或运行域；未知时写 Unknown>
- Observed Severity: BLOCKER | MAJOR | MINOR | UNKNOWN
- Trigger / Conditions: <已观察触发条件；不要写未验证原因>
- Reproducibility: <步骤、频率和 Agent 是否复现>
- Affected Scope: <设备、版本、配置、模块或用户>
- Evidence Confidence: HIGH | MEDIUM | LOW
```

`Observed Severity` 只表达已观察影响，不表示原因已确认。问题陈述必须区分事实、推断和未知项；类别或子系统可以随着新增证据更新，但必须说明变化依据。`Usage Symptom Basis` 必须与方向已确认或无需确认的 Profile 一致，不得用日志中的推测替代用户使用现象。

### Evidence Request 输出契约

只有在 Agent 已先搜索仓库与现有产物后，才能请求用户补充材料。所有请求集中在一张表中：

```md
## Evidence Request

| Priority | Material | Why Needed | Accepted Form | Privacy/Redaction | Blocking Decision |
|---|---|---|---|---|---|
| REQUIRED_NOW/HELPFUL | ... | ... | pasted excerpt/path/file/version | ... | ... |
```

- `REQUIRED_NOW`：缺少材料会阻止问题分类、关键假设判别、产物匹配或修复决策；Agent 暂停根因确认和 Developer 委派。
- `HELPFUL`：材料只提高置信度，不得单独阻止已有证据支持的安全分析。
- 不得重复请求用户已提供或仓库内可发现的材料。用户补充后重新执行证据检查，再继续假设验证。
- 如果无法继续交互或用户不能提供关键材料，最终状态为 `INSUFFICIENT_EVIDENCE`，并保留该表；缺少产品决策、权限或必需硬件资料时使用 `BLOCKED`。

### Bug Analysis 输出契约

`BugResolver` 的 `bug-analysis` 报告必须在通用 Result Report 之后追加以下结构；字段无证据时写 `Unknown` 或 `Not confirmed`，不得删除：

```md
## Bug Analysis

- Symptom: <用户可观察现象和原始错误；保留错误码/文本>
- Expected / Actual: <预期行为 / 实际行为>
- Environment and Revision: <产品形态、软件/固件、硬件、工具链、配置与版本>
- Reproduction: <最小步骤、频率和是否已由 Agent 复现>
- Failure Point: <报错文件:行、symbol、阶段或 log offset；说明它是否只是检测点>
- Root Cause: <已确认的触发条件 → 缺陷机制 → 影响因果链；否则写 Not confirmed>
- Affected Scope: <受影响路径、配置、版本、设备或用户>
- Fix Recommendation: <最小修复方向；分析任务不直接修改>
- Verification Plan: <能证明修复并防回归的检查>
- Missing Information: <仍缺少的精确材料；无则写 None>

### Evidence

1. <file:line、命令/退出码、日志偏移、产物 ID 或版本事实>

### Hypotheses

| Rank | Hypothesis | Supporting Evidence | Counter-evidence / Alternative | Confidence | Smallest Validation |
|---|---|---|---|---|---|
| 1 | ... | ... | ... | HIGH/MEDIUM/LOW | ... |
```

Bug 分析规则：

- 先理解错误，再验证原因；不得仅把异常消息改写成“根因”。
- 必须区分 symptom、reporting/failure point、trigger 和 root-cause location。
- 原因未确认时，`Root Cause` 写 `Not confirmed`，状态使用 `INSUFFICIENT_EVIDENCE`，并在 `Missing Information` 列出能推进判断的最小材料。
- 只有可追踪证据建立完整因果链并排除主要替代解释时，才能确认根因。置信度不能替代证据。
- 用户只要求分析时 `Allowed Changes` 为 `None`；修复建议不构成修改授权。

### 编排与写入所有权

- `Orchestrator` 是默认通用交付入口，只读且不执行命令；Bug 请求必须通过人工 handoff 或专用 prompt 切换到 `BugResolver`，不得自动嵌套 manager。
- `BugResolver` 是 Bug 诊断与解决流程的专职编排者，可执行受限的只读诊断命令，但不直接修改文件；仅可按需调用 `EmbeddedDeveloper`、`QualityReviewer` 和 `DocKeeper`。
- `EmbeddedDeveloper` 是唯一常规功能代码写入者，也负责相关测试和必要构建配置。
- `QualityReviewer` 只做独立质量评估并只读源码；`execute` 仅用于只读 Git、非源码改写的构建/测试审计和静态分析，不负责 Bug 根因诊断或符号化。
- `DocKeeper` 只可写 `docs/`、根 README、`.github/embedded-project.yml`、Task Brief 明确授权的 `.project/` 项目规范和明确授权的非行为性代码注释。
- 任何工作树写入必须串行。无依赖只读评审可以并行；并行结果由 Orchestrator 去重并保留证据来源。
- 自动 subagent 委派只用于各 manager 内部闭环；两个 manager 不得自动相互调用。frontmatter handoff 是 `send: false` 的人工流程切换，不得被描述为自动继续。
- Developer/Reviewer 返工最多两轮；超过限制仍有 BLOCKER/MAJOR 或必需门失败，返回 `FAILED`。

仅在公共 API、架构、硬件假设、操作流程或已确认根因变化时触发 DocKeeper。文档必须完整双语，发布前不得保留同步占位标记。

### Git 交付契约

- 只有 `EmbeddedDeveloper` 可执行常规 commit/push；必须在实现、验证和独立评审完成后使用单独的交付 Task Brief。`Orchestrator` 只编排和核对结果。
- 执行前读取 `.project/project.yml` 指向的 `.project/git/delivery.yml`。对应 `automation.commit`/`automation.push` 必须为 `true`，且 `Git Delivery` 必须授权当前操作；push 授权包含 commit，不反向隐含。
- `Git Delivery: auto` 只在修复、测试、必需检查、独立评审和必要文档均为 `PASS` 后进入 `AUTO_DECIDE`。完整 commit 消息必须先由仓库模板生成并严格校验；缺少 Project、Jira、RN、测试说明或其他必填 metadata 时返回 `BLOCKED` 请求补充，禁止保留占位符。
- `project_policy.py git-plan --operation auto --delivery auto` 只读返回 `AUTO_COMMIT_AND_PUSH`、`OUTPUT_COMMIT_MESSAGE` 或无有效 diff 时的 `NO_DELIVERY`。消息文件必须位于仓库外的操作系统临时目录，不能成为工作树变更。
- `OUTPUT_COMMIT_MESSAGE` 不得运行 `git add`、`git commit` 或 `git push`；面向用户的交付输出只包含已校验的完整 commit 内容，不附加路径、push 目标或未满足条件的诊断。`AUTO_COMMIT_AND_PUSH` 才允许继续写入，且不提供“仅自动 commit”的降级路径。
- 若当前任务修改 Git policy，只能用任务开始时的已提交 policy 判断本轮交付；未提交的放宽配置从后续任务生效，不能自我授权同一任务的 commit/push。
- 使用 `project_policy.py git-plan` 做只读预检；暂存前检查 `git status` 与真实 diff，只显式暂存本任务文件。每个路径必须匹配 `scope.allowed_paths` 且不匹配 `scope.denied_paths`；禁止全仓库暂存。
- 提交消息从 `.project/git/commit.template` 生成，并通过 `project_policy.py message` 严格校验。Agent 参与代码、检查、重构、测试或文档时必须如实填写 AI 字段。所有 `commit.checks` 与必需质量门通过后才可提交；不得使用 `--no-verify`。
- push 的当前分支、remote alias、push URL 和目标远端 ref 只能由 `project_policy.py git-plan` 从当前仓库 `.git` 的 local config 解析；Task Brief、`.project`、全局 Git config、环境变量和命令参数均不得覆盖。push 前再次带 fingerprint 预检，配置漂移时停止。
- `AUTO_COMMIT_AND_PUSH` 必须从初始空 index 开始，且 HEAD 与本地 upstream tracking ref 完全一致、没有既有 incoming/outgoing commit、全部工作树变更正好等于本次修复路径。显式暂存后复查 staged diff，创建一个新 commit，记录完整 SHA，再以首次 fingerprint 和 `--expected-commit <SHA>` 运行第二次 push 预检；outgoing commits 必须只有该 SHA。
- 实际 push 在与预检相同的 local-only、禁用 global/system/env config 注入的 Git 环境中，仅使用预检结果执行 `git -C <root> push <resolved-remote> HEAD:<resolved-remote-ref>`。禁止 `push -u`、force push、删除远端分支、自定义 refspec 和修改 `.git/config`。
- auto 模式在任何 Git 写入前条件不满足时选择 `OUTPUT_COMMIT_MESSAGE` 并保持 Git 不变。commit 成功后若第二次预检或 push 失败，保留本地 commit，不自动回滚；报告完整 commit 内容、SHA 和失败事实。
- policy 或模板缺失/无效、路径/分支不匹配、dirty worktree 无法隔离、upstream/remote 目标不明确、检查失败时返回 `BLOCKED`。不得自行放宽策略后继续交付。

### 安全与证据边界

- 保护 dirty worktree，禁止破坏性 Git、覆盖无关改动、无关重构、静默安装依赖和未经授权的源码改写工具。
- 未获得用户针对当前任务的明确授权，禁止 flash、erase、fuse、reset、板卡上电、HIL、连接/控制真实设备或其他物理硬件动作。画像中的命令永远不构成授权。
- 不得虚构寄存器、地址、位值、引脚、时钟、时序、电气约束、revision、测试结果、标准规则号或来源。
- 私有源码、客户数据、凭据、内部 URL 和未脱敏日志不得上传或放入 Web 查询。DocKeeper 的 Web 仅限官方公开资料。
- `volatile` 只提供编译器可见性，不保证原子性、互斥或内存顺序；并发设计必须使用平台适用的同步机制。
- 证据必须可追溯到文件/行、命令/退出码、日志偏移、产物 ID 或官方文档编号/revision/page。无法追溯的结论必须标为 assumption/hypothesis。

## English

### Purpose and Scope

This document is the shared input, output, and safety contract for `Orchestrator`, `BugResolver`, `EmbeddedDeveloper`, `QualityReviewer`, and `DocKeeper`. All five agents must read this file and `.github/embedded-project.yml`, then discover optional `.project/project.yml`. Load applicable project rules when it exists; continue in legacy-compatible mode when it does not. Role files define specialist behavior and cannot weaken this contract.

Rule precedence is:

1. Explicit user requirements and authorization for the current task.
2. Actual source, build, CI, documentation, and hardware evidence in the target repository.
3. Project rules registered by optional `.project/project.yml` and matching current task paths.
4. Confirmed non-`auto` values in `.github/embedded-project.yml`.
5. Read-only discovery for `auto` fields.
6. Template suggestions used only for an empty project.

Agents match each rule's `applies_to` against the Task Brief `Scope`, `Allowed Changes`, and actual diff; they must read every applicable rule with `required: true`. When a project rule or profile conflicts with repository truth, report “configuration drift”; never silently choose a side or rewrite the project to match configuration.

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
- Git Delivery: <none | commit | commit-and-push | auto>
```

Task Brief rules:

- `Goal` targets one deliverable outcome; split large work into ordered vertical slices.
- `Allowed Changes` is the maximum write authority, not a suggested scope. Do not modify unlisted tracked files.
- `Forbidden Actions` inherits this contract's safety boundary. A Task Brief cannot authorize high-risk action beyond user intent.
- A configured flash/HIL command in `Verification Commands` describes capability and is not execution authorization.
- `Git Delivery` accepts only `none`, `commit`, `commit-and-push`, or `auto`; it never accepts a remote, URL, target branch, or refspec. Do not commit or push for `none`. `auto` is explicit authorization for automatic commit plus push in this run, but policy never replaces that authorization.
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

### Usage Symptom Guidance Output Contract

Before problem identification or root-cause analysis, `BugResolver` normalizes how the user operated the product, what they did, and what they observed. When direction-changing symptoms are missing, guide the user with one consolidated table containing at most five questions in the first set:

```md
## Usage Symptom Questions

| Priority | Question | Why It Matters | Example Answer |
|---|---|---|---|
| REQUIRED_FOR_DIRECTION/HELPFUL | ... | ... | ... |
```

Prioritize user goal/real scenario; operation sequence from normal state to failure; expected versus actual behavior; frequency/pattern/trigger window/boundaries; and software/firmware/hardware revisions, last-known-good/first-known-bad, impact, and recovery. Ask only high-information questions not already answered by the current input, and never repeat questions for complete input. The user may answer `Unknown`; non-critical unknowns do not block analysis. Allow at most one non-repeating follow-up set, and only when answers create a new contradiction or direction ambiguity.

Maintain this normalized result for every analysis, using `Unknown` for unavailable fields:

```md
## Usage Symptom Profile

- User Goal / Scenario: <user goal and real usage scenario>
- Operation Sequence: <operations and events from normal state to failure>
- Expected Behavior: <behavior defined by the user or requirement>
- Actual Behavior: <observable behavior and original error>
- Frequency / Pattern: <frequency, pattern, duration, and trigger window>
- Preconditions / Boundary Conditions: <prior state, load, network, power, timing, and boundary values>
- Environment / Revision: <software, firmware, hardware, configuration, and toolchain revisions>
- Last Known Good / First Known Bad: <last good and first bad version or time>
- Impact / Scope: <affected devices, users, functions, and observed impact>
- Recovery / Workaround: <automatic/manual recovery and known workaround>
- Direction Confirmation: CONFIRMED | NOT_REQUIRED | PENDING
```

When symptoms could indicate two or more modules or root-cause paths, expected versus actual behavior is unclear, or inputs conflict, set direction to `PENDING`, emit one `Current Understanding`, list concrete `Possible Directions`, and ask the user to confirm or correct them. Do not begin deep call-path tracing, confirm root cause, or delegate Developer before confirmation. Use `NOT_REQUIRED` and continue directly when direction is clear; use `CONFIRMED` after user confirmation.

`Usage Symptom Questions` collects usage symptoms only. Request logs, version manifests, configuration, ELF/MAP, dumps, and other material only through `Evidence Request`; never mix the two request types.

### Problem Identification Output Contract

`BugResolver` emits the following structure after the Usage Symptom Profile direction is `CONFIRMED` or `NOT_REQUIRED` and before Bug Analysis. Use `Unknown` for missing fields and never fill them with assumptions:

```md
## Problem Identification

- Usage Symptom Basis: <reference confirmed facts from the Usage Symptom Profile that support this direction>
- Problem Statement: <one-sentence definition based only on observed facts>
- Category: functional/state-machine | crash/exception | memory | concurrency/timing | resource | hardware/I/O | protocol/network | configuration/build/version | performance/power | other/unknown
- Suspected Subsystem: <affected module or execution domain; Unknown when unavailable>
- Observed Severity: BLOCKER | MAJOR | MINOR | UNKNOWN
- Trigger / Conditions: <observed trigger; do not insert an unverified cause>
- Reproducibility: <steps, frequency, and whether the Agent reproduced it>
- Affected Scope: <devices, versions, configurations, modules, or users>
- Evidence Confidence: HIGH | MEDIUM | LOW
```

`Observed Severity` describes observed impact only and does not imply root-cause certainty. Keep facts, inferences, and unknowns separate. Category or subsystem may change with new evidence, but the report must state why. `Usage Symptom Basis` must agree with a Profile whose direction is confirmed or does not require confirmation; never replace user-observed usage symptoms with speculation from a log.

### Evidence Request Output Contract

The Agent may request user material only after searching the repository and existing artifacts. Consolidate every request in one table:

```md
## Evidence Request

| Priority | Material | Why Needed | Accepted Form | Privacy/Redaction | Blocking Decision |
|---|---|---|---|---|---|
| REQUIRED_NOW/HELPFUL | ... | ... | pasted excerpt/path/file/version | ... | ... |
```

- `REQUIRED_NOW`: without the material, problem classification, critical hypothesis discrimination, artifact matching, or a repair decision cannot continue; pause root-cause confirmation and Developer delegation.
- `HELPFUL`: the material only improves confidence and must not block safe analysis already supported by evidence.
- Never re-request material already supplied by the user or discoverable in the repository. After new evidence arrives, repeat the evidence check before hypothesis validation.
- If interaction cannot continue or the user cannot supply critical material, return `INSUFFICIENT_EVIDENCE` and retain this table. Use `BLOCKED` for a missing product decision, authority, or required hardware source.

### Bug Analysis Output Contract

A `BugResolver` `bug-analysis` report appends the following structure after the general Result Report. Use `Unknown` or `Not confirmed` when evidence is absent; do not remove fields:

```md
## Bug Analysis

- Symptom: <user-visible behavior and original error; preserve codes/text>
- Expected / Actual: <expected behavior / actual behavior>
- Environment and Revision: <product form, software/firmware, hardware, toolchain, configuration, and versions>
- Reproduction: <minimum steps, frequency, and whether the Agent reproduced it>
- Failure Point: <reporting file:line, symbol, phase, or log offset; state whether it is only the detection point>
- Root Cause: <confirmed trigger → defect mechanism → impact causal chain; otherwise Not confirmed>
- Affected Scope: <affected paths, configurations, versions, devices, or users>
- Fix Recommendation: <smallest fix direction; analysis does not modify source>
- Verification Plan: <checks that prove the fix and prevent regression>
- Missing Information: <exact material still required; None when complete>

### Evidence

1. <file:line, command/exit code, log offset, artifact ID, or version fact>

### Hypotheses

| Rank | Hypothesis | Supporting Evidence | Counter-evidence / Alternative | Confidence | Smallest Validation |
|---|---|---|---|---|---|
| 1 | ... | ... | ... | HIGH/MEDIUM/LOW | ... |
```

Bug-analysis rules:

- Understand the error before testing causes; never paraphrase an exception message as the root cause.
- Distinguish symptom, reporting/failure point, trigger, and root-cause location.
- When the cause is unconfirmed, write `Not confirmed` for `Root Cause`, use `INSUFFICIENT_EVIDENCE`, and list the minimum material that advances the decision under `Missing Information`.
- Confirm root cause only when traceable evidence establishes the complete causal chain and excludes the main alternatives. Confidence does not replace evidence.
- For analysis-only requests, `Allowed Changes` is `None`; a fix recommendation is not authorization to modify source.

### Orchestration and Write Ownership

- `Orchestrator` is the default general-delivery entry point; it is read-only and does not execute commands. Bug requests transition to `BugResolver` through a manual handoff or dedicated prompt, never nested manager auto-invocation.
- `BugResolver` is the dedicated orchestrator for bug diagnosis and resolution. It may run restricted read-only diagnostic commands but never edits files directly; it may invoke only `EmbeddedDeveloper`, `QualityReviewer`, and `DocKeeper` as needed.
- `EmbeddedDeveloper` is the only routine functional-code writer and owns related tests and necessary build configuration.
- `QualityReviewer` performs independent quality assessment only and reads source without editing it. Its `execute` access is restricted to read-only Git, non-source-rewriting build/test audit, and static analysis; it does not diagnose bug root causes or symbolize faults.
- `DocKeeper` may write only `docs/`, the root README, `.github/embedded-project.yml`, Task-Brief-authorized project rules under `.project/`, and explicitly authorized non-behavioral code comments.
- Serialize every working-tree write. Independent read-only reviews may run in parallel; Orchestrator deduplicates results while preserving evidence provenance.
- Automatic subagent delegation drives the internal loop of each manager; the two managers must not auto-invoke each other. A frontmatter handoff is a manual `send: false` workflow transition and must not be described as automatic continuation.
- Allow at most two Developer/Reviewer rework rounds. Return `FAILED` if BLOCKER/MAJOR findings or required gate failures remain.

Invoke DocKeeper only when a public API, architecture, hardware assumption, operating procedure, or confirmed root cause changed. Documentation must be fully bilingual and contain no synchronization placeholder at release.

### Git Delivery Contract

- Only `EmbeddedDeveloper` performs routine commit/push operations, using a separate delivery Task Brief after implementation, verification, and independent review complete. `Orchestrator` only coordinates and checks the result.
- Before delivery, read `.project/git/delivery.yml` through `.project/project.yml`. The matching `automation.commit`/`automation.push` value must be `true`, and `Git Delivery` must authorize the operation; push authorization includes commit, not conversely.
- Enter `AUTO_DECIDE` for `Git Delivery: auto` only after the repair, tests, required checks, independent review, and required documentation are all `PASS`. First generate the complete commit message from the repository template and validate it strictly. Missing Project, Jira, RN, test notes, or other required metadata returns `BLOCKED` for input; never leave placeholders.
- Read-only `project_policy.py git-plan --operation auto --delivery auto` returns `AUTO_COMMIT_AND_PUSH`, `OUTPUT_COMMIT_MESSAGE`, or `NO_DELIVERY` when there is no effective diff. Store the message file in an operating-system temporary directory outside the repository so it cannot become a worktree change.
- `OUTPUT_COMMIT_MESSAGE` runs no `git add`, `git commit`, or `git push`. Its user-facing delivery output contains only the complete validated commit content, without paths, push target, or failed-condition diagnostics. Only `AUTO_COMMIT_AND_PUSH` permits writes, and there is no automatic commit-only fallback.
- If the current task changes Git policy, evaluate delivery against the committed policy present at task start. An uncommitted relaxation takes effect only for a later task and cannot self-authorize commit/push in the same task.
- Use `project_policy.py git-plan` for read-only preflight. Inspect `git status` and the actual diff, stage only explicit task files, require every path to match `scope.allowed_paths` and no path to match `scope.denied_paths`, and never stage repository-wide.
- Generate the message from `.project/git/commit.template` and strictly validate it with `project_policy.py message`. When an agent participated in code, inspection, refactoring, tests, or documentation, disclose that in the AI fields. Run every `commit.checks` entry and required quality gate; never bypass hooks with `--no-verify`.
- Resolve the current branch, remote alias, push URL, and target remote ref only from this repository's local `.git` config through `project_policy.py git-plan`. Task Briefs, `.project`, global Git config, environment variables, and command arguments cannot override them. Repeat preflight with the fingerprint immediately before push and stop on drift.
- `AUTO_COMMIT_AND_PUSH` requires an initially empty index, HEAD exactly equal to the local upstream tracking ref, no existing incoming/outgoing commit, and a worktree change set exactly equal to the repair paths. Reinspect the staged diff after explicit staging, create one new commit, record its full SHA, then run the second push preflight with the first fingerprint and `--expected-commit <SHA>`; outgoing commits must contain only that SHA.
- In the same local-only Git environment used by preflight, with global/system/environment config injection disabled, the only permitted push form is `git -C <root> push <resolved-remote> HEAD:<resolved-remote-ref>`. Never use `push -u`, force push, remote deletion, custom refspecs, or `.git/config` mutation.
- Before any Git write, an unmet auto-upload condition selects `OUTPUT_COMMIT_MESSAGE` and leaves Git unchanged. If commit succeeds but the second preflight or push fails, keep the local commit without rollback and report the complete message, SHA, and failure fact.
- Return `BLOCKED` for missing/invalid policy or template, path/branch mismatch, unisolatable dirty worktree, ambiguous upstream/remote target, or failed checks. Never loosen policy merely to continue delivery.

### Safety and Evidence Boundary

- Preserve the dirty worktree. No destructive Git, unrelated overwrite/refactor, silent dependency installation, or unauthorized source-rewriting tools.
- Without explicit user authorization for the current task, do not flash, erase, fuse, reset, power a board, run HIL, connect/control a physical device, or perform other physical-hardware actions. Commands in the profile never constitute authorization.
- Never fabricate registers, addresses, bit values, pins, clocks, timing, electrical constraints, revisions, test results, standards rule numbers, or sources.
- Never upload or place private source, customer data, credentials, internal URLs, or unsanitized logs in Web queries. DocKeeper Web access is restricted to public official sources.
- `volatile` provides compiler visibility only and does not guarantee atomicity, mutual exclusion, or memory ordering; concurrency design requires platform-appropriate synchronization.
- Evidence must trace to a file/line, command/exit code, log offset, artifact ID, or official document identifier/revision/page. Anything untraceable must be labeled as an assumption or hypothesis.
