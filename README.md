<a id="readme-top"></a>

[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![MIT License][license-shield]][license-url]

<br />
<div align="center">
  <a href="https://github.com/YinHour/lumina-omax">
    <img src="docs/assets/hero.svg" alt="Lumiton Omax Logo">
  </a>

  <h2 align="center">Lumiton·Omax | 知涌</h2>

  <p align="center">
    面向研发资料管理、证据问答和实验复盘的本地优先 AI 科研助手。
    <br />
    基于 <a href="https://github.com/lfnovo/open-notebook">Open Notebook</a> 二次开发，强化多人试用、中文体验、来源管理、旧 Office 导入和全局 Ask 可信度。
    <br />
    <br />
    <a href="docs/0-START-HERE/index.md">开始使用</a>
    ·
    <a href="docs/3-USER-GUIDE/index.md">用户指南</a>
    ·
    <a href="docs/8-CUSTOMIZATION/00-index.md">二开记录</a>
    ·
    <a href="docs/1-INSTALLATION/index.md">部署文档</a>
  </p>
</div>

---

## 项目定位

Lumiton·Omax | 知涌是一个可自托管、可选择多模型供应商的 AI 科研资料工作台。它保留了 Open Notebook 的笔记本、来源、笔记、搜索、问答、播客和多模型能力，并在本仓库中围绕企业内网试用和油田化学研发资料场景做了持续二次开发。

当前二开重点不是单纯换皮，而是让系统更适合多人试用和真实资料入库：

- 研发历史资料可以持续进入知识库，包括 `.doc`、`.xls`、`.ppt/.pptx`、`.docx/.xlsx/.xlsm`、PDF、网页等常见材料。
- 全局 Ask 显示来源总数、可检索来源数和本次命中来源数，帮助用户判断回答覆盖是否充分。
- 来源、笔记本、上传者、重复文件和长文档阅读体验更适合多人协作。
- 中文界面、登录入口、产品图标、帮助文档和操作提示更贴近正式试用。
- 局域网源码部署路径经过收敛，浏览器通过前端 `/api` 代理访问后端，避免把本机 `localhost` API 地址暴露给终端用户。

## 核心能力

### 资料入库与来源管理

- 支持 PDF、Office 文档、旧版 Office、网页、音频、视频等来源类型。
- 旧版 Word `.doc`、旧版 Excel `.xls` 和演示文稿可通过 LibreOffice 转换后解析。
- Excel 表格内容会清理整列空白列，并修复部分旧表格无法按 Markdown 表格渲染的问题。
- 上传重名文件时支持重复检查，大小写差异和首尾空格也会按重复处理。
- 用户可以选择“仅上传非重复文件”，减少重复资料进入知识库。
- 来源列表支持搜索、分页、上传者展示、原始文件名保留和完整来源详情页。
- 来源详情页的标题、关闭、更多操作、与来源对话和内容 Tab 在长文档阅读时保持易操作。

### 笔记本与多人协作

- 支持多用户账号、注册审批、角色区分、管理员设置和个人资料维护。
- 笔记本记录创建者，密码管理、归档和删除等操作按创建者权限收敛。
- 笔记本首页支持“只看我的”，适合多人试用时快速找到自己创建的笔记本。
- 笔记本可设置来源数量上限，避免单个笔记本过大影响检索和问答体验。
- 添加现有来源时仅展示已完成处理的来源，并支持搜索、全选和剩余槽位限制。
- 打开笔记本后可按来源名称筛选，并控制本次聊天引用哪些来源。

### 问答、搜索与研发复盘

- 支持笔记本内对话、来源对话和全局 Ask。
- 全局 Ask 会展示覆盖统计：来源总数、可检索来源、本次命中来源。
- 全局 Ask 历史保存在浏览器端，可回看问题、回答和当时的覆盖统计。
- NotebookLM 风格导览卡片会根据笔记本内容生成摘要和建议问题。
- 每轮回答后生成下一步建议问题，用户点击即可继续追问。
- 长耗时问答会显示阶段提示，回答完成后不再等待建议问题生成才恢复输入。
- 启用联网搜索时增加超时和降级处理，避免长时间停在“正在搜索”状态。

### 界面、部署与可观测性

- 全站 UI 已迁移到“温暖研究”风格：克制的靛蓝主色、柔和表面、响应式布局和移动导航。
- 登录页、产品图标、浏览器 favicon 和侧边栏品牌统一。
- 用户帮助中心已同步旧 Office 导入、Excel 清理、Ask 覆盖统计、反爬 URL 边界和重名策略。
- `make start-all` 会启动 DB、API、worker 和前端，并等待 API ready 后再启动前端。
- API、worker、前端和 SurrealDB 日志分别写入 `logs/`，聊天链路带有更清楚的 INFO 级可观测日志。
- Next.js 16 入口已迁移到 `proxy.ts`，生产构建路径固定为 `next build --webpack`。

## 与原版 Open Notebook 的关系

本仓库是面向 Lumiton·Omax | 知涌试用的二开版本，核心架构和大量基础能力来自上游 Open Notebook：

- FastAPI 后端、Next.js 前端、SurrealDB 数据库和 LangGraph 工作流。
- 多模型供应商支持，依托 Esperanto 接入 OpenAI、Anthropic、Google、Ollama、Mistral、DeepSeek、xAI、OpenRouter 等。
- 笔记本、来源、笔记、搜索、聊天、播客和内容转换等基础模块。

二开内容主要记录在 [docs/8-CUSTOMIZATION/00-index.md](docs/8-CUSTOMIZATION/00-index.md)。如果要比较上游能力与本仓库改动，应优先阅读该文件。

## 当前源码部署方式

本仓库当前推荐源码方式部署，适合内网试用、二开验证和本地调试。

### 运行环境

- Docker，用于启动 SurrealDB v2。
- Python / `uv`，用于 API 和后台 worker。
- Node.js / npm，用于 Next.js 前端。
- LibreOffice，用于旧版 Office 文件转换和演示文稿转换。
- 可用的 AI 模型凭据，或者本地 Ollama / OpenAI-compatible 服务。

### 本地启动

1. 准备 `.env`。可参考 [.env.example](.env.example) 和 [CONFIGURATION.md](CONFIGURATION.md)。
2. 安装前后端依赖。
3. 启动完整服务：

```bash
make start-all
```

默认端口：

| 服务 | 地址 |
| --- | --- |
| 前端 | `http://localhost:3001` |
| API | `http://localhost:5056` |
| API 文档 | `http://localhost:5056/docs` |
| SurrealDB | `127.0.0.1:8001` |

停止服务：

```bash
make stop-all
```

查看服务状态：

```bash
make status
```

> 局域网访问时，用户浏览器应访问前端地址，例如 `http://<部署机器IP>:3001/`。浏览器侧请求应走相对路径 `/api`，由 Next.js 代理到后端；不要让终端用户直接访问部署机本地 `localhost:5056`。

## 常用开发命令

```bash
# 前端 lint、测试和生产构建
make codex-frontend-check

# 后端 ruff 和 pytest
make codex-backend-check

# 快速检查 diff 空白问题
make codex-quick-check

# 仅启动数据库
make database

# 仅启动 API
make api

# 仅启动 worker
make worker-start
```

更完整的安装说明见 [docs/1-INSTALLATION/index.md](docs/1-INSTALLATION/index.md) 和 [docs/1-INSTALLATION/from-source.md](docs/1-INSTALLATION/from-source.md)。

## Provider Support Matrix

Thanks to the [Esperanto](https://github.com/lfnovo/esperanto) library, this project can work with multiple model providers.

| Provider | LLM Support | Embedding Support | Speech-to-Text | Text-to-Speech |
| --- | --- | --- | --- | --- |
| OpenAI | yes | yes | yes | yes |
| Anthropic | yes | no | no | no |
| Groq | yes | no | yes | no |
| Google (GenAI) | yes | yes | no | yes |
| Vertex AI | yes | yes | no | yes |
| Ollama | yes | yes | no | no |
| Perplexity | yes | no | no | no |
| ElevenLabs | no | no | yes | yes |
| Azure OpenAI | yes | yes | no | no |
| Mistral | yes | yes | no | no |
| DeepSeek | yes | no | no | no |
| Voyage | no | yes | no | no |
| xAI | yes | no | no | no |
| OpenRouter | yes | no | no | no |
| DashScope (Qwen) | yes | no | no | no |
| MiniMax | yes | no | no | no |
| OpenAI Compatible | yes | no | no | no |

OpenAI Compatible includes LM Studio and other OpenAI-compatible endpoints.

## 文档入口

### 用户文档

- [开始使用](docs/0-START-HERE/index.md)
- [用户指南](docs/3-USER-GUIDE/index.md)
- [添加来源](docs/3-USER-GUIDE/adding-sources.md)
- [搜索与全局 Ask](docs/3-USER-GUIDE/search.md)
- [界面概览](docs/3-USER-GUIDE/interface-overview.md)
- [高效对话](docs/3-USER-GUIDE/chat-effectively.md)

### 部署与开发

- [安装部署](docs/1-INSTALLATION/index.md)
- [源码部署](docs/1-INSTALLATION/from-source.md)
- [配置说明](CONFIGURATION.md)
- [API 参考](docs/7-DEVELOPMENT/api-reference.md)
- [贡献指南](CONTRIBUTING.md)
- [二开记录](docs/8-CUSTOMIZATION/00-index.md)

## 近期二开里程碑

- 温暖研究风格 UI 和响应式导航。
- 多用户登录、注册审批、角色权限、个人资料和管理员用户管理。
- 笔记本创建者权限、密码管理、归档/删除权限收敛。
- NotebookLM 风格导览卡片和回答后的建议问题。
- 长耗时问答阶段提示、联网搜索超时降级和聊天链路日志。
- 来源搜索、分页、跨笔记本来源复用、来源数量上限和已嵌入来源过滤。
- 旧版 Office 文件入库、Excel 表格清理、全局 Ask 覆盖统计和历史。
- 重名文件检查、原始文件名保留、来源详情 sticky 操作区和 ChatPanel 长内容宽度约束。
- `make start-all` 源码启动流程、Next.js 16 proxy 入口和前端 `/api` 代理收敛。

## 后续方向

根据试用反馈，后续仍建议继续推进：

- 图片识别从“描述画面”升级为“读取关键数值、判断是否合格、指出异常”。
- 自动提取产品代号、单体、实验类型等标签。
- 将 Excel 实验数据拆成结构化记录，形成可搜索、可筛选的实验索引。
- 按产品形成实验时间线。
- 展示产品版本演进和复配关联关系。
- 针对 ScienceDirect、OnePetro、ACS 等强登录或反爬学术站点，继续评估更稳妥的资料导入路径。

## License

Lumiton·Omax is MIT licensed. See the [LICENSE](LICENSE) file for details.

本仓库基于 Open Notebook 二次开发。上游项目信息、社区和原始文档可参考 [lfnovo/open-notebook](https://github.com/lfnovo/open-notebook)。

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- MARKDOWN LINKS & IMAGES -->
[forks-shield]: https://img.shields.io/github/forks/YinHour/lumina-omax.svg?style=for-the-badge
[forks-url]: https://github.com/YinHour/lumina-omax/network/members
[stars-shield]: https://img.shields.io/github/stars/YinHour/lumina-omax.svg?style=for-the-badge
[stars-url]: https://github.com/YinHour/lumina-omax/stargazers
[issues-shield]: https://img.shields.io/github/issues/YinHour/lumina-omax.svg?style=for-the-badge
[issues-url]: https://github.com/YinHour/lumina-omax/issues
[license-shield]: https://img.shields.io/github/license/YinHour/lumina-omax.svg?style=for-the-badge
[license-url]: https://github.com/YinHour/lumina-omax/blob/main/LICENSE
