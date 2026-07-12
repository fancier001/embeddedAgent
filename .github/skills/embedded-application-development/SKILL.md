---
name: embedded-application-development
description: "规划、实现并验证嵌入式应用逻辑、服务、协议流程和状态机，覆盖事件、超时、重试、幂等、恢复、并发与需求追踪；当用户要求开发 bare-metal、RTOS、模组 SDK、Embedded Linux 或 hybrid 的非驱动功能时使用。 / Plan, implement, and verify embedded application logic, services, protocol flows, and state machines across events, timeouts, retries, idempotency, recovery, concurrency, and traceability; use for non-driver features in bare-metal, RTOS, module SDK, Embedded Linux, or hybrid products."
user-invocable: false
---

# Embedded Application Development

> 中文：本文档采用固定双语结构。更新中文或英文内容时，必须同步更新另一部分，保持两部分语义一致。
>
> English: This document uses a fixed bilingual structure. When either the Chinese or English content is updated, the other section must be updated as well to keep both sections semantically aligned.

## 中文 / Chinese

### 输入与路由

- 接收 `feature_request`，先读取 `.github/agent-contracts.md` 与 `.github/embedded-project.yml`。
- 由 Orchestrator 把请求分类为 `application-feature`，明确参与者、输入/输出、前置条件、状态、事件、时间、错误恢复、兼容性和验收条件。
- 驱动或硬件寄存器工作仍使用 `embedded-driver-development`；应用功能可调用既有 HAL/服务，但不得虚构硬件事实。

### 工作流

1. **发现架构**：检查 application/services/middleware/protocols 路径、任务或 event loop、消息/队列、存储、网络接口、错误码与相邻测试。
2. **定义行为契约**：列出状态与合法转换、重复/乱序事件、超时、重试、取消、幂等、恢复、资源所有权和并发边界。
3. **建立基线**：在修改前运行相关安全构建和测试，区分既有失败与新增回归。
4. **最小实现**：让 EmbeddedDeveloper 完成最小垂直切片，复用现有模块和依赖注入 seam，不进行无关重构。
5. **验证行为**：优先使用 host test、fake clock、fake service 和表驱动状态转换测试，覆盖成功、边界、错误、超时、重复、乱序和停止路径。
6. **独立审计**：让 QualityReviewer 使用 `verification-audit` 核对需求分支、非法转换、并发、资源生命周期和测试有效性。
7. **追踪收口**：维护需求追踪矩阵；使用 [`scripts/validate_traceability.py`](scripts/validate_traceability.py) 和参数 `--input <matrix.yml> --root <repo>` 验证。公共行为或状态机变化时调用 DocKeeper。

### 追踪矩阵接口

固定使用 `schema_version`、`feature` 和 `requirements`。每项需求包含 `id`、`statement_cn`、`statement_en`、`implementation[{path,symbol}]`、`tests[{name,command}]`、`evidence[]` 和 `status`；`status` 只能是 `covered`、`partial`、`missing`、`not-applicable`。

```yaml
schema_version: 1
feature: network-reconnect
requirements:
  - id: APP-001
    statement_cn: 掉线后按退避序列重连
    statement_en: Reconnect with the configured backoff sequence
    implementation: [{path: src/application/reconnect.c, symbol: reconnect_handle}]
    tests: [{name: reconnect-backoff, command: ctest -R reconnect-backoff}]
    evidence: [build/test report path]
    status: covered
```

### 产品形态

- `bare-metal`：super-loop/事件状态机、单步执行上界、禁止隐式阻塞。
- `rtos`：任务职责、队列容量、优先级、timer、超时、锁顺序和对象所有权。
- `module-sdk`：API/URC 配对、网络生命周期、重复事件、重连和兼容性。
- `embedded-linux`：线程/进程、event loop、socket/FD、信号、服务重启和资源回收。
- `hybrid`：明确运行域、跨域协议版本、超时、重启恢复与升级兼容。

不得用通用脚手架生成应用代码。`covered` 需求必须同时给出实现位置、测试和证据；否则标为 `partial` 或 `missing`。

## English

### Input and routing

- Accept `feature_request`; read `.github/agent-contracts.md` and `.github/embedded-project.yml` first.
- Have Orchestrator classify the request as `application-feature` and define actors, inputs/outputs, preconditions, states, events, timing, recovery, compatibility, and acceptance criteria.
- Keep driver/register work under `embedded-driver-development`. Application code may call existing HAL/services but must not invent hardware facts.

### Workflow

1. **Discover architecture**: Inspect application/services/middleware/protocols paths, tasks or event loops, messaging/queues, storage, network interfaces, error conventions, and neighboring tests.
2. **Define the behavior contract**: Enumerate states and legal transitions, duplicate/out-of-order events, timeouts, retries, cancellation, idempotency, recovery, resource ownership, and concurrency boundaries.
3. **Establish a baseline**: Run relevant safe build/tests before editing and separate pre-existing failures from regressions.
4. **Implement minimally**: Have EmbeddedDeveloper deliver the smallest vertical slice, reuse existing modules and dependency-injection seams, and avoid unrelated refactoring.
5. **Verify behavior**: Prefer host tests, fake clocks, fake services, and table-driven transitions. Cover success, boundaries, errors, timeouts, duplicates, reordering, and stop paths.
6. **Audit independently**: Have QualityReviewer use `verification-audit` to inspect requirement branches, illegal transitions, concurrency, resource lifetime, and test effectiveness.
7. **Close traceability**: Maintain a requirement matrix and run [`scripts/validate_traceability.py`](scripts/validate_traceability.py) with `--input <matrix.yml> --root <repo>`. Invoke DocKeeper when public behavior or state machines change.

### Traceability matrix interface

Use fixed top-level fields `schema_version`, `feature`, and `requirements`. Each requirement contains `id`, `statement_cn`, `statement_en`, `implementation[{path,symbol}]`, `tests[{name,command}]`, `evidence[]`, and `status`; `status` is one of `covered`, `partial`, `missing`, or `not-applicable`.

```yaml
schema_version: 1
feature: network-reconnect
requirements:
  - id: APP-001
    statement_cn: 掉线后按退避序列重连
    statement_en: Reconnect with the configured backoff sequence
    implementation: [{path: src/application/reconnect.c, symbol: reconnect_handle}]
    tests: [{name: reconnect-backoff, command: ctest -R reconnect-backoff}]
    evidence: [build/test report path]
    status: covered
```

### Product forms

- `bare-metal`: super-loop/event state machines, bounded step execution, and no implicit blocking.
- `rtos`: task ownership, queue capacity, priority, timers, timeout behavior, lock order, and object ownership.
- `module-sdk`: API/URC pairing, network lifecycle, duplicate events, reconnection, and compatibility.
- `embedded-linux`: threads/processes, event loops, sockets/FDs, signals, service restart, and cleanup.
- `hybrid`: explicit execution domains, cross-domain protocol versions, timeouts, restart recovery, and upgrade compatibility.

Do not generate application code from a generic scaffold. A `covered` requirement must include implementation locations, tests, and evidence; otherwise classify it as `partial` or `missing`.
