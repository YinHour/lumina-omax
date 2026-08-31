# 常见问题

---

## 一般使用

**Lumiton·Omax 是什么？**
自定义的 AI 科研助手。创建研究笔记本、与文档对话、生成播客、跨所有来源语义搜索。

**与 Google Notebook LM 的区别？**
数据默认本地存储。17+ AI 提供商可选。开源、可定制。你完全控制数据和模型。支持多用户认证、聚合笔记本、知识图谱 Hybrid RAG。

**费用如何？**
软件免费。AI API 按用量付费：OpenAI ~$0.50-5/百万 token。本地模型免费。典型月费 $5-50。

**支持哪些文件格式？**
PDF、Word（.docx/.doc）、PowerPoint（.pptx/.ppt）、Excel（.xlsx/.xls/.xlsm）、EPUB、Markdown、HTML、音视频、独立图片（.png/.jpg/.tiff 等）。详见 [添加来源](../3-USER-GUIDE/adding-sources.md#支持的文件类型)。

---

## AI 模型

**推荐哪个提供商？**
新手 → OpenAI（可靠、文档全）。省钱 → Groq、Google 免费层。长上下文 → Anthropic（200K）、Gemini（1M）。中文场景 → MiniMax、DashScope（Qwen）。

**最佳模型组合？**
- 省钱：`gpt-4o-mini` + `text-embedding-3-small`
- 高质量：`claude-sonnet-4-5` + `text-embedding-3-large`
- 隐私：本地 Ollama 模型
- Vision 图片描述：MiniMax-M3（当前推荐，详见 [添加来源 — 推荐模型](../3-USER-GUIDE/adding-sources.md#推荐模型)）

**如何优化成本？**
小事用小模型、大推理用大模型、利用免费层、用「仅摘要」上下文。

---

## 聊天与搜索

**Chat 和 Ask 有什么区别？**
Chat 把选定来源全文发给 LLM（对话式）；Ask 用 RAG 自动检索相关片段（一次性综合）。详见 [核心概念](../2-CORE-CONCEPTS/ai-context-rag.md)。

**聊天卡住很久没反应怎么办？**
- 等待状态会显示「正在等待模型响应（N 秒）」——SSE 心跳在工作
- 超时（默认 240 秒）会以 AI 气泡提示，输入框可继续提问
- 减少上下文来源、换更快模型、新建会话避免长历史拖慢

**模型说「搜索调用次数用完了」是什么意思？**
不等于主模型配额耗尽。是 Tavily 工具的限制（每次回答最多调用次数由设置项管理，默认 5，可调 1-20；或月度免费配额 1000 次耗尽）。在 Tavily 控制台核对用量，或临时关闭联网搜索。

**Ask 的「检索覆盖」是什么？**
答案附带的「来源总数 / 可检索来源 / 本次命中来源」。若本次命中远小于总数，答案基于检索子集，不代表每个文件都被检查。

---

## 笔记本与来源

**笔记本能加多少来源？**
默认 50，管理员可在设置页调整（1-200）。详见 [来源数量上限](../3-USER-GUIDE/adding-sources.md#来源数量上限)。

**删除来源为什么要密码？**
若来源被多个笔记本引用，删除需管理员密码（删源三规则）。详见 [删除来源三规则](../3-USER-GUIDE/adding-sources.md#删除来源三规则)。

**聚合笔记本是什么？**
通过动态视图关联把多个笔记本内容合并到一个视图，不物理拷贝，毫秒级同步。详见 [核心概念 — 聚合笔记本](../2-CORE-CONCEPTS/notebooks-sources-notes.md#聚合笔记本aggregate-notebook)。

**忘记笔记本密码怎么办？**
用管理员密码 `NEXT_PUBLIC_MASTER_NOTEBOOK_PASSWORD` 绕过。只有创建者可设/改/撤销密码。

---

## 数据管理

**数据存在哪？**
- 数据库：SurrealDB 文件（`surreal_data/`）
- 上传文件：`data/uploads/`
- 播客音频：`data/podcasts/`
- 日志：`logs/open_notebook.log`

**如何备份？**
```bash
tar -czf backup-$(date +%Y%m%d).tar.gz data/ surreal_data/
```

---

## 最佳实践

**如何组织笔记本？**
- 按主题：不同研究领域分笔记本
- 每笔记本 20-100 条来源为最佳性能
- 跨项目综合分析用聚合笔记本

**如何获得最佳搜索？**
- 用描述性查询而非单个词
- 尝试两种搜索模式
- 自然语言提问
- 复杂问题用 Ask，配合覆盖统计判断

**如何获得最佳聊天？**
- 控制上下文：背景材料用「仅摘要」
- 用导览卡片和建议问题快速起步
- 长回答后用 3 条下一步建议继续探索
