---
name: analyze-log
description: Analyze embedded runtime, serial, crash, or exception logs / 分析嵌入式运行、串口、崩溃或异常日志
agent: BugResolver
argument-hint: 日志或 dump/ELF/MAP、是否修复及 Git Delivery / Logs or dump/ELF/MAP, fix authorization, and Git Delivery
---

# Analyze Log

> 中文：本文档采用固定双语结构。更新中文或英文内容时，必须同步更新另一部分，保持两部分语义一致。
>
> English: This document uses a fixed bilingual structure. When either the Chinese or English content is updated, the other section must be updated as well to keep both sections semantically aligned.

## 中文 / Chinese

将 `${input:log_input}` 作为 `log_input` 交给 `BugResolver`，执行 [firmware-log-analysis](../skills/firmware-log-analysis/SKILL.md)，并遵循 `.github/agent-contracts.md`。

- 日志不能代替用户目标、操作序列、预期/实际、环境和影响；先建立使用现象画像。
- 保留原始行、偏移和时钟域；没有可靠基准时不得伪造统一时间或跨域顺序。
- 关键材料缺失时，先完成仓库内安全初判，再一次性请求最小证据。
- 默认只读；修复与 Git 交付必须有明确授权并由共享契约控制。

此 Prompt 只适配输入与 Skill 路由，不复制 Agent 状态机或共享交付规则。

## English

Pass `${input:log_input}` to `BugResolver` as `log_input`, run [firmware-log-analysis](../skills/firmware-log-analysis/SKILL.md), and follow `.github/agent-contracts.md`.

- A log does not replace the user's goal, operation sequence, expected/actual behavior, environment, or impact; establish the usage-symptom profile first.
- Preserve original lines, offsets, and clock domains. Never invent a unified timeline or cross-domain order without a reliable basis.
- When critical material is missing, finish safe repository-local triage before requesting the minimum evidence once.
- Work is read-only by default; fixes and Git delivery require explicit authority and remain governed by the shared contract.

This prompt adapts input and Skill routing only; it does not duplicate the Agent state machine or shared delivery rules.
