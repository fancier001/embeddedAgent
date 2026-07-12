---
name: embedded-driver-development
description: "在嵌入式工程中规划、实现并验证外设驱动，要求使用项目画像、硬件证据、独立评审和安全门禁；当用户请求新增或修改 MCU、RTOS、模组 SDK 或 Embedded Linux 驱动时使用。 / Plan, implement, and verify peripheral drivers with project-profile discovery, hardware evidence, independent review, and safety gates; use for new or changed MCU, RTOS, module SDK, or Embedded Linux drivers."
user-invocable: false
---

# Embedded Driver Development

> 中文：本文档采用固定双语结构。更新中文或英文内容时，必须同步更新另一部分，保持两部分语义一致。
>
> English: This document uses a fixed bilingual structure. When either the Chinese or English content is updated, the other section must be updated as well to keep both sections semantically aligned.

## 中文 / Chinese

### 输入与前置条件

- 接收 `driver_request` 和完整的 `Task Brief`；缺少目标、范围、产品形态或验收条件时，先补齐，不让执行者自行猜测。
- 先读取 `.github/agent-contracts.md` 与 `.github/embedded-project.yml`，再检查同类模块、HAL、错误码、构建入口和工作树状态。
- 将项目画像中的 `auto` 作为“需要探测”，而不是具体配置；画像与仓库事实冲突时报告配置漂移。

### 工作流

1. **预检**：确认产品形态、芯片/板卡 revision、接口、资源、并发上下文、时序以及文档证据。对 bare-metal、RTOS、module-sdk、embedded-linux 使用项目画像定义的关注点。
2. **定义契约**：沿用现有目录、API、命名、C 标准和 HAL。明确成功/失败行为、错误码、初始化与释放顺序、线程/ISR 约束和可测试边界。
3. **建立基线**：让 `EmbeddedDeveloper` 在修改前运行项目已有的安全构建和测试命令，分别记录既有失败与本次引入的失败。
4. **最小实现**：把完整 `Task Brief` 交给 `EmbeddedDeveloper`，要求同时实现必要的 fake HAL 或 host 测试，并避免无关重构。
5. **独立评审**：让 `QualityReviewer` 读取真实 diff、调用关系和验证结果，检查正确性、边界、并发、资源、可移植性以及产品形态特有风险。
6. **闭环**：存在 `BLOCKER` 或 `MAJOR` 时，最多进行两轮 `EmbeddedDeveloper → QualityReviewer` 返工；两轮后仍未解决则返回 `FAILED`。
7. **文档与收口**：仅当公共 API、架构、硬件假设或操作流程变化时调用 `DocKeeper`。根据可复查证据输出最终状态和质量门表。

### 安全门禁

- 不得虚构寄存器地址、位定义、引脚、时钟、时序或电气特性。缺少权威资料时返回 `BLOCKED`，或仅在需求允许时建立不含猜测数值的安全抽象。
- 未获得用户对本次操作的明确授权，不得执行 flash、erase、fuse、reset、HIL 或控制真实设备。
- 不覆盖无关用户改动，不使用破坏性 Git 命令，不静默安装依赖。
- 未运行的验证标记为 `NOT_RUN` 并说明原因；`NOT_RUN` 不计为通过。

### 输出

遵循共享契约，报告 `Status`、`Summary`、`Files/APIs`、`Commands and Exit Codes`、`Evidence`、`Assumptions`、`Risks` 和 `Next Steps`。仅在所有必需门禁有通过证据时使用 `COMPLETE`。

## English

### Inputs and prerequisites

- Accept `driver_request` and a complete `Task Brief`. Resolve missing goals, scope, product form, or acceptance criteria before delegation; do not make the worker guess.
- Read `.github/agent-contracts.md` and `.github/embedded-project.yml` first, then inspect similar modules, the HAL, error codes, build entry points, and worktree state.
- Treat `auto` in the project profile as a discovery instruction, not as a concrete setting. Report configuration drift when the profile conflicts with repository evidence.

### Workflow

1. **Preflight**: Confirm the product form, silicon/board revision, interface, resources, concurrency context, timing, and documentary evidence. Apply the profile-defined focus for bare-metal, RTOS, module-sdk, or embedded-linux products.
2. **Define the contract**: Preserve existing directories, APIs, naming, C standard, and HAL. Define success and failure behavior, error codes, initialization and teardown order, thread/ISR constraints, and test seams.
3. **Establish the baseline**: Have `EmbeddedDeveloper` run the project's existing safe build and test commands before editing. Separate pre-existing failures from regressions introduced by the change.
4. **Implement minimally**: Give `EmbeddedDeveloper` the complete `Task Brief`; require necessary fake-HAL or host tests and prohibit unrelated refactoring.
5. **Review independently**: Have `QualityReviewer` inspect the real diff, call relationships, and verification evidence for correctness, boundaries, concurrency, resources, portability, and product-form-specific risks.
6. **Close the loop**: For any `BLOCKER` or `MAJOR`, run at most two `EmbeddedDeveloper → QualityReviewer` rework rounds. Return `FAILED` if such findings remain after round two.
7. **Document and close**: Invoke `DocKeeper` only when public APIs, architecture, hardware assumptions, or operating procedures change. Base the final status and quality-gate table on reproducible evidence.

### Safety gates

- Never invent register addresses, bit definitions, pins, clocks, timing, or electrical characteristics. Return `BLOCKED` when authoritative material is missing, or create only a value-free safe abstraction when the request permits it.
- Do not run flash, erase, fuse, reset, HIL, or real-device control without the user's explicit authorization for that operation.
- Preserve unrelated user changes, avoid destructive Git commands, and do not install dependencies silently.
- Mark unexecuted verification as `NOT_RUN` with a reason. `NOT_RUN` is not a pass.

### Output

Follow the shared contract and report `Status`, `Summary`, `Files/APIs`, `Commands and Exit Codes`, `Evidence`, `Assumptions`, `Risks`, and `Next Steps`. Use `COMPLETE` only when every required gate has passing evidence.
