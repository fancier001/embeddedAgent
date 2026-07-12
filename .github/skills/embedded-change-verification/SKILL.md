---
name: embedded-change-verification
description: "对嵌入式工程改动执行端到端验收，编排基线、构建、测试、静态分析、独立评审、有限返工与文档门禁；当用户要求验证当前改动、发布前检查或完整质量闭环时使用。 / Run end-to-end acceptance for embedded changes by orchestrating baseline comparison, build, tests, static analysis, independent review, bounded rework, and documentation gates; use for change verification, pre-release checks, or a complete quality loop."
user-invocable: false
---

# Embedded Change Verification

> 中文：本文档采用固定双语结构。更新中文或英文内容时，必须同步更新另一部分，保持两部分语义一致。
>
> English: This document uses a fixed bilingual structure. When either the Chinese or English content is updated, the other section must be updated as well to keep both sections semantically aligned.

## 中文 / Chinese

### 输入与范围

- 接收 `change_target` 和完整 `Task Brief`；目标可以是当前 diff、提交、文件集合或用户定义的功能范围。
- 由 `Orchestrator` 读取 `.github/agent-contracts.md` 与 `.github/embedded-project.yml`，明确验收条件、禁止动作和本轮是否允许修复。
- 未明确授权修复时只做验证和评审，不修改功能代码。

### 工作流

1. **预检**：确认目标范围、产品形态、基线、构建变体、工具链、测试层级、硬件依赖和文档要求。范围不可确定时返回 `BLOCKED`。
2. **建立基线**：让 `EmbeddedDeveloper` 运行项目已有的安全 configure/build/test 命令并记录退出码；将既有失败与目标改动导致的回归分开。
3. **执行门禁**：按项目画像运行适用的配置、编译、单元/host 测试、集成测试和静态分析。需要真实设备、flash 或 HIL 的步骤在无明确授权时标记 `NOT_RUN`。
4. **独立审计**：让 `QualityReviewer` 使用 `verification-audit` 模式核对真实 diff、需求覆盖、验证命令、测试有效性以及产品形态特有风险，不采信无证据的自评结论。
5. **有限返工**：仅在 `Task Brief` 授权修复时，将有证据的 `BLOCKER`/`MAJOR` 交回 `EmbeddedDeveloper`；每轮修复后重新运行受影响门禁并复评，最多两轮。
6. **文档门禁**：公共 API、架构、硬件假设、操作步骤或已确认根因发生变化时调用 `DocKeeper`，并检查中英语义、链接和未解决的双语同步标记。
7. **收口**：汇总每个门禁的 `PASS`、`FAIL`、`BLOCKED` 或 `NOT_RUN`。任何必需门禁非 `PASS` 时不得给出 `COMPLETE`。

### 确定性工具

- 使用 [`scripts/profile_gates.py`](scripts/profile_gates.py) 的 `plan --profile .github/embedded-project.yml` 生成 host 门禁计划。脚本只读取配置，明确排除 hardware，不执行命令。
- Agent 逐条运行获准命令并记录证据后，使用 `validate-report --profile <profile> --input <report.json>` 验证命令、退出码、证据和状态。退出码 `3` 表示证据不足。

### 产品形态检查

- bare-metal：MMIO、ISR、原子性、时序、栈和启动流程。
- RTOS：任务/ISR 边界、优先级、同步、死锁和堆使用。
- module-sdk：API/URC、状态机、网络生命周期、日志和兼容性。
- embedded-linux：POSIX、线程/进程、交叉编译、系统接口和资源回收。
- hybrid：组合适用项，并明确不同运行域之间的接口与验证边界。

### 输出

输出质量门表以及共享报告字段：`Status`、`Summary`、`Scope`、`Files/APIs`、`Commands and Exit Codes`、`Evidence`、`Review Findings`、`Assumptions`、`Risks` 和 `Next Steps`。两轮后仍有重大问题时使用 `FAILED`。

## English

### Input and scope

- Accept `change_target` and a complete `Task Brief`. The target may be the current diff, a commit, a file set, or a user-defined feature scope.
- Have `Orchestrator` read `.github/agent-contracts.md` and `.github/embedded-project.yml`, then define acceptance criteria, forbidden actions, and whether fixes are authorized in this run.
- When fix authorization is absent, verify and review only; do not change functional code.

### Workflow

1. **Preflight**: Identify target scope, product form, baseline, build variants, toolchain, test levels, hardware dependencies, and documentation requirements. Return `BLOCKED` when the scope cannot be established.
2. **Establish the baseline**: Have `EmbeddedDeveloper` run the project's existing safe configure/build/test commands and record exit codes. Separate pre-existing failures from regressions caused by the target change.
3. **Run gates**: Execute applicable configure, compile, unit/host test, integration test, and static-analysis gates from the project profile. Mark real-device, flash, or HIL steps `NOT_RUN` unless explicitly authorized.
4. **Audit independently**: Have `QualityReviewer` use `verification-audit` mode to inspect the real diff, requirement coverage, verification commands, test effectiveness, and product-form-specific risks. Reject unsupported self-assessment.
5. **Bound rework**: Only when the `Task Brief` authorizes fixes, return evidenced `BLOCKER`/`MAJOR` findings to `EmbeddedDeveloper`. Rerun affected gates and review after each fix, for at most two rounds.
6. **Gate documentation**: Invoke `DocKeeper` when public APIs, architecture, hardware assumptions, operating steps, or a confirmed root cause changes. Check Chinese/English parity, links, and unresolved bilingual-sync markers.
7. **Close**: Summarize every gate as `PASS`, `FAIL`, `BLOCKED`, or `NOT_RUN`. Never return `COMPLETE` when a required gate is not `PASS`.

### Deterministic tool

- Use [`scripts/profile_gates.py`](scripts/profile_gates.py) with `plan --profile .github/embedded-project.yml` to produce the host-gate plan. It reads configuration only, explicitly excludes hardware, and executes no commands.
- After the agent runs each approved command and records evidence, run `validate-report --profile <profile> --input <report.json>` to validate commands, exit codes, evidence, and states. Exit code `3` means insufficient evidence.

### Product-form checks

- bare-metal: MMIO, ISR behavior, atomicity, timing, stack, and startup flow.
- RTOS: task/ISR boundaries, priorities, synchronization, deadlocks, and heap use.
- module-sdk: API/URC behavior, state machines, network lifecycle, logging, and compatibility.
- embedded-linux: POSIX behavior, threads/processes, cross-compilation, system interfaces, and resource cleanup.
- hybrid: combine applicable checks and state the interfaces and verification boundaries between execution domains.

### Output

Provide a quality-gate table plus the shared report fields: `Status`, `Summary`, `Scope`, `Files/APIs`, `Commands and Exit Codes`, `Evidence`, `Review Findings`, `Assumptions`, `Risks`, and `Next Steps`. Use `FAILED` when major issues remain after two rounds.
