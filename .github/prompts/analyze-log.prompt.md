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

若日志输入明确授权修复，BugResolver 必须在修复闭环中保留显式 `Git Delivery` 和 commit metadata。未提供交付选择时，交付前 Task Brief 使用 `Git Delivery: none` 防止提前写入；全部门禁通过后在 `DELIVERY` 先用 `Task Change Baseline`、Developer 修改账本和当前真实 diff 执行 `DETECT_COMMIT_SCOPE`，再生成一次包含精确 `Commit Content` 的 `Commit Delivery Confirmation`，建议 `commit` 为待确认默认值。推荐值不构成授权，`commit-and-push`/`auto` 必须显式选择。Jira ID 始终由用户主动提供；其余 commit 字段由 Agent 根据项目、根因、真实 diff、测试和评审证据生成完整预览，只请求确认或修正。未确认时返回 `BLOCKED`，不得写 Git 或静默关闭；确认后用携带基线、修改账本和确认内容的单独交付 Task Brief 调用 `EmbeddedDeveloper`。`commit-and-push` 在 commit 后输出 `CONFIRM_PUSH` 并等待独立确认；`auto` 进入 `AUTO_DECIDE` 并保持自动 push，失败时输出 `MANUAL_PUSH`。每次结果只生成一个结构化 `Next Action`；闭环后执行 `CLOSE → RESET → INTAKE` 并请求新问题。

`Commit Content` 必须逐文件展示 Git state、增删统计、真实摘要、排除路径和 fingerprint，并标记 `Change Confirmation: PENDING`。用户认为修改过多时进入 `ADJUST_CHANGESET`，只调整本任务修改，重新执行受影响的验证、独立评审和交付确认；旧确认失效，最终收到“确认修改并提交”前不得写 Git。

每次结果按共享优先级从当前状态动态生成唯一规范 `Action` 和 `UI Route`。方向确认、补证、Jira 和 commit/push 确认走 `CURRENT_INPUT`；需要人工角色切换时只指向当前 Agent frontmatter 中存在的精确 `HANDOFF` 标签；无需输入且已授权时用 `AGENT_CONTINUE` 同轮继续；外部命令和终态分别使用 `EXTERNAL`、`NONE`。所有交付模式在 `CONFIRM_COMMIT` 前必须将 Documentation 记录为 `PASS`，或 `NOT_RUN — Not required: <reason>`；否则下一动作是 `DOCUMENT_CHANGES`，不得进入提交预览。

## English

Use the [firmware-log-analysis](../skills/firmware-log-analysis/SKILL.md) workflow with this input:

- `log_input`: `${input:log_input}`

Whether or not a log is already supplied, perform the shared `GUIDE_SYMPTOMS` first and create a Usage Symptom Profile. When usage symptoms that could change direction are missing, ask them together through Usage Symptom Questions, with at most five questions in the first set. A log does not replace user goal, operation sequence, expected/actual behavior, frequency/boundaries, or impact/recovery. The user may answer `Unknown`, and non-critical unknowns do not block. When symptoms have multiple directions or conflict, perform `CONFIRM_DIRECTION`, emit Current Understanding and Possible Directions, and pause deep log correlation, root-cause confirmation, and Developer delegation.

After direction is `CONFIRMED` or `NOT_REQUIRED`, emit the shared Problem Identification grounded in the Usage Symptom Profile and apply the project profile's bare-metal, RTOS, module-SDK, Embedded-Linux, or hybrid log workflow. When input is empty or critical evidence is missing, search the repository and finish safe preliminary analysis before requesting log content/a valid path and the smallest evidence artifacts once through the shared Evidence Request table. Never mix usage-symptom questions into that table, and do not confirm root cause or invoke Developer until evidence arrives. This prompt only adapts input and routing; execute the complete workflow defined by the Skill, project profile, and shared contract.

If the log input explicitly authorizes a fix, BugResolver preserves explicit `Git Delivery` and commit metadata throughout the repair loop. When no delivery choice is supplied, pre-delivery Task Briefs use `Git Delivery: none` to prevent early writes. After all gates pass, `DELIVERY` uses `Task Change Baseline`, the Developer change ledger, and current actual diff for `DETECT_COMMIT_SCOPE`, then creates one `Commit Delivery Confirmation` with exact `Commit Content` and proposes `commit` as the recommended default pending confirmation. A recommendation is not authorization; `commit-and-push`/`auto` require an explicit choice. Jira ID is always user-supplied. Generate every other commit field from the project, root cause, actual diff, tests, and review evidence, then ask only for confirmation or corrections. Without confirmation return `BLOCKED`; never write Git or close silently. After confirmation invoke `EmbeddedDeveloper` with a separate delivery Task Brief carrying the baseline, change ledger, and confirmed content. `commit-and-push` emits `CONFIRM_PUSH` after commit and waits for separate confirmation; `auto` enters `AUTO_DECIDE`, keeps automatic push, and emits `MANUAL_PUSH` on failure. Emit exactly one structured `Next Action` per result; after closure run `CLOSE → RESET → INTAKE` and request a new issue.

`Commit Content` lists each file's Git state, added/deleted counts, truthful summary, excluded paths, and fingerprint, and marks `Change Confirmation: PENDING`. When the user says the change is too broad, enter `ADJUST_CHANGESET`, adjust only current-task work, and rerun affected verification, independent review, and delivery confirmation. Invalidate the old confirmation and perform no Git write before `confirm changes and commit`.

Every result dynamically generates exactly one canonical `Action` and `UI Route` from the current state using the shared priority. Direction confirmation, evidence, Jira, and commit/push confirmation use `CURRENT_INPUT`; a manual role transition names only an exact `HANDOFF` label present in the current agent frontmatter; an authorized no-input action uses `AGENT_CONTINUE` and continues in the same turn; external commands and terminal states use `EXTERNAL` and `NONE`. Before `CONFIRM_COMMIT` in every delivery mode, record Documentation as `PASS` or `NOT_RUN — Not required: <reason>`; otherwise the next action is `DOCUMENT_CHANGES` and no commit preview is allowed.
