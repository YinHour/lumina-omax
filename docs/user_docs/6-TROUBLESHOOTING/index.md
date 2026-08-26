# 故障排查 — 问题解决指南

---

## 快速问题映射

| 症状 | 查看 |
|------|------|
| Docker 启动失败 | [快速修复](quick-fixes.md) |
| 端口冲突 | [快速修复](quick-fixes.md) |
| API 无法启动 | [快速修复](quick-fixes.md) |
| 无法连接服务器 | [连接问题](connection-issues.md) |
| 模型不显示 | [AI 与聊天问题](ai-chat-issues.md) |
| API 密钥无效 | [AI 与聊天问题](ai-chat-issues.md) |
| 聊天不工作 | [AI 与聊天问题](ai-chat-issues.md) |
| 聊天回复差 | [AI 与聊天问题](ai-chat-issues.md) |
| 聊天超时/无响应 | [AI 与聊天问题](ai-chat-issues.md) |
| 联网搜索卡死 | [AI 与聊天问题](ai-chat-issues.md) |
| 无法上传文件 | [快速修复](quick-fixes.md) |
| 搜索无结果 | [快速修复](quick-fixes.md) |
| 播客生成失败 | [快速修复](quick-fixes.md) |

---

## 诊断检查清单

- [ ] 检查服务是否运行：`docker ps`
- [ ] 查看日志：`docker compose logs api`
- [ ] 验证端口连通性：`curl http://localhost:5055/health`
- [ ] 检查环境变量：`docker inspect <容器名>`
- [ ] 尝试重启：`docker compose restart`
- [ ] 检查防火墙

---

## 获取帮助

- 查看相关指南的所有步骤
- 检查日志 — 错误信息通常在日志中
- 完整错误信息 + 复现步骤 → GitHub Issues
