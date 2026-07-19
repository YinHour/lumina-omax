# 精选科研方法 Skills P1 实施计划

日期：2026-07-19

对应设计：
`docs/superpowers/specs/2026-07-19-curated-research-method-skills-p1-design.md`

## 1. 只读 Skill 资产与安全校验

- 新增 `open_notebook/research_skills/` 模型、注册表和 10 个 Skill 目录。
- 每个目录仅提交 `manifest.json` 与 `SKILL.md`。
- 校验固定版本、来源、MIT 许可证、审阅状态、允许工具、SHA-256、长度和危险语句。
- 增加注册表目录、正文按需加载、篡改和危险内容拒绝测试。

## 2. Research Agent 加载链路

- 扩展 `ResearchState` 的 Skill 模式和 ID。
- 新增只读 `load_research_skills` 工具；仅 `auto` 可调用，单轮最多加载 2 个。
- `selected` 在系统提示中预加载 1–3 个正文，`off` 不暴露目录或正文。
- 系统提示明确 Skill 不是证据、不能扩大权限，最终回答报告方法与版本。
- 将加载工具加入 ToolNode 和 SSE 活动阶段。

## 3. API

- 新增认证后的 Research Skill 目录 GET 接口，响应不含正文。
- 扩展 Research 执行请求，严格校验模式、数量、重复项和未知 ID。
- 将合法选择传入 LangGraph state，并记录不含正文的结构化日志。
- 增加请求模型、目录响应、state 传递和活动阶段测试。

## 4. Research UI

- 扩展 API 类型和客户端。
- 在 notebook chat hook 中获取目录，管理 `auto/off/selected` 状态并发送请求。
- 显式选择最多 3 个，请求结束后恢复 `auto`；新 Research 会话也恢复默认。
- 在 `ChatPanel` Research 设置行增加下拉选择器。
- 增加科研方法加载活动状态。
- 为 9 个现有 locale 补齐选择器、方法名称、描述、限制和活动文案。
- 增加 hook、组件、活动映射和 API 客户端测试。

## 5. 文档与验证

- 更新 `docs/8-CUSTOMIZATION/00-index.md`，记录能力、边界、文件和验证结果。
- 后端目标验证：
  - `uv run pytest tests/test_research_skills.py tests/test_research_agent.py tests/test_chat_api.py -q`
  - `uv run ruff check` 覆盖本轮 Python 文件。
- 前端目标验证：
  - 相关 Vitest 测试；
  - `npm run lint`；
  - `npm run build`。
- 回归验证：
  - `uv run pytest tests/ -m "not e2e" -q`。
- 手工验证自动选择、关闭、显式选择、数量限制、SSE 提示、最终方法版本和权限不扩张。

## 风险与缓解

- **上下文膨胀**：常驻只给短描述；自动最多 2 个，显式最多 3 个，正文单个不超过 8,000 字符。
- **提示注入**：固定仓库内容、哈希校验、危险语句扫描、禁止脚本和额外文件。
- **方法被误当证据**：系统提示和最终合成明确分离方法与证据。
- **模型误选方法**：用户可关闭或显式选择；自动选择受数量限制并在活动流和答案中可见。
- **权限提升**：Skill 工具集合与请求实际授权取交集，Skill 清单不能启用任何能力。
- **i18n 漂移**：用英文 locale 结构作为类型基线，运行全量类型构建和组件测试。
