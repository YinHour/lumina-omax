# 高级配置

性能调优、调试和高级功能。

---

## 性能调优

### 并发控制
```env
SURREAL_COMMANDS_MAX_TASKS=5   # CPU 2 核→2-3，4 核→5，8 核+→10-20
```

### 重试策略
```env
SURREAL_COMMANDS_RETRY_WAIT_STRATEGY=exponential_jitter  # 推荐
```

### 超时设置
```env
API_CLIENT_TIMEOUT=300    # API 客户端超时（秒）
ESPERANTO_LLM_TIMEOUT=60  # LLM 推理超时（秒）
```

---

## 笔记本聊天心跳与超时

笔记本聊天（`/chat/execute`）有 SSE 心跳与超时保护：

```env
# 主回答超时（秒），超时发 llm_timeout SSE 事件
CHAT_LLM_TIMEOUT_SECONDS=240

# 首字节前心跳间隔（秒），让前端显示「正在等待模型响应（Ns）」
CHAT_STREAM_HEARTBEAT_SECONDS=5
```

- 心跳仅在首字节到达前发送，避免与 AI 流相互干扰
- 超时以 AI 对话气泡提示，含操作指引，不持久化进会话记忆
- 范围：仅笔记本聊天；源聊天与全局 Ask 暂未引入

详见 [故障排查 — 聊天超时](../6-TROUBLESHOOTING/ai-chat-issues.md#聊天超时llm_timeout)。

---

## Vision 图片描述

文档图片走 Vision LLM 描述链路，可调优并发、超时、重试：

```env
VISION_CONCURRENCY=2                    # 并发数（MiniMax 建议 2）
VISION_TIMEOUT_SECONDS=120              # 单图超时
VISION_MAX_RETRIES=2                    # 最大重试
VISION_RETRY_BASE_DELAY_SECONDS=3       # 退避基数

# 云模型（OpenAI-compatible）
VISION_MAX_TOKENS=384
VISION_TEMPERATURE=0

# Ollama 本地
VISION_NUM_CTX=2048
VISION_NUM_PREDICT=384
```

- 外部 Vision API 的 5xx/520/超时视为可恢复故障，指数退避重试
- 单图失败只生成该图降级描述，不阻塞整份文档
- 当前推荐模型 MiniMax-M3，详见 [添加来源 — 推荐模型](../3-USER-GUIDE/adding-sources.md#推荐模型)

---

## 联网搜索（Tavily）

```env
TAVILY_SEARCH_MAX_CALLS=5   # 已由设置项「单次回答联网搜索次数上限」管理（设置页可调，1-20，默认 5）
```

超过上限后直接返回降级说明，不再触发真实网络请求。Tavily 免费档月度配额 1000/月，耗尽时返回失败。

---

## 批处理

### TTS 批处理
```env
TTS_BATCH_SIZE=5  # OpenAI:5, Google:4, ElevenLabs:2, Local:1
```

> TTS 失败会回退静音音频，不阻塞播客生成。

### Embedding 批处理
```env
EMBEDDING_BATCH_SIZE=10  # 5=低内存慢处理，10=平衡，20+=高吞吐
```

---

## 内容处理引擎

```env
CCORE_DOCUMENT_ENGINE=mineru   # 中文 PDF（默认）
# CCORE_DOCUMENT_ENGINE=docling  # 英文文档
# CCORE_DOCUMENT_ENGINE=simple   # 纯文本最快
```

| 引擎 | 最佳场景 |
|------|----------|
| `mineru` | 中文 PDF、复杂排版、强表格识别 |
| `docling` | 英文 PDF、层级结构提取 |
| `simple` | 纯文本、Markdown |

**MinerU 专用设置**：
```env
MINERU_TABLE_ENABLE=true
HF_ENDPOINT=https://hf-mirror.com   # 国内镜像加速
MINERU_MODEL_SOURCE=modelscope
```

---

## 日志与调试
```bash
RUST_LOG=debug   # Rust 组件
LOGLEVEL=DEBUG   # Python 组件（落地 logs/open_notebook.log）
```

---

## 端口配置

| 部署模式 | 前端 | API | SurrealDB |
|----------|------|-----|-----------|
| **标准容器** | 3000 | 5055 | 8000 |
| **本地源码** | 3001 | 5056 | 127.0.0.1:8001 |

> 本地源码模式下 SurrealDB 仅绑定宿主机回环，不向局域网暴露；浏览器走相对 `/api`，由 Next.js 代理至 `INTERNAL_API_URL`。

---

## 备份与恢复
```bash
# 备份
tar -czf backup.tar.gz data/ surreal_data/

# 恢复
tar -xzf backup.tar.gz
```
