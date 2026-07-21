---
name: analyze-bug
description: 理解错误、验证根因假设并输出证据化 Bug 分析 / Understand errors, test root-cause hypotheses, and report evidence-backed bug analysis
agent: BugResolver
argument-hint: Bug 描述、原始错误、复现步骤、是否修复及 Git Delivery / Bug description, error, reproduction, fix authorization, and Git Delivery
---

# Analyze Bug

> 中文：本文档采用固定双语结构。更新中文或英文内容时，必须同步更新另一部分，保持两部分语义一致。
>
> English: This document uses a fixed bilingual structure. When either the Chinese or English content is updated, the other section must be updated as well to keep both sections semantically aligned.

## 中文 / Chinese

使用 `BugResolver` 系统提示词中的 `bug-analysis` 模式和 `.github/agent-contracts.md` 的 Bug Analysis 输出契约处理以下输入：

- `bug_input`: `${input:bug_input}`

输入为空或缺少会影响方向的使用上下文时，先执行 `GUIDE_SYMPTOMS`：输出共享 `Usage Symptom Profile`，再用一张 `Usage Symptom Questions` 表集中询问尚未回答的高信息量现象，首轮最多 5 个。问题只采集用户目标/场景、操作序列、预期/实际、频率/边界和环境/影响/恢复，允许回答 `Unknown`，不得与 `Evidence Request` 混用或重复提问。现象可能指向多个模块/根因路径、预期/实际不清或输入矛盾时执行 `CONFIRM_DIRECTION`，输出 `Current Understanding` 和 `Possible Directions`；确认前不得深入追踪、确认根因或调用 Developer。方向明确时标记 `NOT_REQUIRED` 并继续。

默认只读分析：保留原始错误，方向为 `CONFIRMED` 或 `NOT_REQUIRED` 后输出引用 Usage Symptom Profile 的共享 `Problem Identification`，再核对环境、revision、复现和 baseline；使用 `search → read → execute` 的证据流程追踪上下文、建立假设并运行最小安全验证。存在 crash、dump、ELF/MAP 或运行日志时同时启用 `fault-analysis` 辅助模式。关键证据缺失时，先搜索仓库并完成安全初判，再用一张共享 `Evidence Request` 表集中索取证据产物并暂停根因确认；不得重复索取、调用 Developer 或把最高概率假设写成已确认根因。

若输入明确授权修复，切换到 `bug-resolution`，提取并在整个修复闭环保留显式 `Git Delivery` 与 commit metadata。输入未提供交付选择时，交付前 Task Brief 使用 `Git Delivery: none` 防止提前写入；门禁全部通过后的 `DELIVERY` 先用 `Task Change Baseline`、Developer 修改账本和当前真实 diff 执行 `DETECT_COMMIT_SCOPE`，再生成一次包含精确 `Commit Content` 的 `Commit Delivery Confirmation`，建议 `commit` 为待确认默认值。推荐值不构成授权，`commit-and-push`/`auto` 必须显式选择。Jira ID 始终由用户主动提供；其余 commit 字段由 Agent 根据项目、根因、真实 diff、测试和评审证据生成完整预览，只请求用户确认或修正。Project 仅在仍为 `auto` 且无法唯一解析时额外询问。未确认时返回 `BLOCKED`，不得写 Git或生成占位 commit；确认后用携带基线、修改账本和确认内容的单独交付 Task Brief 调用 `EmbeddedDeveloper`。`commit-and-push` 在 commit 后输出 `CONFIRM_PUSH` 并等待独立确认；`auto` 进入 `AUTO_DECIDE` 并保持自动 push，失败时输出 `MANUAL_PUSH`。每次结果只生成一个结构化 `Next Action`；闭环后执行 `CLOSE → RESET → INTAKE` 并请求新问题。

`Commit Content` 必须逐文件展示 Git state、增删统计、真实摘要、排除路径和 fingerprint，并标记 `Change Confirmation: PENDING`。用户认为修改过多时进入 `ADJUST_CHANGESET`，只调整本任务修改，重新执行受影响的验证、独立评审和交付确认；旧确认失效，最终收到“确认修改并提交”前不得写 Git。

每次结果按共享优先级从当前状态动态生成唯一规范 `Action` 和 `UI Route`。方向确认、补证、Jira 和 commit/push 确认走 `CURRENT_INPUT`；需要人工角色切换时只指向当前 Agent frontmatter 中存在的精确 `HANDOFF` 标签；无需输入且已授权时用 `AGENT_CONTINUE` 同轮继续；外部命令和终态分别使用 `EXTERNAL`、`NONE`。所有交付模式在 `CONFIRM_COMMIT` 前必须将 Documentation 记录为 `PASS`，或 `NOT_RUN — Not required: <reason>`；否则下一动作是 `DOCUMENT_CHANGES`，不得进入提交预览。

## English

Use the `bug-analysis` mode in the `BugResolver` system prompt and the Bug Analysis output contract in `.github/agent-contracts.md` for this input:

- `bug_input`: `${input:bug_input}`

When input is empty or usage context that could change direction is missing, perform `GUIDE_SYMPTOMS` first: emit the shared Usage Symptom Profile and ask unanswered high-information symptoms through one Usage Symptom Questions table, with at most five questions in the first set. Questions collect only user goal/scenario, operation sequence, expected/actual behavior, frequency/boundaries, and environment/impact/recovery. Allow `Unknown`, never mix these questions with Evidence Request, and do not repeat them. If symptoms could indicate multiple modules/root-cause paths, expected versus actual behavior is unclear, or inputs conflict, perform `CONFIRM_DIRECTION`: emit Current Understanding and Possible Directions. Do not trace deeply, confirm root cause, or invoke Developer before confirmation. Mark clear direction `NOT_REQUIRED` and continue.

Analysis is read-only by default: preserve the original error, and after direction is `CONFIRMED` or `NOT_REQUIRED`, emit the shared Problem Identification grounded in the Usage Symptom Profile, then establish environment, revision, reproduction, and baseline. Use the `search → read → execute` evidence flow to trace context, form hypotheses, and run the smallest safe validation. Add `fault-analysis` for crash, dump, ELF/MAP, or runtime-log evidence. When critical evidence is missing, search the repository and finish safe preliminary analysis before asking once for evidence artifacts through the shared Evidence Request table, then pause root-cause confirmation. Never request the same evidence again, invoke Developer, or present the most likely hypothesis as confirmed while the causal chain is incomplete.

If the input explicitly authorizes a fix, switch to `bug-resolution` and preserve explicit `Git Delivery` plus commit metadata throughout the repair loop. When no delivery choice is supplied, use `Git Delivery: none` in pre-delivery Task Briefs to prevent early writes. After all gates pass, use `Task Change Baseline`, the Developer change ledger, and current actual diff for `DETECT_COMMIT_SCOPE`, then create one `Commit Delivery Confirmation` with exact `Commit Content` in `DELIVERY` and propose `commit` as the recommended default pending confirmation. A recommendation is not authorization; `commit-and-push`/`auto` require an explicit choice. Jira ID is always user-supplied. Generate every other commit field from the project, root cause, actual diff, tests, and review evidence, show one complete preview, and ask only for confirmation or corrections. Ask for Project additionally only when it remains `auto` and cannot be resolved uniquely. Without confirmation return `BLOCKED`; never write Git or create a placeholder commit. After confirmation invoke `EmbeddedDeveloper` with a separate delivery Task Brief carrying the baseline, change ledger, and confirmed content. `commit-and-push` emits `CONFIRM_PUSH` after commit and waits for separate confirmation; `auto` enters `AUTO_DECIDE`, keeps automatic push, and emits `MANUAL_PUSH` on failure. Emit exactly one structured `Next Action` per result; after closure run `CLOSE → RESET → INTAKE` and request a new issue.

`Commit Content` lists each file's Git state, added/deleted counts, truthful summary, excluded paths, and fingerprint, and marks `Change Confirmation: PENDING`. When the user says the change is too broad, enter `ADJUST_CHANGESET`, adjust only current-task work, and rerun affected verification, independent review, and delivery confirmation. Invalidate the old confirmation and perform no Git write before `confirm changes and commit`.

Every result dynamically generates exactly one canonical `Action` and `UI Route` from the current state using the shared priority. Direction confirmation, evidence, Jira, and commit/push confirmation use `CURRENT_INPUT`; a manual role transition names only an exact `HANDOFF` label present in the current agent frontmatter; an authorized no-input action uses `AGENT_CONTINUE` and continues in the same turn; external commands and terminal states use `EXTERNAL` and `NONE`. Before `CONFIRM_COMMIT` in every delivery mode, record Documentation as `PASS` or `NOT_RUN — Not required: <reason>`; otherwise the next action is `DOCUMENT_CHANGES` and no commit preview is allowed.
