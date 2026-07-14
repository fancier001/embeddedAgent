# embedded-multi-agent

> 中文：本文档采用固定双语结构。更新中文或英文内容时，必须同步更新另一部分，保持两部分语义一致。
>
> English: This document uses a fixed bilingual structure. When either the Chinese or English content is updated, the other section must be updated as well to keep both sections semantically aligned.

## 中文 / Chinese

### 概述

`embedded-multi-agent` 是一个 VS Code-first、仓库内嵌、无 MCP 依赖的嵌入式 C Agent Kit。它固定提供五个可直接选择的 custom agent，并用浅层 manager 模式完成驱动与应用逻辑的需求、实现、验证、评审和文档闭环：

- `Orchestrator`：默认入口与通用交付编排者。
- `BugResolver`：使用现象引导、Bug 理解、根因验证和修复闭环的专职编排者。
- `EmbeddedDeveloper`：唯一常规功能代码修改者。
- `QualityReviewer`：只负责独立只读质量评估。
- `DocKeeper`：团队文档、项目画像和知识沉淀维护者。

本 Kit 随固件仓库版本化，先遵循目标工程已有事实，再应用模板默认值。它适配 bare-metal、RTOS、通信模组 SDK、Embedded Linux 和混合产品，但不自带板卡烧录权限、MCP、私有工具链或供应商资料。

### 产品设计

五个 agent 对应稳定职责，而重复流程放在 prompt 和按需加载的 skill 中。Agent persona、VS Code approvals 和宿主 sandbox 是三层不同控制：角色说明约束行为，工具列表缩小能力面，审批与 sandbox 才控制真实命令和文件边界。

自动闭环使用 subagent：

```text
User
  ├──▶ Orchestrator ── ordinary work ──▶ EmbeddedDeveloper
  │          ├── quality review ───────▶ QualityReviewer
  │          └── documentation ────────▶ DocKeeper
  │
  └──▶ BugResolver ── diagnosis/root cause
             ├── authorized fix ───────▶ EmbeddedDeveloper
             ├── quality gate ─────────▶ QualityReviewer
             └── docs when needed ─────▶ DocKeeper
```

Handoff 是另一条人工路径：agent 回复结束后显示按钮，由用户确认切换角色；`send: false` 表示不会自动提交。Handoff 不等于 subagent 调用，也不代表下一阶段已经执行。

### 五个 Agent

| Agent | 工具 | 允许写入 | 主要输出 |
| --- | --- | --- | --- |
| `Orchestrator` | `agent`, `read`, `search` | 无 | Task Brief、编排状态、质量门和最终汇总 |
| `BugResolver` | `agent`, `read`, `search`, `execute` | 无 | 使用现象引导、方向确认、问题识别卡、日志时间线、证据化根因、主动索证和修复闭环 |
| `EmbeddedDeveloper` | `edit`, `read`, `search`, `execute` | 任务范围内功能代码、测试和构建配置 | 最小 diff、API、baseline/build/test 证据 |
| `QualityReviewer` | `read`, `search`, `execute` | 无 | 高信噪比质量 findings、MISRA 风险和 verdict |
| `DocKeeper` | `read`, `search`, `edit`, `web` | README、`docs/`、项目画像和授权注释 | 设计、How-to、Reference、ADR、FAQ 和结案记录 |

所有 agent 都可从下拉框直接选择。复杂的通用交付任务优先使用 `Orchestrator`，Bug 分析或解决使用 `BugResolver`；直接专家模式仍遵守 [公共契约](.github/agent-contracts.md)。

### 工作状态与质量门

公共状态为：

- `COMPLETE`：全部必需门禁通过。
- `CONDITIONAL`：用户明确接受剩余风险。
- `BLOCKED`：缺少决策、资料、工具或权限，无法安全推进。
- `FAILED`：验证失败或两轮返工后仍有 BLOCKER/MAJOR。
- `INSUFFICIENT_EVIDENCE`：仅用于评审/Bug/故障分析，表示证据不足。

Orchestrator 的标准交付流程是：

```text
INTAKE → PREFLIGHT → PLAN → IMPLEMENT → VERIFY → REVIEW
                                              │
                          最多两轮 REWORK ◀───┘
                                              │
                         DOCUMENT（按需）→ CLOSE
```

Bug 请求通过 `/analyze-bug`、`/analyze-log`、直接选择或 Orchestrator 的人工 handoff 进入 `BugResolver`，两个 manager 不自动嵌套。诊断路径为 `INTAKE → GUIDE_SYMPTOMS → CONFIRM_DIRECTION（按需）→ SCOPE → NORMALIZE_ERROR → IDENTIFY_PROBLEM → TRACE_CONTEXT → REPRODUCE_BASELINE → EVIDENCE_CHECK → AWAIT_EVIDENCE / HYPOTHESES → VALIDATE_CAUSE → DECIDE`；用户明确授权修复后，再进入 `PLAN_FIX → IMPLEMENT → VERIFY → QUALITY_REVIEW → REWORK → DOCUMENT → CLOSE`。

BugResolver 先用 `Usage Symptom Profile` 理解用户目标、实际操作、预期/实际、频率/边界、环境、影响和恢复；缺少会改变分析方向的现象时，通过一张 `Usage Symptom Questions` 表集中询问，首轮最多 5 个，允许回答 `Unknown`。只有可能指向不同模块/根因路径或输入矛盾时才要求方向确认；确认前不深入追踪或委派 Developer，场景清晰时直接继续。随后用引用该 Profile 的 `Problem Identification` 区分已观察问题、类别、疑似子系统、严重度和证据置信度。

缺少关键证据时，BugResolver 会先搜索仓库并完成不依赖缺失项的安全初判，再通过一张独立的 `Evidence Request` 表集中请求日志、版本、配置或 ELF/MAP/dump 等最小材料；现象问题与证据请求不混用，资料补充前不确认根因、不重复索取，也不调用 Developer。日志分析覆盖 bare-metal、RTOS、模组 SDK、Embedded Linux 与 hybrid，保留原始日志偏移和时钟域；没有可靠时间证据时不伪造统一时间线。

命令证据必须包含实际命令、退出码和关键输出。未执行项标为 `NOT_RUN`，不计为通过。

### 项目画像

[`.github/embedded-project.yml`](.github/embedded-project.yml) 是项目事实入口。安装后先确认：

- `product_form` 与 MCU/SoC、RTOS、工具链、C 标准。
- source/driver/application/services/middleware/protocols/test/docs/vendor/generated 路径；新增应用路径缺失时等同 `auto`。
- 主机侧的 `commands.configure`、`commands.build`、`commands.test`、`commands.static_analysis` 命令。
- 隔离在 `commands.hardware.flash`、`commands.hardware.erase`、`commands.hardware.fuse`、`commands.hardware.reset`、`commands.hardware.hil` 下且默认禁用、必须明确审批的硬件命令。
- ELF、MAP、日志和静态分析报告位置。
- MISRA 版本、deviation 文件和硬件资料 revision。

字段可保留为 `auto`，此时 agent 会从仓库探测。画像与仓库冲突时必须报告配置漂移。产品形态的详细检查面见 [Embedded Product Forms](docs/product-forms.md)。

### 安装

1. 将本 Kit 放到目标固件仓库根目录；必须合并 `.github`，不要覆盖已有配置。
2. 人工合并 `.github/copilot-instructions.md`，保留目标工程原有规则。
3. 调整 `.github/embedded-project.yml`；未知值保持 `auto`，不要填写未经确认的硬件事实。
4. 用 VS Code 直接打开固件仓库根目录并信任工作区。若只打开父目录，VS Code 不会自动发现该 `.github`。
5. 启用 GitHub Copilot Chat，确认 custom agents、prompt files、Agent Skills 和 `agent/runSubagent` 可用；不需要启用递归 subagent。
6. 在 Chat 的 Customizations/Diagnostics 中确认五个 agent、六个 prompt 和 instructions 均无错误。

Orchestrator 与 BugResolver frontmatter 中的 `agents` allowlist 可能依赖目标 VS Code 与 GitHub Copilot 环境中的 Experimental custom-agent/subagent 支持。本 Kit 不声明未经验证的最低版本；请在实际目标环境运行 Customizations/Diagnostics，并分别用一次通用委派和 Bug 修复委派烟测确认 allowlist 生效。

本仓库不提供自动覆盖安装脚本。升级时按目录比较和合并，尤其保护项目画像、全局规则和本地 prompt 定制。

### 使用

推荐入口：

```text
选择 Orchestrator：为 W25Q128 增加 SPI 驱动；先复用现有 HAL，完成主机构建、测试和独立评审。缺少匹配 datasheet 时停止，不要猜寄存器值。
```

斜杠命令：

- `/new-driver <driver_request>`：由 Orchestrator 完成驱动预检、实现、验证和评审。
- `/implement-feature <feature_request>`：由 Orchestrator 完成应用行为建模、实现、追踪、验证和评审。
- `/analyze-bug <bug_input>`：由 BugResolver 先引导并规范化使用现象，必要时确认分析方向，再识别问题、追踪代码/配置上下文和验证根因假设；缺资料时主动集中索证，用户授权时继续协调修复与质量评估。
- `/analyze-log <log_input>`：即使已有日志也先补齐使用场景和方向，再分析多产品形态日志、事件关联、ELF/MAP、产物身份和证据时间线。
- `/misra-review <review_target>`：由 QualityReviewer 做 MISRA-oriented 风险筛查。
- `/verify-change <change_target>`：由 Orchestrator 审计 baseline、构建、测试、评审和文档门禁。

直接模式：

- 只实现代码：选择 `EmbeddedDeveloper`，提供 Goal、Scope、约束和验收条件。
- 分析或解决 Bug/日志问题：选择 `BugResolver`，可先提供已有的原始错误或日志；Agent 会引导补齐实际使用目标、步骤、预期/实际、频率/边界、环境和影响，方向清晰后识别问题，并在本地发现后集中请求仍缺少的最小证据。需要解决时明确是否授权修改。
- 只做独立质量评估：选择 `QualityReviewer`，提供需求、真实 diff/files 和可用构建/测试/静态分析证据。
- 只维护文档：选择 `DocKeeper`，提供已经确认的源码/API/测试或根因证据。

### 安全与权限

- `BugResolver`、`EmbeddedDeveloper` 和 `QualityReviewer` 的 `execute` 都受 VS Code 审批设置约束。BugResolver 只运行只读诊断与符号化；Reviewer 只运行 Git 只读、构建/测试审计和静态分析。
- flash、erase、fuse、reset、HIL、设备电源、发布和外部部署始终需要明确人工授权；画像中存在命令不等于授权。
- DocKeeper 的 Web 仅用于官方或供应商公开资料，不得上传私有源码、日志、客户数据或凭据。
- 同一 checkout 不并行运行写任务。未来只有一任务一 worktree/branch 隔离后才能考虑并行写入。
- Agent 不能替代人工代码评审、硬件验证、功能安全评估或正式 MISRA 合规工具。
- Skill 脚本统一使用退出码 `0` 成功、`2` 输入错误、`3` 证据不足、`4` 外部工具失败。`profile_gates.py` 只生成/验证门禁证据，不执行画像命令；hardware 永不进入 host 门禁。

### 验证 Kit

安装开发依赖并运行静态验证：

```sh
python -m pip install -r .github/agent-kit/requirements-dev.txt
python .github/agent-kit/scripts/validate_customizations.py --root .
python -m unittest discover -s .github/agent-kit/tests -p "test_*.py"
```

构建主机示例：

```sh
cmake -S examples/minimal-firmware -B build/minimal-firmware
cmake --build build/minimal-firmware
ctest --test-dir build/minimal-firmware --output-on-failure
```

CI 在 Windows 和 Ubuntu 上执行上述验证。真实交互还需按照 [VS Code Manual Smoke Test](docs/manual-smoke-test.md) 检查 agent 发现、自动编排、缺资料、baseline 失败、缺陷评审、ELF 不匹配和硬件审批。

### 目录

```text
.github/
├── copilot-instructions.md
├── embedded-project.yml
├── agent-contracts.md
├── agents/                  # 固定五个 agent
├── agent-kit/               # Kit 自检脚本、测试、fixtures 和开发依赖
├── instructions/            # C、双语和 Kit 配置规则
├── prompts/                 # 六个薄 slash 入口
├── skills/                  # 五个按需工作流及确定性脚本
└── workflows/validate.yml
docs/                        # 产品形态与人工烟测
examples/minimal-firmware/   # CMake/CTest + fake HAL
```

### 双语规范

README、`docs/` 和 `.github/` 中的 first-party Markdown 使用：

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

vendor、generated、第三方文档和许可证原文不自动双语化。发布门禁不接受未归属的 `TODO(sync)`。

### 扩展原则

- 不为新流程随意增加第六个 agent；先扩展现有角色的模式或新增按需 skill。
- Prompt 用于人工入口和 agent 路由；复杂检查表、模板和脚本放 skill。
- 共享规则只维护一份，并由 agent/skill 链接，避免上下文重复。
- 本 Kit 明确以 VS Code 为完整支持目标。GitHub cloud/CLI 可能忽略 handoff 或 VS Code-specific allowlist，不属于 v1 验收范围。

## English

### Overview

`embedded-multi-agent` is a VS Code-first, repository-embedded, MCP-free Agent Kit for Embedded C. It provides exactly five directly selectable custom agents and uses a shallow manager pattern for driver and application-logic requirements, implementation, verification, review, and documentation:

- `Orchestrator`: the default entry point and general delivery orchestrator.
- `BugResolver`: the dedicated orchestrator for guiding usage symptoms, understanding bugs, validating root cause, and closing authorized repairs.
- `EmbeddedDeveloper`: the sole routine functional-code writer.
- `QualityReviewer`: responsible only for independent read-only quality assessment.
- `DocKeeper`: the maintainer of team documentation, the project profile, and captured knowledge.

The kit is versioned with the firmware repository. It follows existing project facts before applying template defaults. It adapts to bare-metal, RTOS, communication-module SDK, Embedded Linux, and hybrid products, but it does not include board-programming authority, MCP, private toolchains, or vendor documentation.

### Product Design

The five agents represent stable responsibilities, while repeated workflows live in prompts and on-demand skills. Agent persona, VS Code approvals, and the host sandbox are separate control layers: role text constrains behavior, tool lists reduce the capability surface, and approvals plus sandboxing control actual commands and file boundaries.

Automatic closure uses subagents:

```text
User
  ├──▶ Orchestrator ── ordinary work ──▶ EmbeddedDeveloper
  │          ├── quality review ───────▶ QualityReviewer
  │          └── documentation ────────▶ DocKeeper
  │
  └──▶ BugResolver ── diagnosis/root cause
             ├── authorized fix ───────▶ EmbeddedDeveloper
             ├── quality gate ─────────▶ QualityReviewer
             └── docs when needed ─────▶ DocKeeper
```

A handoff is a separate human-controlled path: a button appears after an agent response and the user confirms the role switch. `send: false` means it is not submitted automatically. A handoff is not a subagent invocation and does not mean the next stage ran.

### The Five Agents

| Agent | Tools | Allowed writes | Main output |
| --- | --- | --- | --- |
| `Orchestrator` | `agent`, `read`, `search` | None | Task Briefs, orchestration state, quality gates, and final synthesis |
| `BugResolver` | `agent`, `read`, `search`, `execute` | None | Usage-symptom guidance, direction confirmation, problem-identification card, log timeline, evidence-backed root cause, active evidence request, and repair closure |
| `EmbeddedDeveloper` | `edit`, `read`, `search`, `execute` | In-scope functional code, tests, and build configuration | Minimal diff, APIs, baseline/build/test evidence |
| `QualityReviewer` | `read`, `search`, `execute` | None | High-signal quality findings, MISRA risks, and verdict |
| `DocKeeper` | `read`, `search`, `edit`, `web` | README, `docs/`, project profile, and authorized comments | Design, How-to, Reference, ADR, FAQ, and closure records |

All agents remain directly selectable. Use `Orchestrator` for complex general delivery and `BugResolver` for bug analysis or resolution; direct specialist mode still follows the [shared contract](.github/agent-contracts.md).

### Workflow Status and Quality Gates

Common statuses are:

- `COMPLETE`: every required gate passed.
- `CONDITIONAL`: the user explicitly accepted remaining risk.
- `BLOCKED`: a decision, document, tool, or permission is missing, so safe progress is impossible.
- `FAILED`: verification failed or BLOCKER/MAJOR findings remain after two rework rounds.
- `INSUFFICIENT_EVIDENCE`: review/bug/fault analysis only; available evidence cannot support a conclusion.

The standard Orchestrator delivery flow is:

```text
INTAKE → PREFLIGHT → PLAN → IMPLEMENT → VERIFY → REVIEW
                                              │
                       up to two REWORK rounds ◀───┘
                                              │
                         DOCUMENT (as needed) → CLOSE
```

Bug requests enter `BugResolver` through `/analyze-bug`, `/analyze-log`, direct selection, or Orchestrator's manual handoff; the two managers are never auto-nested. Its diagnostic path is `INTAKE → GUIDE_SYMPTOMS → CONFIRM_DIRECTION (when needed) → SCOPE → NORMALIZE_ERROR → IDENTIFY_PROBLEM → TRACE_CONTEXT → REPRODUCE_BASELINE → EVIDENCE_CHECK → AWAIT_EVIDENCE / HYPOTHESES → VALIDATE_CAUSE → DECIDE`. After the user explicitly authorizes a fix, it continues through `PLAN_FIX → IMPLEMENT → VERIFY → QUALITY_REVIEW → REWORK → DOCUMENT → CLOSE`.

BugResolver first uses Usage Symptom Profile to understand the user's goal, actual operations, expected/actual behavior, frequency/boundaries, environment, impact, and recovery. When direction-changing symptoms are missing, it asks them together through one Usage Symptom Questions table with at most five questions in the first set and permits `Unknown`. It asks for direction confirmation only when symptoms indicate different modules/root-cause paths or conflict; it does not trace deeply or delegate Developer before confirmation, and proceeds directly when the scenario is clear. It then emits Problem Identification grounded in that Profile to separate the observed problem, category, suspected subsystem, severity, and evidence confidence.

When critical evidence is missing, BugResolver searches the repository and finishes safe preliminary analysis before requesting the smallest logs, versions, configuration, or ELF/MAP/dump artifacts once through a separate Evidence Request table. Symptom questions and evidence requests never mix. Until evidence arrives, it neither confirms root cause, repeats the request, nor invokes Developer. Log analysis covers bare-metal, RTOS, module SDK, Embedded Linux, and hybrid systems while preserving original offsets and clock domains; it never invents a unified timeline without reliable timing evidence.

Command evidence includes the exact command, exit code, and relevant output. An unexecuted check is `NOT_RUN`, not a pass.

### Project Profile

[`.github/embedded-project.yml`](.github/embedded-project.yml) is the entry point for project facts. After installation, confirm:

- `product_form`, MCU/SoC, RTOS, toolchain, and C standard.
- Source/driver/application/services/middleware/protocols/test/docs/vendor/generated paths; absent application path fields are equivalent to `auto`.
- Host-side `commands.configure`, `commands.build`, `commands.test`, and `commands.static_analysis` commands.
- Hardware commands isolated under `commands.hardware.flash`, `commands.hardware.erase`, `commands.hardware.fuse`, `commands.hardware.reset`, and `commands.hardware.hil`; they are disabled by default and require explicit approval.
- ELF, MAP, log, and static-analysis report locations.
- MISRA edition, deviation file, and hardware-document revision.

Fields may remain `auto`, in which case agents discover them from the repository. Profile/repository conflicts are reported as configuration drift. See [Embedded Product Forms](docs/product-forms.md) for detailed review areas.

### Installation

1. Place this kit at the target firmware repository root; merge `.github` instead of overwriting existing configuration.
2. Manually merge `.github/copilot-instructions.md` and preserve the target project's existing rules.
3. Adjust `.github/embedded-project.yml`. Keep unknown values as `auto`; do not enter unconfirmed hardware facts.
4. Open the firmware repository root directly in VS Code and trust the workspace. Opening only its parent prevents automatic `.github` discovery.
5. Enable GitHub Copilot Chat and confirm that custom agents, prompt files, Agent Skills, and `agent/runSubagent` are available. Recursive subagents are not required.
6. Confirm in Chat Customizations/Diagnostics that all five agents, six prompts, and instructions load without errors.

The `agents` allowlists in the Orchestrator and BugResolver frontmatter may depend on Experimental custom-agent/subagent support in the target VS Code and GitHub Copilot environment. This kit does not claim an unverified minimum version; run Customizations/Diagnostics in the actual target environment and perform both a general delegation smoke test and a bug-resolution delegation smoke test to confirm that the allowlists are honored.

The repository intentionally has no overwriting installation script. Compare and merge directories during upgrades, especially the profile, global rules, and local prompt customizations.

### Usage

Recommended entry point:

```text
Select Orchestrator: Add an SPI driver for W25Q128, reusing the existing HAL and completing host build, tests, and independent review. Stop rather than guessing register values if a matching datasheet is unavailable.
```

Slash commands:

- `/new-driver <driver_request>`: Orchestrator performs driver preflight, implementation, verification, and review.
- `/implement-feature <feature_request>`: Orchestrator performs application behavior modeling, implementation, traceability, verification, and review.
- `/analyze-bug <bug_input>`: BugResolver first guides and normalizes usage symptoms, confirms direction only when needed, then identifies the problem, traces code/configuration context, tests root-cause hypotheses, actively requests missing evidence as one set, and coordinates repair plus quality assessment when authorized.
- `/analyze-log <log_input>`: even with logs supplied, BugResolver establishes usage context and direction before analyzing multi-product logs, event correlation, ELF/MAP artifacts, artifact identity, and the evidence timeline.
- `/misra-review <review_target>`: QualityReviewer performs MISRA-oriented risk screening.
- `/verify-change <change_target>`: Orchestrator audits baseline, build, tests, review, and documentation gates.

Direct mode:

- Implementation only: select `EmbeddedDeveloper` and provide the Goal, Scope, constraints, and acceptance criteria.
- Bug/log analysis or resolution: select `BugResolver` and provide any available original error or log. The agent guides you to complete the real goal, steps, expected/actual behavior, frequency/boundaries, environment, and impact; once direction is clear, it identifies the problem, discovers local context, and asks once for the remaining minimum evidence. State whether changes are authorized when resolution is required.
- Independent quality assessment only: select `QualityReviewer` and provide requirements, the real diff/files, and available build/test/static-analysis evidence.
- Documentation only: select `DocKeeper` and provide confirmed source/API/test or root-cause evidence.

### Safety and Permissions

- VS Code approval settings govern `execute` for BugResolver, EmbeddedDeveloper, and QualityReviewer. BugResolver runs only read-only diagnostics and symbolization; Reviewer runs only read-only Git, build/test audit, and static analysis.
- Flash, erase, fuse, reset, HIL, device power, release, and external deployment always require explicit human authorization. A command's presence in the profile is not authorization.
- DocKeeper uses the web only for official or vendor public sources and never uploads private source, logs, customer data, or credentials.
- Do not run write tasks concurrently in one checkout. Parallel writing may be considered only after one-task-per-worktree/branch isolation exists.
- Agents do not replace human code review, hardware verification, functional-safety assessment, or formal MISRA compliance tools.
- Skill scripts use exit code `0` for success, `2` for invalid input, `3` for insufficient evidence, and `4` for external-tool failure. `profile_gates.py` only plans/validates gate evidence and never executes profile commands; hardware never enters host gates.

### Validate the Kit

Install development dependencies and run static validation:

```sh
python -m pip install -r .github/agent-kit/requirements-dev.txt
python .github/agent-kit/scripts/validate_customizations.py --root .
python -m unittest discover -s .github/agent-kit/tests -p "test_*.py"
```

Build the host example:

```sh
cmake -S examples/minimal-firmware -B build/minimal-firmware
cmake --build build/minimal-firmware
ctest --test-dir build/minimal-firmware --output-on-failure
```

CI runs these checks on Windows and Ubuntu. Real interaction also requires the [VS Code Manual Smoke Test](docs/manual-smoke-test.md), covering discovery, automatic orchestration, missing documents, baseline failure, seeded-defect review, ELF mismatch, and hardware approval.

### Layout

```text
.github/
├── copilot-instructions.md
├── embedded-project.yml
├── agent-contracts.md
├── agents/                  # exactly five agents
├── agent-kit/               # kit self-check scripts, tests, fixtures, and dev dependencies
├── instructions/            # C, bilingual, and kit configuration rules
├── prompts/                 # six thin slash entries
├── skills/                  # five on-demand workflows with deterministic scripts
└── workflows/validate.yml
docs/                        # product forms and manual smoke test
examples/minimal-firmware/   # CMake/CTest + fake HAL
```

### Bilingual Rules

First-party Markdown in the README, `docs/`, and `.github/` uses:

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

Vendor, generated, third-party documentation, and license text are not automatically bilingualized. The release gate does not accept an unowned `TODO(sync)`.

### Extension Principles

- Do not add a sixth agent casually for a new workflow; extend an existing role mode or add an on-demand skill first.
- Prompts provide manual entry and agent routing; complex checklists, templates, and scripts belong in skills.
- Maintain shared rules once and link them from agents and skills to avoid repeated context.
- The kit fully supports VS Code only. GitHub cloud/CLI may ignore handoffs or VS Code-specific allowlists and are outside v1 acceptance.
