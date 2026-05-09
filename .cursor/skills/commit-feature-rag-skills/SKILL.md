# feature-rag 与技能更新：提交规范

## 何时使用

- 当前分支为 `feature-rag` 或与 RAG 功能线相关
- 改动涉及：RAG 应用代码、`rag-platform/`、`.cursor/skills/`、`.cursor/rules/`（如 `RAG.mdc`）
- 用户要求写提交说明、整理暂存区提交、或「按项目规范提交」

## 格式（Conventional Commits）

单行主题：

```
<type>(<scope>): <简短描述>
```

- **type**：`feat` | `fix` | `docs` | `refactor` | `chore` | `test` | `perf`
- **scope**（择一或与本次改动最贴近）：
  - `rag`：业务功能、API、检索、入库等
  - `skills`：`.cursor/skills/` 下技能说明
  - `rules`：`.cursor/rules/` 下规则
  - `frontend` / `backend`：若仓库分前后端且本次只动一侧

**描述**：祈使句、现在时（英文习惯用 `add` / `fix`，不用 `added`）；若团队统一中文主题，保持同一风格即可。

可选正文（解释动机、破坏性变更、关联 issue）：

```
<type>(<scope>): <主题>

- 要点 1
- 要点 2
```

## 与「技能更新」对应的类型建议

| 改动内容 | type | scope 示例 |
|---------|------|------------|
| 新增或改写 Agent Skill | `docs` 或 `chore` | `skills` |
| 新增或改写 Cursor 规则 | `docs` 或 `chore` | `rules` |
| RAG 检索/入库/对话逻辑 | `feat` / `fix` | `rag` |
| 仅依赖、格式化、脚本 | `chore` | 按目录选 scope |

纯文档/说明类技能与规则更新，默认用 `docs(scope):`，若更强调「工程维护」可用 `chore(scope):`。

## 示例

**只改技能文件：**

```
docs(skills): add commit conventions for feature-rag work
```

**只改 RAG 规则：**

```
docs(rules): clarify local BM25 setup in RAG platform rule
```

**功能 + 技能同时更新（拆成两次提交更清）：**

```
feat(rag): support hybrid score in search API

docs(skills): document rag search troubleshooting
```

## 执行前检查

- [ ] 主题不超过约 72 字符（含 type/scope）
- [ ] 一次提交只做一类事；混改时优先拆分
- [ ] 若用户要求「一条英文一条中文说明」，主题仍用上述格式，正文可中文补充

## 分支名（参考）

与功能线一致时可用：`feature-rag` 或 `feature/rag-<topic>`；提交信息不必重复写分支全名，scope 已表达模块。
