# Embedded Product Forms

> 中文：本文档采用固定双语结构。更新中文或英文内容时，必须同步更新另一部分，保持两部分语义一致。
>
> English: This document uses a fixed bilingual structure. When either the Chinese or English content is updated, the other section must be updated as well to keep both sections semantically aligned.

## 中文 / Chinese

### 用途

`.github/embedded-project.yml` 用同一套五 Agent 适配不同嵌入式产品。画像保存经过团队确认的项目事实；Agent 指令保存工作方法，两者不要混写。

字段为 `auto` 时，Agent 从 README、CI、构建文件、VS Code tasks、相邻模块和测试中探测。如果画像与仓库冲突，Agent 报告配置漂移，不静默选择其中一个。

`paths.application`、`paths.services`、`paths.middleware` 和 `paths.protocols` 用于定位应用逻辑。它们是向后兼容的可选字段，缺失时等同 `auto`。驱动与应用路径可以重叠，但 Agent 必须按真实职责和调用关系判断层次。

### `bare-metal`

适用于无操作系统 MCU 固件。主要检查：

- 启动、链接脚本、向量表和初始化顺序。
- MMIO 访问宽度、`volatile`、屏障和寄存器副作用。
- ISR 延迟、共享数据原子性、临界区和看门狗。
- 静态内存、栈深度、时序预算和低功耗状态。

### `rtos`

适用于 FreeRTOS、ThreadX、Zephyr 或同类系统。除 bare-metal 风险外，主要检查：

- task 与 ISR 可调用 API 的边界。
- 优先级、优先级反转、锁顺序和死锁。
- 队列/信号量容量、超时、取消和关闭顺序。
- heap 策略、对象生命周期、栈水位和调度时序。

### `module-sdk`

适用于通信模组 SDK、AT/URC 框架和事件驱动产品。主要检查：

- 命令、响应和 URC 的关联及乱序处理。
- 网络注册、连接、重连、休眠和关机状态机。
- 回调重入、异步生命周期、缓冲区所有权和超时。
- 公共 API、错误码、日志格式和版本向后兼容。

### `embedded-linux`

适用于 Linux 用户态守护进程、工具和设备服务。主要检查：

- POSIX 返回值、`errno`、线程/进程和信号处理。
- 文件描述符、socket、共享内存和子进程回收。
- 交叉编译、sysroot、ABI 和部署目录。
- 权限、服务生命周期、日志和资源清理。

### `hybrid`

适用于 MCU 与 Linux/模组协作或多核异构产品。画像应明确每个路径属于哪个执行环境；Agent 分别应用对应规则，并额外检查协议版本、重启恢复、跨域超时和升级兼容。

### 命令安全分类

- `commands.configure`、`commands.build`、`commands.test` 和 `commands.static_analysis`：主机侧配置、构建、测试和静态分析入口；允许的写入应限于相应构建或报告产物。
- `commands.hardware.flash`、`commands.hardware.erase`、`commands.hardware.fuse`、`commands.hardware.reset` 和 `commands.hardware.hil`：独立的硬件操作入口。每项都包含 `command`、`enabled` 和 `requires_explicit_approval`；默认 `enabled: false`，且执行前必须获得明确授权。
- 当前画像不定义设备电源、发布或外部部署命令字段，不得把它们映射到不存在的键或从其他字段推断授权。此类操作仍须由项目既有流程管理，并在本 Kit 中视为未经明确授权不得执行。
- 命令存在不代表已授权。VS Code approvals 和宿主 sandbox 才是技术执行边界。

## English

### Purpose

`.github/embedded-project.yml` adapts the same five agents to different embedded products. The profile stores team-confirmed project facts; agent instructions store working methods. Do not mix the two.

When a field is `auto`, agents discover it from the README, CI, build files, VS Code tasks, neighboring modules, and tests. If the profile conflicts with the repository, agents report configuration drift instead of silently choosing one side.

`paths.application`, `paths.services`, `paths.middleware`, and `paths.protocols` locate application logic. They are backward-compatible optional fields; absence is equivalent to `auto`. Driver and application paths may overlap, but agents determine the layer from actual responsibilities and call relationships.

### `bare-metal`

Use for MCU firmware without an operating system. Primary review areas are:

- Startup, linker scripts, vector tables, and initialization order.
- MMIO access width, `volatile`, barriers, and register side effects.
- ISR latency, shared-data atomicity, critical sections, and watchdog behavior.
- Static memory, stack depth, timing budgets, and low-power states.

### `rtos`

Use for FreeRTOS, ThreadX, Zephyr, or similar systems. In addition to bare-metal risks, review:

- API boundaries between tasks and ISRs.
- Priorities, priority inversion, lock ordering, and deadlocks.
- Queue/semaphore capacity, timeouts, cancellation, and shutdown order.
- Heap strategy, object lifetime, stack watermarks, and scheduling timing.

### `module-sdk`

Use for communication-module SDKs, AT/URC frameworks, and event-driven products. Review:

- Command, response, and URC correlation, including out-of-order events.
- Network registration, connection, reconnection, sleep, and shutdown state machines.
- Callback reentrancy, asynchronous lifetime, buffer ownership, and timeouts.
- Public APIs, error codes, log formats, and backward compatibility.

### `embedded-linux`

Use for Linux user-space daemons, tools, and device services. Review:

- POSIX return values, `errno`, threads/processes, and signal handling.
- File descriptors, sockets, shared memory, and child-process reaping.
- Cross-compilation, sysroots, ABI, and deployment paths.
- Permissions, service lifecycle, logging, and resource cleanup.

### `hybrid`

Use for MCU plus Linux/module products or heterogeneous multi-core systems. The profile identifies which execution environment owns each path. Agents apply the corresponding rules and additionally review protocol versions, restart recovery, cross-domain timeouts, and upgrade compatibility.

### Command Safety Classes

- `commands.configure`, `commands.build`, `commands.test`, and `commands.static_analysis`: host-side configuration, build, test, and static-analysis entry points; allowed writes should remain in the corresponding build or report artifacts.
- `commands.hardware.flash`, `commands.hardware.erase`, `commands.hardware.fuse`, `commands.hardware.reset`, and `commands.hardware.hil`: isolated hardware-operation entries. Each contains `command`, `enabled`, and `requires_explicit_approval`; `enabled` defaults to `false`, and execution requires explicit authorization.
- The current profile defines no device-power, release, or external-deployment command fields. Do not map those operations to nonexistent keys or infer their authorization from another field. Existing project procedures must govern them, and this kit treats them as forbidden without explicit authorization.
- The presence of a command is not authorization. VS Code approvals and the host sandbox form the technical execution boundary.
