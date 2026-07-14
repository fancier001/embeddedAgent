---
name: analyze-log
description: 分析嵌入式运行、串口、崩溃或异常日志 / Analyze embedded runtime, serial, crash, or exception logs
agent: BugResolver
argument-hint: 日志片段、日志路径或 dump/ELF/MAP 信息 / Log text, log path, or dump/ELF/MAP details
---

# Analyze Log

> 中文：本文档采用固定双语结构。更新中文或英文内容时，必须同步更新另一部分，保持两部分语义一致。
>
> English: This document uses a fixed bilingual structure. When either the Chinese or English content is updated, the other section must be updated as well to keep both sections semantically aligned.

## 中文 / Chinese

使用 [firmware-log-analysis](../skills/firmware-log-analysis/SKILL.md) 工作流处理以下输入：

- `log_input`: `${input:log_input}`

无论是否已提供日志，都先执行共享 `GUIDE_SYMPTOMS`：生成 `Usage Symptom Profile`；缺少会影响方向的使用现象时，用 `Usage Symptom Questions` 集中询问，首轮最多 5 个。日志不能代替用户目标、操作序列、预期/实际、频率/边界和影响/恢复。用户可回答 `Unknown`，非关键未知项不阻塞；现象存在多方向或矛盾时执行 `CONFIRM_DIRECTION`，输出 `Current Understanding` 与 `Possible Directions`，确认前暂停深入日志关联、根因确认和 Developer 委派。

方向为 `CONFIRMED` 或 `NOT_REQUIRED` 后，输出引用 Usage Symptom Profile 的共享 `Problem Identification`，再覆盖项目画像对应的 bare-metal、RTOS、模组 SDK、Embedded Linux 或混合系统日志流程。输入为空或关键证据缺失时，先搜索仓库并完成安全初判，再用共享 `Evidence Request` 表一次性索取日志/有效路径和最小证据产物；不得把使用现象问题混入该表，在补充前不确认根因或调用 Developer。Prompt 仅负责输入与路由；执行 Skill、项目画像和共享契约定义的完整流程。

## English

Use the [firmware-log-analysis](../skills/firmware-log-analysis/SKILL.md) workflow with this input:

- `log_input`: `${input:log_input}`

Whether or not a log is already supplied, perform the shared `GUIDE_SYMPTOMS` first and create a Usage Symptom Profile. When usage symptoms that could change direction are missing, ask them together through Usage Symptom Questions, with at most five questions in the first set. A log does not replace user goal, operation sequence, expected/actual behavior, frequency/boundaries, or impact/recovery. The user may answer `Unknown`, and non-critical unknowns do not block. When symptoms have multiple directions or conflict, perform `CONFIRM_DIRECTION`, emit Current Understanding and Possible Directions, and pause deep log correlation, root-cause confirmation, and Developer delegation.

After direction is `CONFIRMED` or `NOT_REQUIRED`, emit the shared Problem Identification grounded in the Usage Symptom Profile and apply the project profile's bare-metal, RTOS, module-SDK, Embedded-Linux, or hybrid log workflow. When input is empty or critical evidence is missing, search the repository and finish safe preliminary analysis before requesting log content/a valid path and the smallest evidence artifacts once through the shared Evidence Request table. Never mix usage-symptom questions into that table, and do not confirm root cause or invoke Developer until evidence arrives. This prompt only adapts input and routing; execute the complete workflow defined by the Skill, project profile, and shared contract.
