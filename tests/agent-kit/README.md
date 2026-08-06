# Agent Kit Tests

## 中文 / Chinese

此目录是 Agent Kit 的独立验证层，不参与 Agent 运行时发现：

- `test_*.py`：验证配置结构、项目策略与 Skill 脚本。
- `fixtures/`：只供自动测试使用的正例和负例输入。
- `manual/vscode-smoke-test.md`：需要真实 VS Code Agent 交互的人工场景。
- `requirements.txt`：仅测试和本地验证所需的 Python 依赖。

在仓库根目录运行：

```sh
python -m pip install -r tests/agent-kit/requirements.txt
python .github/agent-kit/scripts/validate_customizations.py --root . --development
python -m unittest discover -s tests/agent-kit -p "test_*.py" -v
```

运行时实现保留在 `.github/agent-kit/scripts/`。测试只在维护 Agent Kit 源码时通过 `--development` 检查，不得成为 Agent Prompt、共享契约、目标项目验证或生产路径的隐式输入。

## English

This directory is the Agent Kit's independent validation layer and is not part of runtime Agent discovery:

- `test_*.py` validates configuration structure, project policy, and Skill scripts.
- `fixtures/` contains positive and negative inputs used only by automated tests.
- `manual/vscode-smoke-test.md` contains scenarios that require real VS Code Agent interaction.
- `requirements.txt` contains Python dependencies used only for tests and local validation.

Run from the repository root:

```sh
python -m pip install -r tests/agent-kit/requirements.txt
python .github/agent-kit/scripts/validate_customizations.py --root . --development
python -m unittest discover -s tests/agent-kit -p "test_*.py" -v
```

Runtime implementation remains under `.github/agent-kit/scripts/`. Tests are checked through `--development` only while maintaining the Agent Kit source and must not become implicit input to Agent prompts, the shared contract, target-project validation, or production paths.
