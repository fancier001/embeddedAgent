---
name: new-driver
description: Create or change an embedded peripheral driver / 新增或修改嵌入式外设驱动
agent: Orchestrator
argument-hint: 描述外设、接口、硬件 revision 与验收条件 / Describe the peripheral, interface, hardware revision, and acceptance criteria
---

# New Driver

> 中文：本文档采用固定双语结构。更新中文或英文内容时，必须同步更新另一部分，保持两部分语义一致。
>
> English: This document uses a fixed bilingual structure. When either the Chinese or English content is updated, the other section must be updated as well to keep both sections semantically aligned.

## 中文 / Chinese

使用 [embedded-driver-development](../skills/embedded-driver-development/SKILL.md) 工作流处理以下输入：

- `driver_request`: `${input:driver_request}`

若输入为空或缺少会影响硬件实现的关键信息，先向用户补充确认。Prompt 仅负责输入与路由；执行 Skill、项目画像和共享契约定义的完整流程。

## English

Use the [embedded-driver-development](../skills/embedded-driver-development/SKILL.md) workflow with this input:

- `driver_request`: `${input:driver_request}`

If the input is empty or lacks information that materially affects the hardware implementation, ask the user to supply it first. This prompt only adapts input and routing; execute the complete workflow defined by the Skill, project profile, and shared contract.
