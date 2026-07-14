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

若输入为空，先请求日志或有效路径。收到输入后先输出共享 `Problem Identification`，覆盖项目画像对应的 bare-metal、RTOS、模组 SDK、Embedded Linux 或混合系统日志流程。关键上下文缺失时先搜索仓库并完成安全初判，再用共享 `Evidence Request` 表一次性请求最小资料集；在补充前不确认根因或调用 Developer。Prompt 仅负责输入与路由；执行 Skill、项目画像和共享契约定义的完整流程。

## English

Use the [firmware-log-analysis](../skills/firmware-log-analysis/SKILL.md) workflow with this input:

- `log_input`: `${input:log_input}`

If the input is empty, request log content or a valid path first. After input arrives, emit the shared Problem Identification and apply the project profile's bare-metal, RTOS, module-SDK, Embedded-Linux, or hybrid log workflow. When critical context is missing, search the repository and finish safe preliminary analysis before requesting the smallest evidence set once through the shared Evidence Request table; do not confirm root cause or invoke Developer until it arrives. This prompt only adapts input and routing; execute the complete workflow defined by the Skill, project profile, and shared contract.
