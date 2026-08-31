# 环境变量完整参考

---

## API 配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `OPEN_NOTEBOOK_ENCRYPTION_KEY` | **必须设置** | 加密数据库中的凭证 |
| `OPEN_NOTEBOOK_PASSWORD` | 无 | 超级管理员后门密码（也用于删除多引用来源校验） |
| `AUTH_JWT_SECRET` | 由 ENCRYPTION_KEY 派生 | JWT 签名密钥 |
| `API_URL` | 自动检测 | 前端访问 API 的 URL（LAN 源码部署留空以走相对 `/api`） |
| `INTERNAL_API_URL` | `http://127.0.0.1:5056` | Next.js 服务端代理 API 的内部地址（源码模式） |
| `HOSTNAME` | `0.0.0.0` | Next.js 绑定网卡 |
| `OPEN_NOTEBOOK_ENV` | dev | 环境标识（非 dev/test 时强制要求配置 JWT 密钥） |

---

## 数据库

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SURREAL_URL` | `ws://surrealdb:8000/rpc` | WebSocket 连接（源码模式用 `ws://127.0.0.1:8001/rpc`） |
| `SURREAL_USER` | root | 用户名 |
| `SURREAL_PASSWORD` | root | 密码 |
| `SURREAL_NAMESPACE` | open_notebook | 命名空间 |
| `SURREAL_DATABASE` | open_notebook | 数据库名 |

---

## 并发 & 重试

| 变量 | 默认值 |
|------|--------|
| `SURREAL_COMMANDS_MAX_TASKS` | 5 |
| `SURREAL_COMMANDS_RETRY_ENABLED` | true |
| `SURREAL_COMMANDS_RETRY_MAX_ATTEMPTS` | 3 |
| `SURREAL_COMMANDS_RETRY_WAIT_STRATEGY` | exponential_jitter |

---

## 超时

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `API_CLIENT_TIMEOUT` | 300 秒 | API 客户端超时 |
| `ESPERANTO_LLM_TIMEOUT` | 60 秒 | LLM 推理超时 |
| `CHAT_LLM_TIMEOUT_SECONDS` | 240 秒 | 笔记本聊天主回答超时（超时发 `llm_timeout` SSE） |
| `CHAT_STREAM_HEARTBEAT_SECONDS` | 5 秒 | 笔记本聊天首字节前 SSE 心跳间隔 |

> **范围**：`CHAT_LLM_TIMEOUT_SECONDS` 与 `CHAT_STREAM_HEARTBEAT_SECONDS` 仅作用于笔记本聊天（`/chat/execute`）。源聊天与全局 Ask 暂未引入心跳。

---

## Vision 图片描述

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `VISION_CONCURRENCY` | 2 | Vision 并发数（MiniMax 建议 2） |
| `VISION_TIMEOUT_SECONDS` | 120 | 单图调用超时 |
| `VISION_MAX_RETRIES` | 2 | 最大重试次数 |
| `VISION_RETRY_BASE_DELAY_SECONDS` | 3 | 指数退避基数 |
| `VISION_MAX_TOKENS` | 384 | 云模型最大 token（OpenAI-compatible） |
| `VISION_TEMPERATURE` | 0 | Vision 温度 |
| `VISION_NUM_CTX` | 2048 | Ollama 上下文长度 |
| `VISION_NUM_PREDICT` | 384 | Ollama 最大预测 token |

> **供应商差异**：`num_ctx`/`num_predict` 是 Ollama 参数，云模型用 `max_tokens`；不能无差别传给所有供应商。

---

## 联网搜索（Tavily）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `TAVILY_API_KEY` | 无 | Tavily API 密钥（也在 Settings → Web Search 配置） |
| `TAVILY_INCLUDE_DOMAINS` | 无 | 白名单域名 |
| `tavily_search_max_calls`（设置项） | 5 | 单次回答最多 Tavily 调用次数（设置页「联网搜索」可调，1-20） |

---

## 内容处理引擎

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `CCORE_DOCUMENT_ENGINE` | mineru | 文档引擎（mineru/docling/simple） |
| `MINERU_TABLE_ENABLE` | true | MinerU 表格识别增强 |
| `HF_ENDPOINT` | 无 | 国内镜像加速（`https://hf-mirror.com`） |
| `MINERU_MODEL_SOURCE` | 无 | 模型源（`modelscope`） |

---

## 调试

| 变量 | 说明 |
|------|------|
| `LANGCHAIN_TRACING_V2=true` | 启用 LangSmith 追踪 |
| `LANGCHAIN_API_KEY` | LangSmith API 密钥 |
| `RUST_LOG=debug` | Rust 组件日志 |
| `LOGLEVEL=DEBUG` | Python 组件日志（落地 `logs/open_notebook.log`） |
