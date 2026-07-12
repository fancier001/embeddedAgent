---
name: First-Party Bilingual Markdown
applyTo: "README.md,docs/**/*.md,.github/**/*.md"
description: 团队维护 Markdown 的完整中英双区规范 / Complete Chinese-English sections for team-maintained Markdown
---

# First-Party Bilingual Markdown Rules

> 中文：本文档采用固定双语结构。更新中文或英文内容时，必须同步更新另一部分，保持两部分语义一致。
>
> English: This document uses a fixed bilingual structure. When either the Chinese or English content is updated, the other section must be updated as well to keep both sections semantically aligned.

## 中文 / Chinese

### 范围

- 本规则适用于 README、`docs/` 和 `.github/` 中由团队维护的 Markdown。
- vendor、generated、第三方文档、许可证原文和外部同步的 changelog 不自动双语化。
- Copilot 配置和 Skill 文件必须保留合法 YAML frontmatter。

### 固定结构

```md
# <Document Title>

> 中文：本文档采用固定双语结构。更新中文或英文内容时，必须同步更新另一部分，保持两部分语义一致。
>
> English: This document uses a fixed bilingual structure. When either the Chinese or English content is updated, the other section must be updated as well to keep both sections semantically aligned.

## 中文 / Chinese

<完整中文内容>

## English

<Complete English content>
```

### 规则

- 两个语言区分别完整、语义一致，不要求逐句直译。
- 标题后的双语约束说明块不可省略。
- 更新任一语言区时同步更新另一语言区；发布门禁不接受未归属的 `TODO(sync)`。
- YAML、代码、命令、路径、标识符、日志、寄存器名和链接保持原文，两边正文分别解释。
- 链接使用相对路径指向仓库文件，并在交付前检查目标存在。
- Agent/Prompt/Instructions/Skill 正文也遵循双区结构，但共享规则通过链接复用，不在每个角色中复制。

## English

### Scope

- This rule applies to team-maintained Markdown in the README, `docs/`, and `.github/`.
- Vendor, generated, third-party documentation, license text, and externally synchronized changelogs are not automatically bilingualized.
- Copilot configuration and Skill files must preserve valid YAML frontmatter.

### Fixed Structure

```md
# <Document Title>

> 中文：本文档采用固定双语结构。更新中文或英文内容时，必须同步更新另一部分，保持两部分语义一致。
>
> English: This document uses a fixed bilingual structure. When either the Chinese or English content is updated, the other section must be updated as well to keep both sections semantically aligned.

## 中文 / Chinese

<完整中文内容>

## English

<Complete English content>
```

### Rules

- Each language section is complete and semantically aligned; sentence-by-sentence translation is not required.
- Do not omit the bilingual maintenance notice after the title.
- Update both language sections together. The release gate does not accept an unowned `TODO(sync)`.
- Keep YAML, code, commands, paths, identifiers, logs, register names, and links unchanged, and explain them separately in each prose section.
- Use relative links for repository files and verify that every target exists before delivery.
- Agent, Prompt, Instructions, and Skill bodies also follow the two-section structure, while shared rules are reused through links instead of copied into every role.
