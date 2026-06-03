# Ollama 指南

---

## 安装

1. 安装：https://ollama.ai
2. 运行：`ollama serve`
3. 下载模型：`ollama pull mistral`

---

## 配置

Settings → API Keys → 添加凭证 → 选 Ollama → 输入 Base URL：

| 场景 | Base URL |
|------|----------|
| 同机非 Docker | `http://localhost:11434` |
| Docker 内连宿主机 | `http://host.docker.internal:11434` |
| Docker 内连 Ollama 容器 | `http://ollama:11434` |

---

## 推荐模型

| 模型 | 特点 | 内存需求 |
|------|------|----------|
| `llama3.3:70b` | 最佳质量 | 40GB+ RAM |
| `llama3.1:8b` | 平衡推荐 | 8GB RAM |
| `qwen2.5:7b` | 编程推理优秀 | 8GB RAM |
| `mistral:7b` | 通用 | 8GB RAM |
| `phi3:3.8b` | 小且快 | 4GB RAM |

---

## 网络配置

若 Ollama 在另一台机器：
```bash
# 编辑 Ollama 配置允许外部连接
# 然后在 Lumiton·Omax 中添加凭证，URL 用 http://Ollama机器IP:11434
```
