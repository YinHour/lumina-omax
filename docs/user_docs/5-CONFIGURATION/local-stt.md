# 本地 STT（语音转文本）

使用 Speaches 设置本地语音识别。

---

## Docker 配置

同 [本地 TTS](local-tts.md)，Speaches 同时提供 TTS 和 STT 服务。

---

## Whisper 模型选项

| 模型 | 大小 | 质量 |
|------|------|------|
| `tiny` | ~1GB | 基础 |
| `small` | ~2GB | 良好 |
| `medium` | ~5GB | 很好 |
| `large` | ~10GB | 最佳 |

---

## 在 Lumiton·Omax 中配置

Settings → API Keys → 添加 OpenAI-Compatible 凭证
- Base URL：`http://speaches:8001/v1`
- 配置 STT 端点
