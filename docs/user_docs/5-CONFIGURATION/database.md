# 数据库 — SurrealDB 配置

---

## 默认配置（推荐：同 docker-compose）

```env
SURREAL_URL="ws://surrealdb:8000/rpc"
SURREAL_USER="root"
SURREAL_PASSWORD="root"
SURREAL_NAMESPACE="open_notebook"
SURREAL_DATABASE="open_notebook"
```

---

## 其他部署场景

### DB 在宿主机、Lumiton·Omax 在 Docker 中
```env
SURREAL_URL="ws://宿主机IP:8000/rpc"  # 或用 host.docker.internal
```

### 两者都在同一台机器本地运行（Docker）
```env
SURREAL_URL="ws://localhost:8000/rpc"
```

### 本地源码模式（`make start-all`）
```env
SURREAL_URL="ws://127.0.0.1:8001/rpc"
```

SurrealDB 仅映射到宿主机回环（`127.0.0.1:8001:8000`），不向局域网暴露。本地进程连接本机数据库不需要 TLS。

---

## 多数据库

一个 SurrealDB 实例可创建多个 namespace 和 database，无需部署多个数据库实例。
