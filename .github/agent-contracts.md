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
- `DocKeeper` 只可�]=�]��G����ƭy�lusion.

The standard Orchestrator delivery flow is:

```text
INTAKE → PREFLIGHT → PLAN → IMPLEMENT → VERIFY → REVIEW
                                              │
                       up to two REWORK rounds ◀───┘
                                              │
                         DOCUMENT (as needed) → CLOSE
```

Bug requests enter `BugResolver` through `/analyze-bug`, `/analyze-log`, direct selection, or Orchestrator's manual handoff; the two managers are never auto-nested. Its diagnostic path is `INTAKE → GUIDE_SYMPTOMS → CONFIRM_DIRECTION (when needed) → SCOPE → NORMALIZE_ERROR → IDENTIFY_PROBLEM → TRACE_CONTEXT → REPRODUCE_BASELINE → EVIDENCE_CHECK → AWAIT_EVIDENCE / HYPOTHESES → VALIDATE_CAUSE → DECIDE`. After the user explicitly authorizes a fix, it continues through `PLAN_FIX → IMPLEMENT → VERIFY → QUALITY_REVIEW → REWORK → DOCUMENT → CLOSE`.

BugResolver first uses Usage Symptom Profile to understand the user's goal, actual operations, expected/actual behavior, frequency/boundaries, environment, impact, and recovery. When direction-changing symptoms are missing, it asks them together through one Usage Symptom Questions table with at most five questions in the first set and permits `Unknown`. It asks for direction confirmation only when symptoms indicate different modules/root-cause paths or conflict; it does not trace deeply or delegate Developer before confirmation, and proceeds directly when the scenario is clear. It then emits Problem Identification grounded in that Profile to separate the observed problem, category, suspected subsystem, severity, and evidence confidence.

When critical evidence is missing, BugResolver searches the repository and finishes safe preliminary analysis before requesting the smallest logs, versions, configuration, or ELF/MAP/dump artifacts once through a separate Evidence Request table. Symptom questions and evidence requests never mix. Until evidence arrives, it neither confirms root cause, repeats the request, nor invokes Developer. Log analysis covers bare-metal, RTOS, module SDK, Embedded Linux, and hybrid systems while preserving original offsets and clock domains; it never invents a unified timeline without reliable timing evidence.

Command evidence includes the exact command, exit code, and relevant output. An unexecuted check is `NOT_RUN`, not a pass.

### Project Profile

[`.github/embedded-project.yml`](.github/embedded-project.yml) is the entry point for project facts. After installation, confirm:

- `product_form`, MCU/SoC, RTOS, toolchain, and C standard.
- Source/driver/application/services/middleware/protocols/test/docs/vendor/generated paths; absent application path fields are equivalent to `auto`.
- Host-side `commands.configure`, `commands.build`, `commands.test`, and `commands.static_analysis` commands.
- Hardware commands isolated under `commands.hardware.flash`, `commands.hardware.erase`, `commands.hardware.fuse`, `commands.hardware.reset`, and `commands.hardware.hil`; they are disabled by default and require explicit approval.
- ELF, MAP, log, and static-analysis report locations.
- MISRA edition, deviation file, and hardware-document revision.

Fields may remain `auto`, in which case agents discover them from the repository. Profile/repository conflicts are reported as configuration drift. See [Embedded Product Forms](docs/product-forms.md) for detailed review areas.

### Project-Level Constraints

The optional root [`.project/`](.project/README.md) directory is a sibling of `.github/` and stores target-project conventions, path policy, Git delivery policy, and extensions. Its absence returns `NOT_CONFIGURED` for legacy compatibility. When present, [`.project/project.yml`](.project/project.yml) registers rule files and `applies_to` globs under `rules`; agents load only matching rules, and the directory is validated strictly.

`python .github/agent-kit/scripts/project_policy.py rules --root . --path <repo-relative-path>` deterministically emits applicable rules and Git policy. Repeat `--path` for multiple paths, or use `--all` for audit.

The default [Git delivery policy](.project/git/delivery.yml) defines automation, scope, commit template/checks, and push branch/check rules, but cannot store a remote, URL, or target ref. Both `automation` switches default to off, and Task Brief `Git Delivery` accepts only `none`, `commit`, `commit-and-push`, or `auto`. The strict [commit template](.project/git/commit.template) is copied into the repository and has no runtime dependency on an external drive.

Push preflight resolves the current branch, branch remote/merge, and one push URL only from this project's local `.git` config. Global/system config, environment, `.project`, and user text cannot override it. Missing upstream, detached HEAD, multiple push URLs, protected branches, out-of-scope paths, or fingerprint drift block delivery; the tool itself performs no commit or push.

`Git Delivery: auto` decides only after the repair, tests, required checks, independent review, and required documentation pass. Missing required message metadata blocks for input; no diff means no delivery; any unmet automatic-upload prerequisite leaves Git unchanged and makes the agent output only the complete commit content. It explicitly stages, creates one commit, and pushes after fingerprint/SHA revalidation only when policy enables both commit and push, the index starts empty, changes exactly match the repair scope, HEAD equals the local upstream, and the target is safe and unique. A push failure keeps the local commit without automatic rollback.

`extensions` may hold namespaced project-integration configuration, and `.project/` may contain other subdirectories and content, so project rules can grow without changing the five-agent structure.

### Installation

1. Place this kit at the target firmware repository root and merge `.github` rather than overwriting configuration. Install sibling `.project` only when project-level rules are wanted; legacy projects may omit it.
2. Manually merge `.github/copilot-instructions.md` and preserve the target project's existing rules.
3. Adjust `.github/embedded-project.yml`. Keep unknown values as `auto`; do not enter unconfirmed hardware facts.
4. When using `.project`, adjust `project.yml`, applicable rules, and Git policy. Keep `automation.commit/push: false` until paths, branches, and checks are confirmed. Never add a remote, URL, or target branch to policy.
5. Open the firmware repository root directly in VS Code and trust the workspace. Opening only its parent prevents automatic `.github` discovery.
6. Enable GitHub Copilot Chat and confirm that custom agents, prompt files, Agent Skills, and `agent/runSubagent` are available. Recursive subagents are not required.
7. Confirm in Chat Customizations/Diagnostics that all five agents, six prompts, and instructions load without errors, then run the Kit validator for `.project` references and Git policy.

The `agents` allowlists in the Orchestrator and BugResolver frontmatter may depend on Experimental custom-agent/subagent support in the target VS Code and GitHub Copilot environment. This kit does not claim an unverified minimum version; run Customizations/Diagnostics in the actual target environment and perform both a general delegation smoke test and a bug-resolution delegation smoke test to confirm that the allowlists are honored.

The repository intentionally has no overwriting installation script. Compare and merge directories during upgrades, especially the profile, `.project/` rules, global rules, and local prompt customizations.

### Usage

Recommended entry point:

```text
Select Orchestrator: Add an SPI driver for W25Q128, reusing the existing HAL and completing host build, tests, and independent review. Stop rather than guessing register values if a matching datasheet is unavailable.
```

Slash commands:

- `/new-driver <driver_request>`: Orchestrator performs driver preflight, implementation, verification, and review.
- `/implement-feature <feature_request>`: Orchestrator performs application behavior modeling, implementation, traceability, verification, and review.
- `/analyze-bug <bug_input>`: BugResolver first guides and normalizes usage symptoms, confirms direction only when needed, then identifies the problem, traces code/configuration context, tests root-cause hypotheses, actively requests missing evidence as one set, and coordinates repair plus quality assessment when authorized.
- `/analyze-log <log_input>`: even with logs supplied, BugResolver establishes usage context and direction before analyzing multi-product logs, event correlation, ELF/MAP artifacts, artifact identity, and the evidence timeline.
- `/misra-review <review_target>`: QualityReviewer performs MISRA-oriented risk screening.
- `/verify-change <change_target>`: Orchestrator audits baseline, build, tests, review, and documentation gates.

Direct mode:

- Implementation only: select `EmbeddedDeveloper` and provide the Goal, Scope, constraints, and acceptance criteria.
- Bug/log analysis or resolution: select `BugResolver` and provide any available original error or log. The agent guides you to complete the real goal, steps, expected/actual behavior, frequency/boundaries, environment, and impact; once direction is clear, it identifies the problem, discovers local context, and asks once for the remaining minimum evidence. State whether changes are authorized when resolution is required.
- Independent quality assessment only: select `QualityReviewer` and provide requirements, the real diff/files, and available build/test/static-analysis evidence.
- Documentation only: select `DocKeeper` and provide confirmed source/API/test or root-cause evidence.
- Automatic Git delivery: set Task Brief `Git Delivery` to only `none`, `commit`, `commit-and-push`, or `auto` and enable matching `.project` `automation`. The remote, URL, and target branch always come from this project's `.git`. Orchestrator delegates a separate delivery task to `EmbeddedDeveloper` only after gates and independent review. `auto` safely chooses between automatic commit-plus-push and outputting only the complete commit content; it never degrades to automatic commit-only.

### Safety and Permissions

- VS Code approval settings govern `execute` for BugResolver, EmbeddedDeveloper, and QualityReviewer. BugResolver runs only read-only diagnostics and symbolization; Reviewer runs only read-only Git, build/test audit, and static analysis.
- Flash, erase, fuse, reset, HIL, device power, release, and external deployment always require explicit human authorization. A command's presence in the profile is not authorization.
- A `.project` Git policy constrains work but is not authorization. Commit/push stages only explicit task paths; protected branches, force push, `push -u`, custom refspecs, and automatic `.git/config` changes are forbidden.
- DocKeeper uses the web only for official or vendor public sources and never uploads private source, logs, customer data, or credentials.
- Do not run write tasks concurrently in one checkout. Parallel writing may be considered only after one-task-per-worktree/branch isolation exists.
- Agents do not replace human code review, hardware verification, functional-safety assessment, or formal MISRA compliance tools.
- Skill scripts use exit code `0` for success, `2` for invalid input, `3` for insufficient evidence, and `4` for external-tool failure. `profile_gates.py` only plans/validates gate evidence and never executes profile commands; hardware never enters host gates.

### Validate the Kit

Install development dependencies and run static validation:

```sh
python -m pip install -r .github/agent-kit/requirements-dev.txt
python .github/agent-kit/scripts/validate_customizations.py --root .
python -m unittest discover -s .github/agent-kit/tests -p "test_*.py"
```

Build the host example:

```sh
cmake -S examples/minimal-firmware -B build/minimal-firmware
cmake --build build/minimal-firmware
ctest --test-dir build/minimal-firmware --output-on-failure
```

CI runs these checks on Windows and Ubuntu. Real interaction also requires the [VS Code Manual Smoke Test](docs/manual-smoke-test.md), covering discovery, project-constraint invocation, controlled Git delivery, automatic orchestration, missing documents, baseline failure, seeded-defect review, ELF mismatch, and hardware approval.

### Layout

```text
.github/
├── copilot-instructions.md
├── embedded-project.yml
├── agent-contracts.md
├── agents/                  # exactly five agents
├── agent-kit/               # kit self-check scripts, tests, fixtures, and dev dependencies
├── instructions/            # C, bilingual, and kit configuration rules
├── prompts/                 # six thin slash entries
├── skills/                  # five on-demand workflows with deterministic scripts
└── workflows/validate.yml
.project/
├── project.yml              # project constraint manifest and extension entry point
├── README.md                # bilingual usage guide
├── rules/                   # project-specific rules invoked by repository path
└── git/
    ├── delivery.yml         # automation, scope, safety, branch rules, and checks; no target
    └── commit.template      # strict commit message template
docs/                        # product forms and manual smoke test
examples/minimal-firmware/   # CMake/CTest + fake HAL
```

### Bilingual Rules

First-party Markdown in the README, `docs/`, `.github/`, and `.project/` uses:

```md
# <Document Title>

> 中文：本文档采用固定双语结构。更新中文或英文内容时，必须同步更新另一部分，保持两部分语义一致。
>
> English: This document uses a fixed bilingual structure. When either the Chinese or English content is updated, the other section must be updated as well to keep both sections semantically aligned.

## 中文 / Chinese

<完整中文内容>

## English

<Complete English content>
```

Vendor, generated, third-party documentation, and license text are not automatically bilingualized. The release gate does not accept an unowned `TODO(sync)`.

### Extension Principles

- Do not add a sixth agent casually for a new workflow; extend an existing role mode or add an on-demand skill first.
- Prompts provide manual entry and agent routing; complex checklists, templates, and scripts belong in skills.
- Maintain shared rules once and link them from agents and skills to avoid repeated context.
- Put project-specific rules under `.project/` and register them through the manifest. Use namespaced `extensions` for other structured integrations; preserve unknown extensions without executing them automatically.
- The kit fully supports VS Code only. GitHub cloud/CLI may ignore handoffs or VS Code-specific allowlists and are outside v1 acceptance.
