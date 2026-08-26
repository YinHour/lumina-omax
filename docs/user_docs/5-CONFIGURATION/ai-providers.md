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

---

## Vision 模型（图片描述）

Vision 模型用于自动描述文档中的图片内容（PDF/PPT/Excel 图表、独立图片源）。配置入口：**Settings → API Keys → 高级 → Vision Model**。

经对比评测，当前推荐 **MiniMax-M3**：

| 模型 | 主要表现 | 主要问题 |
|------|----------|----------|
| **MiniMax-M3**（推荐） | 综合描述、表格截图、领域提取最好 | 高峰期动态限流/500/520 |
| Gemma 4 31B（本地 Ollama） | 可本地运行，隐私好 | 单图约 90 秒，吞吐低 |
| Qwen 3.7 Plus | 部分图较丰富 | 推理泄漏、断裂 JSON |
| Step 3.7 Flash | 速度最快 | 类型误判、定量臆测 |
| Doubao Seed 2.0 Pro | 输出整洁 | 表格数据提取弱 |

Vision 参数详见 [高级配置 — Vision 图片描述](advanced.md#vision-图片描述)。代码保留 OpenAI-compatible 多供应商能力，便于后续切换和回归评测。

> **注意**：`num_ctx`/`num_predict` 是 Ollama 参数，云模型用 `max_tokens`，不能无差别传给所有供应商。
