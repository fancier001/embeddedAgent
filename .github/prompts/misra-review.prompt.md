---
name: misra-review
description: 对当前改动或指定目标执行 MISRA 风险筛查 / Screen current changes or a selected target for MISRA risks
agent: QualityReviewer
argument-hint: 文件、目录或提交；留空评审当前 Git 改动 / File, directory, or commit; leave empty for current Git changes
---

# MISRA Risk Review

> 中文：本文档采用固定双语结构。更新中文或英文内容时，必须同步更新另一部分，保持两部分语义一致。
>
> English: This document uses a fixed bilingual structure. When either the Chinese or English content is updated, the other section must be updated as well to keep both sections semantically aligned.

## 中文 / Chinese

使用 [misra-risk-review](../skills/misra-risk-review/SKILL.md) 工作流处理以下输入：

- `review_target`: `${input:review_target}`

输入为空时评审当前 Git 改动；若无法确定改动范围，则请求明确目标。Prompt 仅负责输入与路由；执行 Skill、项目画像和共享契约定义的完整流程。

## English

Use the [misra-risk-review](../skills/misra-risk-review/SKILL.md) workflow with this input:

- `review_target`: `${input:review_target}`

When the input is empty, review the current Git changes; request an explicit target if that scope cannot be determined. This prompt only adapts input and routing; execute the complete workflow defined by the Skill, project profile, and shared contract.
