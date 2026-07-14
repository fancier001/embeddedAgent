---
name: analyze-bug
description: 理解错误、验证根因假设并输出证据化 Bug 分析 / Understand errors, test root-cause hypotheses, and report evidence-backed bug analysis
agent: BugResolver
argument-hint: Bug 描述、原始错误、复现步骤、相关文件或日志 / Bug description, original error, reproduction, related files, or logs
---

# Analyze Bug

> 中文：本文档采用固定双语结构。更新中文或英文内容时，必须同步更新另一部分，保持两部分语义一致。
>
> English: This document uses a fixed bilingual structure. When either the Chinese or English content is updated, the other section must be updated as well to keep both sections semantically aligned.

## 中文 / Chinese

使用 `BugResolver` 系统提示词中的 `bug-analysis` 模式和 `.github/agent-contracts.md` 的 Bug Analysis 输出契约处理以下输入：

- `bug_input`: `${input:bug_input}`

输入为空时先请求 Bug 现象或原始错误。默认只读分析：保留原始错误，先输出共享 `Problem Identification`，再核对预期/实际行为、环境、revision、复现和 baseline；使用 `search → read → execute` 的证据流程追踪上下文、建立假设并运行最小安全验证。存在 crash、dump、ELF/MAP 或运行日志时同时启用 `fault-analysis` 辅助模式。关键资料缺失时，先搜索仓库并完成安全初判，再用一张共享 `Evidence Request` 表集中询问并暂停根因确认；不得重复索取、调用 Developer 或把最高概率假设写成已确认根因。

## English

Use the `bug-analysis` mode in the `BugResolver` system prompt and the Bug Analysis output contract in `.github/agent-contracts.md` for this input:

- `bug_input`: `${input:bug_input}`

If input is empty, request the bug symptom or original error first. Analysis is read-only by default: preserve the original error, emit the shared Problem Identification first, establish expected/actual behavior, environment, revision, reproduction, and baseline, then use the `search → read → execute` evidence flow to trace context, form hypotheses, and run the smallest safe validation. Add `fault-analysis` for crash, dump, ELF/MAP, or runtime-log evidence. When critical material is missing, search the repository and finish safe preliminary analysis before asking once through the shared Evidence Request table, then pause root-cause confirmation. Never request the same evidence again, invoke Developer, or present the most likely hypothesis as confirmed while the causal chain is incomplete.
