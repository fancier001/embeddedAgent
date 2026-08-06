# Project-Level Policy

> 中文：本文档采用固定双语结构。更新中文或英文内容时，必须同步更新另一部分，保持两部分语义一致。
>
> English: This document uses a fixed bilingual structure. When either the Chinese or English content is updated, the other section must be updated as well to keep both sections semantically aligned.

## 中文 / Chinese

### 目录职责

`.project/` 与 `.github/` 同级，保存目标仓库自己的路径规则、代码规范和 Git 交付策略。`.project/project.yml` 是唯一入口；未注册文件不会自动成为 Agent 指令，`extensions` 中的未知数据只保留、不执行。

该目录对非 Git 工作是可选增强。目标仓库没有 `.project/` 时，Agent Kit 可沿用已有工程事实和项目画像完成分析或开发，但任何 Git Delivery 都返回 `BLOCKED / PROJECT_POLICY_REQUIRED`。目录一旦存在，清单、引用和 Git policy 必须通过严格校验。

### 规则调用

Agent 将 Task Brief 范围和真实 diff 与每条规则的 `applies_to` 匹配。适用且 `required: true` 的规则缺失时返回 `BLOCKED`。具有执行权限的角色和 CI 使用统一只读工具：

```sh
python .github/agent-kit/scripts/project_policy.py rules --root . \
  --path examples/minimal-firmware/src/status_led.c
```

重复 `--path` 可解析多个路径，`--all` 用于配置审计。工具仅输出 JSON，不执行规则或 Git 写操作。

### Commit 模板

`.project/git/commit.template` 是仓库内权威模板，运行时不依赖外部磁盘。首行格式为 `<Project><Function block>: <Summary>`，正文严格使用模板中的英文键和顺序。允许连续填写多个 `<Jira ID>:` 行；测试步骤或理由写在对应字段之后的缩进行中。

Bug 修复交付默认生成 `Commit Delivery Confirmation`：建议 `commit` 为待确认默认值，但不构成写入授权。Jira ID 始终由用户主动提供且不得推断；除无法解析的 Project 外，其余字段由 Agent 根据 manifest、根因、真实 diff、测试/构建、独立评审和文档证据生成。所有交付模式确认前必须将 Documentation 记录为 `PASS` 或 `NOT_RUN — Not required: <reason>`。用户确认或修正完整预览后才可创建消息文件；动态 `Next Action` 使用 `UI Route: CURRENT_INPUT`、`Dispatch Target: NONE` 和可直接复制的 `Instruction`，`commit-and-push`/`auto` 必须显式选择。点击 `执行下一步 / Next Action` 只会重显指令，不构成 commit 或 push 确认。

AI 实质参与代码生成、检查、重构、测试或文档时填写 `Y` 和一个真实主要场景/详情；完全未参与时精确填写 `<AI-Tool-Used>: N`、`<AI-Tool-Scenario>: /`、`<AI-Tool-Detail>: /`。validator 仍兼容冒号后的可选空格，但拒绝 AI=`N` 时使用 `N/A`、空值或实际使用内容。

确认发生在当前执行交付的 BugResolver 或 EmbeddedDeveloper 会话中。Agent 先反馈逐文件内容和将原样交给 Git 的完整 commit message，并标记 `Commit Content Confirmation: PENDING`。用户核对后在当前输入框明确回复 `确认提交内容`，Agent 才执行 `STAGE` 和 `COMMIT`；也可回复 `调整修改: <要求>` 进入 `ADJUST_CHANGESET` 和重新确认。模式选择、Jira、按钮点击或笼统要求提交不构成内容确认；文件、diff、范围或消息漂移会使确认失效。

一次性交付确认选择 `commit-and-push` 或 `auto` 时，同时授权精确内容的 commit 和随后一次普通非 force push，不再生成 `CONFIRM_PUSH`。`auto` 在 commit 前仍使用当前 fingerprint 防止内容漂移；缺失或漂移时预检返回 `CONFIRM_COMMIT_CONTENT`，不得暂存或提交。push 失败保留本地 commit、不自动重试，并输出 `MANUAL_PUSH` 与最近一次安全解析 remote/ref 对应的非 force 命令。

`commit-msg` hook 在 Git 创建 commit 前内部执行以下校验；Agent 不再额外预检：

```sh
python .github/agent-kit/scripts/project_policy.py message \
  --root . --file <completed-message-file>
```

BugResolver 或 EmbeddedDeveloper 只可运行 `git add -- <task-paths>` 显式暂存已确认任务路径，禁止全仓库暂存。Agent 不修改 `.git/config`，而是在每次提交命令中临时强制 `core.hooksPath=.githooks`。

### Git 交付

`.project/git/delivery.yml` 的 `workflow` 固定精简模式：`new-or-worsened` 增量诊断、`risk-based` 独立评审、`impact-based` 文档和 `once` 一次性交付确认。该文件还定义自动化开关、排除路径、提交字段、分支规则和检查命令。commit 内容由本次任务的初始 Git 基线、修改账本和当前真实 diff 检测，不由 YAML 路径白名单决定；旧 `scope.allowed_paths` 仅为兼容字段且不参与筛选。`denied_paths` 仍可排除构建或生成产物。policy 禁止保存 remote、URL 或目标 ref；push 目标只能从当前项目的本地 `.git` 配置读取。

Task Brief 的 `Git Delivery` 只接受 `none`、`commit`、`commit-and-push`、`auto`。一次 `CONFIRM_COMMIT` 同时确认精确内容和所选模式；选择 `commit-and-push` 时包含一次普通 push 授权，不受关闭的 automation 开关阻塞。只有 `auto` 要求两个 automation 开关同时启用。Task Brief 不得提供 remote、URL、目标分支或 refspec。

普通提交的范围由 `DETECT_COMMIT_SCOPE` 根据任务基线、修改账本和真实 diff 展示，最终确认后由 Agent 显式暂存。所有 staged 内容都会进入本次 commit，因此调用入口前必须核对完整 staged 路径和 diff，并排除无关 staged 文件。`fingerprint` 只用于 `auto` 的内容确认与漂移检测；普通 commit 不依赖 fingerprint 或 commit `git-plan`。用户可通过 `ADJUST_CHANGESET` 要求删减，调整后必须重新验证、独立评审和确认。

```sh
python .github/agent-kit/scripts/project_policy.py git-plan \
  --root . --operation push --delivery commit-and-push

python .github/agent-kit/scripts/project_policy.py git-plan \
  --root . --operation auto --delivery auto \
  --message-file <outside-repository-temp-file> --path <repair-file> \
  --expected-content-fingerprint <confirmed-fingerprint>

git add -- <confirmed-task-path>...

PROJECT_POLICY_PYTHON=<current-python> \
git -c core.hooksPath=.githooks commit \
  --file <message-file> --cleanup=verbatim
```

`project_policy.py git-plan` 只读，并继续服务于 `auto` 与 push。`commit.checks` 由 Agent 的 `CHECK_GATES` 阶段执行。提交前必须确认 `.githooks/commit-msg` 存在且在 Git Bash/Linux 可执行；hook 是唯一消息门禁，并调用 `project_policy.py message`。禁止未带版本化 hook 的 `git commit`、amend 或 `--no-verify`。

push 预检只用 `git config --local --no-includes` 读取当前分支的 `branch.<name>.remote`、`branch.<name>.merge` 及唯一 `remote.<name>.pushurl`（缺失时唯一 `url`），并通过 Git dir/common dir 兼容 linked worktree。输出包含脱敏 URL 和 fingerprint；实际 push 前必须带 `--expected-fingerprint` 再次预检。实际 push 在同一 local-only、禁用 global/system/env config 注入的 Git 环境中仅执行 `git -C <root> push <resolved-remote> HEAD:<resolved-remote-ref>`。禁止 force、`push -u`、自定义 refspec、删除远端分支、自动修改 `.git/config` 或用未提交 policy 自我授权。

auto 预检在无 diff 时返回 `NO_DELIVERY`；完整消息缺必填 metadata 时返回 `BLOCKED`；未传入确认 fingerprint 或内容漂移时返回 `CONFIRM_COMMIT_CONTENT` 和当前 `commit_content`，Agent 不运行任何 Git 写操作并重新请求确认；其余写入前条件不足时返回 `OUTPUT_COMMIT_MESSAGE`。仅当 `content_confirmation.status: CONFIRMED` 且决策为 `AUTO_COMMIT_AND_PUSH` 时可继续：index 初始必须为空，HEAD 必须等于本地 upstream tracking ref，工作树必须只包含修复路径；新 commit 后使用首次 push fingerprint 和 `--expected-commit <SHA>` 二次预检，outgoing commits 必须只有该 SHA。若随后 push 失败，保留本地 commit 并报告 SHA，不回滚。消息临时文件必须放在仓库外，避免成为无关 dirty 文件。

## English

### Directory Responsibility

`.project/` is a sibling of `.github/` and stores target-repository path rules, coding conventions, and Git delivery policy. `.project/project.yml` is the only entry point. Unregistered files do not automatically become agent instructions, and unknown `extensions` data is preserved without execution.

The directory is optional for non-Git work. When a target repository has no `.project/`, the Agent Kit may continue analysis or development with existing repository facts and the project profile, but every Git Delivery returns `BLOCKED / PROJECT_POLICY_REQUIRED`. Once the directory exists, its manifest, references, and Git policy are validated strictly.

### Rule Invocation

Agents match the Task Brief scope and actual diff against each rule's `applies_to`. A missing applicable rule with `required: true` returns `BLOCKED`. Executable roles and CI use the unified read-only tool:

```sh
python .github/agent-kit/scripts/project_policy.py rules --root . \
  --path examples/minimal-firmware/src/status_led.c
```

Repeat `--path` for multiple paths, or use `--all` for configuration audit. The tool emits JSON only and never executes a rule or Git write operation.

### Commit Template

`.project/git/commit.template` is the repository-owned canonical template and has no runtime dependency on an external drive. Its subject is `<Project><Function block>: <Summary>`, and its body uses the template's English keys in strict order. Consecutive `<Jira ID>:` rows are allowed; indented rows following a test field contain its steps or rationale.

Bug-fix delivery creates a `Commit Delivery Confirmation` and proposes `commit` as the recommended default pending confirmation; it does not authorize a write. Jira ID is always user-supplied and never inferred. Except for a Project identity that cannot be resolved, the agent generates every other field from the manifest, root cause, actual diff, test/build evidence, independent review, and documentation. Every delivery mode records Documentation as `PASS` or `NOT_RUN — Not required: <reason>` before confirmation. It creates the message file only after the user confirms or corrects the complete preview; the dynamic `Next Action` uses `UI Route: CURRENT_INPUT`, `Dispatch Target: NONE`, and a copy-ready `Instruction`. `commit-and-push`/`auto` require an explicit choice. Clicking `执行下一步 / Next Action` only repeats the instruction and does not confirm a commit or push.

Use AI=`Y` with one truthful primary scenario/detail when AI materially participated in code generation, inspection, refactoring, tests, or documentation. When AI did not participate at all, use exactly `<AI-Tool-Used>: N`, `<AI-Tool-Scenario>: /`, and `<AI-Tool-Detail>: /`. The validator remains compatible with optional whitespace after the colon but rejects `N/A`, empty values, or usage content when AI=`N`.

Confirmation occurs in the current BugResolver or EmbeddedDeveloper conversation that performs delivery. The Agent first reports per-file content and the complete commit message exactly as Git will receive it, marked `Commit Content Confirmation: PENDING`. After reviewing both, the user explicitly replies `confirm commit content` in the current input, and only then does the Agent run `STAGE` and `COMMIT`. The user may instead reply `adjust changes: <request>` to enter `ADJUST_CHANGESET` and a new confirmation. Mode selection, Jira, button clicks, and generic commit requests are not content confirmation; file, diff, scope, or message drift invalidates confirmation.

A one-time delivery confirmation selecting `commit-and-push` or `auto` authorizes the commit of the exact content and one subsequent ordinary non-force push; it never emits `CONFIRM_PUSH`. Auto still uses the current fingerprint before commit to detect content drift. Missing or stale confirmation returns `CONFIRM_COMMIT_CONTENT` without staging or committing. A failed push preserves the local commit without automatic retry and emits `MANUAL_PUSH` with the non-force command for the most recently safe resolved remote/ref.

The `commit-msg` hook runs this validation internally before Git creates a commit; the Agent does not prevalidate it separately:

```sh
python .github/agent-kit/scripts/project_policy.py message \
  --root . --file <completed-message-file>
```

BugResolver or EmbeddedDeveloper may run only `git add -- <task-paths>` to stage confirmed task paths explicitly; repository-wide staging is forbidden. An Agent does not change `.git/config`; every commit command temporarily forces `core.hooksPath=.githooks`.

### Git Delivery

The `workflow` section of `.project/git/delivery.yml` fixes streamlined mode with `new-or-worsened` diagnostics, `risk-based` independent review, `impact-based` documentation, and `once` delivery confirmation. The file also contains automation switches, denied paths, commit fields, branch rules, and check commands. Commit content is detected from the task's initial Git baseline, change ledger, and current actual diff, not from a YAML path allowlist; legacy `scope.allowed_paths` is compatibility-only and never filters content. `denied_paths` may still exclude build or generated artifacts. The policy forbids remote aliases, URLs, and target refs; push targets come exclusively from the current project's local `.git` configuration.

Task Brief `Git Delivery` accepts only `none`, `commit`, `commit-and-push`, or `auto`. One `CONFIRM_COMMIT` confirms the exact content and selected mode; selecting `commit-and-push` includes one ordinary push authorization. Only `auto` requires both automation switches. A Task Brief never supplies a remote, URL, target branch, or refspec.

For ordinary commit, `DETECT_COMMIT_SCOPE` presents scope from the task baseline, change ledger, and actual diff, and the Agent stages it explicitly only after final confirmation. Every staged item enters the commit, so inspect the complete staged path set and diff and exclude unrelated staged files before invoking the entrypoint. A `fingerprint` is used only for auto content confirmation and drift detection; ordinary commit does not depend on a fingerprint or commit `git-plan`. The user can request a reduction through `ADJUST_CHANGESET`, after which verification, independent review, and confirmation run again.

```sh
python .github/agent-kit/scripts/project_policy.py git-plan \
  --root . --operation push --delivery commit-and-push

python .github/agent-kit/scripts/project_policy.py git-plan \
  --root . --operation auto --delivery auto \
  --message-file <outside-repository-temp-file> --path <repair-file> \
  --expected-content-fingerprint <confirmed-fingerprint>

git add -- <confirmed-task-path>...

PROJECT_POLICY_PYTHON=<current-python> \
git -c core.hooksPath=.githooks commit \
  --file <message-file> --cleanup=verbatim
```

`project_policy.py git-plan` is read-only and remains available for auto and push. The Agent runs `commit.checks` during `CHECK_GATES`. Before commit, require `.githooks/commit-msg` to exist and be executable on Git Bash/Linux. The hook is the sole message gate and calls `project_policy.py message`. A `git commit` without the versioned hook is forbidden, as are amend and `--no-verify`.

Push preflight uses only `git config --local --no-includes` for `branch.<name>.remote`, `branch.<name>.merge`, and one `remote.<name>.pushurl` (falling back to one `url`), with Git-dir/common-dir support for linked worktrees. It emits a redacted URL and fingerprint; rerun with `--expected-fingerprint` immediately before push. An actual push may use only `git -C <root> push <resolved-remote> HEAD:<resolved-remote-ref>` in the same local-only Git environment with global/system/environment config injection disabled. Force, `push -u`, custom refspecs, remote deletion, automatic `.git/config` mutation, and self-authorization through uncommitted policy are forbidden.

Auto preflight returns `NO_DELIVERY` for no diff, and missing required message metadata returns `BLOCKED`. Missing or stale content confirmation returns `CONFIRM_COMMIT_CONTENT` with current `commit_content`; the agent performs no Git write and asks for confirmation again. Other unmet pre-write conditions return `OUTPUT_COMMIT_MESSAGE`. Only `content_confirmation.status: CONFIRMED` together with `AUTO_COMMIT_AND_PUSH` continues: the index must initially be empty, HEAD must equal the local upstream tracking ref, and the worktree must contain exactly the repair paths. After the new commit, repeat push preflight with its first fingerprint and `--expected-commit <SHA>`; outgoing commits must contain only that SHA. If push then fails, keep the local commit and report its SHA without rollback. Keep the temporary message file outside the repository so it cannot become unrelated dirty state.
