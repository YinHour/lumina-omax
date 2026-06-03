# AI 提供商 — 配置指南

---

## 云端提供商

### OpenAI
- 获取密钥：https://platform.openai.com/api-keys
- 推荐模型：`gpt-4o`（最佳平衡）、`gpt-4o-mini`（便宜 90%）
- 费用：轻量 $1-5/月，中度 $10-30/月

### Anthropic (Claude)
- 获取密钥：https://console.anthropic.com/
- 推荐：`claude-sonnet-4-5`（最新最强）、`claude-3-5-haiku`（快&便宜）
- 优势：200K token 长上下文

### Google Gemini
- 获取密钥：https://aistudio.google.com/app/apikey
- 推荐：`gemini-2.0-flash-exp`（最佳性价比）
- 优势：1M token 超长上下文、多模态

### Groq
- 获取密钥：https://console.groq.com/keys
- 推荐：`llama-3.3-70b-versatile`
- 优势：超快推理、极便宜

### OpenRouter
- 获取密钥：https://openrouter.ai/keys
- 一个密钥访问 100+ 模型
- 推荐：`anthropic/claude-sonnet-4.5`

### DashScope (Qwen)
- 获取密钥：https://dashscope.console.aliyun.com/
- 推荐：`qwen-max`（最佳质量）、`qwen-plus`（平衡）

### MiniMax
- 获取密钥：https://platform.minimaxi.com/
- 推荐：`MiniMax-M2.5`（最佳）、204K 上下文

---

## 本地/自托管

### Ollama（推荐本地）
- 安装：https://ollama.ai
- 下载模型：`ollama pull mistral`
- 推荐：`llama3.1:8b`（平衡）、`qwen2.5:7b`（编程）
- 硬件：8GB VRAM（GPU）或 16GB+ RAM（CPU）

### LM Studio
- 下载：https://lmstudio.ai
- 图形界面操作
- 在 Settings 中添加 OpenAI-Compatible 凭证

---

## 推荐组合

| 场景 | 方案 |
|------|------|
| 通用 | OpenAI gpt-4o |
| 省钱 | Groq 或 Ollama |
| 隐私优先 | Ollama 本地运行 |
| 企业 | Azure OpenAI |
