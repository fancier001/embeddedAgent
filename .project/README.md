# Project-Level Policy

> 中文：本文档采用固定双语结构。更新中文或英文内容时，必须同步更新另一部分，保持两部分语义一致。
>
> English: This document uses a fixed bilingual structure. When either the Chinese or English content is updated, the other section must be updated as well to keep both sections semantically aligned.

## 中文 / Chinese

### 目录职责

`.project/` 与 `.github/` 同级，保存目标仓库自己的路径规则、代码规范和 Git 交付策略。`.project/project.yml` 是唯一入口；未注册文件不会自动成为 Agent 指令，`extensions` 中的未知数据只保留、不执行。

该目录是可选增强。目标仓库没有 `.project/` 时，Agent Kit 沿用已有工程事实和项目画像；目录一旦存在，清单、引用和 Git policy 必须通过严格校验。

### 规则调用

Agent 将 Task Brief 范围和真实 diff 与每条规则的 `applies_to` 匹配。适用且 `required: true` 的规则缺失时返回 `BLOCKED`。具有执行权限的角色和 CI 使用统一只读工具：

```sh
python .github/agent-kit/scripts/project_policy.py rules --root . \
  --path examples/minimal-firmware/src/status_led.c
```

重复 `--path` 可解析多个路径，`--all` 用于配置审计。工具仅输出 JSON，不执行规则或 Git 写操作。

### Commit 模板

`.project/git/commit.template` 是仓库内权威模板，运行时不依赖外部磁盘。首行格式为 `<Project><Function block>: <Summary>`，正文严格使用模板中的英文键和顺序。允许连续填写多个 `<Jira ID>:` 行；测试步骤或理由写在对应字段之后的缩进行中。

Bug 修复交付默认生成 `Commit Delivery Confirmation`：建议 `commit` 为待确认默认值，但不构成写入授权。Jira ID 始终由用户主动提供且不得推断；除无法解析的 Project 外，其余字段由 Agent 根据 manifest、根因、真实 diff、测试/构建、独立评审和文档证据生成。所有交付模式确认前必须将 Documentation 记录为 `PASS` 或 `NOT_RUN — Not required: <reason>`。用户确认或修正完整预览后才可创建消息文件；动态 `Next Action` 使用 `UI Route: CURRENT_INPUT`，`commit-and-push`/`auto` 必须显式选择。

AI 实质参与代码生成、检查、重构、测试或文档时填写 `Y` 和一个真实主要场景/详情；完全未参与时精确填写 `<AI-Tool-Used>: N`、`<AI-Tool-Scenario>: /`、`<AI-Tool-Detail>: /`。validator 仍兼容冒号后的可选空格，但拒绝 AI=`N` 时使用 `N/A`、空值或实际使用内容。

确认发生在已经切换到 `EmbeddedDeveloper` 的同一会话中。用户核对逐文件内容后，在当前输入框回复 `确认修改并提交`，Developer 才直接执行预检、显式暂存和 commit；也可回复 `调整修改: <要求>` 进入 `ADJUST_CHANGESET` 和重新确认。无需新的 handoff 按钮，也不得再次委派 EmbeddedDeveloper。

`commit-and-push` 在 commit 成功后输出 `CONFIRM_PUSH` 并等待 `确认推送`；`auto` 不增加二次确认。auto push 失败保留本地 commit、不自动重试，并输出 `MANUAL_PUSH` 与最近一次安全解析 remote/ref 对应的非 force 命令。

自动提交前必须先验证完整消息：

```sh
python .github/agent-kit/scripts/project_policy.py message \
  --root . --file <completed-message-file>
```

人工提交可使用 `git commit --template .project/git/commit.template`。Kit 不修改本地 `git config commit.template`。

### Git 交付

`.project/git/delivery.yml` 只定义自动化开关、排除路径、提交字段、分支规则和检查命令。commit 内容由本次任务的初始 Git 基线、修改账本和当前真实 diff 检测，不由 YAML 路径白名单决定；旧 `scope.allowed_paths` 仅为兼容字段且不参与筛选。`denied_paths` 仍可排除构建或生成产物。policy 禁止保存 remote、URL 或目标 ref；push 目标只能从当前项目的本地 `.git` 配置读取。

Task Brief 的 `Git Delivery` 只接受 `none`、`commit`、`commit-and-push`、`auto`。用户确认后的 `commit`/`commit-and-push` 分别由 `CONFIRM_COMMIT`/`CONFIRM_PUSH` 授权，不受关闭的 automation 开关阻塞；只有 `auto` 要求 `automation.commit` 和 `automation.push` 同时启用。Task Brief 不得提供 remote、URL、目标分支或 refspec。`auto` 是本轮一次 commit 加一次普通 push 的明确授权，不支持仅自动 commit。

commit 预检中的每个 `--path` 都来自 `DETECT_COMMIT_SCOPE`。JSON 的 `commit_content.paths` 是待提交文件，`entries` 逐文件提供 `states`、`added`、`deleted` 和 `binary`，`excluded_paths` 是保留在工作树但不会纳入本次 commit 的其他修改，`fingerprint` 用于在用户确认后检测内容漂移。Agent 将这些证据与真实摘要组成 `Change Confirmation: PENDING`；用户可确认修改并提交，或通过 `ADJUST_CHANGESET` 要求删减，调整后必须重新验证、独立评审和确认。

```sh
python .github/agent-kit/scripts/project_policy.py git-plan \
  --root . --operation commit --delivery commit \
  --message-file <message-file> --path <file>

python .github/agent-kit/scripts/project_policy.py git-plan \
  --root . --operation push --delivery commit-and-push

python .github/agent-kit/scripts/project_policy.py git-plan \
  --root . --operation auto --delivery auto \
  --message-file <outside-repository-temp-file> --path <repair-file>
```

push 预检只用 `git config --local --no-includes` 读取当前分支的 `branch.<name>.remote`、`branch.<name>.merge` 及唯一 `remote.<name>.pushurl`（缺失时唯一 `url`），并通过 Git dir/common dir 兼容 linked worktree。输出包含脱敏 URL 和 fingerprint；实际 push 前必须带 `--expected-fingerprint` 再次预检。工具只读；`EmbeddedDeveloper` 在验证和独立评审后显式暂存、提交，并在同一 local-only、禁用 global/system/env config 注入的 Git 环境中仅执行 `git -C <root> push <resolved-remote> HEAD:<resolved-remote-ref>`。禁止 force、`push -u`、自定义 refspec、删除远端分支、修改 `.git/config` 或用未提交 policy 自我授权。

auto 预检在无 diff 时返回 `NO_DELIVERY`；完整消息缺必填 metadata 时返回 `BLOCKED`；其余写入前条件不足时返回 `OUTPUT_COMMIT_MESSAGE`，Agent 不运行任何 Git 写操作且只向用户展示完整 commit 内容。仅 `AUTO_COMMIT_AND_PUSH` 可继续：index 初始必须为空，HEAD 必须等于本地 upstream tracking ref，工作树必须只包含修复路径；新 commit 后使用首次 fingerprint 和 `--expected-commit <SHA>` 二次预检，outgoing commits 必须只有该 SHA。若随后 push 失败，保留本地 commit 并报告 SHA，不回滚。消息临时文件必须放在仓库外，避免成为无关 dirty 文件。

## English

### Directory Responsibility

`.project/` is a sibling of `.github/` and stores target-repository path rules, coding conventions, and Git delivery policy. `.project/project.yml` is the only entry point. Unregistered files do not automatically become agent instructions, and unknown `extensions` data is preserved without execution.

The directory is an optional enhancement. When a target repository has no `.project/`, the Agent Kit continues with existing repository facts and the project profile. Once the directory exists, its manifest, references, and Git policy are validated strictly.

### Rule Invocation

Agents match the Task Brief scope and actual diff against each rule's `applies_to`. A missing applicable rule with `required: true` returns `BLOCKED`. Executable roles and CI use the unified read-only tool:

```sh
python .github/agent-kit/scripts/project_policy.py rules --root . \
  --path examples/minimal-firmware/src/status_led.c
```

Repeat `--path` for multiple paths, or use `--all` for configuration audit. The tool emits JSON only and never executes a rule or Git write operation.

### Commit Template

`.project/git/commit.template` is the repository-owned canonical template and has no runtime dependency on an external drive. Its subject is `<Project><Function block>: <Summary>`, and its body uses the template's English keys in strict order. Consecutive `<Jira ID>:` rows are allowed; indented rows following a test field contain its steps or rationale.

Bug-fix delivery creates a `Commit Delivery Confirmation` and proposes `commit` as the recommended default pending confirmation; it does not authorize a write. Jira ID is always user-supplied and never inferred. Except for a Project identity that cannot be resolved, the agent generates every other field from the manifest, root cause, actual diff, test/build evidence, independent review, and documentation. Every delivery mode records Documentation as `PASS` or `NOT_RUN — Not required: <reason>` before confirmation. It creates the message file only after the user confirms or corrects the complete preview; the dynamic `Next Action` uses `UI Route: CURRENT_INPUT`. `commit-and-push`/`auto` require an explicit choice.

Use AI=`Y` with one truthful primary scenario/detail when AI materially participated in code generation, inspection, refactoring, tests, or documentation. When AI did not participate at all, use exactly `<AI-Tool-Used>: N`, `<AI-Tool-Scenario>: /`, and `<AI-Tool-Detail>: /`. The validator remains compatible with optional whitespace after the colon but rejects `N/A`, empty values, or usage content when AI=`N`.

Confirmation occurs in the same conversation that has already switched to `EmbeddedDeveloper`. After reviewing per-file content, the user replies `confirm changes and commit`, and only then does Developer run preflight, explicit staging, and commit directly. The user may instead reply `adjust changes: <request>` to enter `ADJUST_CHANGESET` and a new confirmation. No additional handoff button or delegation back to EmbeddedDeveloper is needed.

`commit-and-push` emits `CONFIRM_PUSH` after commit and waits for `confirm push`; `auto` adds no second confirmation. A failed auto push preserves the local commit without automatic retry and emits `MANUAL_PUSH` with the non-force command for the most recently safe resolved remote/ref.

Validate a completed message before automatic commit:

```sh
python .github/agent-kit/scripts/project_policy.py message \
  --root . --file <completed-message-file>
```

Manual users may run `git commit --template .project/git/commit.template`. The Kit never changes local `git config commit.template`.

### Git Delivery

`.project/git/delivery.yml` contains automation switches, denied paths, commit fields, branch rules, and check commands only. Commit content is detected from the task's initial Git baseline, change ledger, and current actual diff, not from a YAML path allowlist; legacy `scope.allowed_paths` is compatibility-only and never filters content. `denied_paths` may still exclude build or generated artifacts. The policy forbids remote aliases, URLs, and target refs; push targets come exclusively from the current project's local `.git` configuration.

Task Brief `Git Delivery` accepts only `none`, `commit`, `commit-and-push`, or `auto`. User-confirmed `commit`/`commit-and-push` are authorized through `CONFIRM_COMMIT`/`CONFIRM_PUSH` and are not blocked by disabled automation switches; only `auto` requires both `automation.commit` and `automation.push`. A Task Brief never supplies a remote, URL, target branch, or refspec. `auto` explicitly authorizes one commit plus one ordinary push for this run; automatic commit-only is unsupported.

Every commit-preflight `--path` comes from `DETECT_COMMIT_SCOPE`. In JSON, `commit_content.paths` lists files for this commit, `entries` provides per-file `states`, `added`, `deleted`, and `binary`, `excluded_paths` lists other worktree changes that remain untouched, and `fingerprint` detects content drift after user confirmation. The agent combines this evidence with truthful summaries as `Change Confirmation: PENDING`; the user can confirm changes and commit or request a reduction through `ADJUST_CHANGESET`, after which verification, independent review, and confirmation run again.

```sh
python .github/agent-kit/scripts/project_policy.py git-plan \
  --root . --operation commit --delivery commit \
  --message-file <message-file> --path <file>

python .github/agent-kit/scripts/project_policy.py git-plan \
  --root . --operation push --delivery commit-and-push

python .github/agent-kit/scripts/project_policy.py git-plan \
  --root . --operation auto --delivery auto \
  --message-file <outside-repository-temp-file> --path <repair-file>
```

Push preflight uses only `git config --local --no-includes` for `branch.<name>.remote`, `branch.<name>.merge`, and one `remote.<name>.pushurl` (falling back to one `url`), with Git-dir/common-dir support for linked worktrees. It emits a redacted URL and fingerprint; rerun with `--expected-fingerprint` immediately before push. The tool is read-only. After verification and independent review, `EmbeddedDeveloper` explicitly stages and commits, then may run only `git -C <root> push <resolved-remote> HEAD:<resolved-remote-ref>` in the same local-only Git environment with global/system/environment config injection disabled. Force, `push -u`, custom refspecs, remote deletion, `.git/config` mutation, and self-authorization through uncommitted policy are forbidden.

Auto preflight returns `NO_DELIVERY` for no diff, and missing required message metadata returns `BLOCKED`. Any other unmet pre-write condition returns `OUTPUT_COMMIT_MESSAGE`; the agent performs no Git write and shows the user only the complete commit content. Only `AUTO_COMMIT_AND_PUSH` continues: the index must initially be empty, HEAD must equal the local upstream tracking ref, and the worktree must contain exactly the repair paths. After the new commit, repeat preflight with the first fingerprint and `--expected-commit <SHA>`; outgoing commits must contain only that SHA. If push then fails, keep the local commit and report its SHA without rollback. Keep the temporary message file outside the repository so it cannot become unrelated dirty state.
