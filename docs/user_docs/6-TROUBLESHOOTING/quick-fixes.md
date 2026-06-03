# 快速修复 — 最常见问题

---

## #1：无法连接服务器

```bash
# 检查 API 是否运行
docker ps | grep api

# 验证端口 5055 可访问
curl http://localhost:5055/health
# 应返回：{"status":"ok"}

# 不行就重启
docker compose restart
```

---

## #2：API 密钥无效 / 模型不显示

1. Settings → API Keys → 测试连接
2. 失败则删除重建，用正确的密钥
3. 测试通过 → Discover Models → Register Models
4. `OPEN_NOTEBOOK_ENCRYPTION_KEY` 必须已设置

---

## #3：端口冲突

```bash
# 找谁在用 8502
lsof -i :8502
# 或换端口：docker-compose.yml 中改为 "8503:8502"
```

---

## #4：无法处理文件

- ✓ PDF、DOCX、PPTX、XLSX
- ✓ MP3、WAV、MP4、URL
- ✗ 纯图片（无 OCR）、>100MB 文件

---

## #5：聊天很慢

- 换更快模型：gpt-4o-mini、claude-haiku、Groq
- 减少上下文来源
- 大文档用"仅摘要"模式

---

## #6：聊天回复差

- 确保正确来源在上下文中（"完整内容"模式）
- 问具体问题："基于方法论部分，3 个主要局限是什么？"
- 换成更强模型：gpt-4o、claude-sonnet

---

## #7：搜索无结果

- 无结果 → 换向量搜索（概念匹配）
- 向量搜索无结果 → 换文本搜索（关键词）
- 检查来源是否处理完成（绿色"就绪"状态）

---

## #8：播客生成失败

- 确保至少 1-2 条来源
- 检查 TTS 提供商配额
- 等 30 秒重试
- 换不同 TTS 提供商

---

## #9：服务无法启动

```bash
docker compose logs          # 查日志
docker compose restart       # 重启
docker compose down && docker compose up --build  # 重建
df -h                        # 检查磁盘（至少 5GB）
```

---

## 终极方案（数据丢失警告）

```bash
docker compose down -v       # 完全重置
docker compose up --build    # 重建
```
