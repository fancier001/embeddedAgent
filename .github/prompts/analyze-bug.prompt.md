---
name: analyze-bug
description: 理解错误、验证根因假设并输出证据化 Bug 分析 / Understand errors, test root-cause hypotheses, and report evidence-backed bug analysis
agent: BugResolver
argument-hint: Bug 描述、原始错误、复现步骤、是否修复及 Git Delivery / Bug description, error, reproduction, fix authorization, and Git Delivery
---

# Analyze Bug

> 中文：本文档采用固定双语结构。更新中文或英文内容时，必须同步更新另一部分，保持两部分语义一致。
>
> English: This document uses a fixed bilingual structure. When either the Chinese or English content is updated, the other section must be updated as well to keep both sections semantically aligned.

## 中文 / Chinese

将 `${input:bug_input}` 作为 `bug_input` 交给 `BugResolver`，并严格执行 `.github/agent-contracts.md` 的 Bug Analysis、证据、修复闭环和 Next Action 契约。

- 默认只读分析；只有输入明确授权修复时才进入 `bug-resolution`。
- 先规范化使用现象，只有多方向、含糊或矛盾时才确认方向；缺少关键证据时先完成仓库内安全初判，再集中索证。
- crash、dump、ELF/MAP 或运行日志场景同时启用 `fault-analysis`。
- 保留用户显式 Git Delivery 选择；未提供时不得推断 commit 或 push 授权。

此 Prompt 只适配输入，不复制 Agent 状态机或共享交付规则。

## English

Pass `${input:bug_input}` to `BugResolver` as `bug_input`, then follow the Bug Analysis, evidence, resolution-loop, and Next Action contracts in `.github/agent-contracts.md`.

- Analysis is read-only by default; enter `bug-resolution` only when the input explicitly authorizes a fix.
- Normalize usage symptoms first. Confirm direction only when it is ambiguous, conflicting, or has multiple paths; when key evidence is missing, finish safe repository-local triage before requesting it together.
- Add `fault-analysis` for crash, dump, ELF/MAP, or runtime-log cases.
- Preserve an explicit Git Delivery choice and never infer commit or push authority when it is omitted.

This prompt adapts input only; it does not duplicate the Agent state machine or shared delivery rules.
