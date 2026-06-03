# 连接问题 — 网络与 API

---

## "无法连接服务器"（最常见）

```bash
# 检查 API 是否运行
docker ps | grep api

# 测试 API 连通性
curl http://localhost:5055/health

# 重启
docker compose restart
```

---

## 连接被拒

- API 端口未开放 → 检查 docker-compose.yml 端口映射
- API 崩溃 → 查日志：`docker compose logs api`

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
# .env 中：
API_URL=http://你的服务器IP:5055

# 开放端口：
sudo ufw allow 8502
sudo ufw allow 5055
```

---

## CORS 错误

浏览器控制台出现 CORS 错误 → 检查 `API_URL` 是否与前端 URL 匹配 → 重启前端服务

---

## 诊断命令

```bash
docker compose ps              # 所有服务应显示 "Up"
curl http://localhost:5055/health  # 应返回 {"status":"ok"}
```
