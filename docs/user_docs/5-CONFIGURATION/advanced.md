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

## 批处理

### TTS 批处理
```env
TTS_BATCH_SIZE=5  # OpenAI:5, Google:4, ElevenLabs:2, Local:1
```

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
```

---

## 日志与调试
```bash
RUST_LOG=debug   # Rust 组件
LOGLEVEL=DEBUG   # Python 组件
```

---

## 端口配置

前端 8502、API 5055、SurrealDB 8000（Docker 默认）

---

## 备份与恢复
```bash
# 备份
tar -czf backup.tar.gz data/ surreal_data/

# 恢复
tar -xzf backup.tar.gz
```
