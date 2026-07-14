---
name: analyze-log
description: 分析固件串口、崩溃或异常日志 / Analyze firmware serial, crash, or exception logs
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

若输入为空，先请求日志或有效路径。Prompt 仅负责输入与路由；执行 Skill、项目画像和共享契约定义的完整流程。

## English

Use the [firmware-log-analysis](../skills/firmware-log-analysis/SKILL.md) workflow with this input:

- `log_input`: `${input:log_input}`

If the input is empty, request log content or a valid path first. This prompt only adapts input and routing; execute the complete workflow defined by the Skill, project profile, and shared contract.
