---
name: firmware-log-analysis
description: "分析 bare-metal、RTOS、模组 SDK、Embedded Linux 与混合系统的运行、串口、崩溃、异常和看门狗日志，识别问题、验证产物、关联事件并主动索取缺失证据。 / Analyze runtime, serial, crash, exception, and watchdog logs across bare-metal, RTOS, module SDK, Embedded Linux, and hybrid systems; identify the problem, validate artifacts, correlate events, and actively request missing evidence."
user-invocable: false
---

# Firmware Log Analysis

> 中文：本文档采用固定双语结构。更新中文或英文内容时，必须同步更新另一部分，保持两部分语义一致。
>
> English: This document uses a fixed bilingual structure. When either the Chinese or English content is updated, the other section must be updated as well to keep both sections semantically aligned.

## 中文 / Chinese

### 输入与模式

- 接收 `log_input`，内容可以是日志片段、仓库内文件路径，或经用户明确纳入范围的 log、dump、core、ELF、MAP 等产物。
- 使用 `BugResolver` 的 `bug-analysis` 主模式和 `fault-analysis` 辅助模式，并先读取 `.github/agent-contracts.md` 与 `.github/embedded-project.yml`。
- 覆盖 `bare-metal`、`rtos`、`module-sdk`、`embedded-linux` 和 `hybrid`。字段为 `auto` 时先从仓库入口、依赖、日志格式和构建产物探测。
- 保留原始行、行号/字节偏移、地址、寄存器、错误码和工具诊断；不得把私有日志发送到 Web 服务。
- 即使已经提供完整日志，也必须先执行共享 `GUIDE_SYMPTOMS`；日志不能替代用户目标、操作序列、预期行为和实际影响。

### 日志分析工作流

1. **引导使用现象（`GUIDE_SYMPTOMS`）**：先根据已有描述生成 `## Usage Symptom Profile`。若会改变日志解释方向的现象缺失，使用 `## Usage Symptom Questions` 集中询问，首轮最多 5 个；问题只采集目标、操作、预期/实际、频率/边界和环境/影响/恢复，不索取日志产物。
2. **确认方向（`CONFIRM_DIRECTION`，按需）**：日志可能对应两个以上组件或根因路径、预期/实际不清或输入矛盾时，将 `Direction Confirmation` 标记为 `PENDING`，输出 `Current Understanding` 与 `Possible Directions` 并暂停深入分析。方向明确时写 `NOT_REQUIRED`，用户确认后写 `CONFIRMED`。用户可回答 `Unknown`；非关键未知项不得阻塞，只允许因新矛盾产生的一组不重复补充问题。
3. **识别问题（`IDENTIFY_PROBLEM`）**：方向可继续后，根据 Usage Symptom Profile、日志和用户描述输出初步 `## Problem Identification`，引用已确认的使用现象，并区分观察现象、检测点、触发条件和未知原因。
4. **发现上下文**：先从仓库搜索日志格式、打印位置、错误码、组件、构建版本、配置、测试和现有 ELF/MAP/dump，不能要求用户重复提供可发现材料。
5. **规范化事件**：逐条提取原始时间戳与时钟域、level、component、CPU/core、task/thread/process、session/correlation ID、事件码和消息，同时保留原始行与偏移。时间基准或时钟换算无证据时使用 `Unknown`，不得伪造统一时间。
6. **应用产品形态检查**：按下方矩阵解释上下文；未知形态不得直接套用某一平台假设。
7. **建立时间线与关联**：在各自可信时钟域内排序，标出最后正常事件、首个异常、异常传播、复位/恢复和重复模式；跨域关联必须说明用于对齐的事件与误差。
8. **验证产物身份**：核对 firmware/software version、build ID、时间戳、芯片/板卡 revision、ELF、MAP、core/dump 和工具链。相似文件名不能证明匹配。
9. **提取与符号化证据**：收集 PC/LR/SP、异常状态、调用栈、任务/进程、内存/资源/协议状态和邻近窗口。仅在产物匹配且工具链已识别时运行只读符号化，并记录命令、退出码和原始输出。
10. **证据检查（`EVIDENCE_CHECK`）**：若关键资料仍缺失，完成所有安全初判后输出 `## Evidence Request`，集中索取最小证据产物并进入 `AWAIT_EVIDENCE`；不得把使用现象问题混入该表，不得确认根因或委派修复。补充后重新检查且不重复索取。
11. **形成结论**：分别列出 `Evidence` 与 `Hypotheses`，记录支持证据、反证、置信度和最小验证动作。只有完整因果链成立并排除主要替代解释时才确认根因。

### 产品形态关注点

- `bare-metal`：reset reason、异常寄存器、PC/LR/SP、ISR、启动/低功耗路径、MMIO 与看门狗。
- `rtos`：task/ISR 身份、调度和优先级、队列/信号量/锁、栈水位、heap、超时与看门狗。
- `module-sdk`：AT command/response/URC 关联、网络注册与连接状态、异步 session、重试、超时和恢复。
- `embedded-linux`：syslog/journal/dmesg、systemd unit、PID/TID、signal、`errno`、kernel/user-space 边界、文件描述符与服务生命周期。
- `hybrid`：分别识别每个运行域的 firmware/software build、时钟域和日志格式，再使用协议序号、共享事件或明确 correlation ID 关联；不得直接按文本顺序合并。

### 确定性工具

优先使用 [`scripts/artifact_evidence.py`](scripts/artifact_evidence.py) 收集和核对证据。`inspect` 读取 ELF/build ID/符号，`match` 验证日志匹配，`symbolize` 仅在匹配后解析源码位置，`roundtrip` 生成并验证派生日志。脚本输出 JSON；退出码 `3` 表示 `INSUFFICIENT_EVIDENCE`，不得绕过后继续猜测。

### 输出

先输出共享 `Usage Symptom Profile`；需要补充现象时输出 `Usage Symptom Questions`，方向歧义时输出 `Current Understanding` 与 `Possible Directions` 并暂停。方向为 `CONFIRMED` 或 `NOT_REQUIRED` 后，再输出共享 `Problem Identification`、按 Bug Analysis 契约报告，并追加：

- `Log Scope`：输入文件/片段、采集窗口、产品形态、组件与运行域。
- `Normalized Events`：原始偏移、原始时间/时钟域、可信的规范化时间或 `Unknown`、执行上下文、事件和原文。
- `Anomalies and Correlations`：异常点、跨组件/跨域关联依据及不确定性。
- `Artifact Identity`：版本、build ID、ELF/MAP/dump/toolchain 匹配结论。
- `Timeline`：最后正常事件到首个异常、传播、复位和恢复。
- `Next Evidence Needed`：无缺口时写 `None`；否则与共享 `Evidence Request` 表一致。

未经证实的根因必须写 `Not confirmed` 并保留为假设。无法继续交互或用户不能提供 `REQUIRED_NOW` 材料时返回 `INSUFFICIENT_EVIDENCE`；缺少授权、产品决策或必需硬件资料时返回 `BLOCKED`。

## English

### Input and mode

- Accept `log_input` as pasted content, a repository path, or log, dump, core, ELF, or MAP artifacts explicitly placed in scope by the user.
- Use the `BugResolver` `bug-analysis` primary mode with `fault-analysis` as an auxiliary mode, and read `.github/agent-contracts.md` plus `.github/embedded-project.yml` first.
- Cover `bare-metal`, `rtos`, `module-sdk`, `embedded-linux`, and `hybrid`. For `auto`, discover the form from entry points, dependencies, log format, and build artifacts.
- Preserve original lines, line/byte offsets, addresses, registers, error codes, and tool diagnostics. Never send private logs to a Web service.
- Even when a complete log is supplied, perform the shared `GUIDE_SYMPTOMS` first. A log does not replace the user's goal, operation sequence, expected behavior, or actual impact.

### Log-analysis workflow

1. **Guide usage symptoms (`GUIDE_SYMPTOMS`)**: first create `## Usage Symptom Profile` from available descriptions. When missing symptoms would change log interpretation, ask them together through `## Usage Symptom Questions`, with at most five questions in the first set. Questions collect only goals, operations, expected/actual behavior, frequency/boundaries, and environment/impact/recovery, not log artifacts.
2. **Confirm direction (`CONFIRM_DIRECTION`, when needed)**: when the log could map to two or more components or root-cause paths, expected versus actual behavior is unclear, or inputs conflict, set `Direction Confirmation` to `PENDING`, emit `Current Understanding` and `Possible Directions`, and pause deep analysis. Use `NOT_REQUIRED` when direction is clear and `CONFIRMED` after user confirmation. The user may answer `Unknown`; non-critical unknowns do not block, and only one non-repeating follow-up set is allowed for a new contradiction.
3. **Identify the problem (`IDENTIFY_PROBLEM`)**: after direction may continue, use the Usage Symptom Profile, log, and user report to emit a provisional `## Problem Identification` grounded in confirmed usage facts, separating the observed symptom, detection point, trigger, and unknown cause.
4. **Discover context**: search the repository first for log formats, emitters, error codes, components, build version, configuration, tests, and existing ELF/MAP/dump artifacts. Never ask for material that is already discoverable.
5. **Normalize events**: extract original timestamp and clock domain, level, component, CPU/core, task/thread/process, session/correlation ID, event code, and message while preserving the original line and offset. Use `Unknown` rather than inventing a unified timestamp when time-base evidence is absent.
6. **Apply product-form focus**: interpret context with the matrix below. Never apply a platform assumption when the form is unknown.
7. **Build and correlate timelines**: order events within each trusted clock domain; mark the last normal event, first anomaly, propagation, reset/recovery, and repetition. State alignment events and uncertainty for cross-domain correlation.
8. **Validate artifact identity**: cross-check firmware/software version, build ID, timestamps, silicon/board revision, ELF, MAP, core/dump, and toolchain. Similar filenames do not prove a match.
9. **Extract and symbolize evidence**: collect PC/LR/SP, exception state, stack, task/process, memory/resource/protocol state, and nearby windows. Run read-only symbolization only after artifacts match and the toolchain is identified; record command, exit code, and raw output.
10. **Check evidence (`EVIDENCE_CHECK`)**: when critical material remains missing, finish safe preliminary analysis, emit one consolidated `## Evidence Request` for evidence artifacts, and enter `AWAIT_EVIDENCE`. Never mix usage questions into that table, confirm root cause, or delegate a repair. Recheck after new evidence and never request it twice.
11. **Form conclusions**: separate `Evidence` and `Hypotheses`, including support, counter-evidence, confidence, and the smallest validation. Confirm root cause only when the complete causal chain holds and main alternatives are excluded.

### Product-form focus

- `bare-metal`: reset reason, exception registers, PC/LR/SP, ISR, startup/low-power paths, MMIO, and watchdog.
- `rtos`: task/ISR identity, scheduling/priority, queue/semaphore/lock, stack watermark, heap, timeout, and watchdog.
- `module-sdk`: AT command/response/URC correlation, network registration/connection state, asynchronous session, retry, timeout, and recovery.
- `embedded-linux`: syslog/journal/dmesg, systemd unit, PID/TID, signal, `errno`, kernel/user-space boundary, file descriptors, and service lifecycle.
- `hybrid`: identify firmware/software build, clock domain, and log format per execution domain, then correlate through protocol sequence, shared events, or an explicit correlation ID; never merge by text order alone.

### Deterministic tool

Prefer [`scripts/artifact_evidence.py`](scripts/artifact_evidence.py) for evidence collection and matching. `inspect` reads ELF/build-ID/symbol identity, `match` validates a log, `symbolize` resolves source only after a match, and `roundtrip` creates and verifies a derived log. The script emits JSON; exit code `3` means `INSUFFICIENT_EVIDENCE` and must not be bypassed with a guess.

### Output

Emit the shared Usage Symptom Profile first. When symptoms are missing, emit Usage Symptom Questions; when direction is ambiguous, emit Current Understanding plus Possible Directions and pause. After direction is `CONFIRMED` or `NOT_REQUIRED`, emit the shared Problem Identification, then the Bug Analysis contract, followed by:

- `Log Scope`: input files/excerpts, capture window, product form, components, and execution domains.
- `Normalized Events`: original offset, original time/domain, evidence-backed normalized time or `Unknown`, execution context, event, and original message.
- `Anomalies and Correlations`: anomaly points, cross-component/domain evidence, and uncertainty.
- `Artifact Identity`: version, build ID, ELF/MAP/dump/toolchain match result.
- `Timeline`: last normal event through first anomaly, propagation, reset, and recovery.
- `Next Evidence Needed`: `None` when complete; otherwise identical to the shared Evidence Request table.

Write `Not confirmed` for an unproven root cause and keep it as a hypothesis. Return `INSUFFICIENT_EVIDENCE` when interaction cannot continue or the user cannot supply `REQUIRED_NOW` material; use `BLOCKED` for missing authority, product decisions, or required hardware sources.
