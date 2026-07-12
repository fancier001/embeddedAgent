---
name: verify-change
description: 对嵌入式改动执行完整质量验收 / Run complete quality acceptance for an embedded change
agent: Orchestrator
argument-hint: 当前 diff、提交、文件集合或功能范围 / Current diff, commit, file set, or feature scope
---

# Verify Change

> 中文：本文档采用固定双语结构。更新中文或英文内容时，必须同步更新另一部分，保持两部分语义一致。
>
> English: This document uses a fixed bilingual structure. When either the Chinese or English content is updated, the other section must be updated as well to keep both sections semantically aligned.

## 中文 / Chinese

使用 [embedded-change-verification](../skills/embedded-change-verification/SKILL.md) 工作流处理以下输入：

- `change_target`: `${input:change_target}`

输入为空时以当前 Git 改动为候选范围；若无法确定范围，则先请求明确目标。Prompt 仅负责输入与路由；执行 Skill、项目画像和共享契约定义的完整流程。

## English

Use the [embedded-change-verification](../skills/embedded-change-verification/SKILL.md) workflow with this input:

- `change_target`: `${input:change_target}`

When the input is empty, use the current Git changes as the candidate scope; request an explicit target if that scope cannot be determined. This prompt only adapts input and routing; execute the complete workflow defined by the Skill, project profile, and shared contract.
