# 长会话 Transcript 持久化与分页设计

**日期：** 2026-07-11

## 1. 问题

当前 notebook chat 把完整用户历史和 LangGraph 执行状态都放在 SQLite checkpoint：

- 会话列表逐个读取 checkpoint 计算消息数。
- 会话详情每次返回全部 human/AI 消息。
- SSE 完成后前端重新获取整场会话。
- 100 轮后，SQLite 反序列化、HTTP 响应、Markdown 渲染都会随历史线性增长。

## 2. 数据职责

- SurrealDB `chat_message`：用户可见 transcript 的长期事实来源，保存 human / final AI 消息。
- LangGraph checkpoint：近期执行记忆、工具调用协议和压缩摘要，不再承担 UI 历史归档。
- `chat_session` 维护 `message_count`、`last_message_preview`、`transcript_initialized` 和更新时间，列表不再扫描已迁移 checkpoint。

## 3. 兼容策略

- 新会话创建时 `transcript_initialized=true`，每轮把用户问题与最终 AI 回答写入 transcript。
- 旧会话缺少 transcript 标记时，首次读取或首次继续对话时从 checkpoint 提取可见 human/AI 消息并懒迁移；迁移成功前继续保留 checkpoint 回退。
- 只有 transcript 成功持久化后才压缩 checkpoint，避免数据库失败导致历史丢失。
- 删除会话时同时删除 transcript；checkpoint 物理线程清理作为后续维护任务，不阻塞本期。

## 4. 分页协议

- 会话详情默认返回最新 50 条，按时间顺序排列。
- `before_sequence` cursor 加载更早消息；响应返回 `has_more` 与 `next_cursor`。
- 前端在消息区顶部显示“加载更早消息”，增量前插，不替换当前流式消息。
- 导出 Markdown 会自动遍历全部分页，不只导出当前已渲染页面。

## 5. Checkpoint 压缩

- transcript 保存成功后，按 Quick/Research 既有消息数与 token 预算选择近期协议安全窗口。
- 被移除的早期 human/final AI 内容写入 `conversation_summary`；原始 ToolMessage 不进入摘要。
- 使用 LangGraph `RemoveMessage` 删除已归档的旧 checkpoint 消息，保留工具调用原子组。
- 下轮 system prompt 同时包含持久摘要和当前窗口摘要。

## 6. 验收标准

1. 新会话消息可从 `chat_message` 分页读取。
2. 旧会话在不丢历史的前提下懒迁移。
3. 已迁移会话列表不再打开 checkpoint 计算消息数。
4. 100 轮会话首屏只返回最新 50 条，可继续加载更早消息。
5. 导出包含完整会话。
6. transcript 写入失败时保留 checkpoint 且不执行压缩。
7. Quick/Research checkpoint 压缩继续保持工具消息协议合法。
