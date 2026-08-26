# 连接问题 — 网络与 API

---

## 端口对照

Lumiton·Omax 有两种部署模式，端口不同：

| 服务 | 标准容器（Docker） | 本地源码（`make start-all`） |
|------|---------------------|------------------------------|
| 前端 | `3000` | `3001` |
| API | `5055` | `5056` |
| SurrealDB | `8000`（容器内） | `127.0.0.1:8001`（宿主机回环） |

> **本地源码模式安全调整**：SurrealDB 仅绑定 `127.0.0.1:8001`，不向局域网暴露数据库；浏览器流量走相对 `/api`，由 Next.js 服务端代理至 `INTERNAL_API_URL=http://127.0.0.1:5056`，不注入浏览器可见的 `API_URL`。

---

## 「无法连接服务器」（最常见）

```bash
# 标准容器
docker ps | grep api
curl http://localhost:5055/health

# 本地源码
curl http://127.0.0.1:5056/health

# 重启
docker compose restart          # 容器
make start-all                  # 本地源码（重启相应进程）
```

---

## 连接被拒

- API 端口未开放 → 检查 docker-compose.yml 端口映射
- API 崩溃 → 查日志：`docker compose logs api`（容器）或 `logs/open_notebook.log`（源码）
- 本地源码启动时 Next.js 报 `/api/config` proxy `ECONNREFUSED` → API 未就绪，`make start-all` 会等待 `/api/config` ready 再启动前端

---

## 超时 / 慢连接

```bash
# 降低并发
SURREAL_COMMANDS_MAX_TASKS=2

# 增加超时
API_CLIENT_TIMEOUT=600
```

---

## 远程访问

```bash
# .env 中（标准容器远程服务器）：
API_URL=http://你的服务器IP:5055

# 开放端口：
sudo ufw allow 5055   # API
sudo ufw allow 3000   # 前端
```

> **LAN 源码部署**：局域网用户应通过 `http://<Mac-IP>:3001` 访问前端，浏览器走相对 `/api`。不要把浏览器流量直接路由到机器本地 `localhost` API URL。详见 [配置指南](../5-CONFIGURATION/environment-reference.md)。

---

## CORS 错误

浏览器控制台出现 CORS 错误 → 检查 `API_URL` 是否与前端 URL 匹配 → 重启前端服务。

> 开发环境 CORS 允许所有来源（`api/main.py` 配置）。生产环境应通过反向代理收敛。

---

## 诊断命令

```bash
# 标准容器
docker compose ps                          # 所有服务应显示 "Up"
curl http://localhost:5055/health          # 应返回 {"status":"ok"}

# 本地源码
curl http://127.0.0.1:5056/health
tail -f logs/open_notebook.log             # 查实时日志
```
