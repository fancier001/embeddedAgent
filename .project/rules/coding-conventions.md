# Embedded C Project Conventions

> 中文：本文档采用固定双语结构。更新中文或英文内容时，必须同步更新另一部分，保持两部分语义一致。
>
> English: This document uses a fixed bilingual structure. When either the Chinese or English content is updated, the other section must be updated as well to keep both sections semantically aligned.

## 中文 / Chinese

### 适用范围

本规则适用于 `project.yml` 中 `embedded-c-conventions` 所匹配的 C、头文件和 CMake 入口。目标项目可在安装时替换本节内容和 glob，但应保留清单引用。

### 当前项目规范

- 公共接口放在 `examples/minimal-firmware/include/`，实现放在 `src/`，host/fake 测试放在 `tests/`；不要在这些目录之外复制第二套接口。
- 保持现有 CMake target、命名、错误返回和 fake HAL 结构。新增行为必须有直接测试，修复回归必须先证明测试能覆盖原失败路径。
- 头文件使用 include guard，公共声明只暴露必需类型；资源所有权、回调上下文和并发边界必须可从接口或相邻文档验证。
- 不把格式化、无关重命名或批量重构混入功能提交。`fixtures/defects/` 是缺陷样例，不得把其中代码当作生产实现复制。
- 不臆造硬件数值或工具链结果。涉及寄存器、时序、ISR、原子性和内存顺序时，遵循项目 HAL 与匹配 revision 的证据。

## English

### Applicability

This rule applies to C, header, and CMake entry-point paths matched by `embedded-c-conventions` in `project.yml`. A target project may replace this content and the globs during installation, but should preserve the manifest reference.

### Current Project Conventions

- Put public interfaces in `examples/minimal-firmware/include/`, implementations in `src/`, and host/fake tests in `tests/`; do not duplicate a second interface set elsewhere.
- Preserve existing CMake targets, naming, error returns, and fake-HAL structure. New behavior needs direct tests, and a regression fix must first show that its test covers the original failing path.
- Use include guards and expose only required types in public declarations. Resource ownership, callback context, and concurrency boundaries must be verifiable from the interface or adjacent documentation.
- Do not mix formatting, unrelated renaming, or broad refactoring into a functional commit. `fixtures/defects/` contains defect examples and is not production implementation material.
- Never invent hardware values or toolchain results. For registers, timing, ISRs, atomicity, and memory ordering, follow the project HAL and evidence matching the exact revision.
