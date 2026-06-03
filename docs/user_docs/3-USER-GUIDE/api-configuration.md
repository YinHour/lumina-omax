# API 配置指南

通过设置界面配置 AI 提供商凭证。无需编辑文件。

> **前提条件**：必须先在 `docker-compose.yml` 中设置 `OPEN_NOTEBOOK_ENCRYPTION_KEY`，然后才能存储凭证。

---

## 概述

Lumiton·Omax 通过**凭证系统**管理 AI 提供商访问：

1. 为每个提供商创建**凭证**（API 密钥 + 设置）
2. 凭证被**加密**存储在数据库中
3. **测试连接**验证凭证是否有效
4. **发现并注册模型**让它们可用

---

## 配置步骤

### 第 1 步：添加凭证
设置 → API Keys → 添加凭证 → 选择提供商 → 填写信息 → 保存

### 第 2 步：测试连接
点击凭证卡片上的 **Test Connection**

### 第 3 步：发现模型
点击 **Discover Models**

### 第 4 步：注册模型
选择要使用的模型 → 点击 **Register Models**

---

## Vision Model 配置

Vision Model 用于自动描述文档中的图片内容（PDF、PPT、Excel 中的图表）：

1. 设置 → API Keys → 高级设置
2. 找到 **Vision Model** 下拉选择器
3. 选择一个支持视觉的模型（如 `gpt-4o`）

配置后，文档中的图片会被自动提取、描述并纳入向量搜索索引。

---

## 多凭证支持

每个提供商可以有**多个凭证**。适用于：
- 不同项目使用不同的 API 密钥
- 不同端点测试
- 多团队成员各自管理

---

## 支持的提供商

### 云端
OpenAI、Anthropic、Google Gemini、Groq、Mistral、DeepSeek、xAI、OpenRouter、Voyage AI、ElevenLabs、DashScope (Qwen)、MiniMax

### 本地
Ollama、LM Studio（OpenAI 兼容模式）

### 企业
Azure OpenAI、Vertex AI

---

## 常见问题

**凭证无法保存** → 检查 `OPEN_NOTEBOOK_ENCRYPTION_KEY` 是否已设置

**测试连接失败** → 验证 API 密钥格式是否正确、检查网络/代理设置

**模型未显示** → 重新执行 Discover Models → Register Models
