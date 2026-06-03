# OpenAI 兼容端点 — LM Studio、vLLM 等

---

## LM Studio（本地）

1. 下载：https://lmstudio.ai
2. 下载模型 → Local Server 标签 → 启动服务（默认端口 1234）

**在 Lumiton·Omax 中**：
Settings → API Keys → 添加凭证 → OpenAI-Compatible
- Base URL：`http://host.docker.internal:1234/v1`（Docker）或 `http://localhost:1234/v1`（本地）
- API 密钥：`lm-studio`（占位，LM Studio 不需要）

---

## 自定义 OpenAI 兼容端点

适用于 Text Generation UI、vLLM 等：

Settings → API Keys → 添加凭证 → OpenAI-Compatible
- 输入你的端点 Base URL（如 `http://localhost:8000/v1`）
- 可选配置各服务独立 URL：LLM、Embedding、TTS、STT
