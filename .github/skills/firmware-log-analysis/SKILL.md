---
name: firmware-log-analysis
description: "分析嵌入式固件串口、崩溃、异常和看门狗日志，验证固件与符号产物匹配后建立时间线、符号化地址并区分证据与假设；当用户提供日志、dump、ELF/MAP 或要求定位固件故障时使用。 / Analyze embedded serial, crash, exception, and watchdog logs by validating firmware-to-symbol artifact identity, building a timeline, symbolizing addresses, and separating evidence from hypotheses; use for logs, dumps, ELF/MAP artifacts, or firmware fault diagnosis."
user-invocable: false
---

# Firmware Log Analysis

> 中文：本文档采用固定双语结构。更新中文或英文内容时，必须同步更新另一部分，保持两部分语义一致。
>
> English: This document uses a fixed bilingual structure. When either the Chinese or English content is updated, the other section must be updated as well to keep both sections semantically aligned.

## 中文 / Chinese

### 输入与模式

- 接收 `log_input`，内容可以是日志片段、仓库内文件路径或经用户明确纳入范围的日志/转储产物。
- 使用 `QualityReviewer` 的 `fault-analysis` 模式，并先读取 `.github/agent-contracts.md` 与 `.github/embedded-project.yml`。
- 保留日志、地址、寄存器、错误码和工具诊断原文；不得把私有日志发送到 Web 服务。

### 工作流

1. **确认现象**：记录设备、产品形态、复现步骤、时间基准、预期行为和实际行为；缺失项作为未知量列出。
2. **验证产物身份**：从日志和产物中核对 firmware version、build ID、时间戳、芯片/板卡 revision、ELF、MAP 与工具链。不能仅凭相似文件名认定匹配。
3. **建立时间线**：按原始时间戳排序，标出最后一个正常事件、首个异常、复位/看门狗/异常入口和后续恢复行为；说明时钟回绕或多核日志交错等不确定性。
4. **提取证据**：收集 PC/LR/SP、异常状态寄存器、任务/线程、调用栈、内存错误、资源状态和邻近日志。所有转换均保留原值。
5. **安全符号化**：仅在 ELF/MAP 与运行固件匹配且工具链已识别时运行项目已有的 `addr2line`、调试器或等效只读命令，并记录命令、退出码和输出。
6. **形成结论**：分别列出 `Evidence` 与 `Hypotheses`。为每个假设给出支持证据、反证、置信度和下一项最小验证动作；不要把相关性写成根因。
7. **判定状态**：证据能够排除主要替代解释时给出根因；产物不匹配或关键上下文缺失时返回 `INSUFFICIENT_EVIDENCE`，并列出具体所需材料。

### 确定性工具

优先使用 [`scripts/artifact_evidence.py`](scripts/artifact_evidence.py) 收集和核对证据。`inspect` 读取 ELF/build ID/符号，`match` 验证日志匹配，`symbolize` 仅在匹配后解析源码位置，`roundtrip` 生成并验证派生日志。脚本输出 JSON；退出码 `3` 表示 `INSUFFICIENT_EVIDENCE`，不得绕过后继续猜测。

### 输出

报告 `Status`、`Symptom`、`Artifact Identity`、`Timeline`、`Evidence`、`Hypotheses`、`Root Cause`、`Fix Recommendation`、`Commands and Exit Codes`、`Risks` 和 `Next Evidence Needed`。未经证实的根因必须明确标记为假设。

## English

### Input and mode

- Accept `log_input` as a pasted log, a repository file path, or log/dump artifacts explicitly placed in scope by the user.
- Use the `QualityReviewer` `fault-analysis` mode and read `.github/agent-contracts.md` plus `.github/embedded-project.yml` first.
- Preserve logs, addresses, registers, error codes, and tool diagnostics verbatim. Never send private logs to a Web service.

### Workflow

1. **Confirm the symptom**: Record the device, product form, reproduction steps, time base, expected behavior, and actual behavior. List missing items as unknowns.
2. **Validate artifact identity**: Cross-check firmware version, build ID, timestamps, silicon/board revision, ELF, MAP, and toolchain evidence from the log and artifacts. Similar filenames alone do not prove a match.
3. **Build the timeline**: Order events by original timestamps; identify the last normal event, first anomaly, reset/watchdog/exception entry, and recovery behavior. Call out uncertainty from clock wrap or interleaved multicore logs.
4. **Extract evidence**: Collect PC/LR/SP, exception status registers, task/thread identity, stack frames, memory faults, resource state, and nearby logs. Preserve original values alongside every transformation.
5. **Symbolize safely**: Run the project's existing `addr2line`, debugger, or equivalent read-only command only after matching the ELF/MAP to the running firmware and identifying the toolchain. Record commands, exit codes, and outputs.
6. **Form conclusions**: Separate `Evidence` from `Hypotheses`. For every hypothesis, state supporting evidence, counter-evidence, confidence, and the smallest next validation action. Do not present correlation as root cause.
7. **Set status**: State a root cause only when the evidence excludes the main alternatives. Return `INSUFFICIENT_EVIDENCE` for mismatched artifacts or missing critical context and list the exact material required.

### Deterministic tool

Prefer [`scripts/artifact_evidence.py`](scripts/artifact_evidence.py) for evidence collection and matching. `inspect` reads ELF/build-ID/symbol identity, `match` validates a log, `symbolize` resolves source only after a match, and `roundtrip` creates and verifies a derived log. The script emits JSON; exit code `3` means `INSUFFICIENT_EVIDENCE` and must not be bypassed with a guess.

### Output

Report `Status`, `Symptom`, `Artifact Identity`, `Timeline`, `Evidence`, `Hypotheses`, `Root Cause`, `Fix Recommendation`, `Commands and Exit Codes`, `Risks`, and `Next Evidence Needed`. Label every unproven root-cause statement explicitly as a hypothesis.
