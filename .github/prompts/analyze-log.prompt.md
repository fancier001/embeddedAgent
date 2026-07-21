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

若日志输入明确授权修复，BugResolver 必须保留显式 `Git Delivery` 和 commit metadata。未选择交付时使用 `none`；门禁通过后根据 baseline、修改账本和真实 diff 生成精确 Commit Content。`commit-and-push`/`auto` 必须显式选择，但选择 auto 不确认内容：必须显示 `Commit Content Confirmation: PENDING` 并要求用户用当前 fingerprint `确认自动提交内容`。缺失或漂移时 `AUTO_DECIDE` 返回 `CONFIRM_COMMIT_CONTENT`，不得写 Git；只有 `content_confirmation.status: CONFIRMED` 才可自动 commit，之后保持自动 push。Jira 由用户提供，其余字段从证据生成；每次结果只生成一个结构化 Next Action，闭环后执行 `CLOSE → RESET → INTAKE`。

`Commit Content` 必须逐文件展示 Git state、增删统计、真实摘要、排除路径和 fingerprint，并标记 `Change Confirmation: PENDING`。用户认为修改过多时进入 `ADJUST_CHANGESET`，只调整本任务修改，重新执行受影响的验证、独立评审和交付确认；旧确认失效，最终收到“确认修改并提交”前不得写 Git。

每次结果生成唯一完整 Next Action。角色切换使用 `UI Route: NEXT_ACTION_BUTTON` 和当前 Agent 的精确基础按钮 Dispatch Target；方向确认、补证、Jira 和 commit/push 确认使用 `CURRENT_INPUT + NONE` 并提供可复制 Instruction；外部命令和终态分别使用 `EXTERNAL + NONE`、`NONE + NONE`。修复方向唯一且已确认时直接进入 `IMPLEMENT_FIX`，多个方向未决时才使用 `CONFIRM_DIRECTION`。统一按钮点击不代替输入或 Git 授权。所有交付模式在 `CONFIRM_COMMIT` 前必须记录 Documentation 为 `PASS` 或 `NOT_RUN — Not required: <reason>`，否则生成 `DOCUMENT_CHANGES`。

## English

Use the [firmware-log-analysis](../skills/firmware-log-analysis/SKILL.md) workflow with this input:

- `log_input`: `${input:log_input}`

Whether or not a log is already supplied, perform the shared `GUIDE_SYMPTOMS` first and create a Usage Symptom Profile. When usage symptoms that could change direction are missing, ask them together through Usage Symptom Questions, with at most five questions in the first set. A log does not replace user goal, operation sequence, expected/actual behavior, frequency/boundaries, or impact/recovery. The user may answer `Unknown`, and non-critical unknowns do not block. When symptoms have multiple directions or conflict, perform `CONFIRM_DIRECTION`, emit Current Understanding and Possible Directions, and pause deep log correlation, root-cause confirmation, and Developer delegation.

After direction is `CONFIRMED` or `NOT_REQUIRED`, emit the shared Problem Identification grounded in the Usage Symptom Profile and apply the project profile's bare-metal, RTOS, module-SDK, Embedded-Linux, or hybrid log workflow. When input is empty or critical evidence is missing, search the repository and finish safe preliminary analysis before requesting log content/a valid path and the smallest evidence artifacts once through the shared Evidence Request table. Never mix usage-symptom questions into that table, and do not confirm root cause or invoke Developer until evidence arrives. This prompt only adapts input and routing; execute the complete workflow defined by the Skill, project profile, and shared contract.

If the log input authorizes a fix, BugResolver preserves explicit Git Delivery and commit metadata. Use `none` before delivery; after gates pass, build exact Commit Content from the baseline, ledger, and actual diff. Commit-and-push/auto require explicit selection, but selecting auto does not confirm content: show `Commit Content Confirmation: PENDING` and require `confirm automatic commit content` with the current fingerprint. Missing or stale confirmation makes `AUTO_DECIDE` return `CONFIRM_COMMIT_CONTENT` with no Git write; only `content_confirmation.status: CONFIRMED` permits automatic commit, followed by automatic push. Jira is user-supplied and other fields come from evidence. Emit one structured Next Action and close through `CLOSE → RESET → INTAKE`.

At `DELIVERY`, run `DETECT_COMMIT_SCOPE` and use a separate delivery Task Brief to create one Commit Delivery Confirmation with `commit` as the recommended default. Jira ID is always user-supplied. `commit-and-push` waits at `CONFIRM_PUSH`; failed automatic push emits `MANUAL_PUSH`.

`Commit Content` lists each file's Git state, added/deleted counts, truthful summary, excluded paths, and fingerprint, and marks `Change Confirmation: PENDING`. When the user says the change is too broad, enter `ADJUST_CHANGESET`, adjust only current-task work, and rerun affected verification, independent review, and delivery confirmation. Invalidate the old confirmation and perform no Git write before `confirm changes and commit`.

Every result emits one complete Next Action. Role transitions use `UI Route: NEXT_ACTION_BUTTON` with an exact current-agent base-button Dispatch Target. Direction confirmation, evidence, Jira, and commit/push confirmation use `CURRENT_INPUT + NONE` with a copy-ready Instruction; external and terminal states use `EXTERNAL + NONE` and `NONE + NONE`. Enter `IMPLEMENT_FIX` directly when one direction is confirmed; use `CONFIRM_DIRECTION` only while multiple directions remain. The unified-button click never substitutes for input or Git authorization. Before `CONFIRM_COMMIT` in every delivery mode, record Documentation as `PASS` or `NOT_RUN — Not required: <reason>`; otherwise emit `DOCUMENT_CHANGES`.
