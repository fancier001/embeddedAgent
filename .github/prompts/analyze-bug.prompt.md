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

输入为空或缺少会影响方向的使用上下文时，先执行 `GUIDE_SYMPTOMS`：输出共享 `Usage Symptom Profile`，再用一张 `Usage Symptom Questions` 表集中询问尚未回答的高信息量现象，首轮最多 5 个。问题只采集用户目标/场景、操作序列、预期/实际、频率/边界和环境/影响/恢复，允许回答 `Unknown`，不得与 `Evidence Request` 混用或重复提问。现象可能指向多个模块/根因路径、预期/实际不清或输入矛盾时执行 `CONFIRM_DIRECTION`，输出 `Current Understanding` 和 `Possible Directions`；确认前不得深入追踪、确认根因或调用 Developer。方向明确时标记 `NOT_REQUIRED` 并继续。

默认只读分析：保留原始错误，方向为 `CONFIRMED` 或 `NOT_REQUIRED` 后输出引用 Usage Symptom Profile 的共享 `Problem Identification`，再核对环境、revision、复现和 baseline；使用 `search → read → execute` 的证据流程追踪上下文、建立假设并运行最小安全验证。存在 crash、dump、ELF/MAP 或运行日志时同时启用 `fault-analysis` 辅助模式。关键证据缺失时，先搜索仓库并完成安全初判，再用一张共享 `Evidence Request` 表集中索取证据产物并暂停根因确认；不得重复索取、调用 Developer 或把最高概率假设写成已确认根因。

## English

Use the `bug-analysis` mode in the `BugResolver` system prompt and the Bug Analysis output contract in `.github/agent-contracts.md` for this input:

- `bug_input`: `${input:bug_input}`

When input is empty or usage context that could change direction is missing, perform `GUIDE_SYMPTOMS` first: emit the shared Usage Symptom Profile and ask unanswered high-information symptoms through one Usage Symptom Questions table, with at most five questions in the first set. Questions collect only user goal/scenario, operation sequence, expected/actual behavior, frequency/boundaries, and environment/impact/recovery. Allow `Unknown`, never mix these questions with Evidence Request, and do not repeat them. If symptoms could indicate multiple modules/root-cause paths, expected versus actual behavior is unclear, or inputs conflict, perform `CONFIRM_DIRECTION`: emit Current Understanding and Possible Directions. Do not trace deeply, confirm root cause, or invoke Developer before confirmation. Mark clear direction `NOT_REQUIRED` and continue.

Analysis is read-only by default: preserve the original error, and after direction is `CONFIRMED` or `NOT_REQUIRED`, emit the shared Problem Identification grounded in the Usage Symptom Profile, then establish environment, revision, reproduction, and baseline. Use the `search → read → execute` evidence flow to trace context, form hypotheses, and run the smallest safe validation. Add `fault-analysis` for crash, dump, ELF/MAP, or runtime-log evidence. When critical evidence is missing, search the repository and finish safe preliminary analysis before asking once for evidence artifacts through the shared Evidence Request table, then pause root-cause confirmation. Never request the same evidence again, invoke Developer, or present the most likely hypothesis as confirmed while the causal chain is incomplete.
