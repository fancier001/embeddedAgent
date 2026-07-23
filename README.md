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

五个业务 Agent 对应稳定职责，共享状态、报告、Next Action 和 Git 交付只在 `agent-contracts.md` 定义；Prompt 只适配输入，按需 Skill 只描述专项步骤。Agent persona、VS Code approvals 和宿主 sandbox 是三层不同控制：角色说明约束行为，工具列表缩小能力面，审批与 sandbox 才控制真实命令和文件边界。

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

五个业务 Agent 的原有基础 handoff 由 frontmatter 静态定义、始终显示且保持 `send: false`，只作为人工备用角色入口。每组按钮末尾另有 `执行下一步 / Next Action`，使用 `send: true` 进入隐藏的 `NextActionRouter`；Router 读取最新唯一 Next Action，自动执行安全角色路由，或为缺输入、外部操作和受保护确认给出精确指令。切换后 Router 自己继续显示五个 `send:false` 静态返回按钮，分别返回 Orchestrator、BugResolver、EmbeddedDeveloper、QualityReviewer 和 DocKeeper，避免底部变为空白。基础/返回按钮不表示当前推荐动作，提前点击不匹配的按钮会被目标 Agent 门禁阻塞。

### 五个业务 Agent与隐藏 Router

| Agent | 工具 | 允许写入 | 主要输出 |
| --- | --- | --- | --- |
| `Orchestrator` | `agent`, `read`, `search` | 无 | Task Brief、编排状态、质量门和最终汇总 |
| `BugResolver` | `agent`, `read`, `search`, `execute` | 无 | 使用现象引导、方向确认、问题识别卡、日志时间线、证据化根因、主动索证和修复闭环 |
| `EmbeddedDeveloper` | `edit`, `read`, `search`, `execute` | 任务范围内功能代码、测试和构建配置 | 最小 diff、API、baseline/build/test 证据 |
| `QualityReviewer` | `read`, `search`, `execute` | 无 | 高信噪比质量 findings、MISRA 风险和 verdict |
| `DocKeeper` | `read`, `search`, `edit`, `web` | README、`docs/`、项目画像和授权注释 | 设计、How-to、Reference、ADR、FAQ 和结案记录 |
| `NextActionRouter` | `agent`, `read`, `search` | 无 | 隐藏的持续路由、输入/外部操作指令和循环保护 |

五个业务 Agent 可从下拉框直接选择；Router 设置为 `user-invocable:false`，只由统一按钮进入并持续接管到输入、外部操作、阻塞或终态。Router 的五个静态返回按钮仅供人工恢复，点击后不会自动提交，也不会代替缺失输入或 Git 授权。

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
                DOCUMENT（按需）→ DELIVERY → CLOSE
```

Bug 请求通过 `/analyze-bug`、`/analyze-log`、直接选择或 Orchestrator 的人工 handoff 进入 `BugResolver`，两个 manager 不自动嵌套。诊断路径为 `INTAKE → GUIDE_SYMPTOMS → CONFIRM_DIRECTION（按需）→ SCOPE → NORMALIZE_ERROR → IDENTIFY_PROBLEM → TRACE_CONTEXT → REPRODUCE_BASELINE → EVIDENCE_CHECK → AWAIT_EVIDENCE / HYPOTHESES → VALIDATE_CAUSE → DECIDE`；用户明确授权修复后，再进入 `PLAN_FIX → IMPLEMENT → VERIFY → QUALITY_REVIEW → REWORK → DOCUMENT → DELIVERY → CLOSE → RESET → INTAKE`。

BugResolver 会把显式 `Git Delivery` 和 commit metadata 保留到 `DELIVERY`。若修复请求未提供交付选择，交付前统一使用 `none` 防止提前写入；门禁全部通过后生成一次 `Commit Delivery Confirmation`，建议 `commit` 为待确认默认值。推荐值不构成授权，用户确认前不写 Git；`commit-and-push`/`auto` 必须明确选择，显式 `none` 记录跳过。

Jira ID 是唯一始终要求用户主动提供的 commit 字段，Agent 不会从分支或路径猜测。Project 优先从 `.project/project.yml` 或已确认任务上下文解析；Function block、Summary、Change Type、原因、根因、方案、AI 使用、影响功能、适用项目、RN 和 Test Notes 均从本次根因、真实 diff、测试、评审和文档证据生成。Agent 一次性展示完整预览，用户只需回复 Jira ID 并确认，或指出要修改的字段；未确认时返回 `BLOCKED` 且 Git 状态不变。

AI 字段按真实参与生成：AI 实质参与代码生成、检查、重构、测试或文档时填写 `Y`、一个真实主要场景和详情；完全未参与时规范填写 `<AI-Tool-Used>: N`、`<AI-Tool-Scenario>: /`、`<AI-Tool-Detail>: /`。`N/A` 不再是 AI=`N` 的合法占位值。

VS Code 的人工 handoff 不会自动返回上一 manager，因此 `BugResolver`、`QualityReviewer` 和 `DocKeeper` 都保留 `Git 提交交付 / Git Delivery` 按钮作为进入 `EmbeddedDeveloper` 的人工入口。BugResolver 自己管理的修复闭环在全部门禁和用户确认通过后也可直接创建本地 commit；push 和 `auto` 仍交给 EmbeddedDeveloper。

进入 EmbeddedDeveloper 并看到 `Commit Delivery Confirmation` 后，最后一步不是另一个 handoff 按钮。Agent 必须先反馈逐文件修改内容和将原样交给 Git 的完整 commit message，并显示 `Commit Content Confirmation: PENDING`；用户核对后在当前输入框回复 `确认提交内容`，或回复 `调整修改: <要求>` 进入删减和重新验证流程。模式选择、Jira、按钮点击或笼统要求“提交”都不等于内容确认。最终确认后当前 Agent 使用 `git add -- <task-paths>` 显式暂存已确认任务路径并核对完整 staged 内容与预览完全一致，再执行 `git -c core.hooksPath=.githooks commit --file <message-file> --cleanup=verbatim`。文件、diff、范围或消息漂移会使确认失效并重新预览。`commit-msg` hook 是唯一消息门禁，直接调用 `project_policy.py message`；不存在额外提交包装层。

每个业务 Agent 结果都包含唯一动态 Next Action：Current State、Chat Language、Action、Owner、UI Route、Dispatch Target、Input Required、Required Input、Reply Template、Instruction、On Success。`Chat Language` 只来自用户亲自输入并在路由中原样传递；需要回复时显示 `Input Required: YES`，逐项列出字段、格式和可复制模板，并明确要求在当前输入框回复；无需回复时显示 `Input Required: NO` 并明确提示点击“执行下一步”或无需操作。统一按钮点击只授权安全路由，不代替 Jira、修改内容、commit、push 或外部命令确认。

修复、验证、独立评审、必要文档和所选 Git 交付均处理完成后，EmbeddedDeveloper 的 `问题已解决 / Close Issue` handoff 返回 BugResolver。BugResolver 输出闭环报告、清除问题级 Jira/根因/范围/授权等状态，再用 `START_NEW_ISSUE` 进入新问题；提前点击该 handoff 会返回 `BLOCKED`。

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

### 项目级约束

根目录可选的 [`.project/`](.project/README.md) 与 `.github/` 同级，保存目标工程自己的代码规范、路径策略、Git 交付策略和后续扩展。缺失时仅非 Git 规则发现返回 `NOT_CONFIGURED` 以兼容旧项目；`message`、`git-plan` 和 hook 保护的 commit 全部 fail-closed，返回 `BLOCKED / PROJECT_POLICY_REQUIRED`。存在时固定入口 [`.project/project.yml`](.project/project.yml) 用 `rules` 注册规则文件及 `applies_to` 路径 glob，Agent 根据 Task Brief 范围和真实 diff 只加载适用规则；整个目录按严格 schema 校验。

`python .github/agent-kit/scripts/project_policy.py rules --root . --path <repo-relative-path>` 可确定性输出适用规则和 Git policy；重复 `--path` 支持多路径，`--all` 用于审计。

默认 [Git delivery policy](.project/git/delivery.yml) 定义自动化开关、`denied_paths`、commit 模板/检查和 push 分支/检查，但禁止保存 remote、URL 或目标 ref。commit 内容由 `Task Change Baseline`、本任务修改账本和当前真实 diff 检测，不由 YAML 路径白名单决定；旧 `allowed_paths` 仅兼容解析。两个 `automation` 开关默认关闭且只约束 `auto`；用户确认的 `commit`/`commit-and-push` 不受其限制。Task Brief 的 `Git Delivery` 只接受 `none`、`commit`、`commit-and-push`、`auto`。即使已选择 `auto`，自动 commit 前仍必须确认精确 Commit Content fingerprint；缺失或漂移时只读预检返回 `CONFIRM_COMMIT_CONTENT`。严格的 [commit template](.project/git/commit.template)、版本化 [commit-msg hook](.githooks/commit-msg) 和 [`project_policy.py`](.github/agent-kit/scripts/project_policy.py) 共同构成提交消息门禁；消息规则只在 policy 脚本中实现。

提交前的 `Commit Content` 逐文件显示 Git state、增删统计、真实摘要和排除路径，并同时展示完整 commit message；所有模式都显示 `Commit Content Confirmation: PENDING`，只有 auto 额外显示 fingerprint。用户可回复 `确认提交内容`，也可要求移除文件、缩小 hunk、减少实现或修改消息；后者进入 `ADJUST_CHANGESET`，只调整本任务内容并重新运行受影响验证、独立评审和确认，旧确认不会沿用。

push 预检只通过当前项目 `.git` 的 local config 解析 current branch、branch remote/merge 和唯一 push URL；global/system config、环境变量、`.project` 和用户文本不能覆盖。无 upstream、detached HEAD、多个 push URL、保护分支、命中 `denied_paths` 或 fingerprint 漂移都会阻塞；工具只读，不执行 commit/push。

`Git Delivery: auto` 只在修复、测试、必需检查、独立评审和必要文档全部通过后决策。完整消息缺必填 metadata 时阻塞请求补充；无 diff 时不交付；任一自动上传前提不足时 Git 保持不变，Agent 只输出完整 commit 内容。只有 policy 同时启用 commit/push、index 初始为空、改动正好属于修复范围、HEAD 与本地 upstream 一致且目标安全唯一时，才显式暂存、创建一个 commit，并用首次 fingerprint 与新 commit SHA 二次预检后 push；push 失败保留本地 commit，不自动回滚。

`extensions` 可保存命名空间化的项目集成配置，`.project/` 也允许增加其他子目录和内容，因此扩展项目规范无需改变五 Agent 结构。

### 安装

1. 将本 Kit 放到目标固件仓库根目录并合并 `.github`，不要覆盖已有配置；需要项目级规则时再安装同级 `.project`，旧项目可不安装。
2. 人工合并 `.github/copilot-instructions.md`，保留目标工程原有规则。
3. 调整 `.github/embedded-project.yml`；未知值保持 `auto`，不要填写未经确认的硬件事实。
4. 使用 `.project` 时调整 `project.yml`、适用规则和 Git policy；按需维护 `denied_paths`、分支和检查，不使用路径白名单定义 commit 内容。先保留 `automation.commit/push: false`，确认自动交付条件后再为 `auto` 启用；这不会阻止用户确认的 commit/push。不得在 policy 中写 remote、URL 或目标分支。
5. 用 VS Code 直接打开固件仓库根目录并信任工作区。若只打开父目录，VS Code 不会自动发现该 `.github`。
6. 启用 GitHub Copilot Chat，确认 custom agents、prompt files、Agent Skills 和 `agent/runSubagent` 可用；不需要启用递归 subagent。
7. 在 Chat 的 Customizations/Diagnostics 中确认五个 agent、六个 prompt 和 instructions 均无错误，并运行 Kit validator 检查 `.project` 引用和 Git policy。

Orchestrator 与 BugResolver frontmatter 中的 `agents` allowlist 可能依赖目标 VS Code 与 GitHub Copilot 环境中的 Experimental custom-agent/subagent 支持。本 Kit 不声明未经验证的最低版本；请在实际目标环境运行 Customizations/Diagnostics，并分别用一次通用委派和 Bug 修复委派烟测确认 allowlist 生效。

本仓库不提供自动覆盖安装脚本。升级时按目录比较和合并，尤其保护项目画像、`.project/` 项目规范、全局规则和本地 prompt 定制。

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
- Git 交付：Task Brief 的 `Git Delivery` 只写 `none`、`commit`、`commit-and-push` 或 `auto`。所有提交模式都必须先反馈逐文件内容与完整 commit message，并等待明确内容确认；`commit`/`commit-and-push` 通过 `确认提交内容` 授权，只有 `auto` 需要在 `.project` policy 中启用两个 `automation` 开关并额外确认当前 fingerprint。remote、URL 和目标分支始终由当前项目 `.git` 解析。BugResolver 可在完整修复闭环后直接创建受 hook 保护的本地 commit；push 和 `auto` 交给 `EmbeddedDeveloper`。`auto` 选择不等于内容确认：用户用当前 fingerprint 确认后，预检才可返回 `content_confirmation.status: CONFIRMED` 和 `AUTO_COMMIT_AND_PUSH`。

### 安全与权限

- `BugResolver`、`EmbeddedDeveloper` 和 `QualityReviewer` 的 `execute` 都受 VS Code 审批设置约束。BugResolver 只运行只读诊断与符号化；Reviewer 只运行 Git 只读、构建/测试审计和静态分析。
- flash、erase、fuse、reset、HIL、设备电源、发布和外部部署始终需要明确人工授权；画像中存在命令不等于授权。
- `.project` Git policy 只定义约束，不等于授权。BugResolver 或 EmbeddedDeveloper 只可用 `git add -- <task-paths>` 显式暂存已确认任务路径，禁止全仓库暂存；所有 staged 内容都将进入提交。提交前必须确认版本化 hook 存在，并只使用带 `core.hooksPath=.githooks` 的 `git commit`；禁止 amend、`--no-verify`、无 hook 提交和自动修改 `.git/config`。内容 fingerprint 仅用于 `auto`。
- DocKeeper 的 Web 仅用于官方或供应商公开资料，不得上传私有源码、日志、客户数据或凭据。
- 同一 checkout 不并行运行写任务。未来只有一任务一 worktree/branch 隔离后才能考虑并行写入。
- Agent 不能替代人工代码评审、硬件验证、功能安全评估或正式 MISRA 合规工具。
- Skill 脚本统一使用退出码 `0` 成功、`2` 输入错误、`3` 证据不足、`4` 外部工具失败。`profile_gates.py` 只生成/验证门禁证据，不执行画像命令；hardware 永不进入 host 门禁。

### 验证 Kit

安装开发依赖并运行静态验证：

```sh
python -m pip install -r tests/agent-kit/requirements.txt
python .github/agent-kit/scripts/validate_customizations.py --root .
python -m unittest discover -s tests/agent-kit -p "test_*.py"
```

构建主机示例：

```sh
cmake -S examples/minimal-firmware -B build/minimal-firmware
cmake --build build/minimal-firmware
ctest --test-dir build/minimal-firmware --output-on-failure
```

CI 在 Windows 和 Ubuntu 上执行上述验证。真实交互还需按照 [VS Code Manual Smoke Test](tests/agent-kit/manual/vscode-smoke-test.md) 检查 agent 发现、项目约束调用、受控 Git 交付、自动编排、缺资料、baseline 失败、缺陷评审、ELF 不匹配和硬件审批。

### 目录

```text
.github/
├── copilot-instructions.md
├── embedded-project.yml
├── agent-contracts.md
├── agents/                  # 五个业务 Agent 与一个隐藏 Router
├── agent-kit/               # Kit 运行与自检脚本
├── instructions/            # C、双语和 Kit 配置规则
├── prompts/                 # 六个薄 slash 入口
├── skills/                  # 五个按需工作流及确定性脚本
└── workflows/validate.yml
.githooks/
└── commit-msg               # 版本化、fail-closed 的 commit 消息门禁
.project/
├── project.yml              # 项目约束清单与扩展入口
├── README.md                # 双语使用说明
├── rules/                   # 按仓库路径调用的项目特定规范
└── git/
    ├── delivery.yml         # 自动化、范围、安全、分支与检查；不含 push 目标
    └── commit.template      # 严格 commit 消息模板
docs/                        # 产品说明
tests/agent-kit/             # 单元测试、fixtures、依赖与人工烟测
examples/minimal-firmware/   # CMake/CTest + fake HAL
```

### 双语规范

README、`docs/`、`.github/` 和 `.project/` 中的 first-party Markdown 使用：

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

聊天输出不强制双语。Agent 在新会话首次回复的第一个字符前完成 Language Preflight：有 Latin-script 自然语言单词且无 Han 自然语言文本时必须使用 `en-US`，Jira ID 等标识符不改变该结果。进度、提问、Result Report 和 Next Action 都使用 Task Brief/Next Action 的 `Chat Language` 在 Agent、Router 和 handoff 间原样传递；按钮及自动双语 prompt 不会触发语言切换。当该值为 `en` 或 `en-*` 时，Agent 在发送前扫描完整草稿，出现 Agent 生成的 Han 字符必须丢弃并重写；只有明确标记的原文证据可保持原文。聊天中的 `Dispatch Target` 使用 `HANDOFF:QUALITY_REVIEWER` 这类纯 ASCII 稳定 ID，双语按钮标签只保留在 UI 层。

### 扩展原则

- 不为新流程随意增加第六个 agent；先扩展现有角色的模式或新增按需 skill。
- Prompt 用于人工入口和 agent 路由；复杂检查表、模板和脚本放 skill。
- 共享规则只维护一份，并由 agent/skill 链接，避免上下文重复。
- 项目专属规范放在 `.project/` 并通过清单注册；其他结构化集成使用命名空间化 `extensions`，未知扩展保持可保留但不自动执行。
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

The five business Agents represent stable responsibilities. Shared state, reports, Next Action, and Git delivery are defined only in `agent-contracts.md`; prompts only adapt input, and on-demand Skills describe specialized steps. Agent persona, VS Code approvals, and the host sandbox are separate control layers: role text constrains behavior, tool lists reduce the capability surface, and approvals plus sandboxing control actual commands and file boundaries.

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

The five business agents' existing base handoffs are static, always visible, and remain `send: false` manual fallback role entries. Each set ends with `执行下一步 / Next Action`, a `send: true` handoff to the hidden `NextActionRouter`. The Router reads the latest unique Next Action, executes safe role routing, or emits exact instructions for missing input, external work, and protected confirmations. Once active, the Router itself exposes five `send:false` static return buttons for Orchestrator, BugResolver, EmbeddedDeveloper, QualityReviewer, and DocKeeper so the footer never becomes empty. A mismatched early base/return-button click is blocked by the target agent's gates.

### Five Business Agents and the Hidden Router

| Agent | Tools | Allowed writes | Main output |
| --- | --- | --- | --- |
| `Orchestrator` | `agent`, `read`, `search` | None | Task Briefs, orchestration state, quality gates, and final synthesis |
| `BugResolver` | `agent`, `read`, `search`, `execute` | None | Usage-symptom guidance, direction confirmation, problem-identification card, log timeline, evidence-backed root cause, active evidence request, and repair closure |
| `EmbeddedDeveloper` | `edit`, `read`, `search`, `execute` | In-scope functional code, tests, and build configuration | Minimal diff, APIs, baseline/build/test evidence |
| `QualityReviewer` | `read`, `search`, `execute` | None | High-signal quality findings, MISRA risks, and verdict |
| `DocKeeper` | `read`, `search`, `edit`, `web` | README, `docs/`, project profile, and authorized comments | Design, How-to, Reference, ADR, FAQ, and closure records |
| `NextActionRouter` | `agent`, `read`, `search` | None | Hidden persistent routing, input/external instructions, and loop protection |

The five business agents remain directly selectable. `NextActionRouter` is `user-invocable:false` and is entered only by the unified button, then persists until input, external work, a blocker, or a terminal state. Its five static return buttons are manual recovery entries with `send:false`; they neither auto-submit nor replace missing input or Git authorization.

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
                DOCUMENT (as needed) → DELIVERY → CLOSE
```

Bug requests enter `BugResolver` through `/analyze-bug`, `/analyze-log`, direct selection, or Orchestrator's manual handoff; the two managers are never auto-nested. Its diagnostic path is `INTAKE → GUIDE_SYMPTOMS → CONFIRM_DIRECTION (when needed) → SCOPE → NORMALIZE_ERROR → IDENTIFY_PROBLEM → TRACE_CONTEXT → REPRODUCE_BASELINE → EVIDENCE_CHECK → AWAIT_EVIDENCE / HYPOTHESES → VALIDATE_CAUSE → DECIDE`. After the user explicitly authorizes a fix, it continues through `PLAN_FIX → IMPLEMENT → VERIFY → QUALITY_REVIEW → REWORK → DOCUMENT → DELIVERY → CLOSE → RESET → INTAKE`.

BugResolver preserves explicit `Git Delivery` and commit metadata through `DELIVERY`. If a repair request omitted the delivery choice, all pre-delivery work uses `none` to prevent early writes. After all gates pass it creates one `Commit Delivery Confirmation` and proposes `commit` as the recommended default pending confirmation. A recommendation is not authorization and Git remains unchanged before confirmation. `commit-and-push`/`auto` require an explicit choice; explicit `none` records a skip.

Jira ID is the only commit field that is always user-supplied; the agent never guesses it from a branch or path. Project comes from `.project/project.yml` or confirmed task context when resolvable. Function block, Summary, Change Type, reason, root cause, solution, AI usage, affected function, applicable project, RN, and Test Notes are generated from the confirmed root cause, actual diff, tests, review, and documentation evidence. The agent shows one complete preview; the user need only reply with Jira ID plus confirmation, or name corrections. Without confirmation the result is `BLOCKED` and Git remains unchanged.

AI fields reflect actual participation. Use `Y` with one truthful primary scenario and detail when AI materially participated in code generation, inspection, refactoring, tests, or documentation. When AI did not participate at all, use exactly `<AI-Tool-Used>: N`, `<AI-Tool-Scenario>: /`, and `<AI-Tool-Detail>: /`; `N/A` is no longer valid for AI=`N`.

A manual VS Code handoff does not automatically return to the previous manager, so `BugResolver`, `QualityReviewer`, and `DocKeeper` retain a `Git 提交交付 / Git Delivery` button as a manual entry to `EmbeddedDeveloper`. A BugResolver managing its own repair loop may also create the local commit directly after all gates and user confirmation pass; push and auto remain with EmbeddedDeveloper.

After entering EmbeddedDeveloper and seeing `Commit Delivery Confirmation`, the final step is not another handoff button. The Agent first reports exact per-file changes and the complete commit message exactly as Git will receive it, with `Commit Content Confirmation: PENDING`. Review both, then reply `confirm commit content` in the current input, or use `adjust changes: <request>` to reduce and reverify them. Mode selection, Jira, button clicks, and generic commit requests are not content confirmation. After final confirmation, the current Agent stages confirmed task paths with `git add -- <task-paths>`, requires the complete staged content to match the preview exactly, then runs `git -c core.hooksPath=.githooks commit --file <message-file> --cleanup=verbatim`. File, diff, scope, or message drift invalidates confirmation and produces a new preview. The `commit-msg` hook is the sole message gate and directly invokes `project_policy.py message`; there is no commit wrapper.

Every business-agent result contains one dynamic Next Action with Current State, Chat Language, Action, Owner, UI Route, Dispatch Target, Input Required, Required Input, Reply Template, Instruction, and On Success. `Chat Language` comes only from user-authored input and is preserved through routing. When a reply is required, `Input Required: YES` itemizes fields and formats, supplies a copy-ready template, and explicitly says to reply in the current input. Otherwise, `Input Required: NO` explicitly tells the user to click Next Action or take no action. Clicking the unified button authorizes safe routing only and never substitutes for Jira, change-content, commit, push, or external-command confirmation.

After repair, verification, independent review, required documentation, and selected Git delivery are handled, EmbeddedDeveloper's `问题已解决 / Close Issue` handoff returns to BugResolver. BugResolver emits the closure report, clears issue-level Jira/root-cause/scope/authorization state, and enters a fresh issue through `START_NEW_ISSUE`; an early handoff returns `BLOCKED`.

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

### Project-Level Constraints

The optional root [`.project/`](.project/README.md) directory is a sibling of `.github/` and stores target-project conventions, path policy, Git delivery policy, and extensions. When it is absent, only non-Git rule discovery returns `NOT_CONFIGURED` for legacy compatibility; `message`, `git-plan`, and hook-protected commit fail closed with `BLOCKED / PROJECT_POLICY_REQUIRED`. When present, [`.project/project.yml`](.project/project.yml) registers rule files and `applies_to` globs under `rules`; agents load only matching rules, and the directory is validated strictly.

`python .github/agent-kit/scripts/project_policy.py rules --root . --path <repo-relative-path>` deterministically emits applicable rules and Git policy. Repeat `--path` for multiple paths, or use `--all` for audit.

The default [Git delivery policy](.project/git/delivery.yml) defines automation, `denied_paths`, commit template/checks, and push branch/check rules, but cannot store a remote, URL, or target ref. Commit content is detected from `Task Change Baseline`, the task-change ledger, and the current actual diff, never from a YAML path allowlist; legacy `allowed_paths` is parsed for compatibility only. Both `automation` switches default to off and gate only `auto`; user-confirmed `commit`/`commit-and-push` ignore them. Task Brief `Git Delivery` accepts only `none`, `commit`, `commit-and-push`, or `auto`. Even after selecting `auto`, the exact Commit Content fingerprint must be confirmed before automatic commit. The strict [commit template](.project/git/commit.template), versioned [commit-msg hook](.githooks/commit-msg), and [`project_policy.py`](.github/agent-kit/scripts/project_policy.py) form the commit-message gate; message rules exist only in the policy script.

Before commit, `Commit Content` shows each file's Git state, added/deleted counts, truthful summary, and excluded paths together with the complete commit message. Every mode shows `Commit Content Confirmation: PENDING`; only auto also shows a fingerprint. The user may reply `confirm commit content`, or ask to remove a file, narrow a hunk, reduce the implementation, or change the message. The latter enters `ADJUST_CHANGESET`, changes only current-task work, and reruns affected verification, independent review, and confirmation without reusing the old confirmation.

Push preflight resolves the current branch, branch remote/merge, and one push URL only from this project's local `.git` config. Global/system config, environment, `.project`, and user text cannot override it. Missing upstream, detached HEAD, multiple push URLs, protected branches, paths matching `denied_paths`, or fingerprint drift block delivery; the tool itself performs no commit or push.

`Git Delivery: auto` decides only after the repair, tests, required checks, independent review, and required documentation pass. Missing required message metadata blocks for input; no diff means no delivery; any unmet automatic-upload prerequisite leaves Git unchanged and makes the agent output only the complete commit content. It explicitly stages, creates one commit, and pushes after fingerprint/SHA revalidation only when policy enables both commit and push, the index starts empty, changes exactly match the repair scope, HEAD equals the local upstream, and the target is safe and unique. A push failure keeps the local commit without automatic rollback.

`extensions` may hold namespaced project-integration configuration, and `.project/` may contain other subdirectories and content, so project rules can grow without changing the five-agent structure.

### Installation

1. Place this kit at the target firmware repository root and merge `.github` rather than overwriting configuration. Install sibling `.project` only when project-level rules are wanted; legacy projects may omit it.
2. Manually merge `.github/copilot-instructions.md` and preserve the target project's existing rules.
3. Adjust `.github/embedded-project.yml`. Keep unknown values as `auto`; do not enter unconfirmed hardware facts.
4. When using `.project`, adjust `project.yml`, applicable rules, and Git policy. Maintain denied paths, branches, and checks as needed; do not define commit content through a path allowlist. Leave `automation.commit/push: false` until automatic-delivery conditions are confirmed, then enable them only for `auto`; this does not block user-confirmed commit/push. Never add a remote, URL, or target branch to policy.
5. Open the firmware repository root directly in VS Code and trust the workspace. Opening only its parent prevents automatic `.github` discovery.
6. Enable GitHub Copilot Chat and confirm that custom agents, prompt files, Agent Skills, and `agent/runSubagent` are available. Recursive subagents are not required.
7. Confirm in Chat Customizations/Diagnostics that all five agents, six prompts, and instructions load without errors, then run the Kit validator for `.project` references and Git policy.

The `agents` allowlists in the Orchestrator and BugResolver frontmatter may depend on Experimental custom-agent/subagent support in the target VS Code and GitHub Copilot environment. This kit does not claim an unverified minimum version; run Customizations/Diagnostics in the actual target environment and perform both a general delegation smoke test and a bug-resolution delegation smoke test to confirm that the allowlists are honored.

The repository intentionally has no overwriting installation script. Compare and merge directories during upgrades, especially the profile, `.project/` rules, global rules, and local prompt customizations.

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
- Git delivery: set Task Brief `Git Delivery` to only `none`, `commit`, `commit-and-push`, or `auto`. Every commit mode first reports per-file content plus the complete commit message and waits for explicit content confirmation; `confirm commit content` authorizes `commit`/`commit-and-push`, while only `auto` requires both `.project` automation switches and an additional current-fingerprint confirmation. A BugResolver may create the hook-protected local commit after its complete repair loop; push and auto remain with `EmbeddedDeveloper`. Selecting `auto` is not content confirmation: only a user-confirmed current fingerprint may produce `content_confirmation.status: CONFIRMED` plus `AUTO_COMMIT_AND_PUSH`.

### Safety and Permissions

- VS Code approval settings govern `execute` for BugResolver, EmbeddedDeveloper, and QualityReviewer. BugResolver runs only read-only diagnostics and symbolization; Reviewer runs only read-only Git, build/test audit, and static analysis.
- Flash, erase, fuse, reset, HIL, device power, release, and external deployment always require explicit human authorization. A command's presence in the profile is not authorization.
- A `.project` Git policy constrains work but is not authorization. BugResolver or EmbeddedDeveloper may use only `git add -- <task-paths>` to stage confirmed task paths explicitly; repository-wide staging is forbidden and every staged item enters the commit. Require the versioned hook before committing and use only `git commit` with `core.hooksPath=.githooks`; amend, `--no-verify`, hookless commit, and automatic `.git/config` changes are forbidden. Content fingerprints remain auto-only.
- DocKeeper uses the web only for official or vendor public sources and never uploads private source, logs, customer data, or credentials.
- Do not run write tasks concurrently in one checkout. Parallel writing may be considered only after one-task-per-worktree/branch isolation exists.
- Agents do not replace human code review, hardware verification, functional-safety assessment, or formal MISRA compliance tools.
- Skill scripts use exit code `0` for success, `2` for invalid input, `3` for insufficient evidence, and `4` for external-tool failure. `profile_gates.py` only plans/validates gate evidence and never executes profile commands; hardware never enters host gates.

### Validate the Kit

Install development dependencies and run static validation:

```sh
python -m pip install -r tests/agent-kit/requirements.txt
python .github/agent-kit/scripts/validate_customizations.py --root .
python -m unittest discover -s tests/agent-kit -p "test_*.py"
```

Build the host example:

```sh
cmake -S examples/minimal-firmware -B build/minimal-firmware
cmake --build build/minimal-firmware
ctest --test-dir build/minimal-firmware --output-on-failure
```

CI runs these checks on Windows and Ubuntu. Real interaction also requires the [VS Code Manual Smoke Test](tests/agent-kit/manual/vscode-smoke-test.md), covering discovery, project-constraint invocation, controlled Git delivery, automatic orchestration, missing documents, baseline failure, seeded-defect review, ELF mismatch, and hardware approval.

### Layout

```text
.github/
├── copilot-instructions.md
├── embedded-project.yml
├── agent-contracts.md
├── agents/                  # five business agents plus one hidden router
├── agent-kit/               # kit runtime and self-check scripts
├── instructions/            # C, bilingual, and kit configuration rules
├── prompts/                 # six thin slash entries
├── skills/                  # five on-demand workflows with deterministic scripts
└── workflows/validate.yml
.githooks/
└── commit-msg               # versioned, fail-closed commit-message gate
.project/
├── project.yml              # project constraint manifest and extension entry point
├── README.md                # bilingual usage guide
├── rules/                   # project-specific rules invoked by repository path
└── git/
    ├── delivery.yml         # automation, scope, safety, branch rules, and checks; no target
    └── commit.template      # strict commit message template
docs/                        # product documentation
tests/agent-kit/             # unit tests, fixtures, dependencies, and manual smoke test
examples/minimal-firmware/   # CMake/CTest + fake HAL
```

### Bilingual Rules

First-party Markdown in the README, `docs/`, `.github/`, and `.project/` uses:

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

Chat output is not forcibly bilingual. Before the first character of a new conversation's first response, the Agent performs Language Preflight: Latin-script natural-language words with no Han natural-language text require `en-US`, and identifiers such as Jira IDs never override that result. Progress updates, questions, Result Reports, and Next Actions preserve `Chat Language` across agents, the Router, and handoffs; buttons and generated bilingual prompts never switch it. For `en` or `en-*`, the Agent scans the complete draft before sending and discards/regenerates it if any agent-generated portion contains a Han-script character. Only clearly marked verbatim evidence may retain its original script. Chat `Dispatch Target` values use ASCII-only stable IDs such as `HANDOFF:QUALITY_REVIEWER`; bilingual button labels remain UI-only.

### Extension Principles

- Do not add a sixth agent casually for a new workflow; extend an existing role mode or add an on-demand skill first.
- Prompts provide manual entry and agent routing; complex checklists, templates, and scripts belong in skills.
- Maintain shared rules once and link them from agents and skills to avoid repeated context.
- Put project-specific rules under `.project/` and register them through the manifest. Use namespaced `extensions` for other structured integrations; preserve unknown extensions without executing them automatically.
- The kit fully supports VS Code only. GitHub cloud/CLI may ignore handoffs or VS Code-specific allowlists and are outside v1 acceptance.
