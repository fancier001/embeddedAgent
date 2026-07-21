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

若输入明确授权修复，切换到 `bug-resolution`，在闭环保留显式 `Git Delivery` 与 commit metadata。未选择交付时使用 `none` 防止提前写入；门禁通过后用 baseline、修改账本和真实 diff 生成精确 `Commit Content` 预览。推荐 `commit` 不构成授权，`commit-and-push`/`auto` 必须显式选择；选择 auto 仍不确认内容，必须显示 `Commit Content Confirmation: PENDING`，要求用户用当前 fingerprint `确认自动提交内容`。缺失或漂移时 `AUTO_DECIDE` 返回 `CONFIRM_COMMIT_CONTENT`，不得写 Git；只有 `content_confirmation.status: CONFIRMED` 才可自动 commit，之后保持自动 push。Jira 始终由用户提供，其余字段从证据生成；调整后重建确认。每次只生成一个结构化 Next Action；闭环后执行 `CLOSE → RESET → INTAKE`。

`Commit Content` 必须逐文件展示 Git state、增删统计、真实摘要、排除路径和 fingerprint，并标记 `Change Confirmation: PENDING`。用户认为修改过多时进入 `ADJUST_CHANGESET`，只调整本任务修改，重新执行受影响的验证、独立评审和交付确认；旧确认失效，最终收到“确认修改并提交”前不得写 Git。

每次结果生成唯一完整 Next Action。角色切换使用 `UI Route: NEXT_ACTION_BUTTON` 和当前 Agent 的精确基础按钮 Dispatch Target；方向确认、补证、Jira 和 commit/push 确认使用 `CURRENT_INPUT + NONE` 并提供可复制 Instruction；外部命令和终态分别使用 `EXTERNAL + NONE`、`NONE + NONE`。修复方向唯一且已确认时直接进入 `IMPLEMENT_FIX`，多个方向未决时才使用 `CONFIRM_DIRECTION`。统一按钮点击不代替输入或 Git 授权。所有交付模式在 `CONFIRM_COMMIT` 前必须记录 Documentation 为 `PASS` 或 `NOT_RUN — Not required: <reason>`，否则生成 `DOCUMENT_CHANGES`。

## English

Use the `bug-analysis` mode in the `BugResolver` system prompt and the Bug Analysis output contract in `.github/agent-contracts.md` for this input:

- `bug_input`: `${input:bug_input}`

When input is empty or usage context that could change direction is missing, perform `GUIDE_SYMPTOMS` first: emit the shared Usage Symptom Profile and ask unanswered high-information symptoms through one Usage Symptom Questions table, with at most five questions in the first set. Questions collect only user goal/scenario, operation sequence, expected/actual behavior, frequency/boundaries, and environment/impact/recovery. Allow `Unknown`, never mix these questions with Evidence Request, and do not repeat them. If symptoms could indicate multiple modules/root-cause paths, expected versus actual behavior is unclear, or inputs conflict, perform `CONFIRM_DIRECTION`: emit Current Understanding and Possible Directions. Do not trace deeply, confirm root cause, or invoke Developer before confirmation. Mark clear direction `NOT_REQUIRED` and continue.

Analysis is read-only by default: preserve the original error, and after direction is `CONFIRMED` or `NOT_REQUIRED`, emit the shared Problem Identification grounded in the Usage Symptom Profile, then establish environment, revision, reproduction, and baseline. Use the `search → read → execute` evidence flow to trace context, form hypotheses, and run the smallest safe validation. Add `fault-analysis` for crash, dump, ELF/MAP, or runtime-log evidence. When critical evidence is missing, search the repository and finish safe preliminary analysis before asking once for evidence artifacts through the shared Evidence Request table, then pause root-cause confirmation. Never request the same evidence again, invoke Developer, or present the most likely hypothesis as confirmed while the causal chain is incomplete.

If the input authorizes a fix, preserve explicit Git Delivery and metadata. Before delivery, use `none`; after gates pass, build an exact Commit Content preview from the baseline, ledger, and actual diff. A recommended commit is not authorization, and commit-and-push/auto require explicit selection. Selecting auto still does not confirm content: show `Commit Content Confirmation: PENDING` and require `confirm automatic commit content` with the current fingerprint. Missing or stale confirmation makes `AUTO_DECIDE` return `CONFIRM_COMMIT_CONTENT` with no Git write; only `content_confirmation.status: CONFIRMED` permits automatic commit, followed by automatic push. Jira is user-supplied and other fields come from evidence; adjustments regenerate confirmation. Emit one structured Next Action and close through `CLOSE → RESET → INTAKE`.

At `DELIVERY`, run `DETECT_COMMIT_SCOPE` and use a separate delivery Task Brief to create one Commit Delivery Confirmation with `commit` as the recommended default. Jira ID is always user-supplied. `commit-and-push` waits at `CONFIRM_PUSH`; failed automatic push emits `MANUAL_PUSH`.

`Commit Content` lists each file's Git state, added/deleted counts, truthful summary, excluded paths, and fingerprint, and marks `Change Confirmation: PENDING`. When the user says the change is too broad, enter `ADJUST_CHANGESET`, adjust only current-task work, and rerun affected verification, independent review, and delivery confirmation. Invalidate the old confirmation and perform no Git write before `confirm changes and commit`.

Every result emits one complete Next Action. Role transitions use `UI Route: NEXT_ACTION_BUTTON` with an exact current-agent base-button Dispatch Target. Direction confirmation, evidence, Jira, and commit/push confirmation use `CURRENT_INPUT + NONE` with a copy-ready Instruction; external and terminal states use `EXTERNAL + NONE` and `NONE + NONE`. Enter `IMPLEMENT_FIX` directly when one direction is confirmed; use `CONFIRM_DIRECTION` only while multiple directions remain. The unified-button click never substitutes for input or Git authorization. Before `CONFIRM_COMMIT` in every delivery mode, record Documentation as `PASS` or `NOT_RUN — Not required: <reason>`; otherwise emit `DOCUMENT_CHANGES`.
