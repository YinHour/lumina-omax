# 配置指南 — 基本设置

---

## 需要配置什么？

三件事：
1. **AI 提供商** — 选择 LLM/embedding 服务
2. **数据库** — SurrealDB 连接（通常预配置）
3. **服务器** — API URL、端口（通常自动检测）

---

## 快速决策：用哪个提供商？

### 云端（最快）
- OpenAI、Anthropic、Google Gemini、Groq、DeepSeek、OpenRouter
- 获取 API 密钥 → Settings 中添加凭证

### 本地（免费 & 隐私）
- **Ollama**（开源模型，本机运行）
- **LM Studio**（图形界面，易于使用）

### 企业
- **Azure OpenAI**（合规、VPC 集成）

---

## 最简配置

```env
# 在 .env 或 docker.env 中：
OPEN_NOTEBOOK_ENCRYPTION_KEY=你的密钥

# 其余用默认值
# 然后在 Settings → API Keys 中添加 AI 提供商凭证
```

---

## 场景配置

### Docker 本地
```env
OPEN_NOTEBOOK_ENCRYPTION_KEY=你的密钥
```

### Docker 远程服务器
```env
OPEN_NOTEBOOK_ENCRYPTION_KEY=你的密钥
API_URL=http://你的服务器IP:5055
```

### 反向代理（Nginx/Cloudflare）
```env
OPEN_NOTEBOOK_ENCRYPTION_KEY=你的密钥
API_URL=https://你的域名.com
```
