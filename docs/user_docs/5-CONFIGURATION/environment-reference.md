# 环境变量完整参考

---

## API 配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `OPEN_NOTEBOOK_ENCRYPTION_KEY` | **必须设置** | 加密数据库中的凭证 |
| `OPEN_NOTEBOOK_PASSWORD` | 无 | 超级管理员后门密码 |
| `AUTH_JWT_SECRET` | 由 ENCRYPTION_KEY 派生 | JWT 签名密钥 |
| `API_URL` | 自动检测 | 前端访问 API 的 URL |
| `HOSTNAME` | `0.0.0.0` | Next.js 绑定网卡 |

---

## 数据库

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SURREAL_URL` | `ws://surrealdb:8000/rpc` | WebSocket 连接 |
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

---

## 超时

| 变量 | 默认值 |
|------|--------|
| `API_CLIENT_TIMEOUT` | 300 秒 |
| `ESPERANTO_LLM_TIMEOUT` | 60 秒 |

---

## 调试

| 变量 | 说明 |
|------|------|
| `LANGCHAIN_TRACING_V2=true` | 启用 LangSmith 追踪 |
| `LANGCHAIN_API_KEY` | LangSmith API 密钥 |
