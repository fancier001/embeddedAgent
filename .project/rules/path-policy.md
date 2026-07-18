# Repository Path Policy

> 中文：本文档采用固定双语结构。更新中文或英文内容时，必须同步更新另一部分，保持两部分语义一致。
>
> English: This document uses a fixed bilingual structure. When either the Chinese or English content is updated, the other section must be updated as well to keep both sections semantically aligned.

## 中文 / Chinese

### 路径分类

- `examples/minimal-firmware/include/`、`src/`、`tests/` 和 `CMakeLists.txt` 是最小固件示例的 first-party 实现、测试与构建入口。
- `.github/` 保存 Agent Kit 和 CI；`.project/` 保存目标项目约束。只有维护对应配置且 Task Brief 明确列出时才可修改。
- `docs/` 和根 `README.md` 是团队文档入口，遵循完整中英双区结构。
- `examples/minimal-firmware/artifacts/` 和 `fixtures/` 是分析证据或测试夹具，默认只读；变更必须由专门的测试或样例任务授权。
- 任意 `vendor/`、`generated/`、构建输出、ELF、MAP、凭据和本地环境文件默认不得修改或提交。

### 写入约束

`Allowed Changes` 必须列出精确文件或足够窄的目录。路径类别只说明文件用途，不自动授予写权限。修改前后都要检查真实 diff；不得通过全目录暂存把其他人的 dirty worktree 变更混入任务。

## English

### Path Classes

- `examples/minimal-firmware/include/`, `src/`, `tests/`, and `CMakeLists.txt` are the first-party implementation, test, and build entry points for the minimal firmware example.
- `.github/` contains the Agent Kit and CI; `.project/` contains target-project constraints. Modify them only for corresponding configuration maintenance explicitly listed by the Task Brief.
- `docs/` and the root `README.md` are team documentation entry points and follow the complete Chinese-English section structure.
- `examples/minimal-firmware/artifacts/` and `fixtures/` are analysis evidence or test fixtures and are read-only by default; changes require a dedicated test or example task.
- Any `vendor/`, `generated/`, build output, ELF, MAP, credential, or local-environment file is non-writable and non-committable by default.

### Write Constraints

`Allowed Changes` must list exact files or sufficiently narrow directories. A path class explains a file's purpose but does not grant write authority. Inspect the actual diff before and after editing; never use broad directory staging that mixes another person's dirty-worktree changes into the task.
