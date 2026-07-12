---
name: EmbeddedDeveloper
description: Invalid tool policy fixture
target: vscode
user-invocable: true
disable-model-invocation: false
tools: ['agent', 'edit', 'execute']
handoffs:
  - label: Invalid automatic handoff
    agent: UnknownAgent
    prompt: Invalid fixture
    send: true
---

# Invalid Agent Fixture

## 中文 / Chinese

此 fixture 故意违反工具、引用和 handoff 约束。

## English

This fixture intentionally violates tool, reference, and handoff constraints.
