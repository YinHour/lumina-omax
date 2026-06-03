# 本地 TTS（文本转语音）

使用 Speaches 设置本地语音合成。

---

## Docker 配置

```yaml
services:
  speaches:
    image: speaches/speaches:latest
    ports:
      - "8001:8001"
    environment:
      - WHISPER__MODEL=small
```

---

## GPU 加速

如需 GPU 加速，在 docker-compose 中添加：
```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

---

## 在 Lumiton·Omax 中配置

Settings → API Keys → 添加 OpenAI-Compatible 凭证
- Base URL：`http://speaches:8001/v1`
- 配置 TTS 端点
