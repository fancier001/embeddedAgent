---
name: misra-risk-review
description: "对嵌入式 C 的当前改动或指定文件执行高信噪比 MISRA 风险筛查，结合项目标准、编译配置、deviation 和工具证据输出可定位发现；当用户要求 MISRA、C 安全、可移植性或静态分析评审时使用。 / Perform a high-signal MISRA risk screening of embedded C changes or selected files using the project's standard, compiler configuration, deviations, and tool evidence; use for MISRA, C safety, portability, or static-analysis reviews."
user-invocable: false
---

# MISRA Risk Review

> 中文：本文档采用固定双语结构。更新中文或英文内容时，必须同步更新另一部分，保持两部分语义一致。
>
> English: This document uses a fixed bilingual structure. When either the Chinese or English content is updated, the other section must be updated as well to keep both sections semantically aligned.

## 中文 / Chinese

### 输入与定位

- 接收 `review_target`；未指定时评审当前 Git 改动。没有 Git、无法确定范围或证据不足以支持评审结论时返回 `INSUFFICIENT_EVIDENCE`，列出缺口并要求明确目标或补充证据。仅在缺少必须的用户决策、权限或执行条件，导致工作本身无法继续时使用 `BLOCKED`。
- 使用 `QualityReviewer` 的 `misra-risk-review` 模式，先读取 `.github/agent-contracts.md`、`.github/embedded-project.yml`、实际编译参数、相关头文件和调用关系。
- 默认定位为风险筛查，不宣称 MISRA 合规、认证或完整覆盖。

### 工作流

1. **锁定基线**：确认 MISRA 版本、C 标准、编译器/目标架构、预处理宏、生成/vendor 排除项、deviation 文件和可用静态分析报告。
2. **读取真实改动**：检查 diff 及必要上下文，关注正确性、安全性、未定义/实现定义行为、essential type、控制流、指针与数组、对象生命周期、并发/ISR、资源和可移植性。
3. **使用证据**：仅运行 Git 只读命令、不会改写源码的编译/测试诊断或已配置静态分析。不得运行 formatter、codegen 或带修复选项的工具。
4. **核对偏离**：将工具发现与已批准 deviation 对照；记录适用条件，不能因存在 deviation 文件就自动豁免。
5. **形成发现**：只报告可执行且有证据的问题。每条包含 severity、`file:line`、evidence、rationale、recommendation 和 confidence，并区分 Spec 与 Standards 维度。
6. **谨慎引用规则**：仅在项目配置、授权标准文本或实际工具报告提供可靠依据时写具体 MISRA 规则号；否则描述候选风险类别，不猜测规则号。
7. **给出结论**：存在会导致错误行为、安全风险或验收失败的问题时使用 `FAILED`；剩余风险仅在用户明确接受后才可使用 `CONDITIONAL`；证据缺失时使用 `INSUFFICIENT_EVIDENCE`。

### SARIF 归一化

对 SARIF 2.1.0 报告使用 [`scripts/normalize_sarif.py`](scripts/normalize_sarif.py) 和参数 `--input <report.sarif>`。只保留工具提供的 rule ID、级别、位置、消息和 fingerprint，并转换为共享 Finding 形状；缺少 rule ID 时标记 `UNCLASSIFIED`，不得猜测 MISRA 规则或宣称合规。

### 输出

按 `BLOCKER`、`MAJOR`、`MINOR` 分组；无发现时明确写“未发现问题”，但同时列出范围和未覆盖项。报告 `Status`、`Scope`、`Configuration`、`Findings`、`Commands and Exit Codes`、`Coverage Gaps`、`Assumptions` 和 `Next Steps`。

## English

### Input and positioning

- Accept `review_target`; review the current Git changes when it is omitted. Return `INSUFFICIENT_EVIDENCE`, list the gaps, and request an explicit target or more evidence when Git is unavailable, scope cannot be determined, or the evidence cannot support a review conclusion. Reserve `BLOCKED` for a genuinely halted workflow, such as a missing required user decision, permission, or execution prerequisite.
- Use the `QualityReviewer` `misra-risk-review` mode. First read `.github/agent-contracts.md`, `.github/embedded-project.yml`, actual compiler flags, relevant headers, and call relationships.
- Treat the result as a risk screening by default; never claim MISRA compliance, certification, or complete coverage.

### Workflow

1. **Lock the baseline**: Identify the MISRA edition, C standard, compiler/target architecture, preprocessing macros, generated/vendor exclusions, deviation file, and available static-analysis reports.
2. **Read the real change**: Inspect the diff and required context. Focus on correctness, safety, undefined or implementation-defined behavior, essential types, control flow, pointers and arrays, object lifetime, concurrency/ISR behavior, resources, and portability.
3. **Use evidence**: Run only read-only Git commands, non-rewriting build/test diagnostics, or configured static analysis. Do not run formatters, code generation, or tools with fix options.
4. **Check deviations**: Compare tool findings with approved deviations and record their applicability conditions. The mere presence of a deviation file does not waive a finding.
5. **Create findings**: Report only actionable, evidenced issues. Include severity, `file:line`, evidence, rationale, recommendation, and confidence for each finding, and distinguish the Spec and Standards dimensions.
6. **Cite rules cautiously**: Include an exact MISRA rule number only when project configuration, authorized standard text, or an actual tool report supports it. Otherwise describe the candidate risk category without guessing a rule number.
7. **Reach a verdict**: Use `FAILED` for issues that can cause incorrect behavior, safety risk, or acceptance failure. Use `CONDITIONAL` only after the user explicitly accepts residual risk. Use `INSUFFICIENT_EVIDENCE` when required evidence is missing.

### SARIF normalization

For SARIF 2.1.0 reports, use [`scripts/normalize_sarif.py`](scripts/normalize_sarif.py) with `--input <report.sarif>`. Preserve only tool-supplied rule IDs, levels, locations, messages, and fingerprints while mapping them to the shared Finding shape. Mark a missing rule ID `UNCLASSIFIED`; never guess a MISRA rule or claim compliance.

### Output

Group findings under `BLOCKER`, `MAJOR`, and `MINOR`. When none are found, say so explicitly while listing the reviewed scope and coverage gaps. Report `Status`, `Scope`, `Configuration`, `Findings`, `Commands and Exit Codes`, `Coverage Gaps`, `Assumptions`, and `Next Steps`.
