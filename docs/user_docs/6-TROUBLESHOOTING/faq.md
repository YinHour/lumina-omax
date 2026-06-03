# 常见问题

---

## 一般使用

**Lumiton·Omax 是什么？**
自定义的 AI 科研助手。创建研究笔记本、与文档对话、生成播客、跨所有来源语义搜索。

**与 Google Notebook LM 的区别？**
数据默认本地存储。17+ AI 提供商可选。开源、可定制。你完全控制数据和模型。

**费用如何？**
软件免费。AI API 按用量付费：OpenAI ~$0.50-5/百万 token。本地模型免费。典型月费 $5-50。

---

## AI 模型

**推荐哪个提供商？**
新手 → OpenAI（可靠、文档全）。省钱 → Groq、Google 免费层。长上下文 → Anthropic（200K）、Gemini（1M）。

**最佳模型组合？**
- 省钱：`gpt-4o-mini` + `text-embedding-3-small`
- 高质量：`claude-sonnet-4-5` + `text-embedding-3-large`
- 隐私：本地 Ollama 模型

**如何优化成本？**
小事用小模型、大推理用大模型、利用免费层、用"仅摘要"上下文。

---

## 数据管理

**数据存在哪？**
- 数据库：SurrealDB 文件（`surreal_data/`）
- 上传文件：`data/uploads/`
- 播客音频：`data/podcasts/`

**如何备份？**
```bash
tar -czf backup-$(date +%Y%m%d).tar.gz data/ surreal_data/
```

---

## 最佳实践

**如何组织笔记本？**
- 按主题：不同研究领域分笔记本
- 每笔记本 20-100 条来源为最佳性能

**如何获得最佳搜索？**
- 用描述性查询而非单个词
- 尝试两种搜索模式
- 自然语言提问
