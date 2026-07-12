---
name: Embedded C Rules
applyTo: "**/*.c,**/*.h"
description: 现有工程优先的嵌入式 C 安全与可移植性规则 / Existing-project-first Embedded C safety and portability rules
---

# Embedded C Rules

> 中文：本文档采用固定双语结构。更新中文或英文内容时，必须同步更新另一部分，保持两部分语义一致。
>
> English: This document uses a fixed bilingual structure. When either the Chinese or English content is updated, the other section must be updated as well to keep both sections semantically aligned.

## 中文 / Chinese

### 适用顺序

1. 先读取项目画像、相邻模块和仓库已有格式化/静态分析配置。
2. 已有工程规则优先；以下默认只用于仓库没有对应约定的新代码。
3. vendor、generated 和第三方代码不进行风格重写。

### 回退编码规则

- 使用项目选定的 C 标准；画像为 `auto` 且工程没有证据时，空白工程回退到 C99。
- 默认使用 4 空格、K&R 大括号和一行一条语句。
- 协议字段和寄存器字段使用 `<stdint.h>` 定长类型；不要用裸 `int` 表达宽度相关数据。
- 文件私有函数和对象使用 `static`，公共接口提供原型和简洁 Doxygen 契约。
- 数值常量表达语义和单位；优先复用项目常量体系，不强制迁移到某个固定 `config.h`。
- 可失败操作沿用现有错误模型，调用方必须处理或明确传播错误。

### 内存、MMIO 与并发

- 通过现有 HAL/CMSIS/vendor 头访问 MMIO；不要重新声明已有寄存器。
- 对实际 MMIO 对象使用项目要求的 `volatile` 限定，但另行检查访问宽度、原子性、屏障和临界区。
- ISR 与任务/主循环共享数据时，分别分析编译器可见性、原子访问、内存顺序和同步协议。
- 禁止未检查的缓冲区长度、整数溢出、除零、悬空指针、越界指针和未对齐访问。
- 默认避免动态分配和递归；若项目已有受控 allocator 或 RTOS heap，遵循其预算、失败和生命周期规则。
- 显式处理字节序、对齐和序列化；不要直接把 packed 数据强转成普通结构体指针。

### 产品形态关注点

- bare-metal：启动、MMIO、ISR、时序、栈深度和看门狗。
- RTOS：任务/ISR API 边界、优先级、锁顺序、队列容量和超时。
- module SDK：状态机、命令/URC 配对、网络生命周期和向后兼容。
- Embedded Linux：POSIX 错误、线程/进程、文件描述符、信号和资源回收。

应用层状态机必须集中表达合法转换和忽略策略；超时、重试、重复/乱序事件与用户取消路径需要可注入依赖和 host tests。

## English

### Precedence

1. Read the project profile, neighboring modules, and existing formatter/static-analysis configuration first.
2. Existing project rules take precedence. The defaults below apply only when the repository has no corresponding convention.
3. Do not restyle vendor, generated, or third-party code.

### Fallback Coding Rules

- Use the C standard selected by the project. If the profile is `auto` and no repository evidence exists, a greenfield project falls back to C99.
- Default to four-space indentation, K&R braces, and one statement per line.
- Use fixed-width `<stdint.h>` types for protocol and register fields; do not use bare `int` for width-sensitive data.
- Mark file-private functions and objects `static`, and give public interfaces concise Doxygen contracts.
- Give numeric constants semantic names and units. Reuse the project's constant system instead of forcing a migration to a fixed `config.h`.
- Follow the existing error model for fallible operations. Callers must handle or explicitly propagate errors.

### Memory, MMIO, and Concurrency

- Access MMIO through existing HAL, CMSIS, or vendor headers; do not redeclare existing registers.
- Apply the project's required `volatile` qualification to actual MMIO objects, while separately checking access width, atomicity, barriers, and critical sections.
- For data shared between ISRs and tasks or the main loop, analyze compiler visibility, atomic access, memory ordering, and the synchronization protocol separately.
- Prevent unchecked buffer lengths, integer overflow, division by zero, dangling pointers, out-of-bounds pointers, and unaligned access.
- Avoid dynamic allocation and recursion by default. If the project has a controlled allocator or RTOS heap, follow its budget, failure, and lifetime rules.
- Handle endianness, alignment, and serialization explicitly. Do not cast packed data directly to an ordinary struct pointer.

### Product-Form Focus

- Bare metal: startup, MMIO, ISRs, timing, stack depth, and watchdog behavior.
- RTOS: task/ISR API boundaries, priorities, lock ordering, queue capacity, and timeouts.
- Module SDK: state machines, command/URC pairing, network lifecycle, and backward compatibility.
- Embedded Linux: POSIX errors, threads/processes, file descriptors, signals, and resource cleanup.

Application state machines must express legal transitions and ignored-event policy centrally. Timeouts, retries, duplicate/out-of-order events, and user cancellation require injectable dependencies and host tests.
