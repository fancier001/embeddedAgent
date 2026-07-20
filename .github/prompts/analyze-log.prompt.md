---
name: analyze-log
description: 分析嵌入式运行、串口、崩溃或异常日志 / Analyze embedded runtime, serial, crash, or exception logs
agent: BugResolver
argument-hint: 日志或 dump/ELF/MAP、是否修复及 Git Delivery / Logs or dump/ELF/MAP, fix authorization, and Git Delivery
---

# Analyze Log

> 中文：本文档采用固定双语结构。更新中文或英文内容时，必须同步更新另一部分，保持两部分语义一致。
>
> English: This document uses a fixed bilingual structure. When either the Chinese or English content is updated, the other section must be updated as well to keep both sections semantically aligned.

## 中文 / Chinese

使用 [firmware-log-analysis](../skills/firmware-log-analysis/SKILL.md) 工作流处理以下输入：

- `log_input`: `${input:log_input}`

无论是否已提供日志，都先执行共享 `GUIDE_SYMPTOMS`：生成 `Usage Symptom Profile`；缺少会影响方向的使用现象时，用 `Usage Symptom Questions` 集中询问，首轮最多 5 个。日志不能代替用户目标、操作序列、预期/实际、频率/边界和影响/恢复。用户可回答 `Unknown`，非关键未知项不阻塞；现象存在多方向或矛盾时执行 `CONFIRM_DIRECTION`，输出 `Current Understanding` 与 `Possible Directions`，确认前暂停深入日志关联、根因确认和 Developer 委派。

方向为 `CONFIRMED` 或 `NOT_REQUIRED` 后，输出引用 Usage Symptom Profile 的共享 `Problem Identification`，再覆盖项目画像对应的 bare-metal、RTOS、模组 SDK、Embedded Linux 或混合系统日志流程。输入为空或关键证据缺失时，先搜索仓库并完成安全初判，再用共享 `Evidence Request` 表一次性索取日志/有效路径和最小证据产物；不得把使用现象问题混入该表，在补充前不确认根因或调用 Developer。Prompt 仅负责输入与路由；执行 Skill、项目画像和共享契约定义的完整流程。

若日志输入明确授权修复，BugResolver 必须在修复闭环中保留显式 `Git Delivery` 和 commit metadata。未提供交付选择时，交付前 Task Brief 使用 `Git Delivery: none` 防止提前写入；全部门禁通过后在 `DELIVERY` 生成一次 `Commit Delivery Confirmation`，建议 `commit` 为待确认默认值。推荐值不构成授权，`commit-and-push`/`auto` 必须显式选择。Jira ID 始终由用户主动提供；其余 commit 字段由 Agent 根据项目、根因、真实 diff、测试和评审证据生成完整预览，只请求确认或修正。未确认时返回 `BLOCKED`，不得写 Git 或静默关闭；确认后用单独交付 Task Brief 调用 `EmbeddedDeveloper`，`auto` 进入 `AUTO_DECIDE`。

## English

Use the [firmware-log-analysis](../skills/firmware-log-analysis/SKILL.md) workflow with this input:

- `log_input`: `${input:log_input}`

Whether or not a log is already supplied, perform the shared `GUIDE_SYMPTOMS` first and create a Usage Symptom Profile. When usage symptoms that could change direction are missing, ask them together through Usage Symptom Questions, with at most five questions in the first set. A log does not replace user goal, operation sequence, expected/actual behavior, frequency/boundaries, or impact/recovery. The user may answer `Unknown`, and non-critical unknowns do not block. When symptoms have multiple directions or conflict, perform `CONFIRM_DIRECTION`, emit Current Understanding and Possible Directions, and pause deep log correlation, root-cause confirmation, and Developer delegation.

After direction is `CONFIRMED` or `NOT_REQUIRED`, emit the shared Problem Identification grounded in the Usage Symptom Profile and apply the project profile's bare-metal, RTOS, module-SDK, Embedded-Linux, or hybrid log workflow. When input is empty or critical evidence is missing, search the repository and finish safe preliminary analysis before requesting log content/a valid path and the smallest evidence artifacts once through the shared Evidence Request table. Never mix usage-symptom questions into that table, and do not confirm root cause or invoke Developer until evidence arrives. This prompt only adapts input and routing; execute the complete workflow defined by the Skill, project profile, and shared contract.

If the log input explicitly authorizes a fix, BugResolver preserves explicit `Git Delivery` and commit metadata throughout the repair loop. When no delivery choice is supplied, pre-delivery Task Briefs use `Git Delivery: none` to prevent early writes. After all gates pass, `DELIVERY` creates one `Commit Delivery Confirmation` and proposes `commit` as the recommended default pending confirmation. A recommendation is not authorization; `commit-and-push`/`auto` require an explicit choice. Jira ID is always user-supplied. Generate every other commit field from the project, root cause, actual diff, tests, and review evidence, then ask only for confirmation or corrections. Without confirmation return `BLOCKED`; never write Git or close silently. After confirmation invoke `EmbeddedDeveloper` with a separate delivery Task Brief; `auto` enters `AUTO_DECIDE`.
