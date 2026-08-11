# Lumina OMax — Custom Development Changelog

本文档记录在 [lfnovo/open-notebook](https://github.com/lfnovo/open-notebook) 基础上进行的二次开发变更，包括功能增强、Bug 修复、架构决策等。按主题分类，每个条目标注涉及文件和关键决策。

> **阅读规则**：本文档是累积历史总账，早期章节保留当时实现和决策，不保证代表当前最终状态。同一主题出现冲突时，以更新章节和当前代码为准；实施前仍需核对 Git 现场、真实运行路径和相关测试。

---

## 1. 品牌与国际化

### 品牌重塑（Lumina | Yinshi AI）
- `frontend/src/app/layout.tsx` — 页面标题/Logo 替换
- `frontend/src/components/layout/AppSidebar.tsx` — 侧边栏品牌标识替换
- 8 种语言 i18n 文件全部更新品牌名
- 同步修复受影响的自动化测试

### 阻断自动升级
- `api/routers/config.py` — `get_latest_version_cached` 强制返回空版本
- `frontend/src/lib/hooks/use-version-check.ts` — 废弃版本检查 hook
- `frontend/src/components/layout/SystemInfo.tsx` — 移除所有升级/版本比对 UI

### AI 输出中文化
- `migrations/18.surrealql` — 所有内置 AI 转换模板标题和描述中文化
- 所有默认 AI 处理 Prompt 末尾追加「必须使用简体中文输出」指令

### 新增 i18n 标签
- `frontend/src/lib/locales/zh-CN/index.ts:886-887` — `visionModelLabel`: "视觉模型"
- `frontend/src/lib/locales/en-US/index.ts:885-886` — `visionModelLabel`: "Vision Model"

**决策**：品牌名全局硬编码替换，保持与原项目 UI 框架一致。

---

## 2. 文档处理引擎

### Docling 引擎集成
- `pyproject.toml` — `"content-core[docling]>=1.14.1"`
- `.env` — `CCORE_DOCUMENT_ENGINE=docling`
- 虚拟环境 `content_core/processors/docling.py` — `run_in_executor` 修复异步阻塞

### MinerU 引擎集成（magic-pdf）
- `open_notebook/graphs/source.py:132-230` — 对 PDF/PPT/DOC 劫持至 MinerU 解析，`_sync_extract` 内执行
- 启用 `MINERU_TABLE_ENABLE=true` 增强表格识别
- 镜像加速：`HF_ENDPOINT=https://hf-mirror.com`、`MINERU_MODEL_SOURCE=modelscope`
- 提取图片复制到 `data/uploads/images/{source_id}/` 并重写 URL 至 `/api/uploads/images/...`
- `open_notebook/domain/content_settings.py` — 引擎选项新增 `mineru`
- `patch_mineru.py` — 修复 `mineru_vl_utils` 与 `transformers` 的 `Qwen2VLConfig` 版本冲突
- **失败回退**：MinerU 失败自动降级至 Simple 引擎

### Office 文件转换
- `open_notebook/utils/office_converter.py` — `.doc/.docx/.ppt/.pptx` 通过 LibreOffice headless 转 PDF
- **Excel 排除**：`.xls/.xlsx` 明确排除 PDF 转换，保留行列结构直接解析 Markdown

### Excel 大宽表解析修复
- `open_notebook/graphs/source.py:34-87` — `_sanitize_excel_table_newlines()` 分两阶段修复：
  1. 将碎片行回并到表格行内，用 `<br>` 保留语义换行
  2. 按预期分隔符数量重建行（Markdown 表头分隔行 `|` 计数匹配）
- `tests/test_office_converter.py` — 新增测试，覆盖 doc/docx/ppt/pptx/txt/pdf 转换路径

### Vision LLM 图片描述（新增 2026-05-29）
- `open_notebook/ai/models.py:69` — `DefaultModels` 启用 `default_vision_model` 字段
- `open_notebook/ai/models.py:222-232` — `ModelManager.get_vision_model()` 方法
- `open_notebook/graphs/source.py:255-319` — `content_process` 节点完成后扫描图片目录，逐张调用 Vision LLM 描述，结果以 `## Figure Descriptions` 注入 `full_text`
- 描述纳入向量嵌入，支持按图片内容语义搜索
- `api/models.py:109` / `api/routers/models.py` — API 层 vision model 读写
- `frontend/src/app/(dashboard)/settings/api-keys/page.tsx:1092` — 高级设置新增 Vision Model 选择器

**决策**：MinerU 为首选引擎（中文场景最优），Docling 为备选。Excel 不转 PDF 避免宽表分页破坏结构。

---

## 3. 流式输出（SSE）与异步

### LangGraph 异步化
- `open_notebook/graphs/chat.py`、`source_chat.py` — `model.invoke` → `await model.ainvoke`，全部节点函数异步化
- `SqliteSaver` → `AsyncSqliteSaver`（基于 `aiosqlite`），保障断点记忆并发安全
- `run_in_executor` / `asyncio.to_thread` 处理 CPU 密集/同步阻塞路径

### SSE 流式交互
- 全部 Chat/Ask 工作流引入 `text/event-stream` SSE 流
- `X-Accel-Buffering: no` 响应头击穿 Next.js 代理缓冲
- `frontend/src/lib/hooks/useSourceChat.ts`、`useNotebookChat.ts` — 重构 `ReadableStream` 解析，支持 chunks 缓冲拼接、不完整行防撕裂、事件类型鉴别
- Ask 模式：`astream_events(version="v2")` 双轨流式（思考过程 + 最终答案分开渲染）

### 流式过滤 / 工具输出防泄漏
- Tavily 返回内容包裹在 `<web_search_results>` XML 标签内
- SSE 流底层增加 XML 标签实时嗅探和屏蔽
- 过滤 `get_session` 中的 Tool 执行消息

**决策**：全链路 SSE 替代批量返回，打字机效果提升用户体验。`os.environ` 全局污染修复（独立参数透传避免并发冲突）。

---

## 4. 文件上传与源管理

### original_filename 与重名检测（新增 2026-05-26）
- `open_notebook/domain/notebook.py` — `Asset` 新增 `original_filename` 字段
- `api/routers/sources.py` — 上传时写入原始文件名，默认标题格式 `文件名_YYMMDDhhmmss.扩展名`（时间戳在扩展名前）
- `POST /sources/check-duplicates` — 按 `Asset.original_filename` 查重
- `frontend/src/components/sources/AddSourceDialog.tsx` — 前端改为调用后端批量查重
- 下载文件名优先使用 `original_filename` 还原

### UUID 文件存储
- 物理文件使用 UUID 命名，消除 TOCTOU 并发竞争
- API 层增加文件名映射确保资源标题展示真实文件名

### 上传流程优化
- `api/routers/sources.py` — Office 同步转换逻辑移至后台（`open_notebook/graphs/source.py` MinerU 分支），实现"前台快返回、后台重处理"
- 重构文件上传查重与状态拦截，消除"处理中"进度弹窗闪烁

### 源列表增强
- `frontend/src/app/(dashboard)/sources/page.tsx:469-480` — 源标题增加 Radix Tooltip 悬停浮窗
- `frontend/src/components/sources/SourceCard.tsx:264` — 笔记本源列表标题改用 Radix Tooltip
- 引用热度统计：后端聚合查询新增"引用次数"列

### 删除/移除逻辑分离
- `migrations/17.surrealql` — `source` 表新增 `origin_notebook_id`
- 当前笔记本直接上传的文件允许删除，从现有来源添加的仅允许解绑移除

**决策**：UUID 物理存储不变，`original_filename` 仅作业务语义字段。标题时间戳仅用于展示区分，不作为重名判断依据。

---

## 5. RAG 检索增强

### 双轨引用体系
- Chat 系统提示词强制 `[1](URL)` 内联超链接 + `## 参考文献` 列表格式
- Few-Shot 负面样本防御（跳号/不带链接/双结尾）
- 本地/网络引用隔离：`source-references.tsx` 自动探测网络引用编号上限
- 前端后处理兜底：`source-references-bibliography.ts` 正则补全缺失序号

### 上下文管理
- `open_notebook/utils/context_builder.py` — Notes 截断优先级反转（`note: 100 > source: 75`）
- 短上下文模式下 `full_text` 丢弃问题修复，同时加载原文 + insight
- 截断阈值放宽至 50000 字符，适配 128k 上下文模型
- Chat 模式拉取笔记内容从 `short`（摘要）改为 `long`（全文）

### Ask 模式搜索优化
- `note:` 前缀节点强制置顶
- `max_tokens` 策略优化：agent 2000 / 局部答案 2000 / 最终答案 2000
- DeepSeek-R1 JSON Structured Output 冲突修复

### Tavily 联网搜索全栈集成
- `ContentSettings` 新增 `tavily_api_key` / `tavily_include_domains`
- `open_notebook/graphs/chat.py`、`source_chat.py` — `enable_web_search` 动态 Tool 绑定
- `pyproject.toml` 锁定 `tavily-python`
- 前端 Settings 页面 "Web Search" 配置卡片，ChatPanel 联网搜索开关

### 知识图谱（Hybrid RAG）
- `migrations/15.surrealql` — `kg_entity` 表 BM25 全文搜索索引
- 三类文档（`data_flows_and_retrieval.md`、`kg_design_and_architecture.md`、`kg_research_and_implementation_plan.md`）设计完整 Hybrid RAG 方案：
  - Hub Node 超关系建模（EXPERIMENT 枢纽节点）
  - Qwen 60k+ tokens 单次全篇 KG 抽取
  - SurrealDB `kg_entity`/`kg_relation` 表，`UPSERT` + `slugify` 消歧
  - Ask 模式并行 Vector Search + Graph Search（BM25 入口 → 1-hop 子图扩展）

### Prompt Engineering
- `prompts/chat/system.jinja`、`source_chat/system.jinja` — "触发式领域专家"模式（Oilfield Chemistry）
- 四维结构化框架：机理验证 → 配方分析 → 风险提示 → 行动建议

**决策**：向量检索 + 知识图谱并行，面向科研文献场景做 Hybrid RAG。KG 链路已部分实现，但 Vision LLM + KG 全联动仍在路线图中。

---

## 6. 笔记本与聚合功能

### 聚合笔记本（Aggregate Notebook）
- SurrealDB `aggregates` 动态边结构：动态视图关联替代物理拷贝
- `array::concat` + `flatten` 跨边界查询，毫秒级实时同步
- 独立黑名单：`hidden_sources/hidden_notes` + `array::difference`
- `get_chat_sessions` 查询范围强制收敛，修复聊天会话泄漏
- 前端：聚合入口、多选弹窗、颜色标签 + 自动聚类、Badge 来源信息卡片
- 密码鉴权：聚合合并前逐个校验目标笔记本密码

### 笔记本密码保护
- `migrations/16.surrealql` — `notebook` 表增加 `password` / `creator_name`
- 加密笔记本全屏密码输入，每次访问必须重新验证
- 管理员密码 `NEXT_PUBLIC_MASTER_NOTEBOOK_PASSWORD` 可绕过单笔记本密码
- 创建人展示 + 锁定图标

### 上下文状态记忆
- `localStorage` 按笔记本 ID 持久化记录每个源的勾选状态（全文/见解）
- `SourcesColumn` 表头全局批量操作菜单（全部全文/全部见解）

### 批量管理
- 批量删除带进度反馈，修复高频并发删除静默失败与分页列表错位
- 删除密码校验 + 超级管理员密码全局维护

---

## 7. 聊天与交互优化

### 滚动体验
- `ChatPanel` 用户滚动意图检测：上滚时暂停强制追踪，下滚至底部或发新消息时恢复

### 弹窗嵌套修复
- Radix UI `AlertDialog` 与 `Dialog` 嵌套 `pointer-events: none` 残留修复
- 键盘事件冲突：密码输入框输入时底层列表快捷键拦截修复

### 分页机制
- Sources 列表从无限滚动改为传统页码分页（每页 30 篇）
- 搜索匹配：后端 SurrealQL 从精确匹配改为 `string::contains` 子串匹配

### 问答闭环
- Ask 界面答案结果区新增"复制"和"保存为笔记"功能
- 多终端隔离：LocalStorage 配置独立记忆（联网搜索等偏好多终端互不干扰）

---

## 8. 基础设施与运维

### 环境与配置
- `.env` SurrealDB 连接从 Docker 内网地址改为 `ws://127.0.0.1:8000/rpc`
- `OPEN_NOTEBOOK_ENCRYPTION_KEY` 占位值安全提醒（生产环境必须更换）
- `frontend/.env.local` 删除 `NEXT_PUBLIC_API_URL`，前端自动推断 API URL

### 日志系统
- `logger_config.py` — 基于 loguru 统一接管所有进程日志，落地 `logs/open_notebook.log`
- 在 `open_notebook/graphs/source.py` 中注入解析进度日志

### 数据库
- `open_notebook/database/async_migrate.py` — 空迁移（`-- empty`）跳过 SQL 但推进 version
- 连接池：`asyncio.Queue` + SurrealDB OCC
- `pyproject.toml` 读取版本号替代 shell `grep | cut`（Windows 兼容）

### Windows 兼容
- `Makefile` — 多处 `sleep N` 替换为 `python -c "import time; time.sleep(N)"`
- `make api` shell 命令改为 Python 实现

### 并发与隔离
- `os.environ` 全局污染修复（独立参数透传 + LangGraph Checkpoint 隔离）
- 多用户隔离方案调研（连接池、租户标识、按请求透传 API Key）

### CI/CD
- `.github/workflows/test.yml` 增加 SurrealDB 启动
- 删除 `.github/workflows/claude-code-review.yml` 和 `claude.yml`

---

## 9. 模型适配

### Embedding
- `EMBEDDING_BATCH_SIZE` 改为 10，引入 `asyncio.sleep(0.5)` 多步缓冲
- Embedding 模型死循环修复（错用生成类模型）

### DeepSeek-R1
- JSON Structured Output 冲突修复（移除结构化类型约束）

### Next.js 15+
- `notebooks/[id]/page.tsx`、`sources/[id]/page.tsx` 使用 `React.use()` 异步解包路由参数

---

## 10. 测试体系

- `tests/test_office_converter.py` — Office 格式转换测试（11 条全部通过）
- `tests/test_sources_api.py` — Mock 修复（补 `model_manager.get_defaults()`）
- `frontend/src/components/search/StreamingResponse.test.tsx` — 前端组件测试（30 条通过）

---

## 11. 用户试用反馈修复 + CI/Review（新增 2026-05-29 ~ 2026-05-30）

基于《Lumina™ AI 科研助手试用反馈 20260527》13 项反馈中 P0 优先级的修复，PR #10。

### Chat 停止生成按钮（#1）
- `frontend/src/components/source/ChatPanel.tsx:420-428` — isStreaming 时 Send 变为红色 Stop 按钮（Square 图标），调用 `onCancelStreaming`
- `frontend/src/components/source/ChatPanel.tsx:327` — 拆出 floating spinner 只在无 `onCancelStreaming` 时显示
- `frontend/src/lib/hooks/useNotebookChat.ts:34,244-246,259-260` — 新增 `AbortController` ref，流式循环检测 `signal.aborted`，新增 `cancelStreaming()` 回调
- `frontend/src/lib/hooks/use-ask.ts:131-137` — 新增 `stopStreaming()`，仅 abort 不丢已生成内容
- `frontend/src/app/(dashboard)/sources/[id]/page.tsx:74` — 传 `chat.cancelStreaming` 给 ChatPanel
- `frontend/src/app/(dashboard)/notebooks/components/ChatColumn.tsx:113` — 传 `chat.cancelStreaming` 给 ChatPanel
- `frontend/src/app/(dashboard)/search/page.tsx:373-381` — Ask 流式中渲染 Stop 按钮，调用 `ask.stopStreaming()`
- `frontend/src/lib/locales/zh-CN/index.ts` `en-US/index.ts` — 新增 `chat.stopGenerating`
- `frontend/src/components/source/ChatPanel.tsx` — Send/Stop 按钮补 `aria-label` 可访问性

### Ask 准确率与容错增强（#11）
- `open_notebook/graphs/ask.py:104` — `vector_search` 每搜索词结果数 10 → **30**，解决 160+ 来源只返回 10 的问题
- `open_notebook/utils/error_classifier.py:69-80` — 新增 3 条分类规则：timeout / unsupported passthrough / bad request
- `open_notebook/utils/error_classifier.py:46-50` — 超时规则前置于通用网络规则，避免 `"timed out"` 被误判为 `NetworkError`
- `open_notebook/utils/error_classifier.py:108` — 未分类错误前缀优化，截断长度 200→300

### Excel 内嵌图片提取（#13）
- `open_notebook/graphs/source.py:250-303` — Excel 处理管道新增图片提取：LibreOffice headless 转 PDF → PyMuPDF 逐页扫描 → 存入 `data/uploads/images/{source_id}/` 供 Vision LLM
- 文本仍走 openpyxl 保大宽表结构，图片单独提取，互不干扰
- 全路径异常容灾（非致命）

### save_source 类型安全与 check-duplicates 修复
- `open_notebook/graphs/source.py:405-411` — `original_filename` 增加 `isinstance(str)` 校验，修复 MagicMock 污染
- `api/routers/sources.py:1064-1074` — 修复 `SELECT VALUE DISTINCT` 语法错误（SurrealQL 不接受），改为 `SELECT VALUE` + Python `set()` 去重
- `api/routers/sources.py:1077` — 清理双重 `raise` 死代码，错误消息不泄漏 DB 内部细节

### 测试体系扩充
- `tests/test_error_classifier.py` — 新增 25 条（截断/回归/新增/未分类/边界全覆盖）
- `tests/test_sanitize_excel.py` — 新增 8 条（正常表/多行合并/标题隔离/分隔复位/空输入）
- `frontend/src/components/source/ChatPanel.test.tsx` — 新增 5 条（Stop 渲染/点击回调/向后兼容/禁用状态）
- `tests/test_integration_e2e.py` — 新增 32 条 L2/L4/L5 集成/E2E 测试（Hermes Agent 生成，标记 `@pytest.mark.e2e`，手动运行）

### CI 与 E2E 隔离
- `.github/workflows/test.yml:53` — CI 排除 e2e：`pytest -m "not e2e"`
- `pyproject.toml` — 注册 `e2e` marker
- `tests/test_integration_e2e.py:24` — `pytestmark = pytest.mark.e2e`
- E2E 需 AI 模型配置 + 测试数据文件，不适合 CI

### PR Review（Sourcery）修复
- `api/routers/sources.py:1080` — 错误消息回归通用提示，完整错误仅写 log
- `frontend/src/lib/hooks/useNotebookChat.ts:262` — `abortController` null guard 补全

**决策**：P0 阻断性问题优先修复，E2E 与单元测试分离不阻塞 CI，PR Review 反馈及时收敛。

---

## 12. 多用户认证系统（新增 2026-06-01）

基于企业内部多用户使用场景，实现完整的账号密码登录、注册审批、角色管理和 Landing Page 品牌展示。

### 用户注册与管理员审批
- `api/routers/auth.py:94-142` — `POST /auth/register`，用户自助注册，默认 `status="pending"`、`role="user"`
- `api/routers/auth.py:207-217` — 登录时校验 `pending`（等待审批）和 `rejected`（已拒绝）状态
- `open_notebook/domain/user.py` — 新增 `User` 领域模型，PBKDF2-HMAC-SHA256 密码哈希（100,000 轮迭代 + 16 字节随机盐）
- `migrations/25.surrealql` — 新建 `user` 表（`username`/`password_hash`/`display_name`/`status`/`role`），`username` 唯一索引；`source` 表新增 `uploaded_by`/`uploader_name` 字段

### JWT 认证与安全
- `open_notebook/utils/jwt_config.py` — **新增公共模块**：JWT 密钥从 `AUTH_JWT_SECRET` 环境变量读取，逐级回退至 `OPEN_NOTEBOOK_ENCRYPTION_KEY` → 默认值；统一 `api/auth.py` 和 `api/routers/auth.py` 两处重复代码
- `api/routers/auth.py:53-57` — JWT HS256 签发，7 天过期，负载包含 `id`/`username`/`display_name`/`role`/`status`/`exp`
- `api/auth.py:20-121` — `PasswordAuthMiddleware` 升级为双轨鉴权：1) 超级管理员密码直接放行（后门），2) JWT 解码 + 用户状态校验
- `api/auth.py:81-117` — 中间件层拦截 `pending`/`rejected` 用户请求（403），Token 过期返回 401

### 超级管理员后门保留
- `api/routers/auth.py:154-191` — 登录时输入 `admin` + `OPEN_NOTEBOOK_PASSWORD` 可直接获取超级管理员 JWT
- `api/auth.py:70-79` — Bearer Token 直接匹配 Master Password 时以 `System Admin` 身份放行所有请求
- `frontend/src/lib/stores/auth-store.ts:85-93` — 登录页仅输入密码（无用户名）时默认以 `admin` 身份调用后门登录

### 管理员用户管理
- `frontend/src/app/(dashboard)/settings/components/UserApprovalDashboard.tsx` — **全新组件**（261 行），仅 `role="admin"` 可见
  - 用户列表按 `pending`/`active`/`rejected` 筛选，含注册时间、角色标识
  - **状态操作**：批准激活 / 拒绝申请 / 禁用账号，操作前弹出 `ConfirmDialog` 确认
  - **角色切换**：点击角色标签可在 `admin` ↔ `user` 间切换，保护 `admin` 账户不可降级
  - **密码重置**：`Key` 按钮弹窗输入新密码（≥6 位），调用 `PUT /auth/users/{id}/password`
- `api/routers/auth.py:246-269` — `GET /auth/users`（Admin only）用户列表
- `api/routers/auth.py:272-309` — `PUT /auth/users/{id}/status` 审批/拒绝/禁用
- `api/routers/auth.py:311-349` — `PUT /auth/users/{id}/role` 角色修改（保护 admin 账户）
- `api/routers/auth.py:351-383` — `PUT /auth/users/{id}/password` 管理员重置密码

### 速率限制（Rate Limiting）
- `api/rate_limiter.py` — **新增模块**：滑动窗口限流器，基于客户端 IP 识别
- `/auth/login` — 10 次/分钟；`/auth/register` — 5 次/5 分钟
- 支持 `X-Forwarded-For` 反向代理地址透传

### 登出与 Cookie 同步
- `api/routers/auth.py:385-393` — `POST /auth/logout`，服务端登出端点（为未来 Token 黑名单预留）
- `frontend/src/lib/stores/auth-store.ts:208-229` — 登出时调用 `/auth/logout` + 清除 `auth-token` Cookie + 清空 Zustand 状态

### 服务端路由守卫（Proxy）
- `frontend/src/proxy.ts` — 服务端路由守卫入口（Next.js 16 约定，§27 从 `middleware.ts` 迁移）
  - 检查 `auth-token` Cookie，无 Cookie 时重定向至 `/login?redirect=原路径`
  - 登录成功后 Cookie 与 localStorage 双写（`SameSite=Lax`，7 天过期）
  - 公开路径排除：`/login`、`/_next`、静态资源
- `frontend/src/app/(auth)/login/page.tsx` — 包裹 `Suspense` 边界支持 `useSearchParams`
- `frontend/src/components/auth/LoginForm.tsx:32-38` — 读取 `redirect` URL 参数存入 `sessionStorage`

### 上传者溯源
- `api/routers/sources.py:472-473,560-561` — `create_source` 写入 `uploaded_by=current_user["id"]`、`uploader_name=display_name 或 username`
- `frontend/src/app/(dashboard)/sources/page.tsx:489` — 源列表"上传人"列显示 `uploader_name`，null 时回退 `"System Admin"`
- `open_notebook/domain/notebook.py:320-321` — `Source` 类新增 `uploaded_by`/`uploader_name` 可选字段
- `api/models.py:376,399` / `frontend/src/lib/types/api.ts:48` — API 层和 TS 类型同步新增 `uploader_name`

### Landing Page 品牌重塑
- `frontend/src/components/auth/LoginForm.tsx:216-316` — 登录页左栏（Landing Page）更新：
  - **品牌**：Logo 图片替换为 `Lumiton·Omax图标.png`，标题 "Lumiton·Omax | 知涌"，副标题 "Oilfield Chemistry R&D Platform"
  - **核心叙事**：Hero 描述对齐方法论文档——"将历史经验、实验数据、现场反馈和产品机理假设组织成可追踪、可复盘、可预测的研发决策系统"
  - **四张特性卡**：7步研发闭环（产品代号→配方→工况→性能→归因链路）、原料与配方映射（分子理化特性→水泥矿物相变）、失败用例沉淀（自动结构化不可复用经验）、机理与预测并行（回答区分"已有证据""合理推断""需验证假设"）
  - **研发指标**：+40% 实验复用率 / -30% 现场失效风险 / 1/2 试错周期
  - **AI 能力栏**：50+ 文件格式 / 多源语义向量检索 / 8+ AI 模型供应商
  - **素材来源**：`task/suggestions/lumina_omax_rd_method_and_enablement.md`（油井水泥外加剂研发方法与客户引导方案）
- `frontend/public/logo.png` — 替换为 Lumiton·Omax 品牌图标（1.92MB，SHA256 与设计稿一致）

### 前端代码质量治理
- 全量 ESLint + TypeScript 零错误零警告（涉及 25 个文件）
- `any` 类型替换：`SearchResponse`/`SearchResult`/`Record<string, unknown>`/`instanceof Error` 类型守卫
- 移除 14 个文件的未用 import、6 处 `catch (e)` 裸变量、2 处 `let`→`const`
- Hook 依赖补全：`useCallback` 包裹、`useMemo` 依赖对齐
- `frontend/src/components/auth/LoginForm.tsx:217` — `<img>` → `next/image` 的 `<Image />`

**决策**：选择 PBKDF2 而非 bcrypt/argon2 以降低依赖复杂度。JWT 无状态设计，暂不实现 Token 黑名单。数据隔离保持现有共享模式，仅增加身份标识和操作溯源。

---

## 13. 侧边栏 UI 与个人资料（新增 2026-06-01 ~ 2026-06-02）

基于多用户认证系统上线后的界面体验优化。

### 侧边栏品牌标识重构
- `frontend/src/components/layout/AppSidebar.tsx:140-142` — Logo 图片替换为 `/logo.png`（28px），品牌文字硬编码为 `Lumiton·Omax|知涌`（`text-base font-bold whitespace-nowrap`）
- 文字居中于 Logo 图标与折叠 `<` 按钮之间（扁平化布局：Image | span(flex-1 text-center) | Button）
- 9 个 locale 文件 `appName` 同步更新为 `"Lumiton·Omax|知涌"`

### 底部功能区重组
- 主题/语言切换器从 `flex-col` 改为 `flex-row`，各占 `flex-1` 平分一行宽度
- 用户信息区（头像首字母圆圈 + display_name + @username）位于主题/语言上方、登出按钮上方，点击跳转 `/profile`
- 移除未使用的 `UserCircle` 导入

### 管理员菜单权限控制
- `AppSidebar.tsx:47-76` — `getNavigation` 接受 `isAdmin` 参数，"管理"分组中模型（`/settings/api-keys`）、设置（`/settings`）、高级（`/advanced`）标记 `adminOnly: true`
- 非管理员用户仅可见"转换"和"帮助"两项，模型/设置/高级自动隐藏
- 组件从 `useAuth()` 解构 `user`，传入 `user?.role === 'admin'`

### 侧边栏滚动修复
- `AppSidebar.tsx:160` — `<nav>` 增加 `overflow-y-auto min-h-0`，底部功能区固定在可视区
- `frontend/src/app/layout.tsx:25-29` — `<html>` 和 `<body>` 增加 `h-full overflow-hidden`，消除页面级外层滚动条

### 个人资料页 `/profile`
- `frontend/src/app/(dashboard)/profile/page.tsx` — **全新页面**：首字母头像 + 角色标签（ShieldAlert/Shield）+ 状态标签（CheckCircle/Clock/XCircle）
- **显示名称编辑**：输入框 + 保存按钮，调用 `PUT /auth/me` 更新
- **修改密码**：当前密码验证 + 新密码确认，调用 `PUT /auth/me/password`
- `frontend/src/lib/stores/auth-store.ts:289-338` — 新增 `updateProfile(displayName)` 和 `changePassword(oldPassword, newPassword)` actions
- `api/routers/auth.py:448-505` — 新增 `PUT /auth/me`（更新 display_name）和 `PUT /auth/me/password`（旧密码验证后更新）

**决策**：侧边栏品牌标识改为硬编码（非 i18n key），因为 Lumiton·Omax 是产品专有名称不随语言变化。管理员菜单过滤为纯前端控制，后端路由已有权限中间件兜底。

---

## 14. 帮助文档网页化（新增 2026-06-02）

将 `docs/` Markdown 渲染为可通过 `/help` 直接访问的网页帮助中心。

### 路由与渲染
- `frontend/src/app/(help)/help/` — **新增路由组**（中间件放行 `/help`，无需登录）
- `frontend/src/app/(help)/help/page.tsx` — 首页（`/help`），读取 `docs/user_docs/index.md` 渲染
- `frontend/src/app/(help)/help/[...slug]/page.tsx` — 子页面（如 `/help/3-USER-GUIDE/adding-sources`），动态路由
- `frontend/src/lib/help/docs.ts` — **新增工具模块**：`getHelpNav()` 构建导航树、`resolveDocPath()` 解析 URL、`readDoc()` 读取 Markdown

### 独立用户文档目录
- `docs/user_docs/` — **新建目录**（33 文件），与 `docs/`（开发文档）物理隔离
- 包含章节：2-CORE-CONCEPTS（4）、3-USER-GUIDE（10）、5-CONFIGURATION（12）、6-TROUBLESHOOTING（5）、index.md（1）
- 移除：播客文档（`podcasts-explained.md`）、定制记录（8-CUSTOMIZATION）、安装/贡献开发章节

### 导航系统
- `frontend/src/app/(help)/help/_components/HelpSidebar.tsx` — **客户端组件**：折叠式导航，每个大标题可点击展开/收起子项（`ChevronDown` 旋转动画）
- `docs.ts` — `SECTION_LABELS` + `DOC_LABELS` 两级中文映射表，`INCLUDED_CHAPTERS` 白名单过滤
- 导航数据在服务端 layout 调用 `getHelpNav()`，通过 props 传入客户端组件（避免 `fs` 模块浏览器端报错）

### Markdown 渲染升级
- 对照 `ChatPanel.tsx` 的 `AIMessageContent` 样式：`prose prose-sm prose-neutral` + `rehype-raw`
- 补齐全部组件映射：h1-h4、ul/ol/li、blockquote、pre/code（含 `language-` 检测）、table/thead/tbody/tr/th/td、hr、img
- 外部链接自动 `target="_blank"`

### 全量中文化
- 33 个文件全部翻译为简体中文
- 专业术语保留英文：API、RAG、JWT、SSE、OCR、TTS、STT、Markdown、URL、PDF 等
- 项目特有名词保留：SurrealDB、Ollama、Tavily、MinerU、Docling、Vision LLM 等

### Turbopack 兼容性修复
- `[[...slug]]` → `[...slug]`（Turbopack 不支持可选 catch-all 参数）
- 清理残留的 `[[slug]]` 目录

**决策**：用户文档与开发文档物理分离，避免混淆。导航标签中文化，内容翻译保留技术术语。帮助页面公开访问（无认证要求），方便用户随时查阅。

---

## 15. 品牌文本全局替换（新增 2026-06-01）

在全项目范围内将用户可见的"Open Notebook"替换为"Lumiton·Omax"。

### 替换范围
- `docs/` 全部 45 篇 Markdown 正文中的产品名称引用
- `README.md`、`README.dev.md` 标题、描述段落
- `AGENTS.md`、`CLAUDE.md`（含子目录共 18 个）概述段落
- `api/main.py:125-126,302` — FastAPI app `title`/`description`/根路由消息
- `open_notebook/` 下 30+ 个 Python 文件的模块 docstring、logger 消息、异常描述
- `frontend/src/app/layout.tsx:15` — 页面 `<title>` 元数据
- `Makefile` 注释

### 排除范围
- Python 包导入路径 `from open_notebook...`（代码依赖）
- `lfnovo/open-notebook` GitHub 上游 URL 引用
- 数据库 namespace/database 环境变量
- `pyproject.toml` `name` 字段

### 统计
- 74 文件，纯字符串替换，零代码影响
- Python 导入全部保留 `open_notebook`，lint 验证零破坏

**决策**：仅替换用户可见的产品名称，不动代码路径和配置标识，避免引入运行时问题。

---

## 16. 认证安全加固与测试修复（新增 2026-06-01 ~ 2026-06-02）

基于 Sourcery + GitHub Copilot Code Review 和安全最佳实践的集中加固。

### JWT 密钥安全
- `open_notebook/utils/jwt_config.py:11-18` — 新增 `_derive_key()`：短于 32 字节的密钥通过 SHA-256 派生为完整 HS256 密钥，消除 PyJWT `InsecureKeyLengthWarning`
- 非开发环境（`OPEN_NOTEBOOK_ENV` 非 dev/test）拒绝硬编码默认值，抛出 `RuntimeError`
- `api/auth.py:13-19` — 更新 `PasswordAuthMiddleware` docstring 对齐双轨鉴权（JWT + 后门）行为

### 密码安全
- `open_notebook/domain/user.py:15-16` — PBKDF2 迭代次数 100,000 → **600,000**（OWASP 推荐）
- `open_notebook/domain/user.py:25` — `==` 字符串比较 → `hmac.compare_digest` 恒定时间比较

### 错误信息安全
- `api/routers/auth.py` — 5 处 `detail=f"Failed to...: {str(e)}"` 改为通用提示，完整错误仅写入 `logger.error()`
- 登录页移除后门提示文本（`🔒 超级管理员可使用部署密码直接绕过验证登录` → `Lumiton·Omax 科研数据中台`）

### Python 3.12 兼容
- `api/routers/auth.py:55` — `datetime.utcnow()` → `datetime.now(timezone.utc)`（Python 3.12 废弃警告）
- `pyproject.toml:48` — `pyjwt>=2.8.0` 显式声明为直接依赖

### 认证兼容性修复
- `api/routers/auth.py:60-117` — `get_current_user_from_state` 新增 JWT fallback：中间件未设置 `request.state.user` 时直接从 Authorization header 解码（解决 ASGI scope 传递问题）
- fallback 中包含 master password 后门检查 + pending/rejected/active 状态校验
- `frontend/src/app/(dashboard)/settings/components/UserApprovalDashboard.tsx` — 所有 4 个 API 调用从 `fetch()` 改为 `apiClient`（axios），避免 Next.js 代理层 Authorization header 丢失

### 用户管理 UI 增强
- `UserApprovalDashboard.tsx:51,88-110` — 审批/拒绝/禁用操作前弹出 `ConfirmDialog` 二次确认
- `UserApprovalDashboard.tsx:218-226` — 角色标签可点击切换 `admin` ↔ `user`（`ShieldAlert`/`Shield` 图标），保护 `admin` 账户不可降级
- `UserApprovalDashboard.tsx:374-380` — 密码重置从 `window.prompt` 替换为 `AlertDialog`（双密码输入 + 确认 + 实时校验）
- `api/routers/auth.py:311-349` — `PUT /auth/users/{id}/role` 角色修改端点
- `api/routers/auth.py:351-383` — `PUT /auth/users/{id}/password` 管理员重置密码端点

### 测试环境适配
- `tests/conftest.py:15-17` — 设置 `OPEN_NOTEBOOK_PASSWORD` 和 `AUTH_JWT_SECRET` 测试值（旧逻辑的空密码=跳过认证已失效）
- `tests/test_sources_api.py:17-20,46,91,129` — 3 个 source 创建测试新增 `auth_headers` fixture（Bearer token），适配 JWT 强制认证

### 登录表单增强
- `frontend/src/components/auth/LoginForm.tsx:169-172` — 先检查 `password.trim()` 再执行登录，避免空密码提交

**决策**：安全加固优先于功能，Review 反馈即时收敛。JWT fallback 为防御性编程，解决 ASGI 框架间 state 传递的边界情况。

| 文件 | 涉及主题 |
|------|----------|
| `open_notebook/graphs/source.py` | MinerU 集成、Excel 修复、Vision LLM、进度日志 |
| `open_notebook/ai/models.py` | `default_vision_model`、`get_vision_model()` |
| `open_notebook/utils/office_converter.py` | Office → PDF 转换、Excel 排除 |
| `open_notebook/utils/context_builder.py` | Notes 优先级反转、截断阈值 |
| `open_notebook/utils/jwt_config.py` | JWT 密钥公共模块（§12 新增） |
| `open_notebook/domain/notebook.py` | `original_filename`、`origin_notebook_id`、`uploaded_by`/`uploader_name`（§12） |
| `open_notebook/domain/user.py` | 用户领域模型，PBKDF2 密码哈希（§12 新增） |
| `open_notebook/domain/content_settings.py` | Tavily、MinerU 引擎选项 |
| `open_notebook/database/async_migrate.py` | 空迁移处理 |
| `api/auth.py` | 密码中间件升级双轨鉴权（§12） |
| `api/routers/auth.py` | 注册/登录/用户管理/角色/密码重置/登出（§12） |
| `api/routers/sources.py` | 上传解阻塞、`check-duplicates`、下载名还原、上传者溯源（§12） |
| `api/routers/models.py` | Vision model GET/PUT |
| `api/models.py` | `DefaultModelsResponse` 扩展、`uploader_name`（§12） |
| `api/rate_limiter.py` | 滑动窗口登录限流（§12 新增） |
| `frontend/src/proxy.ts` | 服务端路由守卫，Cookie 鉴权（§12 新增，§27 迁移入口） |
| `frontend/src/lib/stores/auth-store.ts` | Zustand 认证状态管理，双轨登录/注册/登出（§12） |
| `frontend/src/lib/hooks/use-auth.ts` | React 认证 Hook（§12） |
| `frontend/src/components/auth/LoginForm.tsx` | Landing Page + 登录/注册表单（§12） |
| `frontend/src/app/(auth)/login/page.tsx` | 登录页 Suspense 包裹（§12） |
| `frontend/src/app/(dashboard)/settings/components/UserApprovalDashboard.tsx` | 管理员用户审批面板（§12 新增） |
| `frontend/src/lib/api/client.ts` | Axios 拦截器 Bearer Token 注入（§12） |
| `frontend/src/app/(dashboard)/sources/page.tsx` | 分页、Tooltip、上传人列（§12） |
| `frontend/src/lib/types/api.ts` | `uploader_name` 类型（§12） |
| `frontend/src/components/sources/AddSourceDialog.tsx` | 文件重复检测 |
| `frontend/src/components/sources/SourceCard.tsx` | Tooltip、origin_notebook badge |
| `frontend/src/app/(dashboard)/settings/api-keys/page.tsx` | Vision Model 选择器 |
| `frontend/src/lib/locales/zh-CN/index.ts` | Vision 中文标签 |
| `Makefile` | Windows sleep 兼容 |
| `prompts/chat/system.jinja` | 领域专家 Prompt |
| `migrations/` | #15 BM25、#16 password、#17 origin_notebook、#18 中文模板、#25 用户表+source 上传人字段（§12） |
| `tests/test_error_classifier.py` | 新增：错误分类规则测试 |
| `tests/test_sanitize_excel.py` | 新增：Excel 行合并修复测试 |
| `tests/test_integration_e2e.py` | 新增：L2/L4/L5 集成/E2E 测试（手动运行） |
| `frontend/src/components/source/ChatPanel.test.tsx` | 新增：Stop 按钮渲染测试 |
| `.github/workflows/test.yml` | CI 排除 e2e 标记 |
| `frontend/src/app/(dashboard)/profile/page.tsx` | 个人资料页：显示名称编辑、修改密码（§13 新增） |
| `frontend/src/app/(help)/help/` | 帮助中心路由组（§14 新增） |
| `frontend/src/app/(help)/help/_components/HelpSidebar.tsx` | 帮助中心折叠式导航（§14 新增） |
| `frontend/src/lib/help/docs.ts` | 帮助文档工具：导航树构建、路径解析（§14 新增） |
| `docs/user_docs/` | 用户帮助文档独立目录，33 文件全部中文化（§14 新增） |
| `frontend/src/app/layout.tsx` | HTML body overflow-hidden + 页面标题更新（§13/§15） |
| `frontend/src/components/layout/AppSidebar.tsx` | 侧边栏品牌标识重构、菜单权限过滤、布局优化（§13） |
| `frontend/src/lib/locales/*/index.ts` | 9 locale appName 更新为 Lumiton·Omax\|知涌（§13/§15） |
| `frontend/src/lib/stores/auth-store.ts` | `updateProfile` + `changePassword` actions（§13） |
| `frontend/src/components/auth/LoginForm.tsx` | 登录校验增强、后门提示移除（§16） |
| `open_notebook/utils/jwt_config.py` | JWT 密钥安全：SHA-256 派生 + fail-fast（§16） |
| `open_notebook/domain/user.py` | PBKDF2 600k + hmac.compare_digest（§16） |
| `api/routers/auth.py` | PUT /auth/me、PUT /auth/me/password、JWT fallback、错误通用化、utcnow()→timezone.utc（§13/§16） |
| `tests/conftest.py` | 测试认证环境适配（§16） |
| `tests/test_sources_api.py` | auth_headers fixture 适配 JWT 认证（§16） |
| `pyproject.toml` | `pyjwt>=2.8.0` 显式依赖（§16） |

---

## 17. 登录页布局优化与 UI 多语言治理（新增 2026-06-03）

基于 2K/5K 高分辨率屏幕场景的登录页适配，以及全站硬编码中文字符串的 i18n 系统性修复。分支 `en_ui_optima_0603`。

### 登录页大屏布局优化

#### 3xl 断点引入
- `frontend/src/app/globals.css:5` — `@theme inline` 新增 `--breakpoint-3xl: 120rem`（1920px），与 Tailwind v4 默认的 `sm→2xl` 形成六级响应式阶梯
- **决策**：1902×1080 屏幕（< 1920px）使用紧凑 `lg` 尺寸，5120×2880 屏幕（≥ 1920px）使用 `3xl` 展开尺寸，解决之前 `2xl`（1536px）在大屏上过度扩张导致 1080p 竖屏底部内容截断的问题

#### 大屏字体与组件等比缩放
- `frontend/src/components/auth/LoginForm.tsx` — 全组件链引入 `lg:` / `3xl:` 三级渐进式尺寸：
  - **标题**：`text-3xl lg:text-4xl 3xl:text-5xl`
  - **正文**：`text-sm lg:text-base 3xl:text-lg`
  - **脚注/标签**：`text-[10px] lg:text-xs 3xl:text-sm`
  - **Logo**：`h-10 lg:h-12 3xl:h-14`
  - **表单卡片**：`max-w-[420px] lg:max-w-[480px] 3xl:max-w-[540px]`
  - **输入框**：`3xl:text-lg 3xl:py-3`（放大触控区域）
  - **功能卡片**：`p-3 lg:p-4 3xl:p-6`
  - **网格背景密度**：`bg-[size:24px] lg:32px 3xl:40px`
  - **模糊光球**：`w-96 h-96 3xl:w-[600px] 3xl:h-[600px]`
  - **指标数字**：`text-2xl lg:text-3xl 3xl:text-4xl`
  - **图标**：`h-4 w-4 lg:h-5 lg:w-5 3xl:h-6 3xl:w-6`
- **决策**：不按 viewport 百分比缩放（避免 5K 屏字体过大），采用固定断点阶梯式缩放，兼顾 2K 可读性与 5K 舒适度

#### 面板全宽延展
- 移除网格容器 `max-w-[1600px] 2xl:max-w-[1800px] mx-auto`，左侧面板（7/12）渐变与右侧面板（5/12）背景自然延伸至视口边缘，消除大屏两侧生硬的 `bg-background` 色块接缝
- 内容区通过 `max-w-2xl 3xl:max-w-4xl mx-auto` 居中约束，Logo 和版权信息保持面板内边距对齐
- 左侧面板 `overflow-hidden` 保证装饰网格和光球不溢出

#### 亮色/暗色双模式适配
- 左侧面板渐变：`from-slate-50 via-white to-teal-50 dark:from-slate-950 dark:via-slate-900 dark:to-teal-950`
- 主标题：`text-slate-900 dark:text-white`
- 品牌渐变文字：`from-teal-600 to-indigo-600 dark:from-teal-400 dark:to-indigo-400`
- 功能卡片：`border-slate-200 dark:border-white/5 bg-slate-100 dark:bg-white/[0.02]`
- 指标/AI 能力卡片全部适配 `dark:` 变体

#### 底部内容截断修复
- 面板 padding：`p-12` → `p-6 lg:p-10 3xl:p-12`（1080p 竖屏下回收 48px）
- 方法学区间距：`space-y-8` → `space-y-4 lg:space-y-6 3xl:space-y-8`
- 功能卡片：gap `gap-5` → `gap-3 lg:gap-4 3xl:gap-5`，padding `p-4 lg:p-5` → `p-3 lg:p-4 3xl:p-6`
- 指标区：gap `gap-8` → `gap-4 lg:gap-6 3xl:gap-8`，上边距 `pt-6` → `pt-4 lg:pt-5 3xl:pt-6`
- AI 能力区：gap `gap-4` → `gap-2 lg:gap-3 3xl:gap-4`
- **决策**：仅在非 3xl 下缩紧垂直间距，3xl（≥ 1920px）恢复原始舒展尺寸，确保 5K 屏不受影响

#### 三列指标对齐
- 指标区（+40% / -30% / 1/2）从 `flex gap-4 lg:gap-6 3xl:gap-8` 改为 `grid grid-cols-3 gap-2 lg:gap-3 3xl:gap-4`，与下方 AI 能力三列矩形框共享同一网格列宽，精确对齐
- 每项新增 `text-center` 居中

#### 移动端品牌头部
- 右侧面板布局从 `flex items-center justify-center` 改为 `flex flex-col items-center justify-center gap-6`
- 新增 `lg:hidden` 品牌头部区块（Logo 40px + 渐变品牌名），解决移动端仅显示裸表单无品牌标识的问题

#### 过渡动画
- 表单卡片：`transition-shadow hover:shadow-2xl`
- 功能卡片：`transition-all duration-200`

### 多语言硬编码修复

#### 登录表单 i18n 全面改造
- `frontend/src/components/auth/LoginForm.tsx` — ~45 处硬编码中文全部替换为 `t.auth.*` 调用：
  - Tab 按钮（`用户登录`/`申请注册` → `t.auth.tabLogin`/`t.auth.tabRegister`）
  - 表单标签和占位符（`用户名 / 邮箱`/`密码`/9 个注册字段 → `t.auth.*`）
  - 按钮文本（`进入科研平台`/`提交注册申请`/加载态 → `t.auth.*`）
  - 错误/成功消息（6 处 `setRegistrationError`/`setRegistrationSuccess` 硬编码 → `t.auth.*`）
  - 卡片标题（`科研数据中台`/`油井化学智能决策与文献大模型系统` → `t.auth.platformTitle`/`t.auth.platformDesc`）
  - 版本信息（`平台版本：v...` → `t.auth.configVersion`）
  - 底部署名（`Lumiton·Omax 科研数据中台` → `t.auth.platformTagline`）
  - 审批提示（注册须知长文本 → `t.auth.regApprovalHint`）
- `frontend/src/lib/locales/en-US/index.ts:196-237` / `zh-CN/index.ts:196-237` — `auth` 区段从 6 个键扩展至 36 个键
- **决策**：左侧面板品牌叙事文本（方法学卡片描述、指标标签）保留硬编码，因其属于领域专业营销文案，切换语言需重新撰稿而非翻译

#### 个人资料页 i18n
- `frontend/src/app/(dashboard)/profile/page.tsx` — 全面重写，~25 处硬编码 → `t.profile.*`
- `frontend/src/lib/locales/en-US/index.ts:465-489` / `zh-CN/index.ts:465-489` — 新增 `profile` 顶级区段（22 键）：标题、描述、表单标签/占位符、状态（已激活/等待审批/已拒绝）、角色（管理员/用户）、提示消息
- **决策**：用户角色和状态的标签纳入 i18n（其他地方可能复用），避免重复硬编码

#### language.startsWith('zh') 反模式剔除
共修复 6 个文件中 27 处 `language.startsWith('zh') ? '中文' : 'English'` 条件分支：
- `frontend/src/app/(dashboard)/sources/page.tsx` — 13 处（`密码错误`/`上传人`/`引用次数`/分页文本/批量删除对话框等 → `t.sources.*`）
- `frontend/src/components/sources/AddSourceDialog.tsx` — 9 处（重复文件检测 toast/对话框 → `t.sources.*`）
- `frontend/src/app/(dashboard)/notebooks/components/SourcesColumn.tsx` — 3 处（`全部设为参考全文/见解/不参考` → `t.sources.setAllFullText`/`setAllInsights`/`setAllToOff`）
- `frontend/src/app/(dashboard)/notebooks/components/NotesColumn.tsx` — 2 处
- `frontend/src/app/(dashboard)/search/page.tsx` — 2 处（`清空内容` → `t.common.clear`）
- `frontend/src/lib/locales/en-US/index.ts:464-484` / `zh-CN/index.ts:464-484` — `sources` 区段新增 17 个键
- `frontend/src/lib/locales/en-US/index.ts:56` / `zh-CN/index.ts:56` — `common` 区段新增 `clear` 键
- **决策**：`language.startsWith('zh')` 模式绕过 i18n 框架，使多语言支持形同虚设。移除后恢复框架管理的正确多语言路径

### Ask (beta) 标签移除
- `frontend/src/lib/locales/*/index.ts` — 全部 9 个语言文件（en-US/zh-CN/zh-TW/ja-JP/ru-RU/pt-BR/it-IT/fr-FR/bn-IN）的 `searchPage.askBeta` 和 `searchPage.askYourKb` 移除 ` (beta)` / `（ベータ）` 等后缀
- **决策**：Ask 功能已全链路实现（LangGraph 三阶段工作流 + SSE 流式 + 多模型支持），(beta) 标签源自上游项目的保守标注，实际已达到生产可用水平

### 文件上传格式声明对齐
- `frontend/src/components/sources/steps/SourceTypeStep.tsx:253` — 文件选择器 `accept` 属性移除 `.doc, .ppt, .xls, .jpg, .jpeg, .png, .tiff, .zip, .tar, .gz, .html`（11 项），保留 `.pdf, .docx, .pptx, .xlsx, .txt, .md, .epub, .mp4, .avi, .mov, .wmv, .mp3, .wav, .m4a, .aac`
- 全部 9 个语言文件 `sources.selectMultipleFilesHint` 移除 `图片 (JPG, PNG)` / `归档 (ZIP)` / `DOC, PPT, XLS`
- 后续再移除 `媒体 (MP4, MP3, WAV, M4A)` 宣称（处理能力保留但不在 UI 提示中声明）
- **决策**：文件选择器和 UI 宣称与后端 `content_core` 实际处理能力严格对齐。MinerU 和 Docling 均未在 `.env` 配置故视为禁用，依赖它们的老 Office 格式和图片格式同步移除

### 内容转换规则管理员权限加固
- `api/routers/transformations.py` — `update_transformation`（PUT）、`delete_transformation`（DELETE）、`update_default_prompt`（PUT）三个端点新增 `Depends(require_admin)` 依赖注入，非管理员返回 403
- `frontend/src/app/(dashboard)/transformations/components/TransformationCard.tsx` — 导入 `useAuthStore`，编辑按钮（`Edit`）和删除按钮（`Trash2`）仅 `user.role === 'admin'` 渲染
- `frontend/src/app/(dashboard)/transformations/components/DefaultPromptEditor.tsx` — 导入 `useAuthStore`，保存按钮仅管理员可见（后端已保护，前端同步隐藏避免困惑）
- 导入：`from api.routers.auth import require_admin`、`from fastapi import Depends`
- **决策**：定义好的转换模板作为系统级配置，双重保护（后端 403 + 前端 UI 隐藏），Playground 测试功能保持全员可用

### 其他调整
- `frontend/src/app/globals.css:5` — 新增 `--breakpoint-3xl: 120rem`（复用 §17.1）
- `frontend/src/lib/stores/auth-store.ts` 等文件 — 未改动，复用现有 role 字段

---

## 18. 用户反馈驱动优化（新增 2026-06-05 ~ 2026-06-07）

基于《Lumina™ AI 科研助手试用反馈》多轮迭代，涵盖来源搜索、弹窗交互、密码管理、删源规则、流式稳定性等 P0/P1 级体验优化。分支 `enhance_sourcepage_optim_0605`。

---

### 18.1 来源页面搜索与分页

**用户问题**：来源页面缺少搜索按钮，无总页码/总条数显示。

#### API 分页响应重构

- `api/models.py` — 新增 `PaginatedSourceListResponse(items: List[SourceListResponse], total: int)`，替代裸数组返回
- `api/routers/sources.py` — `GET /sources` 返回 `{ items, total }`，额外执行 `SELECT count() FROM source ... GROUP ALL` 查询总数。`response_model` 从 `List[SourceListResponse]` 改为 `PaginatedSourceListResponse`
- **决策**：选方案 C（包裹响应体），前端所有 8 处 `sourcesApi.list()` 调用点同步适配 `.items`

#### 前端搜索与分页展示

- `frontend/src/lib/types/api.ts` — 新增 `SourceListPaginatedResponse` 类型
- `frontend/src/lib/api/sources.ts` — `list()` 返回类型适配
- `frontend/src/lib/hooks/use-sources.ts` — `useSources` / `useNotebookSources` 适配 `data.items`
- `frontend/src/components/sources/AddExistingSourceDialog.tsx` — 适配 `.items`；后改为客户端实时过滤（`useMemo` + `includes()`，与笔记本筛选实现对齐）
- `frontend/src/components/podcasts/GeneratePodcastDialog.tsx` — 适配 `.items`
- `frontend/src/app/(dashboard)/sources/page.tsx`：
  - 搜索框（回车触发服务端 `title_contains`）
  - 分页显示「第 X/Y 页，共 Z 条」
  - 搜索无结果时区分「暂无来源」和「搜索无匹配」，显示「未找到匹配的来源」+「尝试使用不同的搜索词」
- `frontend/src/lib/locales/en-US/index.ts` / `zh-CN/index.ts` — 新增 `filterSources`、`pageOfTotal`、`noSourcesMatchSearch`、`selectAll`、`deselectAll`
- **决策**：全局页搜索采用回车触发（非 debounce/实时），避免中文输入法打断和性能问题。弹窗内采用纯客户端过滤（已全量加载最多 100 条），与笔记本筛选模式一致

---

### 18.2 弹窗关闭后页面卡死（Pointer Events 残留修复）

**用户问题**：弹窗操作（输入密码、修改密码、取消关闭）后回到页面，鼠标点击任何地方无反应。

#### 根因分析

- Radix UI Dialog/AlertDialog 关闭动画结束后偶发 `pointer-events: none` 残留在 `<body>` 上
- 多处输入框的 `e.nativeEvent.stopImmediatePropagation()` 干扰 Radix 内部事件生命周期，导致清理逻辑不触发
- DropdownMenu + Dialog 叠层切换时序加剧问题

#### 全局兜底修复

- `frontend/src/components/common/PointerEventsGuard.tsx` — **新增组件**：`MutationObserver` 监控 `<body>` style 变化，检测到孤立 `pointer-events: none` 且 DOM 中无 `[data-state="open"]` 时自动清除。用 `requestAnimationFrame` 避开 Radix 自身设置 `data-state` 的时序。额外在 `pointerdown` 时再检查一次作为最后兜底
- `frontend/src/app/layout.tsx` — `<ConnectionGuard>` 内注入 `PointerEventsGuard`
- `frontend/src/components/ui/dialog.tsx` — `Dialog` / `DialogContent` 卸载时 + `onOpenChange(false)` 双重清理 `document.body.style.removeProperty('pointer-events')`（含 `setTimeout(0)` 覆盖动画异步关闭时序）
- `frontend/src/components/ui/alert-dialog.tsx` — 同上

#### 移除高风险事件拦截

以下文件中的 `e.nativeEvent.stopImmediatePropagation()` 改为仅保留 `e.stopPropagation()`：

- `frontend/src/app/(dashboard)/notebooks/components/SourcesColumn.tsx`
- `frontend/src/app/(dashboard)/sources/page.tsx`（2 处）
- `frontend/src/components/sources/AddExistingSourceDialog.tsx`
- `frontend/src/components/notebooks/ManageNotebookPasswordDialog.tsx`（2 处）

**决策**：在弹窗基础层做全局修复而非各页面单独补丁。`stopImmediatePropagation` 仅用于阻断向 Radix 内部事件系统传播，不再用于输入框的 Enter 键冲突场景。

---

### 18.3 上下文提示硬编码英文修复

**用户问题**：中文界面下聊天栏出现 "No sources or notes included in context. Toggle icons on cards to include them."

- `frontend/src/components/common/ContextIndicator.tsx` — 全 7 处硬编码英文 → i18n：
  - `Context:` → `上下文：`
  - `Insights for {n} source(s)` → `{n} 个来源的见解`
  - `{n} full source(s)` → `{n} 个来源全文`
  - `{n} full note(s)` → `{n} 个笔记全文`
  - `{n} tokens` → `{n} 令牌`
  - `{n} chars` → `{n} 字符`
  - 空上下文提示 → `上下文中未包含来源或笔记。点击卡片上的图标进行切换。`
- `frontend/src/lib/locales/en-US/index.ts` / `zh-CN/index.ts` — `sources` 区段新增 6 个 `context*` 键
- **决策**：中文不拼接英文复数 `(s)` 后缀，直接在 key 中包含

---

### 18.4 笔记本密码全生命周期管理

**用户问题**：仅新建时可设密码，已建笔记本无法增、改、撤销密码；创建者名称需手动填写。

#### 后端

- `open_notebook/domain/notebook.py` — Notebook 模型新增 `created_by: Optional[str]`（存用户 record ID）；`password` 加入 `nullable_fields: ClassVar[set[str]] = {"password"}`（否则 `None` 被 `_prepare_save_data` 过滤，撤销不生效）
- `api/models.py` — 新增 `NotebookPasswordUpdate(action: set/change/remove, password?, current_password?)` schema；`NotebookResponse` 新增 `created_by`
- `api/routers/notebooks.py`：
  - 创建/聚合端点新增 `Depends(get_current_user_from_state)`，自动填入 `created_by = current_user["id"]`
  - `creator_name` 为空时自动取 `current_user.display_name`
  - 新增 `PATCH /notebooks/{id}/password` 端点，权限：`created_by == user.id` 或 `role == "admin"`；历史笔记本（`created_by == null`）首次设密者自动成为 owner；创建者改密码无需输入当前密码

#### 前端

- `frontend/src/lib/types/api.ts` — 新增 `NotebookPasswordUpdateRequest`；`NotebookResponse` 新增 `created_by`
- `frontend/src/lib/api/notebooks.ts` — 新增 `updatePassword(notebookId, data)`
- `frontend/src/lib/hooks/use-notebooks.ts` — 新增 `useUpdateNotebookPassword`，按 action 区分成功文案
- `frontend/src/components/notebooks/ManageNotebookPasswordDialog.tsx` — **新增组件**：三 Tab 弹窗（设密码 / 改密码 / 撤销密码），含密码确认 + 长度校验
- `frontend/src/app/(dashboard)/notebooks/components/NotebookCard.tsx` — 磁贴「...」菜单新增「密码」入口，打开前先关闭 DropdownMenu 避免叠层冲突
- `frontend/src/app/(dashboard)/notebooks/components/NotebookHeader.tsx` — 详情页顶部新增密码入口按钮
- `frontend/src/components/notebooks/CreateNotebookDialog.tsx` — 移除 `creator_name` 输入框（后端自动取当前用户）
- `frontend/src/lib/locales/en-US/index.ts` / `zh-CN/index.ts` — `notebooks` 区段新增 20 个密码相关键

**决策**：密码不加密（现有系统保持纯文本），权限基于创建者身份而非密码验证。修改密码无需输入当前密码（已通过身份认证）。`nullable_fields` 机制是让 `password = None` 能被 SurrealDB MERGE 写为 null 的唯一方式。

---

### 18.5 笔记本内删除来源三规则

**用户问题**：删除来源不分所有权和引用情况，自己的源也需管理员密码。

#### 三种场景

| 场景 | SourceCard | 弹窗 | 后端 |
|------|:---:|------|------|
| 自己创建 + 未被其他笔记本引用 | 显示「删除」 | 简单确认，无密码 | `ref_count = 1`，放行 |
| 别人的源 | 仅显示「移除」 | 不触发删除 | 前端不展示删除按钮 |
| 自己创建 + 被多笔记本引用 | 显示「删除」 | 需管理员密码 | `ref_count > 1`，校验 `X-Admin-Password` |

#### 后端

- `api/routers/sources.py` — `GET /sources` SELECT 新增 `uploaded_by`；`DELETE /sources/{id}` 先查 `SELECT count() FROM reference WHERE in = $source_id`，`<= 1` 免密码，`> 1` 需 `OPEN_NOTEBOOK_PASSWORD`
- `api/models.py` — `SourceListResponse` / `SourceResponse` 新增 `uploaded_by` 字段
- `open_notebook/domain/notebook.py` — `Source.delete()` 新增 `DELETE reference WHERE in = $source_id_str`，防止悬空引用导致其他笔记本加载报错

#### 前端

- `frontend/src/lib/types/api.ts` — `SourceListResponse` 新增 `uploaded_by`
- `frontend/src/components/sources/SourceCard.tsx` — 新增 `currentUserId` prop；`isOwnSource = uploaded_by === currentUserId`；别人源不显示删除按钮
- `frontend/src/app/(dashboard)/notebooks/components/SourcesColumn.tsx` — 从 auth store 取 `user.id`；按 `notebook_count > 1` 决定弹窗是否含密码输入
- `api/routers/auth.py` — `get_current_user_from_state` 依赖注入至 notebook create/aggregate 端点

**决策**：前后端双重校验（前端 UI 隐藏 + 后端 403 拒绝）。`notebook_count` 为 SurrealDB 聚合计算值，不在 Source 模型上持久化。

---

### 18.6 管理员密码统一为后端校验

**用户问题**：删除源时输入管理员密码无效。

**根因**：前端取 `NEXT_PUBLIC_MASTER_NOTEBOOK_PASSWORD`，后端登录用 `OPEN_NOTEBOOK_PASSWORD`，两个值不一致。

#### 解决方案（选 B 方案——后端校验）

- `api/routers/sources.py` — `DELETE /sources/{id}` 读取 `X-Admin-Password` header，与 `OPEN_NOTEBOOK_PASSWORD` 比对
- `frontend/src/lib/api/sources.ts` — `delete(id, password?)` 通过 `X-Admin-Password` header 发送密码
- `frontend/src/lib/hooks/use-sources.ts` — `useDeleteSource` mutation 改为接受 `{ id, password }` 对象
- `frontend/src/app/(dashboard)/notebooks/components/SourcesColumn.tsx` — 去除客户端 `NEXT_PUBLIC_MASTER_NOTEBOOK_PASSWORD` 比对
- `frontend/src/app/(dashboard)/sources/page.tsx` — 单删 + 批量删同步改传后端
- 所有删除弹窗密码框从 `{env && (` 条件渲染改为始终显示

**决策**：统一维护一个密码（`OPEN_NOTEBOOK_PASSWORD`），前端不再持有密码值。`NEXT_PUBLIC_MASTER_NOTEBOOK_PASSWORD` 逐步废弃。

---

### 18.7 移动端切 Tab 中断回答修复

**用户问题**：手机端从聊天切到来源再切回，AI 回答中断；点停止按钮控制台报 `AbortError`。

#### 修复

- `frontend/src/app/(dashboard)/notebooks/[id]/page.tsx` — 移动端 Tab 从条件渲染 `{activeTab === 'chat' && <ChatColumn />}` 改为 CSS `hidden` 控制显隐，ChatColumn 始终挂载，切页不再中断流式回答
- `frontend/src/lib/api/chat.ts` — `sendMessage` 新增 `signal?: AbortSignal` 参数，传给 `fetch()`
- `frontend/src/lib/api/source-chat.ts` — 同上
- `frontend/src/lib/hooks/useNotebookChat.ts` — 传入 `abortController.signal` 到 `chatApi.sendMessage`；catch 块 `AbortError`（`DOMException.name === 'AbortError'`）直接 `return`，不弹错误 toast、不删消息
- `frontend/src/lib/hooks/useSourceChat.ts` — 同上，且补全 AbortController 创建（之前仅声明 ref 但从未 new 实例）
- **决策**：移动端三 Tab 全部保持挂载（CSS 隐藏替代条件渲染），牺牲少量 DOM 开销换取流式会话不中断的用户体验

---

### 18.8 SearchPage 渲染循环修复

**用户问题**：搜索页面控制台报 `[useTranslation] INFINITE LOOP DETECTED on key: "searchPage"`。

#### 根因

- `useAsk()` 每次渲染返回新对象（内联 `stopStreaming` 函数 + 未 memo 的返回值）
- TanStack Query `useMutation()` 返回新引用使 `handleSearch` 每次重建
- Auto-trigger effect 的 deps 含 `handleSearch`/`handleAsk` → 每渲染都执行
- SSE 流式中 Zustand store 每 chunk 更新触发渲染 → effect 连锁执行 → 1000+ 次 `t.searchPage` 访问

#### 修复

- `frontend/src/lib/hooks/use-ask.ts` — `stopStreaming` 改为 `useCallback(fn, [])`；返回值整体 `useMemo` 包裹，按 store 字段拆分 deps
- `frontend/src/app/(dashboard)/search/page.tsx` — auto-trigger effect 用 `handleSearchRef`/`handleAskRef` 透传回调，从 deps 中移除 `handleSearch` 和 `handleAsk`

**决策**：不改变 SSE 流式渲染频率（业务需要实时更新），仅消除不必要的 effect 重复执行。

---

### 文件索引

| 文件 | 涉及改动 |
|------|----------|
| `api/models.py` | `PaginatedSourceListResponse`、`NotebookPasswordUpdate`、`SourceListResponse`/`SourceResponse` + `uploaded_by`、`NotebookResponse` + `created_by` |
| `api/routers/sources.py` | GET /sources 返回 `{items, total}`、SELECT + `uploaded_by`、DELETE 引用计数 + `X-Admin-Password` 校验 |
| `api/routers/notebooks.py` | 创建/聚合端点自动 `created_by`+`creator_name`；新增 `PATCH /password` |
| `open_notebook/domain/notebook.py` | Notebook + `created_by`、+ `nullable_fields`；Source.delete() + reference 清理 |
| `frontend/src/components/ui/dialog.tsx` | `onOpenChange` 兜底清理 pointer-events |
| `frontend/src/components/ui/alert-dialog.tsx` | 同上 |
| `frontend/src/components/common/PointerEventsGuard.tsx` | **新文件** — MutationObserver 全局守卫 |
| `frontend/src/components/common/ContextIndicator.tsx` | 7 处硬编码 → i18n |
| `frontend/src/app/layout.tsx` | 注入 PointerEventsGuard |
| `frontend/src/lib/types/api.ts` | `SourceListPaginatedResponse`、`NotebookPasswordUpdateRequest`、`SourceListResponse` + `uploaded_by`、`NotebookResponse` + `created_by` |
| `frontend/src/lib/api/sources.ts` | `list()` 返回类型；`delete(id, password?)` 传 header |
| `frontend/src/lib/api/notebooks.ts` | + `updatePassword()` |
| `frontend/src/lib/api/chat.ts` | `sendMessage` + `signal` 参数 |
| `frontend/src/lib/api/source-chat.ts` | 同上 |
| `frontend/src/lib/hooks/use-sources.ts` | `useSources`/`useNotebookSources` 适配 `.items`；`useDeleteSource` 接受 `{id, password}` |
| `frontend/src/lib/hooks/use-notebooks.ts` | + `useUpdateNotebookPassword` |
| `frontend/src/lib/hooks/use-ask.ts` | `stopStreaming` → `useCallback`；返回值 → `useMemo` |
| `frontend/src/lib/hooks/useNotebookChat.ts` | 传 signal 到 fetch；catch AbortError 静默 |
| `frontend/src/lib/hooks/useSourceChat.ts` | 同上 + AbortController 实例化补全 |
| `frontend/src/app/(dashboard)/sources/page.tsx` | 搜索框 + 分页 + 密码传后端 |
| `frontend/src/app/(dashboard)/search/page.tsx` | auto-trigger effect ref 重构 |
| `frontend/src/app/(dashboard)/notebooks/[id]/page.tsx` | 移动端 tab CSS hidden |
| `frontend/src/app/(dashboard)/notebooks/components/SourcesColumn.tsx` | 删源三规则 + 传密码 |
| `frontend/src/app/(dashboard)/notebooks/components/NotebookCard.tsx` | 「...」菜单密码入口 |
| `frontend/src/app/(dashboard)/notebooks/components/NotebookHeader.tsx` | 密码入口按钮 |
| `frontend/src/components/sources/SourceCard.tsx` | `currentUserId` prop + 所有权判定 |
| `frontend/src/components/sources/AddExistingSourceDialog.tsx` | 客户端实时过滤 + 全选按钮 |
| `frontend/src/components/sources/AddSourceDialog.tsx` | 适配 `.items` |
| `frontend/src/components/notebooks/ManageNotebookPasswordDialog.tsx` | **新文件** |
| `frontend/src/components/notebooks/CreateNotebookDialog.tsx` | 移除 creator_name 输入框 |
| `frontend/src/components/podcasts/GeneratePodcastDialog.tsx` | 适配 `.items` |
| `frontend/src/lib/locales/en-US/index.ts` | 新增 `sources`/`notebooks` 区段 30+ 键 |
| `frontend/src/lib/locales/zh-CN/index.ts` | 同上 |

---

## 19. 源解析下载与 Vision 图片描述工程化（新增 2026-06-08 ~ 2026-06-10）

本轮围绕“文档解析结果可交付、图片描述可用、外部 Vision 服务失败时任务可继续”展开。PDF、DOC、PPT 仍通过 MinerU 抽取，Excel 保持独立解析链路；所有抽取图片均进入 Vision 描述流程，不再因尺寸或清晰度门禁而直接跳过。

---

### 19.1 源详情页操作语义与国际化修复

**用户问题**：源详情页顶部存在英文硬编码 `Back to Sources`、`file`，标题右侧上传图标点击无响应且含义不明确。

- `frontend/src/app/(dashboard)/sources/[id]/page.tsx` — 返回来源列表文案改为 i18n
- `frontend/src/components/source/SourceDetailContent.tsx`：
  - 来源类型显示改为本地化文案
  - 移除无实际上传行为的误导性上传图标，改用符合文件语义的图标
  - 整理顶部操作区，为解析结果下载入口提供一致布局
- 9 个 locale 文件同步补充翻译键：`bn-IN`、`en-US`、`fr-FR`、`it-IT`、`ja-JP`、`pt-BR`、`ru-RU`、`zh-CN`、`zh-TW`

**决策**：无交互行为的图标不能作为装饰性按钮保留；源详情页新增文案必须覆盖全部现有语言，不能只修复中英文。

---

### 19.2 解析结果 Markdown 与离线 ZIP 下载

#### 后端

`api/routers/sources.py` 新增两个端点：

- `GET /sources/{source_id}/download/markdown`
  - 下载 `Source.full_text`
  - 输出 UTF-8 Markdown
  - 文件名使用清理后的“来源标题.md”
- `GET /sources/{source_id}/download/package`
  - ZIP 根目录使用来源标题
  - 包含“来源标题.md”和 `images/` 下全部抽取图片
  - 将 Markdown 中的 `/api/uploads/images/{source_id}/...` 重写为 `images/...`
  - 解压后可直接使用 Markdown Preview 查看带图文档

#### 前端

- `frontend/src/lib/api/sources.ts` — 新增 Markdown、ZIP 下载 API
- `frontend/src/components/source/SourceDetailContent.tsx` — 新增下载菜单、加载态和错误提示
- 各 locale 文件补充下载相关翻译键

**决策**：`Source.full_text` 是解析完成后的 Markdown 主存储；ZIP 下载必须改写图片引用，避免离开 Lumina OMax 服务后图片失效。

---

### 19.3 文档图片抽取与上下文传递

#### PDF / DOC / PPT

- 继续由 MinerU 负责正文和图片抽取
- 图片保存至来源专属目录，并在 Markdown 中保留引用
- 每张图片在文档级描述阶段获得页码、附近文本、来源类型等上下文

#### Excel

Excel 不经过 MinerU，由 `openpyxl` 独立处理：

- 抽取工作表中的嵌入图片
- 记录 sheet 名称、图片锚点单元格、宽度和高度
- 从锚点附近提取表头、当前行和相邻文本，作为 Vision 输入上下文
- 图片描述和表格 Markdown 合并进同一个 `Source.full_text`

**决策**：PDF/Office 与 Excel 保持两条抽取链路，但共用后续的图片描述协议、结果清洗和 Markdown 输出格式，避免重复维护两套 Vision 规则。

---

### 19.4 Vision Prompt、结构化结果与用户可读降级

`open_notebook/graphs/source.py` 新增和完善：

- `FigureContext` — 统一承载页码、sheet、单元格、表头、行文本、附近正文和图片尺寸
- `VisionDescription` / `VisionDescriptionResult` — 使用 Pydantic 约束模型返回结构
- 图片类型覆盖：
  - `hpht_curve`
  - `analytical_spectrum`
  - `lab_photo`
  - `performance_comparison`
  - `mechanism_schematic`
  - `embedded_table_or_screenshot`
  - `unknown`
- 结构化字段覆盖可读性、置信度、描述级别、可确认信息、提取值、不确定项和领域解释
- 默认使用简体中文描述；英文界面通过 `Accept-Language` 传递语言要求

#### 输出清洗与容错

- 清除 thinking/reasoning 标记、Prompt 回显和分析过程泄漏
- 从混合文本中提取 JSON，并进行 schema 校验
- 对截断或局部损坏的 JSON 尽量恢复可用字段
- 最终 Markdown 不展示 JSON 碎片和内部诊断词
- 低清晰度图片仍要求模型描述可辨识内容，不再直接归为“不描述”
- 低置信度时保留实物状态、曲线趋势等定性事实，过滤不可靠的定量数值
- Vision 完全失败时保留原图，并使用面向用户的简短提示，不暴露 `invalid_json`、`reasoning_leakage`、`quality_hint` 等内部状态

**决策**：质量控制由“拒绝描述”改为“尽量描述 + 明确不确定性”。用户接受低质量图片存在误差，因此系统应优先保留信息，而不是输出技术性占位文本。

---

### 19.5 Vision 模型评测与当前选择

使用同一批油田化学实验报告，对 Gemma 4、Qwen 3.7 Plus、MiniMax-M3、Step 3.7 Flash、Doubao Seed 2.0 Pro 进行了对比。

| 模型 | 主要表现 | 主要问题 |
|------|----------|----------|
| Gemma 4 31B（本地 Ollama） | 可本地运行，隐私性好 | 单图约 90 秒，吞吐低，格式稳定性一般 |
| Qwen 3.7 Plus | 部分图片能给出较丰富内容 | 推理过程泄漏、重复分析、断裂 JSON 和臆测较多 |
| MiniMax-M3 | 综合描述、复合表格截图和领域信息提取最好 | 高峰期存在动态限流和 500/520 错误 |
| Step 3.7 Flash | 本轮模型中速度最快 | HPHT 类型误判、JSON 碎片和定量臆测偏多 |
| Doubao Seed 2.0 Pro | 输出较整洁、措辞保守 | 表格数据提取较弱，领域过拟合仍存在 |

**当前选择**：Vision LLM 使用 **MiniMax-M3**。代码仍保留 OpenAI-compatible 多供应商能力，便于后续切换和回归评测。

#### 推理参数

| 场景 | 参数 |
|------|------|
| Ollama | `VISION_NUM_CTX=2048`、`VISION_NUM_PREDICT=384`、`VISION_TEMPERATURE=0` |
| OpenAI-compatible 云模型 | `VISION_MAX_TOKENS=384`、`VISION_TEMPERATURE=0` |

**决策**：`num_ctx`、`num_predict` 是 Ollama 参数，云模型使用 `max_tokens`；不能把同一组底层参数无差别传给所有供应商。

---

### 19.6 MiniMax 并发、超时与重试

MiniMax 确认工作日高峰时段会动态调度和阶段性限流，实际错误可能表现为：

```text
500 server_error: unknown error, 520 (1000)
```

该错误不能只按标准 HTTP 429 处理。`open_notebook/graphs/source.py` 增加：

- `VISION_CONCURRENCY` — Vision 并发数，本机当前建议 MiniMax 使用 `2`
- `VISION_TIMEOUT_SECONDS` — 单图调用超时，默认 `120`
- `VISION_MAX_RETRIES` — 最大重试次数，默认 `2`
- `VISION_RETRY_BASE_DELAY_SECONDS` — 指数退避基数，默认 `3` 秒
- 对 429、500、502、503、504、520、timeout、connection error 和 rate limit 文本进行瞬时错误识别
- 使用 semaphore 控制并发
- 单图失败只生成该图片的降级描述，不再阻塞整个来源解析
- 日志记录图片总数、完成数、重试和最终失败原因

`.env.example` 已补充上述配置说明；本地测试环境将 Vision 并发从 6 降至 2。

**决策**：外部 Vision API 的 5xx 视为可恢复故障。稳定完成整份文档比追求瞬时最大并发更重要。

---

### 19.7 Excel 图片尺寸判断与空白表格裁剪

**用户问题**：

1. Markdown 声称 Figure 2 / Figure 3 “图片较小”，实际预览尺寸约为 897×658、895×563
2. 每个 sheet 尾部包含大量空白 Markdown 表格行，影响阅读并浪费后续 LLM token

#### 修复

- 图片尺寸从 Excel 嵌入对象读取，并传入 Vision 上下文
- 仅在宽度 `< 160` 或高度 `< 120` 时提示图片较小
- 已知尺寸较大的图片在模型失败时改为“模型未能稳定识别”，不再误报尺寸问题
- 新增 `_trim_excel_empty_table_rows()`，删除全为空的 Markdown 表格行
- 保留 `_sanitize_excel_table_newlines()`，避免单元格换行破坏 Markdown 表格结构

#### 实测

同一 Excel 解析结果：

- 处理前：850 行，49,646 字符
- 处理后：318 行，31,636 字符
- 删除：532 行，18,010 字符

**决策**：Excel 的有效范围不能完全依赖带格式单元格范围；进入 `Source.full_text` 前必须做空行裁剪，减少无效上下文。

---

### 19.8 测试与验证

- `tests/test_vision_descriptions.py` — 新增 Vision JSON 提取、截断恢复、推理泄漏清理、低置信度降级、520 重试、超时和 Excel 空行裁剪测试
- `tests/test_sources_api.py` — 增加 Markdown/ZIP 下载和图片路径重写测试
- `frontend/src/components/source/SourceDetailContent.test.tsx` — 覆盖源详情页下载操作
- `frontend/src/lib/stores/navigation-store.test.ts` — 覆盖来源详情导航状态

本轮最后一次针对 Vision 模块的验证结果：

```text
uv run pytest tests/test_vision_descriptions.py -q
18 passed, 6 warnings

uv run ruff check open_notebook/graphs/source.py tests/test_vision_descriptions.py
All checks passed
```

警告为既有 Pydantic/依赖弃用提示，不影响本轮测试结果。修改代码或环境变量后需重启 API 和 worker；前端相关改动需重启 frontend。历史 `Source.full_text` 不会自动重写，需要重新解析来源才能看到新结果。

---

### 19.9 已知问题与后续方向

1. **领域 Prompt 仍偏窄**：当前提示词对油井水泥、固井和 HPHT 曲线权重较高，在缓膨微球、调剖剂、堵水剂等报告中可能错误套用“水泥浆/固井”解释。后续应根据标题、章节和附近正文动态选择“油井水泥外加剂”或“油田调剖堵水材料”等领域子 Prompt。
2. **局部 JSON 恢复仍可优化**：少数截断响应会进入“模型返回格式不完整”降级。后续可加强字段级恢复，并统一为更自然的用户文案。
3. **知识图谱大输出截断**：Excel 文档曾出现单次生成约 802 条关系后 JSON 截断，末条 relation 缺少 `type`，导致整个 `KnowledgeGraphSchema` 校验失败并错误记录为 0/0 成功。该问题尚未完成修复，后续应采用分 sheet/分块、限制实体关系数量、局部恢复、失败块拆分重试，并禁止将 0/0 记录为成功。
4. **供应商专项参数**：`VISION_REASONING_EFFORT`、`VISION_IMAGE_DETAIL` 等参数是否能经 Esperanto 透传，仍需结合供应商和库版本验证，不能仅通过 `.env` 配置即视为生效。
5. **回归样本集**：应将当前两份 PDF、一份 Excel 及其抽取图片固化为评测集，对类型准确率、事实覆盖、数值准确率、格式合规率、失败率和单图耗时持续回归。

---

### 19.10 Mac Studio 局域网源码部署安全调整

用户当前采用源码方式运行：Mac Studio 上启动 SurrealDB、API、worker 和 Next.js，局域网用户仅通过 `http://<Mac-IP>:3001` 访问。

- `Makefile`：
  - SurrealDB 端口改为 `127.0.0.1:8001:8000`，不再向局域网直接暴露数据库
  - frontend 不再注入浏览器可见的 `API_URL=http://localhost:5056`
  - 仅设置 `INTERNAL_API_URL=http://127.0.0.1:5056`，由 Next.js 服务端代理 API
- `frontend/src/app/config/route.ts` — 未显式设置 `API_URL` 时返回空地址，使浏览器使用相对 `/api` 路径
- `docker-compose.parallel.yml` — 同步将 SurrealDB 映射限制到宿主机回环地址
- 保留 `ws://127.0.0.1:8001/rpc`：本地进程连接本机数据库不需要 TLS；Sourcery 的 `wss://` 告警不适用于该受限内部连接

**决策**：局域网仅开放前端端口 3001；API 默认保留在本机回环地址，由 Next.js 代理；SurrealDB 仅允许 Mac Studio 本机访问。

---

### 文件索引

| 文件 | 涉及改动 |
|------|----------|
| `api/routers/sources.py` | 来源语言传递；Markdown/ZIP 下载；离线图片路径重写 |
| `commands/source_commands.py` | source command 传递界面语言 |
| `open_notebook/graphs/source.py` | 图片上下文、Vision Prompt、结构化解析、清洗降级、并发重试、Excel 图片与空行处理 |
| `.env.example` | Vision 并发、超时、重试及 Ollama/云模型参数说明 |
| `frontend/src/app/(dashboard)/sources/[id]/page.tsx` | 返回来源列表文案国际化 |
| `frontend/src/components/source/SourceDetailContent.tsx` | 顶部图标语义修复、来源类型本地化、解析结果下载菜单 |
| `frontend/src/lib/api/sources.ts` | Markdown/ZIP 下载 API |
| `frontend/src/lib/stores/navigation-store.ts` | 来源详情导航状态调整 |
| `frontend/src/lib/locales/*/index.ts` | 9 种语言的来源详情与下载文案 |
| `tests/test_sources_api.py` | 下载接口与 ZIP 内容测试 |
| `tests/test_vision_descriptions.py` | Vision 解析、降级、重试、超时与 Excel 裁剪测试 |
| `frontend/src/components/source/SourceDetailContent.test.tsx` | 来源详情下载交互测试 |
| `frontend/src/lib/stores/navigation-store.test.ts` | 来源导航状态测试 |
| `frontend/src/app/config/route.ts` | 未配置外部 API 地址时使用相对 `/api` 路径 |
| `frontend/src/app/config/route.test.ts` | 局域网源码部署 API 路径回归测试 |
| `Makefile` | 本地数据库回环绑定及前端内部 API 代理配置 |
| `docker-compose.parallel.yml` | SurrealDB 宿主机端口限制为 `127.0.0.1` |

---

## 20. 温暖研究风格 UI 美化与设计系统（新增 2026-06-11）

基于 `en_ui_beautify_0610` 分支，本轮完成全站 UI 风格统一。设计方向确定为 **B. 温暖研究**：靛蓝作为主色、琥珀色作为辅助提示色、现代无衬线字体、适中紧凑布局、克制柔和动效，并采用“设计令牌驱动，渐进改造”的实施方式。

### 设计规范与实施计划
- `docs/superpowers/specs/2026-06-10-warm-research-ui-design.md` — 记录已确认的视觉方向、色彩语义、空间密度、字体策略、动效原则和可访问性约束
- `docs/superpowers/plans/2026-06-10-warm-research-ui-implementation.md` — 任务拆分为 9 个阶段：设计令牌、共享控件、反馈表面、布局基础、响应式导航、核心页面迁移、旧样式清理、自动验证、浏览器验证
- 计划状态已同步：除 `make dev` 全栈启动步骤外，其余 UI 改造和验证项均已完成

**决策**：先建立语义 token 和共享组件能力，再迁移代表性页面，避免一次性大范围重写业务逻辑。

### 全局设计令牌
- `frontend/src/app/globals.css`：
  - 新增温暖象牙背景、炭黑前景、靛蓝主色、琥珀高亮、success/warning/destructive 等 OKLCH 语义色
  - 新增 `--shadow-surface`、`--motion-standard`、reduced motion 支持
  - 保留 `3xl` 断点，新增系统现代无衬线字体栈，移除 `next/font/google` 构建期外网依赖
- `frontend/src/app/globals.test.ts`：
  - 覆盖设计 token 存在性、成功色 WCAG AA 对比度、旧 hover scaling 移除、代表页面采用共享布局、本地化回归等静态合同

**决策**：颜色统一走语义 token；琥珀色只用于 insight/attention，不作为普通按钮或装饰色泛用。

### 共享控件与反馈表面
- `frontend/src/components/ui/button.tsx` — 统一按钮圆角、focus ring、hover/active 动效和 link 尺寸兼容
- `frontend/src/components/ui/card.tsx` — 新增 `variant="interactive"` 等语义卡片变体，替代全局 `card-hover`
- `frontend/src/components/ui/input.tsx`、`textarea.tsx`、`select.tsx`、`checkbox.tsx`、`radio-group.tsx` — 统一表单控件表面、边框、禁用态和 focus ring
- `frontend/src/components/ui/badge.tsx`、`alert.tsx` — 增加 `insight`、`success`、`warning` 等语义反馈变体
- `frontend/src/components/ui/dropdown-menu.tsx`、`popover.tsx`、`dialog.tsx`、`sonner.tsx` — 浮层、弹窗、Toast 统一暖色表面和状态色
- `frontend/src/components/layout/SetupBanner.tsx` — literal red/amber 替换为语义 warning/destructive 反馈

**决策**：控件级样式由组件变体承载，业务组件不再依赖 `sidebar-menu-item`、`card-hover`、`scale-[1.02]` 等全局 helper。

### 布局系统与核心页面迁移
- `frontend/src/components/layout/PageContainer.tsx` — 新增统一页面容器，支持 `readable`、`wide`、`full` 宽度和可控滚动
- `frontend/src/components/layout/PageHeader.tsx` — 新增页面标题、描述、操作区布局组件
- `frontend/src/components/layout/PageHeader.test.tsx` — 覆盖标题层级、操作区、宽度和滚动行为
- 已迁移代表性页面：
  - `frontend/src/app/(dashboard)/notebooks/page.tsx`
  - `frontend/src/app/(dashboard)/transformations/page.tsx`
  - `frontend/src/app/(dashboard)/settings/page.tsx`
  - `frontend/src/app/(dashboard)/advanced/page.tsx`
  - `frontend/src/app/(dashboard)/search/page.tsx`
- Notebook 页面补齐聚合笔记本等新增操作文案的 i18n key，刷新按钮使用本地化 `aria-label`

**决策**：仅迁移代表性核心页面，保留页面业务 hook、数据请求和状态逻辑不变。

### 响应式导航与移动端可访问性
- `frontend/src/components/layout/AppShell.tsx` — 移动端导航状态本地化管理，低于 `768px` 显示移动菜单触发器
- `frontend/src/components/layout/AppSidebar.tsx`：
  - 桌面侧栏、折叠侧栏和移动抽屉共用导航内容
  - 当前路由使用最长匹配，`/settings/api-keys` 不再误标 `/settings`
  - 移动抽屉使用 Radix Dialog，支持 Escape 关闭和焦点恢复
  - 新增显式“关闭导航”按钮，打开后焦点落到关闭按钮，关闭后回到“打开导航”
  - active 状态改用 `sidebar-*` 语义 token
- `frontend/src/components/layout/AppShell.test.tsx`、`AppSidebar.test.tsx` — 覆盖移动触发器、抽屉打开/关闭、路由 active、焦点恢复和关闭按钮
- 9 种 locale 文件补齐 `openNavigation`、`closeNavigation`、`navigationLabel`、`quickActions` 等导航可访问性文案

**决策**：移动导航不复用桌面 collapsed 状态，避免桌面折叠影响移动抽屉可读性。

### 旧样式冲突清理
- `frontend/src/components/common/ThemeToggle.tsx`
- `frontend/src/components/common/LanguageToggle.tsx`
- `frontend/src/app/(dashboard)/notebooks/components/NotebookCard.tsx`
- `frontend/src/app/(dashboard)/notebooks/components/NotesColumn.tsx`
- `frontend/src/components/sources/SourceCard.tsx`
- `frontend/src/app/globals.css`

上述组件移除 `sidebar-menu-item`、`card-hover`、hover scaling 和旧 `translateY` 动效，改为共享 Button/Card 变体和局部语义类。

**遗留注意**：部分历史 clickable card/div 仍不是完整语义 button/link，本轮仅清理样式冲突，没有扩大为交互语义重构。

### 生产构建稳定性
- `frontend/src/app/layout.tsx` — 移除 `next/font/google` 的 `Inter` 引入，body 改用 `font-sans`
- `frontend/package.json` — `build` 改为 `next build --webpack`

原因：Next 16 默认 Turbopack 构建在当前项目/环境中停留在 `Creating an optimized production build ...`；Webpack 路径可稳定完成。构建期访问 Google Fonts 在受限网络下会失败，因此改为本地系统字体栈。

**决策**：优先保证标准 `npm run build` 可重复完成；Turbopack 问题后续可独立排查，不阻塞 UI 分支。

### Settings 审批面板本地化修复
- `frontend/src/app/(dashboard)/settings/components/UserApprovalDashboard.tsx` — 成员审批标题、描述、筛选、状态、操作按钮、确认弹窗、重置密码弹窗、Toast 全部改用 `t.settings.userApproval`
- `frontend/src/lib/locales/en-US/index.ts`、`zh-CN/index.ts` — 新增 `settings.userApproval` 文案
- `frontend/src/app/globals.test.ts` — 新增静态回归测试，禁止审批面板重新硬编码中文审批文案

浏览器验证时发现英文模式下 Settings 审批面板仍显示中文，因此作为本轮 UI/localization 修复收敛。

### 浏览器验证与截图证据

截图保存于临时目录（未提交为产品资产）：

```text
/var/folders/9_/wy1n8mb54vd0q74fb8k551lm0000gn/T/lumina-ui-verification-2026-06-11
```

包含：

```text
notebooks-light-desktop.png
notebooks-dark-desktop.png
search-light-tablet.png
settings-dark-mobile.png
mobile-navigation-open.png
```

验证覆盖：
- `/login`、`/notebooks`、`/sources`、`/search`、`/settings`
- light/dark 主题
- 桌面约 `1440×900`
- tablet 约 `1024×768`
- mobile 约 `390×844`
- 中英文切换
- 移动导航打开、关闭按钮和焦点恢复

### 自动验证结果

最后一轮验证：

```text
cd frontend && npm run lint
0 errors, 4 existing warnings

cd frontend && npm test
17 passed, 1 skipped
81 tests passed, 9 skipped

cd frontend && npm run build
exit 0
```

`npm run build` 仍打印 Next standalone trace copy warning：

```text
Failed to copy traced files ... page_client-reference-manifest.js
```

但退出码为 0，未阻塞生产构建。

### 已知阻塞与后续方向

1. **`make dev` 当前不可用**：`Makefile` 中 `dev` 目标引用不存在的 `docker-compose.dev.yml`，并且本地 shell 曾提示 `python: command not found`。本轮 UI 浏览器验证改用 frontend dev server + mock API 完成，未改动全栈启动脚本。
2. **部分 locale 仅补核心语言**：本轮审批面板完整补了 `en-US` 与 `zh-CN`。由于 `TranslationKeys` 以 `en-US` 为类型源，其他语言未立即阻塞构建；若后续启用严格全 locale 完整性检查，应补齐 `settings.userApproval` 到其余语言。
3. **Next Turbopack 构建卡住**：已通过 `--webpack` 稳定标准构建；是否恢复 Turbopack 需单独排查 Next 16 与当前配置。
4. **语义交互债务**：若后续继续做 UI 质量，应优先清理 clickable card/div 的键盘语义，而不是继续添加视觉样式。

**决策**：本轮 UI 美化以设计系统、视觉一致性、响应式可用性和基础可访问性为目标，不改变 API、数据请求、业务 workflow 或状态管理语义。

### 文件索引

| 文件 | 涉及改动 |
|------|----------|
| `docs/superpowers/specs/2026-06-10-warm-research-ui-design.md` | 温暖研究 UI 设计规范 |
| `docs/superpowers/plans/2026-06-10-warm-research-ui-implementation.md` | 分阶段实施计划与状态同步 |
| `frontend/src/app/globals.css` | OKLCH 语义色、字体栈、阴影、动效、旧 helper 移除 |
| `frontend/src/app/globals.test.ts` | 设计 token、布局采用、旧样式、本地化回归测试 |
| `frontend/src/app/layout.tsx` | 移除 Google Fonts，使用 `font-sans` |
| `frontend/package.json` | build 固定到 `next build --webpack` |
| `frontend/src/components/ui/button.tsx` | 按钮视觉、focus、hover/active 统一 |
| `frontend/src/components/ui/card.tsx` | Card 语义变体和 interactive 状态 |
| `frontend/src/components/ui/input.tsx` / `textarea.tsx` / `select.tsx` / `checkbox.tsx` / `radio-group.tsx` | 表单控件表面和焦点态统一 |
| `frontend/src/components/ui/badge.tsx` / `alert.tsx` / `sonner.tsx` | 语义状态反馈 |
| `frontend/src/components/ui/dropdown-menu.tsx` / `popover.tsx` / `dialog.tsx` | 浮层与弹窗表面统一 |
| `frontend/src/components/layout/PageContainer.tsx` | 页面容器 primitive |
| `frontend/src/components/layout/PageHeader.tsx` | 页面头部 primitive |
| `frontend/src/components/layout/AppShell.tsx` | 移动导航状态与菜单触发器 |
| `frontend/src/components/layout/AppSidebar.tsx` | 响应式侧栏、移动抽屉、关闭按钮、active 状态 |
| `frontend/src/app/(dashboard)/notebooks/page.tsx` | 迁移 PageContainer/PageHeader |
| `frontend/src/app/(dashboard)/transformations/page.tsx` | 迁移 PageContainer/PageHeader |
| `frontend/src/app/(dashboard)/settings/page.tsx` | 迁移 PageContainer/PageHeader |
| `frontend/src/app/(dashboard)/advanced/page.tsx` | 迁移 PageContainer/PageHeader |
| `frontend/src/app/(dashboard)/search/page.tsx` | 固定高度搜索工作区迁移共享布局 |
| `frontend/src/components/common/ThemeToggle.tsx` | 移除旧 sidebar helper，使用 Button 变体 |
| `frontend/src/components/common/LanguageToggle.tsx` | 移除旧 sidebar helper，使用 Button 变体 |
| `frontend/src/app/(dashboard)/notebooks/components/NotebookCard.tsx` | 使用 interactive Card 变体 |
| `frontend/src/app/(dashboard)/notebooks/components/NotesColumn.tsx` | 移除旧 card-hover |
| `frontend/src/components/sources/SourceCard.tsx` | 使用 interactive Card 变体 |
| `frontend/src/app/(dashboard)/settings/components/UserApprovalDashboard.tsx` | 审批面板文案本地化 |
| `frontend/src/lib/locales/*/index.ts` | 导航可访问性文案；`en-US`/`zh-CN` 补审批面板文案 |
| `frontend/src/components/layout/AppShell.test.tsx` / `AppSidebar.test.tsx` / `PageHeader.test.tsx` | 布局、导航和可访问性交互测试 |
| `frontend/src/components/ui/ui-variants.test.tsx` | 控件和语义反馈变体测试 |

---

## 21. 笔记本权限、导览建议与可观测性修复（新增 2026-06-11 ~ 2026-06-13）

本轮基于 `bugfix_feat_test_0611` 分支，围绕笔记本多用户权限、NotebookLM 风格导览卡片、回答后的下一步建议、长耗时问答反馈、联网搜索卡死排查、图片源展示和源码启动日志问题进行集中修复。由于本轮覆盖范围较广，以下按“已完成 / 部分完成 / 暂缓和待办”记录，便于后续继续拆分收敛。

---

### 21.1 笔记本创建者权限与三点菜单

**用户问题**：任意登录用户都能修改其他人的笔记本密码、归档和删除笔记本；修复后又发现创建者自己的卡片 hover 仍看不到三点菜单。

#### 后端权限收敛

- `api/routers/notebooks.py`：
  - 新增 `normalize_record_id()`，兼容 SurrealDB record string、dict 和对象字符串，避免 `user:abc` / `abc` / `{ id: "user:abc" }` 形态不一致导致误判
  - 新增 `ensure_notebook_creator()`，统一校验 `notebook.created_by == current_user.id`
  - 密码管理、归档/更新、删除端点均要求当前用户为创建者
  - `NotebookResponse.created_by` 返回前统一归一化，前端无需理解 SurrealDB record 内部形态
- `api/models.py` — `NotebookResponse` / `NotebookCreate` 等 schema 补齐 `created_by` 字段
- `tests/test_notebooks_api.py` — 覆盖创建者可管理密码、非创建者管理员不可越权、无创建者旧笔记本不可被任意认领、非创建者不可归档/删除

#### 数据库 schema 根因修复

根因确认：`notebook` 表为 `SCHEMAFULL`，但早期 migration 仅定义了 `password` 和 `creator_name`，遗漏 `created_by`。因此 API 写入 `created_by=current_user.id` 后会被 SurrealDB 丢弃，前端永远拿到 `created_by=null`。

- `open_notebook/database/migrations/26.surrealql` — 新增：

```surql
DEFINE FIELD IF NOT EXISTS created_by ON TABLE notebook TYPE option<string>;
```

- `open_notebook/database/migrations/26_down.surrealql` — 回滚字段
- `tests/test_notebook_schema_migrations.py` — 新增 schema 回归测试，防止 notebook schema 再次遗漏 `created_by`

#### 前端菜单显示

- `frontend/src/lib/utils/record-id.ts` — 新增 `normalizeRecordId()` / `sameRecordId()`，统一前端 record id 比较
- `frontend/src/app/(dashboard)/notebooks/components/NotebookCard.tsx`：
  - 三点菜单仅创建者可见
  - 创建者菜单不再依赖 `opacity-0 group-hover:opacity-100`，避免 hover 状态或 owner 判断边界导致用户看不到入口
- `frontend/src/app/(dashboard)/notebooks/components/NotebookHeader.tsx` — 详情页密码、归档、删除按钮同样按创建者显示
- `frontend/src/app/(dashboard)/notebooks/components/NotebookCard.test.tsx` — 覆盖 string 和 object 形态 `created_by`、创建者可见、非创建者不可见

**决策**：旧笔记本若数据库中已经没有 `created_by`，不自动用 `creator_name == display_name` 认领。`display_name` 非唯一且可修改，作为权限依据会重新引入越权风险。旧数据若需要恢复归属，应后续单独设计受控 backfill。

---

### 21.2 NotebookLM 风格导览卡片与下一步建议

**用户需求**：参考 NotebookLM，首次导入来源后在聊天区生成结构化 summary 和 3 条建议动作；后续每次回答结束后也给出 3 条下一步建议。用户点击建议时应直接发送该问题。

#### 导览卡片

- `api/notebook_guide_service.py` — 新增导览生成服务，根据笔记本来源内容生成：
  - 标题/摘要
  - 关键要点
  - 3 条建议问题
- `api/routers/notebooks.py` — 新增/接入 `/notebooks/{id}/guide` 导览接口
- `frontend/src/components/source/NotebookGuideCard.tsx` — 新增导览卡片组件
- `frontend/src/app/(dashboard)/notebooks/components/ChatColumn.tsx` — 在无对话或导览可用时展示导览卡片；点击建议问题直接发送
- `frontend/src/app/(dashboard)/notebooks/[id]/page.tsx` — 接入导览数据和状态
- `tests/test_notebook_guide_service.py` / `tests/test_notebook_guide_api.py` — 覆盖服务与 API

#### 回答后的建议问题

- `api/routers/chat.py`：
  - SSE 主回答结束后生成 `suggested_questions` 事件
  - 建议生成设置超时，避免主回答完成后长期阻塞
  - 超时后提供降级建议，目标是回答后仍尽量给出 3 条下一步问题
- `frontend/src/components/source/SuggestedQuestionList.tsx` — 新增建议问题列表组件
- `frontend/src/lib/hooks/useNotebookChat.ts`：
  - 解析 SSE `suggested_questions`
  - 暂存建议问题，避免 session 持久化刷新后 AI message id 变化导致建议丢失
  - 点击建议后复用发送问题链路
- `frontend/src/lib/hooks/useNotebookChat.test.tsx` / `tests/test_chat_suggestions_sse.py` — 覆盖 SSE 建议事件、前端持久化刷新后仍保留建议

**当前状态**：代码和测试已完成，但仍建议在真实笔记本中手测“长回答后是否稳定出现 3 条建议”。如后续仍缺失，应优先查看 `logs/open_notebook.log` 中 `suggestions_start` / `suggestions_end` / `suggestions_timeout`。

---

### 21.3 长耗时问答反馈与可观测日志

**用户问题**：用户发送问题后等待很久才看到流式回答，期间像系统无响应；出现卡死时无法从日志判断卡在哪一步。

#### 前端等待状态

- `frontend/src/components/source/ChatPanel.tsx`：
  - 用户发送后、首个 AI chunk 到达前显示轻量状态提示
  - 状态覆盖获取上下文、联网搜索、生成回答、生成建议等阶段
  - 输入框在回答中显示响应状态，并保留停止按钮
- `frontend/src/app/(dashboard)/notebooks/components/ChatColumn.tsx` — 透传 notebook chat 的阶段状态
- `frontend/src/components/source/ChatPanel.test.tsx` / `frontend/src/app/(dashboard)/notebooks/components/ChatColumn.test.tsx` — 覆盖状态提示渲染

#### 后端 INFO 级日志

- `open_notebook/graphs/observability.py` — 新增聊天链路观测辅助逻辑
- `api/routers/chat.py` / `open_notebook/graphs/chat.py` / `open_notebook/graphs/tools.py`：
  - `chat_trace` 贯穿一次聊天请求
  - INFO 日志覆盖请求开始、context token/字符数、是否启用联网、模型 id、图执行开始、Tavily 查询开始/结束、首个 AI chunk、主回答结束、建议问题生成开始/结束/超时、总耗时
- `tests/test_chat_observability.py` / `tests/test_chat_context_budget.py` — 覆盖关键日志字段和 context budget 行为

**决策**：可观测性优先落在 `logs/open_notebook.log`，方便源码启动模式下直接定位卡点；前端只显示用户能理解的阶段文案，不暴露内部图节点和工具细节。

#### 2026-06-13 后续收敛

- `api/routers/chat.py` — 主回答结束后立即发送 `answer_complete` SSE 事件，再异步继续生成 `suggested_questions`，最后发送原有 `complete` 事件关闭流。这样建议问题慢或超时时，不再阻塞用户继续输入下一条问题。
- `frontend/src/lib/hooks/useNotebookChat.ts` — 收到 `answer_complete` 后立即恢复发送状态和输入框，同时继续读取同一个 SSE 连接中随后到达的建议问题。
- `frontend/src/lib/hooks/useNotebookChat.ts` — 对 notebook context 构建增加签名缓存和同签名 in-flight 去重；签名包含 notebook id、来源/笔记 id、更新时间和上下文选择模式。相同选择下发送消息复用已构建 context，避免大来源笔记本在统计和发送之间重复构建完整上下文。
- `tests/test_chat_suggestions_sse.py` / `frontend/src/lib/hooks/useNotebookChat.test.tsx` — 覆盖 `answer_complete` 事件、建议问题后到达时继续挂载、相同选择下 context 构建复用。

---

### 21.4 Tavily 联网搜索超时与降级

**用户问题**：启用联网搜索后，白名单域名较多时长时间停在“正在联网搜索...”，API 日志显示多次 `web_search_start` 后缺少对应结束。

- `open_notebook/graphs/tools.py`：
  - Tavily 查询增加超时控制
  - 捕获超时和异常，返回可读降级消息
  - 记录 `web_search_start` / `web_search_end`，包括 query 长度、include domain 数、结果数、耗时、timeout/failed 状态
- `tests/test_tavily_search_timeout.py` — 覆盖 Tavily 慢响应时返回超时说明而不是无限等待
- `frontend/src/components/source/ChatPanel.tsx` — 联网搜索阶段显示明确状态，让用户知道系统仍在处理

#### 2026-06-13 后续收敛

- `open_notebook/graphs/tools.py`：
  - 新增 `TAVILY_SEARCH_MAX_CALLS`，默认每次 chat trace 最多 2 次 Tavily 调用
  - 超过上限后直接返回降级说明，不再触发真实 Tavily 网络请求
  - 保留 `unknown` trace 的兼容行为，避免非聊天链路被误限流
- `tests/test_tavily_search_timeout.py` — 覆盖同一 chat trace 下超过上限时第二次搜索不会调用 Tavily。

**当前状态**：已完成“不卡死 + 可降级 + 可观测 + 单回答搜索调用上限”的第二层修复；仍需结合真实 23 源笔记本日志继续分析 context 构建、模型首包和白名单查询质量。

---

### 21.5 笔记本来源选择、默认全文与布局体验

#### 来源筛选与批量选择

- `frontend/src/app/(dashboard)/notebooks/components/SourcesColumn.tsx`：
  - 来源列表增加筛选能力
  - 增加批量选择/上下文模式操作入口
  - 便于大来源数量笔记本中快速定位和调整引用范围

#### 新来源默认参考全文

- `frontend/src/app/(dashboard)/notebooks/components/SourcesColumn.tsx` / `frontend/src/lib/hooks/useNotebookChat.ts`：
  - 新增来源后默认加入全文上下文，而不是默认仅引用见解

#### 对话栏与笔记栏布局

- `frontend/src/app/(dashboard)/notebooks/[id]/page.tsx`：
  - 调整打开笔记本后的布局，使来源栏与对话栏更接近
  - 笔记栏为空时可收起/减少占用，给来源和对话更多空间

**当前状态**：代码已有改动，组件级回归通过；由于本轮浏览器打开 `/notebooks` 时被 API 连接错误页阻挡，真实新上传/添加已有来源、空笔记栏/有笔记栏布局仍需在 API 可用环境下手测确认。

---

### 21.6 图片源处理与详情展示

**用户需求**：如果源本身就是图片文件，进入内容页后应先显示图片，再显示对图片的描述。

- `frontend/src/components/source/SourceDetailContent.tsx`：
  - 识别 `.png`、`.jpg`、`.jpeg`、`.gif`、`.webp`、`.bmp`、`.tif`、`.tiff`、`.img` 等独立图片源
  - 内容页顶部通过 `/api/sources/{id}/download` 显示原图
  - 原图下方继续显示 `full_text` 中的图片描述或解析文本
- `frontend/src/components/source/SourceDetailContent.test.tsx` — 覆盖独立图片源“先图后描述”
- `open_notebook/graphs/source.py` / `tests/test_vision_descriptions.py` — 继续扩展图片描述链路的容错、并发和格式清洗

**当前状态**：图片源详情展示已完成。后端导入链路已覆盖 `.png`、`.jpg`、`.jpeg`、`.gif`、`.webp`、`.bmp`、`.tif`、`.tiff`、`.img`：独立图片绕过 content-core 文本抽取，复制到 `data/uploads/images/{source_id}/`，写入原图 Markdown，并将 Vision 描述或“未配置 Vision 模型”的占位说明合并进 `Source.full_text`。因此即使没有视觉模型，source 也不会因正文为空而失败，后续嵌入与知识图谱抽取继续复用现有 `full_text` 流程。浏览器端用 `http://192.168.10.55:3001/` 新建笔记本验证 `.png/.bmp/.tiff/.img` 上传和详情展示时发现 Chromium 不能直接渲染 TIFF；已新增 `GET /sources/{source_id}/preview` 将 `.tif/.tiff` 转为 PNG 预览，详情页顶部原图和 Markdown 内 TIFF 图片均走该预览端点，原始下载仍保留 TIFF。真实视觉模型质量、纯图片描述文本是否适合 KG 抽取，仍需用更多实际样本继续评估。

#### 2026-06-13 第二段收敛

- `frontend/src/components/source/SourceDialog.tsx` — 源详情弹窗关闭默认浮动 X，避免与内容 header 的右上角动作区争抢空间。
- `frontend/src/components/source/SourceDetailContent.tsx` — 当作为弹窗内容使用时，在类型 badge、三点菜单同一动作区内渲染关闭按钮；内容/见解/详情切换时右上角动作保持同一布局来源。
- `frontend/src/components/source/SourceDetailContent.test.tsx` — 覆盖弹窗模式关闭按钮调用 `onClose`。

---

### 21.7 侧边栏最近笔记本、密码标识与词元翻译

- `frontend/src/lib/stores/recent-notebooks-store.ts` — 新增最近打开笔记本状态
- `frontend/src/components/layout/AppSidebar.tsx` — 在“笔记本”菜单下展示最近打开的笔记本，长标题截断并通过 hover title 查看全名
- `frontend/src/app/(dashboard)/notebooks/components/NotebookCard.tsx` — 带密码笔记本展示锁定/密码标识
- `frontend/src/lib/locales/zh-CN/index.ts` / `frontend/src/lib/locales/en-US/index.ts` — 更新相关文案；中文界面将 Token 统一为“词元”

#### 2026-06-13 第二段收敛

- `frontend/src/components/layout/AppSidebar.tsx` — 最近笔记本链接补原生 `title` 属性，长标题除 Radix Tooltip 外也有浏览器原生 hover 提示。
- `frontend/src/app/(dashboard)/notebooks/components/NotebookCard.tsx` / `NotebookHeader.tsx` — owner 操作和密码按钮文案移除英文 fallback，统一走 i18n；新建笔记本路径仍以 `created_by` 与当前用户匹配作为三点菜单显示条件。
- `frontend/src/components/layout/AppSidebar.test.tsx` — 覆盖最近笔记本长标题 `title`。

**当前状态**：组件级行为已收敛。按安全决策，旧笔记本缺少 `created_by` 不显示 owner 三点菜单，不作为本轮 UI 回归；新建笔记本应在 API 写入 `created_by` 后显示。

---

### 21.8 源码启动日志脚本修复

**用户问题**：`make start-all` 启动时只看到 DB 日志，API/worker/frontend 日志缺失，并出现：

```text
awk: calling undefined function strftime
```

#### 修复

- `Makefile`：
  - 将依赖 `awk strftime()` 的日志时间戳管道替换为 shell `date`
  - 适配 macOS 默认 awk 不支持 `strftime()` 的情况
  - 保留 API、worker、frontend、DB 分进程日志前缀输出
- `tests/test_makefile_logging.py` — 覆盖 Makefile 不再依赖 `awk strftime`

**决策**：当前阶段以源码方式运行服务供用户使用，因此优先修复本地 `make start-all`，而不是仅处理 Docker 启动路径。

---

### 21.9 已验证命令

本轮关键验证包括：

```text
cd frontend && npm test -- --run src/app/'(dashboard)'/notebooks/components/NotebookCard.test.tsx src/lib/hooks/useNotebookChat.test.tsx src/components/source/SourceDetailContent.test.tsx
10 passed

cd frontend && npm run build -- --webpack
exit 0

.venv/bin/python -m pytest tests/test_notebooks_api.py tests/test_chat_suggestions_sse.py -q
9 passed, 1 warning

.venv/bin/python -m pytest tests/test_notebook_schema_migrations.py tests/test_notebooks_api.py -q
6 passed, 1 warning

.venv/bin/python -m pytest tests/test_chat_suggestions_sse.py -q
4 passed, 1 warning

.venv/bin/python -m ruff check api/routers/notebooks.py api/routers/chat.py open_notebook/graphs/source.py tests/test_notebooks_api.py tests/test_chat_suggestions_sse.py tests/test_vision_descriptions.py
All checks passed

git diff --check
passed

2026-06-13 后续收敛验证：

.venv/bin/python -m pytest tests/test_chat_suggestions_sse.py tests/test_tavily_search_timeout.py tests/test_chat_context_budget.py -q
8 passed, 1 warning

cd frontend && npm test -- useNotebookChat.test.tsx
6 passed

.venv/bin/python -m ruff check api/routers/chat.py open_notebook/graphs/tools.py tests/test_chat_suggestions_sse.py tests/test_tavily_search_timeout.py
All checks passed

cd frontend && npx eslint src/lib/hooks/useNotebookChat.ts src/lib/hooks/useNotebookChat.test.tsx
exit 0

cd frontend && npm run build
exit 0

2026-06-13 第二段 UI 收敛验证：

cd frontend && npm test -- NotebookCard.test.tsx ChatPanel.test.tsx ChatColumn.test.tsx SourceDetailContent.test.tsx AppSidebar.test.tsx
34 passed

cd frontend && npx eslint src/components/source/SourceDetailContent.tsx src/components/source/SourceDialog.tsx src/components/layout/AppSidebar.tsx src/app/'(dashboard)'/notebooks/components/NotebookCard.tsx src/app/'(dashboard)'/notebooks/components/NotebookHeader.tsx src/components/source/SourceDetailContent.test.tsx src/components/layout/AppSidebar.test.tsx
exit 0, one existing Next no-img-element warning for standalone image preview

cd frontend && npm run build
exit 0
```

`npm run build -- --webpack` 仍打印 Next standalone traced file copy warning，但退出码为 0；该警告在前序 UI 分支中已存在，不阻塞本轮验证。

---

### 21.10 未尽事宜与后续建议

#### 需要继续优化

1. **联网搜索性能与稳定性**：当前已加超时、降级和每次回答 Tavily 调用上限；还需分析多白名单域名下的查询质量和是否需要更明确的模型提示来减少无效搜索。
2. **大来源数量问答耗时**：已减少前端相同选择下重复 context 构建；23 个源真实场景仍需拆解 context 构建、模型首包、联网搜索和建议生成各阶段耗时，并考虑进一步 context 裁剪或缓存。
3. **导览卡片生成进度**：已有生成中反馈，但尚未做到细粒度步骤进展；首次导入来源后的长等待仍可继续优化。
4. **导览卡片长期保留体验**：代码已朝保留方向处理，但需要真实对话中验证首次提问、点击建议、刷新页面后的保留行为。
5. **新来源默认全文**：已改代码并保留组件级逻辑；需在 API 可用环境分别验证“新上传来源”和“添加已有来源”两条路径。
6. **笔记栏/对话栏布局**：已改方向，但浏览器本轮被 API 连接错误页阻挡；需要结合真实屏幕尺寸、空笔记栏、有笔记栏、移动端三种场景继续调优。
7. **最近笔记本与密码标识**：最近笔记本长标题 title 已补，密码标识基础功能保留；仍需在新建笔记本真实数据上确认视觉显著性和点击切换体验。
8. **图片源完整链路**：已完成详情展示，后续应专项确认图片导入、Vision 描述、嵌入、KG 抽取是否覆盖全部目标格式。

#### 暂缓或未做

1. **已发送问题一键复制回输入框**：已实现“编辑并再次提问”入口，仍可后续根据真实使用反馈调整入口位置或文案。
2. **联网搜索答案中的互联网引用标注**：暂缓。要做到句级区分互联网源与本地源，需要更深的引用跟踪和回答后处理，当前先观察用户反馈。
3. **旧笔记本 `created_by` backfill**：暂缓。缺少可靠创建者字段时不能自动认领，后续如需要应做管理员确认式数据修复。

---

### 文件索引

| 文件 | 涉及改动 |
|------|----------|
| `api/routers/notebooks.py` | 创建者权限校验、`created_by` 归一化、导览接口接入 |
| `api/models.py` | Notebook response/create/password/guide 相关 schema 扩展 |
| `api/routers/chat.py` | SSE 建议问题、阶段日志、超时降级和回答链路可观测性 |
| `api/routers/sources.py` | 图片/来源下载与相关接口适配 |
| `api/notebook_guide_service.py` | **新文件** — 笔记本导览卡片生成服务 |
| `open_notebook/database/migrations/26.surrealql` | notebook 表新增 `created_by` 字段 |
| `open_notebook/database/migrations/26_down.surrealql` | 回滚 `created_by` 字段 |
| `open_notebook/graphs/chat.py` | chat graph 模型调用日志和 trace 传递 |
| `open_notebook/graphs/tools.py` | Tavily 超时、异常降级、开始/结束日志 |
| `open_notebook/graphs/observability.py` | **新文件** — chat trace 可观测辅助 |
| `open_notebook/graphs/source.py` | 图片描述链路延续增强 |
| `Makefile` | `make start-all` 日志时间戳 macOS 兼容 |
| `frontend/src/lib/utils/record-id.ts` | **新文件** — 前端 record id 归一化 |
| `frontend/src/lib/hooks/useNotebookChat.ts` | SSE 状态、建议问题保留、导览/上下文交互 |
| `frontend/src/components/source/ChatPanel.tsx` | 用户等待状态提示、建议问题展示入口 |
| `frontend/src/components/source/SuggestedQuestionList.tsx` | **新文件** — 下一步建议列表 |
| `frontend/src/components/source/NotebookGuideCard.tsx` | **新文件** — 导览卡片 |
| `frontend/src/components/source/SourceDetailContent.tsx` | 独立图片源先显示原图再显示描述 |
| `frontend/src/app/(dashboard)/notebooks/[id]/page.tsx` | 笔记本布局、导览和最近笔记本接入 |
| `frontend/src/app/(dashboard)/notebooks/components/ChatColumn.tsx` | 导览卡片、阶段状态、建议点击发送 |
| `frontend/src/app/(dashboard)/notebooks/components/SourcesColumn.tsx` | 来源筛选、批量选择、默认全文相关改动 |
| `frontend/src/app/(dashboard)/notebooks/components/NotebookCard.tsx` | 创建者菜单、密码标识 |
| `frontend/src/app/(dashboard)/notebooks/components/NotebookHeader.tsx` | 详情页创建者操作控制 |
| `frontend/src/components/layout/AppSidebar.tsx` | 最近打开笔记本列表 |
| `frontend/src/lib/stores/recent-notebooks-store.ts` | **新文件** — 最近笔记本本地状态 |
| `frontend/src/lib/api/notebooks.ts` | guide/password/notebook API 适配 |
| `frontend/src/lib/api/query-client.ts` | notebook 查询失效和刷新支持 |
| `frontend/src/lib/hooks/use-notebooks.ts` | notebook mutation 和密码/权限状态适配 |
| `frontend/src/lib/types/api.ts` | Notebook、guide、chat 建议等 TS 类型扩展 |
| `frontend/src/lib/locales/en-US/index.ts` / `zh-CN/index.ts` | 导览、建议、等待状态、词元、密码等文案 |
| `frontend/src/components/sources/steps/SourceTypeStep.tsx` | 图片格式声明相关调整 |
| `tests/test_notebooks_api.py` | 创建者权限回归 |
| `tests/test_notebook_schema_migrations.py` | schema 中 `created_by` 字段回归 |
| `tests/test_notebook_guide_service.py` / `tests/test_notebook_guide_api.py` | 导览服务/API 回归 |
| `tests/test_chat_suggestions_sse.py` | SSE 建议问题回归 |
| `tests/test_chat_observability.py` / `tests/test_chat_context_budget.py` | chat 日志和上下文预算回归 |
| `tests/test_tavily_search_timeout.py` | Tavily 超时降级回归 |
| `tests/test_makefile_logging.py` | Makefile 日志时间戳兼容回归 |
| `frontend/src/lib/hooks/useNotebookChat.test.tsx` | 前端建议问题保留回归 |
| `frontend/src/components/source/SourceDetailContent.test.tsx` | 图片源详情展示回归 |
| `frontend/src/app/(dashboard)/notebooks/components/NotebookCard.test.tsx` | owner 菜单可见性回归 |
| `frontend/src/components/source/ChatPanel.test.tsx` / `ChatColumn.test.tsx` | 等待状态和建议交互回归 |

---

## 22. Codex 本地协作环境优化（新增 2026-06-13）

本轮基于 `en_local_codex_env_optim_0613` 分支，将长期二开过程中形成的 Codex 使用习惯固化为项目级配置、仓库 skill、轻量 hook 和快捷验证入口，减少后续任务对临时上下文和口头提醒的依赖。

### 22.1 项目级 Codex 配置

- `.codex/config.toml`：
  - `project_doc_max_bytes = 65536`，降低根 `AGENTS.md` 和后续项目说明被默认 32 KiB 限制截断的概率
  - 显式启用 `features.hooks` 和 `features.memories`
- `.codex/hooks.json`：
  - 注册 `Stop` 阶段提醒型 hook
- `.codex/hooks/lumina_stop_check.py`：
  - 检测前端可见文件改动但未触碰 locale 时，提醒确认是否需要 i18n key
  - 检测 API、前端、后端、prompt、Makefile、`.codex`、`.agents` 等耐久行为改动但未更新本总账时，提醒补充 `docs/8-CUSTOMIZATION/00-index.md`
  - 仅输出提醒并返回 0，不阻断开发流程

**决策**：hook 先采用非阻断模式，避免在规则未完全稳定前影响正常迭代；后续若提醒命中率高，可再考虑增强为更严格的检查。

### 22.2 Repo Skill

- `.agents/skills/lumina-omax-development/SKILL.md` — 新增仓库级 skill，触发范围覆盖 `lumina-omax` 中非平凡开发任务，尤其是 UI、i18n、API、RAG、Vision、部署和文档变更
- skill 固化：
  - 先读 `docs/8-CUSTOMIZATION/00-index.md`
  - UI 任务再读 `DESIGN.md` 和相关 `docs/superpowers/` 规格/计划
  - 浏览器侧 API 使用相对 `/api`
  - 前端可见文案走 i18n
  - 代码审查建议先验证再执行
  - 变更后按影响面选择窄验证命令

**决策**：把项目专属流程放到 repo skill，而不是继续扩展根 `AGENTS.md`，以便 Codex 按任务渐进加载，降低普通问题的上下文负担。

### 22.3 根说明与验证入口

- `AGENTS.md`：
  - 新增 Lumina-Omax 本地工作规则
  - 明确非平凡开发先读二开总账
  - 强调 UI 走温暖研究设计系统和 i18n
  - 明确 LAN 源码部署下浏览器流量走相对 `/api`
  - 移除当前仓库不存在的子目录 `AGENTS.md` 引用，改为说明当前 checkout 以根文件为准
- `Makefile`：
  - 新增 `codex-diff-check`：执行 `git diff --check`
  - 新增 `codex-quick-check`：快速 diff hygiene 检查
  - 新增 `codex-frontend-check`：执行 `npm run lint`、`npm test`、`npm run build`
  - 新增 `codex-backend-check`：执行 ruff 和 pytest

**决策**：把常用验证命令命名为 `codex-*`，避免每轮任务重新推断构建/测试入口，也避免误用已知不稳定的旧 `make dev` 路径。

### 22.4 本机全局 Codex 设置

本轮还在本机 `~/.codex` 下做了不会进入 PR 的个人环境调整：

- `~/.codex/AGENTS.md` — 写入通用协作偏好：先读仓库说明、审查建议先验证、可见文案走 i18n、大 UI 先计划、结束时报告验证和缺口
- `~/.codex/config.toml` — `features.js_repl` 从 `false` 改为 `true`，配合 Browser/Chrome 插件提升前端和浏览器验证效率

**决策**：个人默认放全局 Codex home，项目共同约束放仓库；两者分层，避免把个人偏好误当成项目事实。

### 22.5 验证

本轮验证以配置和文本结构为主：

```text
python3 -m json.tool .codex/hooks.json
.codex/hooks/lumina_stop_check.py
python3 - <<'PY'
from pathlib import Path
for path in [
    ".codex/config.toml",
    ".agents/skills/lumina-omax-development/SKILL.md",
    "AGENTS.md",
]:
    assert Path(path).read_text(encoding="utf-8").strip()
PY
make codex-quick-check
```

### 文件索引

| 文件 | 涉及改动 |
|------|----------|
| `.codex/config.toml` | 项目级 Codex 配置，扩大项目说明读取预算并启用 hooks/memories |
| `.codex/hooks.json` | 注册 Stop 阶段工作流提醒 hook |
| `.codex/hooks/lumina_stop_check.py` | i18n 与二开总账更新提醒 |
| `.agents/skills/lumina-omax-development/SKILL.md` | 仓库级 Codex 开发 workflow skill |
| `AGENTS.md` | 本地工作规则、二开总账、UI/i18n、LAN `/api` 约束 |
| `Makefile` | 新增 `codex-*` 快捷验证入口 |
| `docs/8-CUSTOMIZATION/00-index.md` | 记录本轮 Codex 环境优化 |

---

## 23. 打开笔记本来源筛选与本次聊天引用范围（新增 2026-06-13）

本轮基于 `codex/notebook-source-context-selection` 分支，实现打开笔记本内的来源筛选和筛选结果批量选择。该选择只控制**本次聊天引用哪些来源**，不改变来源是否属于当前笔记本。

### 23.1 行为决策

- 来源栏保留总来源数和当前参与聊天上下文的来源数显示。
- 来源筛选按标题、文件路径、URL、来源笔记本名和上传者匹配。
- 筛选框下方新增“全选 / 取消全选”，只作用于当前筛选结果。
- 来源栏右上角三点菜单仍保留原有全部来源的批量上下文模式设置。
- 聊天请求层继续通过 `context_config` 显式传递每个来源的上下文模式：选中的来源为 `full content`，未选来源为 `not in`。

**边界**：这不是来源成员管理。取消选择后，来源仍留在笔记本中，只是不参与当前聊天上下文。

### 23.2 已有上限

新增来源流程当前已有 50 个批量上限：

- `frontend/src/components/sources/AddSourceDialog.tsx`
- `frontend/src/components/sources/steps/SourceTypeStep.tsx`

本轮未把该上限升级为后端 settings 字段；如后续需要管理员可调，应单独扩展 `ContentSettings`、`SettingsResponse`、设置页表单和添加来源入口，避免把聊天引用范围改动与设置 schema 改动混在一个 PR。

### 23.3 验证

```text
cd frontend && npm test -- SourcesColumn.test.tsx useNotebookChat.test.tsx
```

### 文件索引

| 文件 | 涉及改动 |
|------|----------|
| `frontend/src/app/(dashboard)/notebooks/components/SourcesColumn.tsx` | 来源筛选结果的全选/取消全选与筛选内选中数量 |
| `frontend/src/app/(dashboard)/notebooks/[id]/page.tsx` | 批量上下文选择支持限定 source id 范围 |
| `frontend/src/components/source/SourceDetailContent.tsx` | 修复 markdown 图片 `src` 类型窄化，保证生产构建通过 |
| `frontend/src/app/(dashboard)/notebooks/components/SourcesColumn.test.tsx` | 来源栏筛选后批量选择回归 |
| `frontend/src/lib/hooks/useNotebookChat.test.tsx` | 聊天上下文配置遵守来源选择回归 |
| `docs/8-CUSTOMIZATION/00-index.md` | 记录本轮行为决策、边界和验证 |

---

## 24. 添加现有来源仅展示已嵌入来源（新增 2026-06-14）

本轮基于 `codex/processed-source-notebook-reference` 分支，将“未完成嵌入的来源不能通过添加现有来源被选入笔记本”收敛为一个前端选择列表过滤规则，避免把处理状态约束扩散到新增来源路径和后端 reference 语义。

### 24.1 行为决策

- 打开笔记本后的普通“添加来源/新建来源”路径不改变，仍按原流程创建来源并关联笔记本。
- “添加现有来源”弹窗加载全量来源后，仅展示 `source.embedded === true` 的来源。
- 未完成嵌入的来源不在弹窗列表里出现，也不显示禁选原因，避免用户看到不可操作项。
- Knowledge Graph 状态不参与此规则；只要已完成嵌入，即可在“添加现有来源”弹窗中选择。
- 全选、搜索、手动勾选都只作用于已嵌入且未在当前笔记本中的来源。

**边界**：本轮不新增后端 `409` guard，不改变 `POST /notebooks/{notebook_id}/sources/{source_id}` 的语义，也不改变新建来源时的即时 notebook 关联。这里的限制只针对“添加现有来源”弹窗的候选列表。

### 24.2 验证

```text
cd frontend && npm test -- AddExistingSourceDialog.test.tsx SourcesColumn.test.tsx
```

### 文件索引

| 文件 | 涉及改动 |
|------|----------|
| `frontend/src/components/sources/AddExistingSourceDialog.tsx` | 添加现有来源弹窗仅展示已嵌入来源，搜索/全选/勾选都基于过滤后的集合 |
| `frontend/src/components/sources/AddExistingSourceDialog.test.tsx` | 回归覆盖未嵌入来源不展示、KG 状态不影响已嵌入来源可选 |
| `docs/8-CUSTOMIZATION/00-index.md` | 记录本轮行为决策、边界和验证 |

---

## 25. 添加来源数量上限设置（新增 2026-06-14）

本轮基于 `codex/source-add-limit-setting` 分支，将单个笔记本允许包含的来源总数上限做成设置项。默认仍为 50，管理员可在设置页调整。

### 25.1 行为决策

- `ContentSettings.source_batch_limit` 默认值为 50，允许范围为 1-200。
- 设置 API 的读取和更新响应包含 `source_batch_limit`，现有设置记录缺少该字段时回退到 50。
- 设置页“文件管理”区域新增“添加来源数量上限”数字输入，沿用现有管理员设置入口。
- 添加新来源时，打开笔记本路径会按“当前笔记本已有来源数 + 本次新增来源数”判断是否超过上限。
- 添加新来源窗口在当前笔记本没有剩余槽位时，会直接显示“此笔记本的来源数已达到上限”的提示。
- 添加现有来源时，弹窗会按当前笔记本剩余槽位限制单选和全选，不能选出超过上限的数量。
- 非法或缺失的前端设置值在弹窗侧回退到 50，避免旧缓存或异常响应导致无限制添加。

**边界**：本轮不新增后端批量创建接口，也不改变单个 `POST /sources` 或 `POST /notebooks/{notebook_id}/sources/{source_id}` 的语义。这里的限制在打开笔记本的前端添加入口执行，用于防止单个笔记本来源总数超过设置值。

### 25.2 验证

```text
.venv/bin/python -m pytest tests/test_domain.py::TestContentSettings -q
cd frontend && npm test -- SourceTypeStep.test.tsx
cd frontend && npm test -- AddExistingSourceDialog.test.tsx SourceTypeStep.test.tsx
```

### 文件索引

| 文件 | 涉及改动 |
|------|----------|
| `open_notebook/domain/content_settings.py` | 新增 `source_batch_limit` 默认值和范围校验 |
| `api/models.py` | 设置读写模型暴露 `source_batch_limit` |
| `api/routers/settings.py` | 设置读取、更新、响应带上笔记本来源数量上限 |
| `api/settings_service.py` | 客户端设置服务读写新增字段并回退默认值 |
| `frontend/src/app/(dashboard)/settings/components/SettingsForm.tsx` | 文件管理设置区新增数量上限输入 |
| `frontend/src/components/sources/AddSourceDialog.tsx` | 添加新来源时按目标笔记本剩余槽位限制本次新增数量 |
| `frontend/src/components/sources/AddExistingSourceDialog.tsx` | 添加现有来源时按剩余槽位限制单选和全选 |
| `frontend/src/components/sources/AddExistingSourceDialog.test.tsx` | 覆盖 49/50 时添加现有来源最多只能再选 1 个 |
| `frontend/src/components/sources/steps/SourceTypeStep.tsx` | 来源类型步骤展示剩余槽位、已达上限提示，并导出上限/剩余槽位 helper |
| `frontend/src/components/sources/steps/SourceTypeStep.test.tsx` | 覆盖配置化上限、异常值回退、剩余槽位计算和已达上限提示 |
| `frontend/src/lib/locales/en-US/index.ts`、`frontend/src/lib/locales/zh-CN/index.ts` | 新增设置页文案 |
| `tests/test_domain.py` | 覆盖默认 50 和 1-200 范围校验 |
| `docs/8-CUSTOMIZATION/00-index.md` | 记录本轮行为决策、边界和验证 |

---

## 26. 导览点击与回答后建议刷新可观测性（新增 2026-06-14）

本轮基于 `codex/guide-followup-refresh` 分支，收敛导览卡片建议点击、回答后 3 条下一步建议刷新，以及建议生成失败时的日志可观测性。

### 26.1 行为决策

- 导览卡片问题点击继续复用 `ChatPanel` 的普通发送路径，保持与用户手动输入后发送一致。
- 回答后建议生成时，后端明确把本轮用户问题、主回答和 notebook context 一起传入 follow-up prompt，避免只根据回答和上下文生成泛化或重复建议。
- 前端新增连续两轮回答回归，保证每轮 SSE `suggested_questions` 会挂到各自最新持久化 AI 消息上，不把上一轮建议复用到下一轮回答。
- 建议生成流程继续在主回答 `answer_complete` 之后异步完成，不阻塞用户继续输入。
- 聊天路径要求 follow-up 生成器显式暴露解析错误：坏 JSON 进入 `parse_failed`，模型空输出进入 `empty`，模型调用异常进入 `failed`，避免日志里把不同失败原因混在一起。
- 建议生成异常日志细化为：
  - `suggestions_start`：流程确实开始
  - `suggestions_empty`：生成器没有给出任何可用问题
  - `suggestions_parse_failed`：模型输出无法解析为 3 条建议，或数量不符合要求
  - `suggestions_failed`：模型调用或其他异常失败
  - `suggestions_timeout`：建议生成超时
  - `suggestions_fallback`：进入确定性降级建议
  - `suggestions_end`：成功得到 3 条建议

**边界**：本轮不重做导览卡片 UI，不改变聊天 SSE 事件协议的 `suggested_questions` payload，不改变已存在的 fallback 建议内容。

### 26.2 验证

```text
.venv/bin/python -m pytest tests/test_chat_suggestions_sse.py tests/test_notebook_guide_service.py -q
.venv/bin/python -m ruff check api/routers/chat.py api/notebook_guide_service.py tests/test_chat_suggestions_sse.py tests/test_notebook_guide_service.py
cd frontend && npm test -- useNotebookChat.test.tsx ChatPanel.test.tsx
cd frontend && npm run lint
cd frontend && npm run build
git diff --check
```

### 文件索引

| 文件 | 涉及改动 |
|------|----------|
| `api/notebook_guide_service.py` | follow-up prompt 加入用户问题；聊天路径可要求解析失败向外抛出，并区分坏 JSON 与空输出 |
| `api/routers/chat.py` | 建议生成传入本轮问题；补充 empty、parse_failed、failed、timeout、fallback 日志分支 |
| `tests/test_chat_suggestions_sse.py` | 覆盖 question 传递和建议失败日志分支 |
| `tests/test_notebook_guide_service.py` | 覆盖 malformed JSON 抛出 parse error 与空模型输出保留 empty 分支 |
| `frontend/src/lib/hooks/useNotebookChat.test.tsx` | 覆盖连续两轮回答分别挂载新的建议问题 |
| `docs/8-CUSTOMIZATION/00-index.md` | 记录本轮行为决策、边界和验证 |

---

## 27. 试用反馈优先修复：旧格式导入、全局 Ask 覆盖与来源体验（新增 2026-06-17）

本轮基于 `codex/feedback-priority-fixes-0617` 分支，按用户试用反馈优先处理“中期验收前”阻断项：旧版 Office 入库与全局发问可信统计；同时补齐来源详情操作区、产品图标、重复文件提示和 Help 文档。登录鉴权不纳入本轮修复，因为系统已支持一人一号、上传者与上传时间追溯；本次试用无法区分上传者是由于使用了公共试用账号。

### 27.1 行为决策

- `.doc` 继续通过 LibreOffice 转 PDF 后提取；`.ppt/.pptx` 同样通过 LibreOffice 转 PDF 后交给 MinerU/文档引擎解析；`.xls` 改为通过 LibreOffice 转 `.xlsx` 后进入 Excel 表格解析，避免旧版 Excel 因 content-core 不识别而断开入库通道。
- `.xlsx/.xlsm` 仍保持原生表格解析，不转 PDF，避免宽表分页破坏行列结构。
- 前端上传文件选择器的 `accept` 白名单必须与后端恢复后的能力一致，重新放开 `.doc/.ppt/.xls`，并补齐 `.xlsm`；这覆盖 §18 中旧版 Office 临时禁选的历史限制。
- Excel Markdown 清洗在修复单元格换行和空白行之外，新增整列为空的列删除；任意行存在值的列都会保留。Review 后补充空表移除和表格前后正文保留的回归测试。
- 全局 Ask 在回答前查询知识库来源总数和已嵌入可检索来源数，在检索过程中收集本轮命中的唯一 `source:*` 记录，并把覆盖统计作为 SSE metadata 返回前端。
- Ask 最终回答 prompt 明确使用覆盖 metadata，不能把“本次命中来源数”误说成“知识库总来源数”。
- 前端 Ask 面板显示“来源总数 / 可检索来源 / 本次命中来源”，并在浏览器端保留最近全局 Ask 历史，可恢复问题、答案和覆盖统计。
- 来源详情页的标题、关闭、三点菜单、源对话按钮和“内容/见解/详情”Tabs 统一放入同一个 sticky 工具区，长内容滚动到底部时仍可操作；笔记本源列表点击来源改为和总来源列表一致，进入完整 `/sources/{id}` 详情页并记录返回笔记本路径，不再通过来源 modal 查看长内容。来源 modal 仍保留固定高度和内部滚动，避免其他 URL modal 入口裁切内容。浏览器 favicon 统一由登录页产品图标 `logo.png` 生成。
- 笔记本对话面板保留原有左右气泡流排版；仅对 ChatPanel 内的 Radix ScrollArea viewport 增加局部 wrapper 约束，避免长表格、长引用和 `max-w-[80%]` 气泡在特定历史对话中把内部内容层撑宽，导致右侧内容被裁切。
- 创建笔记本和聚合笔记本的名称必填校验使用当前语言的 `common.nameRequired`，避免中文界面删除名称后出现硬编码英文 `Name is required`。
- 重名文件检查继续基于 `asset.original_filename`，但改为大小写不敏感并忽略首尾空格；后端返回本次提交的文件名，保证前端“仅上传非重复文件”过滤能命中。Review 后将归一化匹配下推到 SurrealDB 参数化查询，避免拉取全库文件名再在 Python 侧扫描；空输入/空白输入直接返回无重复且不触发数据库查询。后台处理完成重新保存 `Asset` 时必须保留既有 `original_filename`，避免 `.xlsx/.docx` 等经过 `ProcessSourceState` 后丢失原始文件名导致后续查重失效。
- `make start-all` 启动日志只 tail 本轮 SurrealDB 输出，API 进程显式加载 `.env`，并等待 `/api/config` ready 后再启动前端，避免 Next.js 在 API 尚未监听时产生 `/api/config` proxy `ECONNREFUSED`。
- Next.js 16 下 `middleware.ts` 入口迁移为 `proxy.ts`，鉴权与根路径重定向逻辑保持不变，消除启动时的 middleware deprecated warning。
- 删除重复的 dashboard route-group 根页，根路径跳转统一由 `app/page.tsx` 与 `proxy.ts` 承担，避免 standalone build 复制不存在的 client-reference manifest 时产生 trace warning。
- 19/20 号数据库迁移保留为空迁移文件，消除启动时缺失 migration 文件的 warning，并保留版本连续性。
- `tmp/` 目录加入 `.gitignore`，本轮从反馈 PDF 渲染出的临时 PNG 不纳入版本库；用户确认将试用反馈说明 Markdown、商务版 Word/PDF 和普通版 PDF 作为交付材料纳入本轮变更。
- `docs/superpowers/plans/2026-06-17-feedback-priority-fixes-implementation.md` 作为本轮实施计划留档，便于后续继续核对优先级和验收范围。
- ScienceDirect、OnePetro、ACS 等带真人验证或反爬挑战的学术网页暂不做绕过；Help 文档说明推荐上传下载后的 PDF 或粘贴正文。

**边界**：本轮不新增结构化实验索引、自动标签、实验时间线、产品图谱，不改变用户权限模型，不引入新的服务端 Ask 历史表。Ask 历史先采用浏览器端持久化，满足短期回溯。SurrealDB root 密码保持现状；旧 Office 转换仍要求本机安装 LibreOffice 或配置 `SOFFICE_PATH` / `LIBREOFFICE_PATH`。

### 27.2 验证

```text
.venv/bin/python -m pytest tests/test_office_converter.py tests/test_excel_source_cleanup.py -q
.venv/bin/python -m pytest tests/test_ask_coverage.py -q
.venv/bin/python -m pytest tests/test_sources_duplicates.py -q
.venv/bin/python -m pytest tests/test_graphs.py::TestSaveSourceTitlePreservation -q
cd frontend && npm test -- --run src/components/sources/steps/SourceTypeStep.test.tsx
cd frontend && npm test -- --run src/lib/stores/ask-store.test.ts src/components/search/StreamingResponse.test.tsx
cd frontend && npm test -- --run src/components/source/SourceDetailContent.test.tsx
cd frontend && npm test -- --run src/app/'(dashboard)'/notebooks/components/SourcesColumn.test.tsx src/components/source/SourceDetailContent.test.tsx
cd frontend && npm test -- --run src/components/source/ChatPanel.test.tsx
cd frontend && npm test -- --run src/components/notebooks/CreateNotebookDialog.test.tsx
cd frontend && npm test -- --run src/proxy.test.ts src/app/globals.test.ts
cd frontend && npm run build
make -n start-all
git diff --check
```

补充实机验证：本机已安装 LibreOffice 26.2.4；在非 sandbox 环境下用 `data/test-daba/feat-test/测试老格式的docxlsppt/` 中的 `.doc/.xls/.ppt` 样例调用 `convert_to_modern_office_format()`，分别生成 `.pdf/.xlsx/.pdf` 成功。

### 文件索引

| 文件 | 涉及改动 |
|------|----------|
| `open_notebook/utils/office_converter.py` | `.xls` 转 `.xlsx`，文档/演示仍转 PDF |
| `open_notebook/graphs/source.py` | `.xls` 提取前转换为 `.xlsx`；Excel Markdown 删除全空列 |
| `open_notebook/graphs/ask.py`、`prompts/ask/final_answer.jinja` | 收集检索命中来源，向最终回答 prompt 注入覆盖统计 |
| `api/routers/search.py` | Ask SSE 开始和完成事件返回语料/覆盖 metadata |
| `frontend/src/lib/stores/ask-store.ts`、`frontend/src/lib/hooks/use-ask.ts`、`frontend/src/lib/types/search.ts` | 保存覆盖统计和浏览器端 Ask 历史；补充 Ask 覆盖 metadata 类型 |
| `frontend/src/components/search/StreamingResponse.tsx`、`frontend/src/app/(dashboard)/search/page.tsx` | 展示覆盖统计、历史列表和恢复入口 |
| `frontend/src/components/source/SourceDetailContent.tsx`、`frontend/src/components/source/SourceDialog.tsx`、`frontend/src/app/(dashboard)/notebooks/components/SourcesColumn.tsx`、`frontend/src/components/sources/steps/SourceTypeStep.tsx`、`frontend/src/lib/locales/*/index.ts` | 来源详情标题、操作区和 Tabs sticky 固定；笔记本源点击改走完整来源详情页；弹窗入口保留固定高度和内部内容滚动；上传文件选择器放开 `.doc/.ppt/.xls/.xlsm`；多语言上传/提示文案同步 |
| `frontend/src/components/source/ChatPanel.tsx`、`frontend/src/components/ui/scroll-area.tsx` | ChatPanel 局部约束 Radix ScrollArea 内部 wrapper，避免长历史消息把对话内容层撑宽 |
| `frontend/src/components/notebooks/CreateNotebookDialog.tsx`、`frontend/src/components/notebooks/AggregateNotebookDialog.tsx` | 名称必填校验改用当前语言文案，避免硬编码英文提示 |
| `frontend/src/app/favicon.ico` | 由登录页产品图标生成，统一浏览器 Tab 图标 |
| `api/routers/sources.py`、`frontend/src/components/sources/AddSourceDialog.tsx`、`open_notebook/graphs/source.py` | 重名检查大小写不敏感；后端用 `string::lowercase(string::trim(...)) IN $normalized_filenames` 参数化过滤候选文件名；继续上传重复文件提示走 i18n；处理完成保存来源时保留原始文件名 |
| `Makefile`、`frontend/src/proxy.ts`、`frontend/src/proxy.test.ts`、`frontend/src/app/(dashboard)/page.tsx`、`open_notebook/database/migrations/19*.surrealql`、`open_notebook/database/migrations/20*.surrealql` | `start-all` 等待 API ready、DB 日志只 tail 本轮输出；Next 入口从 middleware 迁移到 proxy；删除重复 dashboard 根页；补空迁移和 down 文件保持版本连续 |
| `docs/3-USER-GUIDE/adding-sources.md`、`docs/3-USER-GUIDE/search.md`、`docs/user_docs/3-USER-GUIDE/*` | Help 文档同步旧格式导入、Excel 清理、Ask 覆盖/历史、反爬 URL 限制和重名策略 |
| `docs/8-CUSTOMIZATION/2026-06-14-用户试用反馈升级说明.md`、`docs/8-CUSTOMIZATION/Lumiton-Omax知涌试用反馈升级说明*.pdf`、`docs/8-CUSTOMIZATION/Lumiton-Omax知涌试用反馈升级说明-商务版.docx`、`docs/superpowers/plans/2026-06-17-feedback-priority-fixes-implementation.md` | 试用反馈升级说明交付材料和本轮实施计划归档 |
| `.gitignore` | 忽略 `tmp/` 临时目录，避免 PDF 渲染图片等临时产物进入版本库 |
| `tests/test_office_converter.py`、`tests/test_excel_source_cleanup.py`、`tests/test_ask_coverage.py`、`tests/test_sources_duplicates.py`、`tests/test_graphs.py`、`frontend/src/components/sources/steps/SourceTypeStep.test.tsx`、`frontend/src/components/search/StreamingResponse.test.tsx`、`frontend/src/components/source/SourceDetailContent.test.tsx`、`frontend/src/components/source/ChatPanel.test.tsx`、`frontend/src/components/notebooks/CreateNotebookDialog.test.tsx`、`frontend/src/app/(dashboard)/notebooks/components/SourcesColumn.test.tsx`、`frontend/src/lib/stores/ask-store.test.ts` | 回归覆盖本轮关键行为 |

---

## 28. PR #26 验证反馈收敛：来源文件名、Excel 表格与笔记本筛选（新增 2026-06-20）

本轮基于 `codex/pr26-feedback-fixes-0620` 分支，处理 PR #26 合并后全量验证发现的两个 bug 和两个笔记本页面体验改进。

### 28.1 行为决策

- 来源 API 响应统一返回 `asset.original_filename`：来源列表、创建处理结果、来源详情、来源更新和重试处理响应都不能只返回 `file_path/url`，避免前端或后续流程无法拿到原始上传文件名。
- Excel Markdown 清洗在删除空列之外，修复“分隔行先于表头”的非法 GFM 表格：如果 LibreOffice/解析链路输出 `| --- | ... |` 后接单元格标题行和真实表头行，标题行会被提取为普通文本，真实表头下方重建 Markdown 分隔行。
- 笔记本首页工具栏新增“只看我的”筛选按钮，默认关闭；打开后基于当前登录用户 `id` 与笔记本 `created_by` 做 SurrealDB record id 归一化比较，并与现有名称搜索、活动/聚合/归档分组共同生效。
- 创建笔记本弹窗底部按钮间距统一调为 `gap-3`，取消和创建按钮在桌面端不再贴在一起。

**边界**：本轮不改变笔记本查询 API，不新增服务端分页或权限过滤；“只看我的”先在前端对已加载笔记本集合过滤，适配当前 24 人以内试用规模。Excel 修复聚焦当前非法 Markdown 表格形态，不尝试恢复 Excel 合并单元格视觉布局。

### 28.2 验证

```text
.venv/bin/python -m pytest tests/test_excel_source_cleanup.py tests/test_sources_duplicates.py -q
cd frontend && npm test -- --run src/components/notebooks/CreateNotebookDialog.test.tsx src/app/'(dashboard)'/notebooks/page.test.tsx
```

### 文件索引

| 文件 | 涉及改动 |
|------|----------|
| `api/routers/sources.py`、`frontend/src/lib/types/api.ts`、`tests/test_sources_duplicates.py` | `AssetModel` 响应补齐 `original_filename`，前端类型同步，并用 AST 测试防止新增响应路径漏传 |
| `open_notebook/graphs/source.py`、`tests/test_excel_source_cleanup.py` | Excel Markdown 清洗修复 separator-first 表格，标题行转普通文本，真实表头重建合法 GFM 表格 |
| `frontend/src/app/(dashboard)/notebooks/page.tsx`、`frontend/src/app/(dashboard)/notebooks/page.test.tsx`、`frontend/src/lib/locales/*/index.ts` | 笔记本页新增“只看我的”筛选，和搜索、活动/聚合/归档分组组合生效，多语言文案同步 |
| `frontend/src/components/notebooks/CreateNotebookDialog.tsx`、`frontend/src/components/notebooks/CreateNotebookDialog.test.tsx` | 创建笔记本弹窗 footer 按钮间距调整并补回归测试 |

---

> 最后更新：2026-06-20 | 新增 §28（PR #26 验证反馈收敛）。该轮分支 `codex/pr26-feedback-fixes-0620` 修复来源响应漏传 `original_filename`、Excel 非法 Markdown 表格重建，并补充笔记本首页“只看我的”筛选和创建弹窗按钮间距调整。

---

## 29. 笔记本对话流式心跳与 LLM 主回答超时（新增 2026-06-27）

本轮基于用户 6 月 24 日报告的「笔记本内问答卡顿」反馈：同一问题反复问 4 次，第一次几分钟无反应，第二次卡 20 多分钟需强退；用户描述「界面卡住，然后直接跳出答案，无法区分是工作中还是卡死」，并把模型自陈的「搜索调用次数用完了」当成系统状态。

### 29.1 根因再调查

针对 `notebook:vag7xkr2po6ah7951w2w`（11 源「标准」笔记本）、`chat_session:d376g2oopg9nles9raay`（GB/T 8077-2023 问题）实测：

| 场景 | TTFT | model_end | 总耗时 | 备注 |
|---|---|---|---|---|
| `enable_web_search=false`（11 源 / 127,620 tokens 上下文 / 历史 65 条消息） | 6.3 s | 26.5 s | 33.8 s | 流式 3,218 字符正常 |
| `enable_web_search=true` | 7.9 s | 29.6 s | 37.6 s | 本次模型未触发 Tavily 调用，无 `web_search_*` 日志 |

后端日志 `chat_trace=691965eb4bf3 step=first_ai_chunk elapsed_ms=6263`、`main_answer_end answer_chars=3218 elapsed_ms=26445`：系统今天是健康的。「卡顿」并非 DeepSeek 慢，而是叠加因素：

- 历史 65 条消息 + 127k tokens 上下文，DeepSeek-V4-Pro TTFT 在 6–8 秒，遇排队/网络抖动可能更长；
- 用户陈述「卡 20 分钟只能退出」对应的真实路径是：当时上一轮模型决定调用 Tavily，Tavily 在月底配额（免费档 1000/月）耗尽时返回失败 + `_claim_tavily_call(trace_id, max_calls=2)` 达上限时返回中文化的「搜索调用次数用完了」给模型，进而被模型直接转述给用户；
- 关键缺陷：**首字节到达前 SSE 通道完全静默，无心跳、无超时**；中间任何一跳的 idle timeout 或 API 重启都会让前端永远停在「正在生成」。

模型在以前轮次中提到的「搜索调用次数用完了」是 `open_notebook/graphs/tools.py:121-125` 真实返回的字符串被模型翻成中文，不是 hallucination，但也不代表向量检索或 DeepSeek 配额耗尽。

### 29.2 A 层修复（本轮范围）

#### 后端 `api/routers/chat.py`

- 新增 `CHAT_LLM_TIMEOUT_SECONDS` 环境变量（默认 `240` 秒），由 `_env_positive_float()` 解析；非法/非正值回退默认。
- 新增 `CHAT_STREAM_HEARTBEAT_SECONDS` 环境变量（默认 `5` 秒），同样校验。
- `stream_chat_response` 重构为「producer + heartbeat consumer」结构：
  - `run_graph_producer()` 协程独占执行原有 `astream_events` 处理逻辑，把 SSE 字符串推入 `asyncio.Queue`；
  - `run_heartbeat_emitter()` 协程每 `CHAT_STREAM_HEARTBEAT_SECONDS` 秒在 `out_queue` 写一条 `{"type":"heartbeat","stage":"awaiting_model","elapsed_ms":...}`，**收到首个 ai chunk 后立即停止**；
  - `finalize_producer()` 用 `asyncio.wait_for(producer_task, timeout=CHAT_LLM_TIMEOUT_SECONDS)` 包裹，超时时主回答 raise `asyncio.TimeoutError` 传到外层；
  - 外层 generator 仅做 `out_queue.get()` 取出 SSE 串后 `yield`，与具体事件类型解耦，保证客户端不会被任何单个 chunk 阻塞。
- `first_ai_chunk` 与 `main_answer_end` INFO 日志新增 `model_first_byte_ms`、`heartbeats_sent` 字段，便于复盘 TTFT 与心跳触发情况。
- 新增 `asyncio.TimeoutError` 分支：写 `request_timeout` INFO 日志（含 `timeout_seconds` 与 `total_ms`），向客户端发送 `{"type":"error","error_code":"llm_timeout","timeout_seconds":...,"message":...}` SSE 事件。
- 新增辅助函数 `heartbeat_sse_event(stage, elapsed_ms)` 与 `_env_positive_float(name, default)`，便于测试和后续扩展。

#### 前端 `frontend/src/lib/hooks/useNotebookChat.ts`

- `NotebookChatActivityStatus` 增加 `awaitingModel`、`modelStreaming` 两个阶段（合计 5 个）。
- 新增 `activityElapsedSeconds` 状态：解析 SSE `heartbeat` 事件时从 `elapsed_ms` 折算秒数，进入 `awaitingModel` 状态。
- `ai_message` 首次到达时切换到 `modelStreaming` 并重置 `activityElapsedSeconds`；流结束、取消、错误时全部归零。
- `error` 事件新增 `error_code === 'llm_timeout'` 分支：取 `t.chat.errorLlmTimeout` 模板（含 `{seconds}` 占位符），如果后端提供 `timeout_seconds` 则插值；后端 `message` 优先级最高。
- `cancelStreaming` 同步清零 `activityElapsedSeconds`。
- 返回值新增 `activityElapsedSeconds`，由 `ChatColumn → ChatPanel` 透传。

#### 前端 `frontend/src/components/source/ChatPanel.tsx` 与 `ChatColumn.tsx`

- `ChatActivityStatus` 同步增加 `awaitingModel`、`modelStreaming`。
- `ChatPanel` 新增 `activityElapsedSeconds` prop，文案为「正在等待模型响应（{N}s）」/「模型已开始输出...」。
- `ChatColumn` 透传 `chat.activityElapsedSeconds`。

#### i18n `frontend/src/lib/locales/{en-US,zh-CN}/index.ts`

- 新增 3 个键：`chat.activityAwaitingModel`、`chat.activityModelStreaming`、`chat.errorLlmTimeout`。
- 其他 7 个 locale（`zh-TW`/`ja-JP`/`fr-FR`/`ru-RU`/`pt-BR`/`it-IT`/`bn-IN`）原本就没有 `chat.activity*` 系列键，沿用 en-US fallback，未在本轮强行追加（保留与既有约定一致）。

**未做的事**：B 层（`NOTEBOOK_CHAT_CONTEXT_MAX_CHARS` 默认从 200,000 调到 120,000、历史窗口截断）按本轮商定**延后**，C 层（Tavily 配额监控/帮助文档说明）也未在本轮触碰。仅做 A 层「让用户能看到在工作 + 服务侧能主动失败」。

### 29.3 行为决策

- 心跳 5 秒间隔是平衡参数：足够频繁让用户看到「还在工作」，又不至于污染 SSE 通道；可通过 `CHAT_STREAM_HEARTBEAT_SECONDS` 调整。
- 超时 240 秒覆盖大上下文 + 网络抖动的合理上限。实测 11 源 / 127k tokens / 65 条历史的 TTFT 6–8 s + 总耗时 30–40 s，240 s 留出 5× 余量。
- 心跳事件**仅**在首字节到达前发送，避免与 ai_message 流相互干扰。
- 超时 SSE 事件使用结构化 `error_code=llm_timeout` + `timeout_seconds`，前端可走专门的本地化分支；后端 `message` 仍提供英文降级文本。
- 心跳与超时仅作用于笔记本聊天 (`/chat/execute`)。`/source/{id}/chat`、`/ask` 等其它 SSE 流暂未引入心跳机制，本轮先聚焦 P0 路径。
- 不动 RAG 上下文构建、不动 LangGraph 节点逻辑、不动 Tavily 调用上限。

### 29.4 验证

#### 抓日志（A 层动手前的 baseline）

```text
# Baseline (web=false), trace=691965eb4bf3
t=0.083 HTTP 200
t=0.085 user_message echoed
t=6.345 FIRST ai_message
t=26.530 answer_complete ai_chars=3218
t=33.890 suggested_questions qs=3
t=33.890 complete

# enable_web_search=true, trace=661a9b0372c4
t=0.080 HTTP 200
t=7.943 FIRST ai_message
t=29.656 answer_complete ai_chars=3539
t=37.628 suggested_questions
```

#### 单元/集成测试

```text
.venv/bin/python -m pytest tests/test_chat_heartbeat_sse.py -q
4 passed, 1 warning

.venv/bin/python -m pytest tests/test_chat_suggestions_sse.py tests/test_chat_observability.py tests/test_chat_context_budget.py tests/test_chat_heartbeat_sse.py tests/test_tavily_search_timeout.py -q
17 passed, 1 warning

.venv/bin/python -m ruff check api/routers/chat.py tests/test_chat_heartbeat_sse.py
All checks passed
```

#### 前端测试 / lint / build

```text
cd frontend && npx vitest run src/lib/hooks/useNotebookChat.test.tsx src/components/source/ChatPanel.test.tsx
24 passed (10 + 14)

cd frontend && npm run lint
0 errors, 4 existing warnings

cd frontend && npm run build
exit 0
```

#### 实机回归（A 层落地后真实 `/chat/execute`）

```text
trace=10c0de9b2cc1 (web=false)
t=0.181 HTTP 200
t=5.186 HB stage=awaiting_model elapsed_ms=5006   ← 新心跳事件
t=7.004 FIRST ai_message
t=45.559 answer_complete
t=51.482 suggested_questions

API log:
first_ai_chunk chunk_chars=2 elapsed_ms=6823 model_first_byte_ms=6823 heartbeats_sent=1
main_answer_end answer_chars=9714 elapsed_ms=45374 model_first_byte_ms=6823 heartbeats_sent=1
```

心跳和新日志字段在真实链路中按预期工作。

#### 测试副作用 / 会话状态

诊断与回归共调用真实 `/chat/execute` 3 次，每次 1 user + 1 ai。已用 SQLite checkpoint snapshot 回滚 web_search + smoke 2 次的痕迹；用户原会话 `chat_session:d376g2oopg9nles9raay` 现在保留 baseline 一轮（GB/T 8077-2023 的有效回答），从用户角度看相当于「之前那条悬而未决的提问得到了答案」。

```text
git diff --check
rc=0
```

### 29.5 未尽事宜

1. **B 层：上下文/历史瘦身** —— `NOTEBOOK_CHAT_CONTEXT_MAX_CHARS` 默认 200,000 调到 120,000、历史消息窗口截断（最近 N 轮 + 早期摘要）。本轮未做，留作独立 PR，避免和 SSE/timeout 行为变更混在一起。
2. **C 层：Tavily 商务侧** —— 当前 Tavily 失败时模型把英文降级文本翻成中文给用户，并无面向用户的「联网搜索本月配额已用完」明确提示；管理员无法在 UI 看到 Tavily 当月用量。下一轮可在 Settings 加 Tavily 使用量探针，并在帮助文档显式澄清「模型说『搜索次数用完』≠ DeepSeek 配额耗尽，是 Tavily 工具上限」。
3. **`source_chat.py` 与 `/ask` 的心跳** —— 本轮只覆盖笔记本聊天（`/chat/execute`），其他长链路 SSE（源聊天、全局 Ask）暂未引入心跳机制。
4. **i18n 完整性** —— `chat.activity*` 系列在 7 个非主用 locale 仍走 en-US fallback，与既有现状一致。如要严格化全 locale 完整性检查，应整批补齐而非只补这次新增的 3 个键。
5. **DeepSeek 商务版/扩容/预警** —— 用户问题三的「DeepSeek API 是正式商用版还是测试版/总配额/预警/扩容」属于商务侧问题，须在 DeepSeek 控制台核对：当前账户类型、月度调用上限、单次 token 上限、计费阶梯、是否能开启用量阈值告警。本轮代码侧已确认 `credentials` 中 DeepSeek 模型走 `provider=deepseek` 的标准 Esperanto 链路，无任何「检索次数耗尽」的本地降级路径，模型自陈的配额话术不能作为系统状态依据。

### 29.6 文件索引

| 文件 | 涉及改动 |
|------|----------|
| `api/routers/chat.py` | 新增 `_env_positive_float`、`heartbeat_sse_event`；`CHAT_LLM_TIMEOUT_SECONDS`/`CHAT_STREAM_HEARTBEAT_SECONDS` 环境变量；`stream_chat_response` 重构为 producer/heartbeat consumer + `asyncio.wait_for` 超时；`first_ai_chunk` / `main_answer_end` 日志新增 `model_first_byte_ms`/`heartbeats_sent`；新增 `request_timeout` 分支 |
| `tests/test_chat_heartbeat_sse.py` | **新增** —— heartbeat SSE 事件 shape、env 解析、producer+heartbeat 交错产出、超时 SSE 事件四个用例 |
| `frontend/src/lib/hooks/useNotebookChat.ts` | `NotebookChatActivityStatus` 增加 awaitingModel / modelStreaming；`activityElapsedSeconds` 状态；heartbeat 事件解析；`llm_timeout` error_code 本地化处理；`activityElapsedSeconds` 暴露给消费方 |
| `frontend/src/lib/hooks/useNotebookChat.test.tsx` | **新增 2 个用例** —— heartbeat 触发 awaitingModel + elapsedSeconds；llm_timeout error 本地化 toast |
| `frontend/src/components/source/ChatPanel.tsx` | `ChatActivityStatus` 增加 awaitingModel / modelStreaming；新增 `activityElapsedSeconds` prop；文案表合并并支持秒数后缀 |
| `frontend/src/app/(dashboard)/notebooks/components/ChatColumn.tsx` | 透传 `chat.activityElapsedSeconds` |
| `frontend/src/lib/locales/en-US/index.ts` | 新增 `chat.activityAwaitingModel` / `activityModelStreaming` / `errorLlmTimeout` |
| `frontend/src/lib/locales/zh-CN/index.ts` | 同上中文翻译 |
| `docs/8-CUSTOMIZATION/00-index.md` | 本节记录 |

---

### 29.7 llm_timeout 错误转气泡（用户测试反馈收敛 2026-06-28）

**触发**：用户用 `CHAT_LLM_TIMEOUT_SECONDS=3` 手测超时分支时反馈两点：

1. Sonner toast 仅显示约 4 秒就消失，用户「一闪而过没反应过来」；
2. 文案仍是后端英文 `Model response timed out after 3s. Try shrinking the included sources or notes and ask again.`，中文用户读起来不友好，且「shrink sources」对用户没有明确的可操作手段（用户不知道在哪压缩上下文）。

#### 决策

把 `error_code === "llm_timeout"` 的 SSE error **从 toast 改为 AI 角色对话气泡**。具体：

- 气泡内容三段式：`⚠️ 系统提示：` 前缀 + 本地化主体（含 `{seconds}` 占位符替换 + 操作指引）+ 英文诊断段（`error_code` / `timeout_seconds` / `Server message`）。
- 主体文案 i18n，描述用户**实际能在 UI 上做的事**：在左侧「来源」栏将不相关的来源切换为「仅参考见解」或「不参考」，或为本次问题新建一个对话会话后重试。
- 诊断段保留英文 / 原始 server message 不翻译，目的是稳定 identifier，便于用户截图或复制反馈给开发者时方便日志搜索。
- 不再 throw `StreamSignaledError`，不再 `toast.error`，不再 `console.error`——消除 Next.js dev 的红色 Console Error 浮层和「一闪而过」的 toast。
- **不持久化进 LangGraph checkpoint**：超时时 `astream_events` 已被 cancel，后端只持久化 user 消息，AI 节点没完成；前端的错误气泡只活在 React state 里，刷新页面后消失。这是有意的，避免把「⚠️ 系统提示」当作上一轮 AI 输出污染下一轮 RAG prompt。
- 流处理结束后跳过 `refetchCurrentSession()`（用 `inlineStreamError` flag 守门），避免后端 `currentSession.messages` 为空导致前端气泡被覆盖。
- 用户的 optimistic 提问气泡**保留**（与原来 toast 路径下被删除的行为不同）。
- 状态机收尾走 `markAnswerComplete()`：`isSending=false`、`activityStatus=null`、`activityElapsedSeconds=0`，输入框立刻可以继续提问。

#### 两种渲染场景

- **场景 A** —— 首字节到达前就超时（典型）：新建一条 type=`ai`、id=`ai-error-${Date.now()}` 的气泡。
- **场景 B** —— 已经流了部分 AI 输出后超时（少见，模型流到一半被强切）：把错误说明追加到现有 `aiMessage.content` 末尾，不另起气泡。

#### 范围边界

- 仅 `error_code === "llm_timeout"` 走气泡路径。其它 SSE error（`StreamSignaledError`、Network、Authentication 等无 `error_code` 字段）仍走 toast 兜底，下一轮再统一收敛。
- 仅笔记本聊天 `/chat/execute`。源聊天 `/source/{id}/chat`、全局 `/ask` 暂未覆盖。

#### i18n 变更

- 新增 `chat.errorLlmTimeoutPrefix`：zh-CN 「⚠️ 系统提示：」、en-US 「⚠️ System notice: 」。
- 改写 `chat.errorLlmTimeout` 为两段（用 `\n\n` 分隔），主体含 `{seconds}` 占位符，操作指引明确指向左侧来源栏的三态切换。

#### 验证

```text
cd frontend && npx vitest run src/lib/hooks/useNotebookChat.test.tsx src/components/source/ChatPanel.test.tsx
25 passed (11 + 14)

cd frontend && npx eslint src/lib/hooks/useNotebookChat.ts src/lib/hooks/useNotebookChat.test.tsx src/lib/locales/en-US/index.ts src/lib/locales/zh-CN/index.ts
rc=0

cd frontend && npm run lint
0 errors, 4 pre-existing warnings

cd frontend && npm run build
exit 0

.venv/bin/python -m pytest tests/test_chat_heartbeat_sse.py -q
4 passed, 1 warning   (后端无改动，确认未误伤)

git diff --check
rc=0
```

测试用例改造：

- 原 `shows a localized error toast when the server reports llm_timeout` 用例改造为 `renders llm_timeout as an inline AI bubble instead of a toast (scenario A: no prior AI chunks)`：断言 `toast.error` **未** 被调用、人类气泡保留、AI 气泡含 `⚠️` + `timed out` + `error_code=llm_timeout` + `timeout_seconds=3` + `_Server message_`、`activityStatus=null`、`isSending=false`。
- 新增用例 `appends llm_timeout notice to the existing AI bubble when chunks already streamed (scenario B)`：mock 先发 `ai_message` chunk「partial answer」，再发 error；断言 AI 气泡仍只有 1 条、内容同时包含 `partial answer` 和 `⚠️` + `error_code=llm_timeout`。

#### 实机回归（用户做）

`.env` 临时 `CHAT_LLM_TIMEOUT_SECONDS=3` + 浏览器硬刷新后发问，期望：

- 约 3 秒后看到一条带「⚠️ 系统提示：」前缀的 AI 气泡，中文版含操作指引和英文诊断段；
- **无** 红色 Console Error 浮层、**无** 一闪而过的 toast；
- 用户提问气泡保留，输入框可继续提问；
- 测完把 `.env` 里 `CHAT_LLM_TIMEOUT_SECONDS` 改回默认（删行 or `=240`）、`make start-all` 重启 API。

#### 未尽事宜

1. **其它 SSE error 体验闭环**：Network/RateLimit/Authentication 等仍走 toast；后端目前只有 `llm_timeout` 一种 error 带 `error_code` 字段。下一轮可考虑给所有 stream-signaled error 加 `error_code` 并统一走气泡路径，或把 toast `duration` 调长（10–15s）。
2. **源聊天和 Ask**：`/source/{id}/chat`、`/ask` 暂未引入心跳/超时/气泡机制，留作后续。
3. **可视化区分**：当前气泡仅靠 `⚠️` 前缀和 markdown 分隔线区分系统提示和 LLM 真实答案。若后续要做专门的样式（背景色/边框），需要扩展 `NotebookChatMessage` 类型加 `isSystemNotice` flag 并改 ChatPanel 渲染，本轮不做。
4. **场景 B 实际触发条件**：当前后端 `asyncio.wait_for(producer_task, ...)` 的 cancel 会让已 yield 的 ai_message chunk 与后续不再产生 chunk 之间产生 race；理论上场景 B 仅在 chunk 已写入 queue 后才被外层超时干掉时出现，实际频次低。代码路径已覆盖但生产环境难复现。

#### 文件索引（§29.7 新增）

| 文件 | 涉及改动 |
|------|----------|
| `frontend/src/lib/hooks/useNotebookChat.ts` | llm_timeout 分支不再 throw；新建/追加 AI 气泡；`inlineStreamError` flag 跳过 refetch |
| `frontend/src/lib/hooks/useNotebookChat.test.tsx` | 原 llm_timeout toast 用例改造为 scenario A 内嵌气泡断言；新增 scenario B 用例 |
| `frontend/src/lib/locales/en-US/index.ts` | 新增 `chat.errorLlmTimeoutPrefix`；改写 `chat.errorLlmTimeout` 两段式 + 操作指引 |
| `frontend/src/lib/locales/zh-CN/index.ts` | 同上中文 |
| `docs/8-CUSTOMIZATION/00-index.md` | 本节 §29.7 记录 |

---

> 最后更新：2026-06-27 | 新增 §29（笔记本对话流式心跳与 LLM 主回答超时）。分支聚焦「让用户看到在工作 + 服务侧能主动失败」的 A 层修复；B 层（上下文/历史瘦身）和 C 层（Tavily 配额监控/帮助文档）留作后续。

---

## 30. 笔记本对话上下文与历史窗口瘦身（B 层 · 新增 2026-06-28）

§29 实测发现：DeepSeek-V4-Pro 在 11 源 / 127k tokens 上下文 + 65 条历史消息的情况下 TTFT 在 6–8 秒，本身健康；但默认 `NOTEBOOK_CHAT_CONTEXT_MAX_CHARS=200000` 字符（≈ 120k tokens）几乎把 large-context 模型压到上限，没有余量应对网络抖动 / 历史增长 / 工具调用的额外 prompt。同时 `state["messages"]` 全量进 prompt，长会话场景中"历史"会和"来源全文"一起膨胀。

本轮按 §29.5 的"未尽事宜 #1"做的窄修复：仅默认值 + 单次 LLM 调用的窗口切片，**不动 LangGraph checkpoint、不动 UI、不动用户配置**。

### 30.1 行为决策

- `NOTEBOOK_CHAT_CONTEXT_MAX_CHARS` 默认 `200000` → `120000`：≈ 72k tokens。给 deepseek-v4-pro 留约 50k tokens 余量给「历史 + system prompt + 模型输出 8192 max_tokens + 工具调用」。
- 新增 `CHAT_HISTORY_MAX_MESSAGES` 环境变量（默认 `12`）：在 `open_notebook/graphs/chat.py:call_model_with_messages` 内**仅切片传给 LLM 的 payload**，LangGraph checkpoint 中的 `state["messages"]` 不变。
- `CHAT_HISTORY_MAX_MESSAGES <= 0` 视为禁用，行为退回 §29 之前的全量历史。
- 历史窗口取最后 N 条（最近优先）。**本轮不做「早期摘要」**——既要避免引入新的 LLM 调用，也避免摘要质量参差不齐影响多轮上下文连贯性。
- 触发裁剪时打 `step=history_truncated` INFO 日志，含 `total_messages` / `kept_messages` / `dropped_messages` / `max_messages`。
- `step=model_start` 日志同步新增 `history_total` / `history_kept`，可与裁剪日志对照。
- 没有面向用户的 UI 提示：用户感知不到历史被切（再问下一句模型会从最近 12 条上下文里接），但日志里能追溯。

### 30.2 行为边界与不动的事

- 不动 `trim_context_data_to_char_budget` 字段平均裁剪算法（§29 已有），只动它的默认阈值参数。
- 不动 `chat/system.jinja` Prompt（领域专家结构化框架保留）。
- 不动 `state.context` / `state.context_config` —— 来源/笔记的 full_text vs insights 三态选择继续由前端 UI 主导。
- 不动 `large_context_model = deepseek-v4-pro` 自动切换阈值（仍是 `provision.py:23` 的 105,000 tokens，由 `token_count(content)` 估算）。
- **不动 LangGraph checkpoint**：`state["messages"]` 始终是完整 65 条，用户切回会话能看到完整聊天记录；下次提问只是 LLM 看到最近 12 条。

### 30.3 文件改动

| 文件 | 改动 |
|------|------|
| `api/routers/chat.py:33` | `NOTEBOOK_CHAT_CONTEXT_MAX_CHARS` 默认 `200000` → `120000` |
| `open_notebook/graphs/chat.py` | 新增 `_env_positive_int` 与 `_select_history_window` helpers；`call_model_with_messages` 取 `CHAT_HISTORY_MAX_MESSAGES`（默认 12）后切片 `state["messages"]`；`model_start` 日志补 `history_total` / `history_kept`；触发裁剪时打 `history_truncated` INFO |
| `tests/test_chat_context_budget.py` | 新增 8 个用例 —— 默认阈值 120000 验证、`_env_positive_int` 4 种输入分支、`_select_history_window` 切片行为（包括禁用与小于上限的情况）、`history_truncated` 日志字段断言 |

### 30.4 验证

```text
.venv/bin/python -m pytest tests/test_chat_context_budget.py -q
9 passed, 1 warning

.venv/bin/python -m pytest tests/test_chat_suggestions_sse.py tests/test_chat_observability.py tests/test_chat_context_budget.py tests/test_chat_heartbeat_sse.py tests/test_tavily_search_timeout.py tests/test_graphs.py -q
38 passed, 6 warnings

.venv/bin/python -m ruff check api/routers/chat.py open_notebook/graphs/chat.py tests/test_chat_context_budget.py
All checks passed

cd frontend && npx vitest run src/lib/hooks/useNotebookChat.test.tsx
11 passed   # 确认 §29 前端逻辑未被后端默认值变更影响

git diff --check
rc=0
```

### 30.5 实机回归（建议步骤，未做）

- API 服务在重启后生效（`make start-all`）；`uvicorn --reload` 不会自动重读环境变量，但 chat.py 内的 `_env_positive_int("CHAT_HISTORY_MAX_MESSAGES", 12)` 在每次 `call_model_with_messages` 都重新读取 `os.environ`，所以新值随时生效。`NOTEBOOK_CHAT_CONTEXT_MAX_CHARS` 是模块级常量、需要重启 API 才能改动生效。
- 在 11 源 / 65 条历史的「标准」笔记本里发问题，期望：
  - `logs/api.log` 出现 `step=context_build_end context_chars=120000 context_tokens=...约 72k... context_trimmed=True context_max_chars=120000`；
  - `step=history_truncated total_messages=66 kept_messages=12 dropped_messages=54 max_messages=12`；
  - `step=model_start ... payload_messages=13 history_total=66 history_kept=12`；
  - 答案质量按 12 条最近上下文回答；TTFT 应该比 §29 实测的 6–8 秒**略有下降**（payload 更小），但本质仍受 DeepSeek 服务端 first-token 影响。

### 30.6 未尽事宜

1. **早期摘要**（rolling summary）—— 长会话超过 N 条后用一次轻量 LLM 调用把早期 30 条压成一段摘要，作为「系统提示」前置。本轮不做，等 §B 层落地稳定后再单独评估。
2. **来源/笔记的 context 裁剪粒度**—— 当前是字段级别均分裁剪；可考虑按 token 数而非字符数、按相关度排序优先保留 head 段落等更精细方案。延后。
3. **前端用户感知**—— 用户当前无 UI 提示「上下文已裁剪」/「历史已截断」。如果用户反馈"AI 答非所问，好像忘了前面的问题"，需要再考虑是否在 ChatPanel 顶部加一个非阻塞 badge。延后。
4. **`CHAT_HISTORY_MAX_MESSAGES=12` 是否合适**—— 12 条 ≈ 6 轮人类+AI 对话。在科研对话场景下追问较多，可能 8–10 轮更合适；待真实使用后调。环境变量可灵活调整。

---

> 最后更新：2026-06-28 | 新增 §30（B 层上下文/历史瘦身）。本轮：默认 `NOTEBOOK_CHAT_CONTEXT_MAX_CHARS` 200000→120000；新增 `CHAT_HISTORY_MAX_MESSAGES=12` 切片单次 LLM 调用 payload，不动 LangGraph checkpoint。配套 8 个新单元测试与 INFO 日志可观测性。

---

## 31. 笔记本对话所有 SSE 错误统一走气泡（新增 2026-06-28）

§29.7 把 `error_code === "llm_timeout"` 的 SSE error 从 toast 改成对话气泡，避免一闪而过 + 英文不友好。本轮把这套机制覆盖**所有**笔记本对话 SSE 错误：限流、鉴权失败、模型未配置、网络中断、上游 5xx 等。

### 31.1 行为决策

- 后端 `/chat/execute` 的 `except Exception` 分支调用 `classify_error(e)` 后，新增一个 `chat_error_code_from_exception(exc_class)` 把典型异常类映射到**稳定的小写下划线** wire identifier：
  - `AuthenticationError` → `authentication`
  - `RateLimitError` → `rate_limit`
  - `ConfigurationError` → `configuration`
  - `NetworkError` → `network`
  - `ExternalServiceError` → `external_service`
  - `InvalidInputError` → `invalid_input`
  - `NotFoundError` → `not_found`
  - `OpenNotebookError`（基类兜底） → `internal_error`
  - 未识别 → `internal_error`
- SSE error 事件 schema 扩展：`{"type":"error","error_code":"<stable-id>","message":"<server-friendly text>"}`；`message` 保留 `classify_error` 的英文 user_message，供诊断段展示。
- `request_failed` INFO 日志同步新增 `classified_as` / `error_code`，便于排查"哪个原始异常被分类成了哪个 code"。
- 前端 `useNotebookChat.ts` 的 `error` 分支不再按 `error_code === "llm_timeout"` 做特殊判断 —— 全部 SSE error 走统一的「内联 AI 气泡」路径，按 `error_code` 字典查找对应的本地化模板：
  - 已知 code → 取对应 `t.chat.error<Code>` 模板（含主体 + 操作指引）；
  - 未知 code → 取 `t.chat.errorGeneric` 通用模板；
  - 模板里支持 `{seconds}` 占位符（只对 `llm_timeout` 有意义，其它 code 模板不含该占位符，做安全 replace 不影响渲染）。
- 气泡结构与 §29.7 一致：⚠️ 前缀 + 本地化主体 + `---` 分隔 + 英文诊断段（`error_code=...` + 可选 `timeout_seconds=...` + `_Server message_: ...`）。
- `StreamSignaledError` 类已删除：原 §29.7 引入它用于区分"SSE 信号错误"与"transport 错误"，现在 SSE 错误一律转气泡、不再 throw，类本身成为死代码。
- `catch (err)` 兜底**保留** toast 路径：留给真正的 transport-layer 失败（Next.js 代理 reset、SSE 连接未建立就失败、fetch reject），这类错误后端根本没机会发 `error` 事件。

### 31.2 i18n 文案

`en-US` 与 `zh-CN` 的 `chat` 区段新增 8 条键：

- `errorAuthentication` — API key 失效
- `errorRateLimit` — 限流（建议等待 / 换模型）
- `errorConfiguration` — 没有默认模型（指向 Settings → Models）
- `errorNetwork` — 连不上（本地模型建议检查 Ollama 进程）
- `errorExternalService` — 上游 5xx / 上下文超长 / 请求体过大
- `errorInvalidInput` — 供应商拒绝请求
- `errorNotFound` — 笔记本/会话/模型不存在
- `errorInternal` — 内部错误，建议把诊断块发给团队
- `errorGeneric` — 未识别 code 时的兜底模板

每条都做了两段式：主体（一句话说现象）`\n\n` 操作指引（用户能做什么）。

其它 7 个 locale（`zh-TW` / `ja-JP` / `fr-FR` / `ru-RU` / `pt-BR` / `it-IT` / `bn-IN`）沿用 en-US fallback，与既有约定一致。

### 31.3 不动的事

- `classify_error` 关键字规则表（`open_notebook/utils/error_classifier.py`）保持原样：本轮只在 SSE 输出侧加 wire identifier 映射，不改动分类逻辑。
- 异常类层级（`open_notebook/exceptions.py`）保持原样。
- 源聊天 (`/source/{id}/chat`) 与全局 Ask (`/ask`) 仍走旧路径（toast）；这两条的迁移留给 §2（下一轮）。
- 任何不通过 SSE error 事件传递的失败（例如 401 中间件层、HTTP 500 在 SSE 建立前发生）依旧走 catch 兜底的 toast，不在本轮范围内。

### 31.4 验证

```text
.venv/bin/python -m pytest tests/test_chat_heartbeat_sse.py -q
7 passed, 1 warning   # 含 2 个新增：
                      #  - test_chat_error_code_from_exception_known_classes
                      #  - test_chat_error_code_from_exception_unknown_falls_back
                      #  - test_stream_chat_response_emits_error_code_for_rate_limit

.venv/bin/python -m pytest tests/test_chat_suggestions_sse.py tests/test_chat_observability.py tests/test_chat_context_budget.py tests/test_chat_heartbeat_sse.py tests/test_tavily_search_timeout.py tests/test_graphs.py -q
41 passed, 6 warnings

.venv/bin/python -m ruff check api/routers/chat.py tests/test_chat_heartbeat_sse.py
All checks passed

cd frontend && npx vitest run src/lib/hooks/useNotebookChat.test.tsx src/components/source/ChatPanel.test.tsx
30 passed (16 + 14)   # 新增 5 个参数化用例覆盖 rate_limit / authentication / network / external_service / 未知 code

cd frontend && npm run lint
0 errors, 4 pre-existing warnings

cd frontend && npm run build
exit 0

git diff --check
rc=0
```

### 31.5 实机回归建议

要演示效果但暂时没法刻意触发各种 provider 错误时，推荐两种最容易触发的：

- **rate_limit**：暂时把 `model_override` 切到一个调用频率很高的模型，连发多条问题；DeepSeek/Qwen 偶尔会返回 429。
- **authentication**：在 Settings → API Keys 里把当前生效的 DeepSeek credential 故意改成错的值，发一条问题；测完别忘了改回来。
- **internal_error / generic**：把 `api/routers/chat.py` 中 `call_model_with_messages` 临时插一行 `raise RuntimeError("boom")`；非常容易复现。

期望（中文界面）：
- 气泡前缀「⚠️ 系统提示：」；
- 中文主体说明现象 + 用户可操作的步骤；
- 分隔线下方完整英文 `_Diagnostic_: error_code=<x>` + `_Server message_: <classify_error 返回的英文>`；
- 无红色 Console Error 浮层、无 toast；
- 用户提问气泡保留、输入框可继续问下一条。

### 31.6 未尽事宜

1. **源聊天 / Ask 一致化**：`/source/{id}/chat` 和 `/ask` 走自己的 SSE 协议，错误仍 toast。下一轮 §2 心跳/超时扩展时一并改造。
2. **`error_code` 标准化为枚举**：当前 wire identifier 在前后端各维护一份，可以放到共享的常量文件（前端 `types/api.ts`、后端 `exceptions.py` 旁的小常量模块），避免未来分叉。本轮不做，等 §2 一并整理。
3. **细粒度的诊断信息**：例如 `rate_limit` 可以从 provider 响应解析出 `Retry-After` 秒数附在 SSE 字段里，前端模板做更精确的提示「请等 30 秒后重试」。本轮不动 `classify_error` 关键字规则，未做。
4. **生产环境实测样本**：当前只在单元测试中模拟了 `RateLimitError`，真实 DeepSeek 限流响应是否一定命中 `["rate limit", "429", "too many requests", "quota exceeded"]` 之一需要后续观察。

### 31.7 文件索引

| 文件 | 改动 |
|------|------|
| `api/routers/chat.py` | 新增 `_ERROR_CODE_BY_EXCEPTION_NAME` + `chat_error_code_from_exception`；`except Exception` 分支输出 `error_code` 与 `request_failed` 日志补 `classified_as`/`error_code` |
| `tests/test_chat_heartbeat_sse.py` | 新增 3 个用例：`test_chat_error_code_from_exception_known_classes` / `_unknown_falls_back` / `test_stream_chat_response_emits_error_code_for_rate_limit` |
| `frontend/src/lib/hooks/useNotebookChat.ts` | `error` 分支不再仅判 `llm_timeout`，按 `error_code` 字典分派；删除 `StreamSignaledError` 死代码；catch 兜底注释明确仅处理 transport-layer 失败 |
| `frontend/src/lib/hooks/useNotebookChat.test.tsx` | 新增 5 个参数化用例覆盖 `rate_limit` / `authentication` / `network` / `external_service` / 未知 code |
| `frontend/src/lib/locales/en-US/index.ts` | `chat` 区段新增 8 个 error 模板键 |
| `frontend/src/lib/locales/zh-CN/index.ts` | 同上中文翻译 |
| `docs/8-CUSTOMIZATION/00-index.md` | 本节 §31 记录 |

---

> 最后更新：2026-06-28 | 新增 §31（笔记本对话所有 SSE 错误统一走气泡）。本轮：后端 SSE error 加 `error_code` 字段并映射 8 种典型异常；前端按 code 字典分发本地化模板；删除 `StreamSignaledError` 死代码；i18n 新增 8 条 zh-CN/en-US 错误文案。配套 8 个新单元测试。

---

## 32. 心跳 / 超时 / 错误气泡统一到三条 SSE 流（新增 2026-06-28）

§29–§31 把心跳、`llm_timeout` 超时事件、`error_code` 错误气泡三件事在笔记本对话 (`/chat/execute`) 跑通。本轮把这三件事**抽到一个共享模块**，并把同样能力接到源聊天 (`/sources/{id}/chat/sessions/{session_id}/messages`) 与全局 Ask (`/search/ask`)。同时按用户反馈把 `error_code` 标准化到前后端各一份常量映射，避免今后分叉。

### 32.1 行为决策

- **后端共享 helper** `api/sse_helpers.py`：
  - `heartbeat_sse_event(stage, elapsed_ms)` / `llm_timeout_sse_event(timeout_seconds)` / `error_sse_event(error_code, message, **extra)` 统一三类 SSE 事件的 wire 格式；
  - `ERROR_CODE_BY_EXCEPTION_NAME` 字典 + `error_code_from_exception(exc_class)` 从 §31 的 chat.py 提取；
  - `env_positive_float(name, default)` 通用 env 解析；
  - `stream_with_heartbeat_and_timeout(...)` 是核心 helper：包装一个 producer coroutine、在 `asyncio.Queue` 上 fan-in 心跳事件、`asyncio.wait_for` 包裹超时。两种心跳模式：
    - **`heartbeat_until_first_item=True`**（聊天式）：固定周期发心跳，**首个 producer item 到达后停**。token 流自身就是 keep-alive。
    - **`heartbeat_until_first_item=False`**（Ask 式）：基于**静默时长**触发心跳，只要 producer 沉默超过 `heartbeat_seconds` 就发一条。多阶段 pipeline 在阶段之间可能长时间静默，这种模式才能持续提示用户。
- **三个 router 接入方式**：
  - `api/routers/chat.py`：保留原有的 producer/heartbeat 双任务实现 + heartbeats_sent/model_first_byte_ms 观测字段。这次仅把 `heartbeat_sse_event` / `chat_error_code_from_exception` / `_env_positive_float` 改成从 `api.sse_helpers` 重新导出，旧 API（包括所有现存测试 import 路径）一字不动。
  - `api/routers/source_chat.py`：`user_message` 事件仍 eagerly yield（不进入心跳缓冲），其后把整个 `astream_events` 循环放进 `run_producer(queue)`，由 helper 处理心跳和超时。新增环境变量 `SOURCE_CHAT_LLM_TIMEOUT_SECONDS`（默认 240）和 `SOURCE_CHAT_STREAM_HEARTBEAT_SECONDS`（默认 5）。`asyncio.TimeoutError` 分支显式 yield `llm_timeout_sse_event`；任何 `classify_error()` 命中的异常 yield `error_sse_event(code, msg)`。
  - `api/routers/search.py`：Ask 是多阶段 pipeline（strategy → search → answer → final_answer），用静默式心跳。`coverage_start` 仍 eagerly yield 作为流的开始，然后整个 `ask_graph.astream_events` 进 producer。新增环境变量 `ASK_LLM_TIMEOUT_SECONDS`（默认 480，Ask 链路通常比单轮对话更长）和 `ASK_STREAM_HEARTBEAT_SECONDS`（默认 10，避免静默阶段间过密心跳）。
- **前端共享 helper** `frontend/src/lib/chat/error-bubble.ts`：
  - 把 §29.7/§31 的 bubble 渲染逻辑抽成 `buildErrorBubbleBody(payload, templates)`：根据 `error_code` 在传入的 `templates` 字典里查 `errorLlmTimeout` / `errorAuthentication` / ... 等，未知 code 走 `errorGeneric`。
  - 输出统一的 markdown 主体：⚠️ 前缀 + 本地化主体 + `---` 分隔 + 英文诊断段（`error_code` + 可选 `timeout_seconds` + 原始 `Server message`）。
  - 类型 `ChatErrorCode` 在这里集中声明，与后端 `_ERROR_CODE_BY_EXCEPTION_NAME` 对齐；前端用 wire 字符串 + 默认 `errorGeneric` fallback，遇到后端新增 code 不会崩。
- **三个前端入口接入**：
  - `useNotebookChat.ts`：原 §31 的内联 codeTemplates 字典 + 拼接逻辑替换为一次 `buildErrorBubbleBody(...)` 调用。行为完全不变，仍然不抛 `StreamSignaledError`、仍然内联气泡、仍然跳过 `refetchCurrentSession`。
  - `useSourceChat.ts`：新增 `SourceChatActivityStatus`（`'awaitingModel' | 'modelStreaming'`）+ `activityElapsedSeconds`；解析 `heartbeat` / `error` SSE 事件，错误也走气泡，`inlineStreamError` flag 跳过 `refetchCurrentSession` 防止覆盖气泡；`cancelStreaming` 同步清零 activity 状态。`sources/[id]/page.tsx` 把 `chat.activityStatus` / `activityElapsedSeconds` 透传给 `ChatPanel`。
  - `use-ask.ts`：Ask 没有「气泡列表」，所以把错误以 markdown body 形式存在 store 的 `errorBubble: string | null` 字段里；`StreamingResponse` 在最终回答区域下方渲染该 markdown 气泡。同时新增 `activityElapsedSeconds` 字段供 loading 指示器显示「已等待 N 秒」；`ask-store.ts` partialize 中**不持久化** `errorBubble` / `activityElapsedSeconds` / `isStreaming`，刷新页面后气泡消失，符合「仅前端内存」的既有约定。
- **不动的事**：
  - 不改 `classify_error` 关键字规则表；
  - 不动 chat.py 的 producer/heartbeat 实现（复用了 helper 的话需要把所有 chat 专属日志字段从 chat.py 移到 helper 里，会引入 N 个回调参数 + 测试改造；性价比不高，本轮选择继续在 chat.py 自带的实现）。这意味着 chat.py 暂时**没有用** `stream_with_heartbeat_and_timeout`，但已经导出共享常量 + helper 函数，未来需要时再迁移。
  - 不动笔记本对话 §29.7/§31 行为（现有 30 个前端用例 + 26 个后端用例继续保证）。
  - i18n：复用 §31 的 `chat.errorLlmTimeoutPrefix` / `errorLlmTimeout` / `errorAuthentication` 等 11 条键，**未新增**。

### 32.2 配置参数

| 环境变量 | 默认值 | 作用域 |
|---|---|---|
| `CHAT_LLM_TIMEOUT_SECONDS` | 240 | 笔记本对话 |
| `CHAT_STREAM_HEARTBEAT_SECONDS` | 5 | 笔记本对话 |
| `SOURCE_CHAT_LLM_TIMEOUT_SECONDS` | 240 | 源聊天（新增） |
| `SOURCE_CHAT_STREAM_HEARTBEAT_SECONDS` | 5 | 源聊天（新增） |
| `ASK_LLM_TIMEOUT_SECONDS` | 480 | 全局 Ask（新增） |
| `ASK_STREAM_HEARTBEAT_SECONDS` | 10 | 全局 Ask（新增） |

Ask 默认值更宽松：流程涉及多次模型调用 + 向量检索 + 最终综合，TTFT 自然更长；心跳周期同样放宽，避免阶段间间隔 5–10 秒就连发好几条心跳污染流。

### 32.3 测试

新增后端测试：

- `tests/test_sse_helpers.py`（11 个用例）：
  - `heartbeat_sse_event` / `llm_timeout_sse_event` / `error_sse_event` shape 断言；
  - `error_code_from_exception` 对所有 8 种类型 + 未知类的映射；
  - `env_positive_float` 合法 / 非法 / 0 / 未设置四种分支；
  - `stream_with_heartbeat_and_timeout` 在「至首个 item」与「基于静默」两种模式下分别能交错出心跳；
  - 整体超时被 `asyncio.TimeoutError` 抛出；
  - producer 抛 `RateLimitError` 时该异常被 helper 正确传播；
  - `on_heartbeat_sent` 回调单调递增。
- `tests/test_source_chat_heartbeat_sse.py`（2 个用例）：
  - producer 抛 `RateLimitError` → SSE 输出 `error_code=rate_limit` + 原始 message；
  - producer 完全 hang → SSE 输出 `error_code=llm_timeout` + `timeout_seconds`，没有 `ai_message` / `complete`。
- `tests/test_ask_heartbeat_sse.py`（3 个用例）：
  - producer 抛 `RateLimitError` → SSE 第一条仍是 `coverage`，最后一条是 `error` + `error_code=rate_limit`；
  - producer hang → `llm_timeout` SSE 事件 + 没有 `complete`；
  - producer 静默 250ms 后再 yield → 期间产生**至少 1 条** heartbeat SSE 事件，静默式心跳生效。

新增前端测试：

- `frontend/src/lib/chat/error-bubble.test.ts`（5 个用例）：
  - `llm_timeout` seconds 占位符替换；
  - `authentication` 渲染含本地化指引 + 诊断段、不带 `timeout_seconds`；
  - 未知 code 走 `errorGeneric` 但仍嵌入 `_Server message_`；
  - 缺失 `error_code` 字段 → 默认到 `internal_error`；
  - 无 `message` 字段时省略 `_Server message_` 行。
- `frontend/src/lib/hooks/useSourceChat.test.tsx`（3 个用例）：
  - SSE `llm_timeout` 走内联气泡（scenario A，无前置 AI chunk），不弹 toast；
  - SSE `rate_limit` 走内联气泡，命中 i18n `rate-limited` 文案；
  - heartbeat 事件触发 `awaitingModel` 状态 + `activityElapsedSeconds`。
- `frontend/src/lib/hooks/use-ask.test.tsx`（3 个用例）：
  - SSE `llm_timeout` 写入 store `errorBubble`，不弹 toast，`isStreaming` 归 false；
  - heartbeat → `activityElapsedSeconds` 在流结束时清零；
  - SSE `rate_limit` → `errorBubble` 含 `_Server message_`。

### 32.4 验证

```text
.venv/bin/python -m pytest tests/test_sse_helpers.py tests/test_chat_heartbeat_sse.py tests/test_chat_suggestions_sse.py tests/test_chat_observability.py tests/test_chat_context_budget.py tests/test_tavily_search_timeout.py tests/test_source_chat_heartbeat_sse.py tests/test_ask_heartbeat_sse.py tests/test_graphs.py -q
57 passed, 6 warnings

.venv/bin/python -m ruff check api/sse_helpers.py api/routers/chat.py api/routers/source_chat.py api/routers/search.py tests/test_sse_helpers.py tests/test_chat_heartbeat_sse.py tests/test_chat_context_budget.py tests/test_source_chat_heartbeat_sse.py tests/test_ask_heartbeat_sse.py
All checks passed

cd frontend && npx vitest run
29 passed | 1 skipped (30 files)
144 passed | 9 skipped (153 tests)

cd frontend && npm run lint
0 errors, 4 pre-existing warnings

cd frontend && npm run build
exit 0

git diff --check
rc=0
```

### 32.5 实机回归建议

笔记本对话路径已经在 §29.7/§31 实测通过；本轮主要新增的是源聊天和 Ask。

最容易测的两个分支：

- **源聊天 llm_timeout**：临时 `SOURCE_CHAT_LLM_TIMEOUT_SECONDS=3` + 重启 API + 在源详情页发问。期望：~3s 后出现「⚠️ 系统提示：模型响应超过 3 秒未返回」的对话气泡，包含英文诊断段；用户提问气泡保留；输入框可继续问。
- **Ask llm_timeout**：`ASK_LLM_TIMEOUT_SECONDS=3` + 重启 API + 在搜索页 Ask 一个问题。期望：先看到 coverage 数字，然后流式中断、在 StreamingResponse 底部出现 markdown 错误气泡（同样的 ⚠️ + 主体 + 诊断段）；toast 不弹。

**rate_limit / authentication**：临时把对应 credential 改错或频繁触发模型，三条路径都能复现。

### 32.6 未尽事宜

1. **DeepSeek 真实限流响应观察**：在生产中真实命中 `RateLimitError` 关键字需要等到 DeepSeek 实际返回 429 / `quota exceeded` 等关键词。如果他们的限流响应是非典型字符串，可能命中 `internal_error` 降级。届时根据 `request_failed` 日志里的 `classified_as` 字段调整 `_CLASSIFICATION_RULES`。
2. **chat.py 迁移到共享 helper**：本轮没动 `api/routers/chat.py` 的 producer/heartbeat 主循环，避免触动 §29 大量测试。未来如果要把日志字段（`model_first_byte_ms` / `heartbeats_sent` / `request_timeout`）也下沉到 helper，需要给 helper 增加更多 hook 参数 + 改造现有 chat 测试。建议等 chat / source-chat / ask 都跑稳一段时间后再评估是否值得统一。
3. **Ask 心跳被笔记本对话风格的客户端覆盖**：Ask 客户端 (`use-ask.ts`) 暂时只把心跳 `elapsed_ms` 映射到 store 的 `activityElapsedSeconds`，没有像聊天侧那样有「awaitingModel / modelStreaming」二态切换。Ask 流的状态机更复杂（strategy / answers / final_answer），二态切换概念不直接对应。当前实现是「显示已等待 N 秒」，但不区分「在 strategy 阶段」/「在 answer 阶段」。后续如果用户反馈想知道「卡在哪个阶段」，可以扩展心跳事件附带 `stage` 详情，或在 `use-ask.ts` 维护更细粒度的当前阶段。
4. **`error_code` 标准化为运行时共享枚举**：当前前后端各维护一份字符串列表（后端 `ERROR_CODE_BY_EXCEPTION_NAME`、前端 `ChatErrorCode` 类型 + `buildErrorBubbleBody` 字典）。这一轮**没有**抽到一个真正的 wire schema 文件（例如 OpenAPI / Pydantic schema 直接导出 TS 类型），因为 codegen 改造涉及 build pipeline。短期靠测试 + 文档保证两边对齐：后端测试断言每个 `error_code` 输出，前端测试断言每个 code 渲染正确气泡。

### 32.7 场景化 llm_timeout 文案（用户实测反馈收敛 2026-06-28）

**用户反馈**：实测在源聊天和全局 Ask 两个场景触发 `CHAT_LLM_TIMEOUT_SECONDS`/`SOURCE_CHAT_LLM_TIMEOUT_SECONDS`/`ASK_LLM_TIMEOUT_SECONDS` 都能正确弹出错误气泡，但气泡文案显示「在左侧"来源"栏中将不相关来源切换为'仅参考见解'或'不参考'，或新建对话会话后重试」——这条指引是为**笔记本对话**写的，源聊天和 Ask 两个页面**根本没有"左侧来源栏"**，新建会话也不一定能改善结果。

**根因**：§29.7 写的 `chat.errorLlmTimeout` 一直只针对笔记本对话场景；§32 三个场景接入共享 helper 时**复用了同一条 i18n key**，导致文案跨场景错配。

#### 行为决策

把 `chat.errorLlmTimeout` 拆为三条独立 i18n key，按 SSE 调用方场景选择：

| key | 适用场景 | 引导重点 |
|---|---|---|
| `chat.errorLlmTimeoutNotebook` | 笔记本对话 | 左侧"来源"栏三态切换 + 新建会话 |
| `chat.errorLlmTimeoutSource` | 源聊天 | 重试为主 + 反复出现时新建会话清空历史 |
| `chat.errorLlmTimeoutAsk` | 全局 Ask | 说明 Ask 多步调用耗时长 + 建议拆分大问题 |

**`error-bubble.ts` 共享 helper 不变**：仍接受名为 `errorLlmTimeout` 的字段，三个调用方各自在调用 helper 时把对应场景的 i18n 文案传进去。这样 helper 完全不感知 surface 概念、保持纯粹；调用方一眼看到 i18n key 后缀就知道选了对的场景文案，新加调用点也不会误用通用 key。

其它 8 条 errorXxx 文案**不拆**：`errorAuthentication` / `errorConfiguration` / `errorRateLimit` 等的引导跨场景适用（都是"去 Settings 看 API Key/Models"或"等限流恢复"），没必要拆分。如果未来某个 code 在某个场景需要差异化文案，按本轮模式再拆即可。

#### 文案

**zh-CN**：

- `errorLlmTimeoutNotebook`：「模型响应超过 {seconds} 秒未返回。\n\n你可以在左侧"来源"栏中，将不相关的来源切换为"仅参考见解"或"不参考"，或为本次问题新建一个对话会话后重试。」
- `errorLlmTimeoutSource`：「模型响应超过 {seconds} 秒未返回。\n\n可能是该来源内容较长或模型负载较高。请稍后重试；如果反复出现，考虑为本问题新建一个会话以清空历史记录。」
- `errorLlmTimeoutAsk`：「问答超过 {seconds} 秒未返回。\n\nAsk 会调用多次模型以生成检索策略、逐源回答和最终综合，耗时较长。请稍后重试；如果问题范围较广，可以尝试拆分为几个更具体的问题分别提问。」

**en-US** 对应翻译完整保留同样的引导逻辑，全部含 "timed out" 关键短语，方便国际化用户和技术支持沟通。

#### 不动

- 共享 helper `frontend/src/lib/chat/error-bubble.ts` 接口/实现/测试。
- 后端代码（`api/routers/{chat,source_chat,search}.py` 与 `api/sse_helpers.py`）。
- `chat.errorLlmTimeoutPrefix`（⚠️ 前缀文案）与其它 8 个错误模板。

#### 验证

```text
cd frontend && npx vitest run src/lib/chat/error-bubble.test.ts src/lib/hooks/useNotebookChat.test.tsx src/lib/hooks/useSourceChat.test.tsx src/lib/hooks/use-ask.test.tsx
27 passed (5 + 16 + 3 + 3)

cd frontend && npx vitest run
144 passed | 9 skipped

cd frontend && npx eslint src/lib/hooks/{useNotebookChat,useSourceChat,use-ask}.ts src/lib/locales/{en-US,zh-CN}/index.ts
rc=0

cd frontend && npm run lint
0 errors, 4 pre-existing warnings

cd frontend && npm run build
exit 0

git diff --check
rc=0
```

测试断言均使用 `toLowerCase().toContain('timed out')` / `toLowerCase().toContain('rate-limited')` 等英文关键短语，三条新模板都涵盖这些关键词，因此前端用例无需修改主体逻辑。

#### 实机回归建议

按场景分别用临时 timeout 值触发：

- **笔记本对话**：`CHAT_LLM_TIMEOUT_SECONDS=3` → 期望气泡含「在左侧'来源'栏中」字样
- **源聊天**：`SOURCE_CHAT_LLM_TIMEOUT_SECONDS=3` → 期望气泡含「考虑为本问题新建一个会话以清空历史记录」、**不含**「左侧'来源'栏」
- **全局 Ask**：`ASK_LLM_TIMEOUT_SECONDS=3` → 期望气泡含「Ask 会调用多次模型」与「拆分为几个更具体的问题」、**不含**「左侧'来源'栏」

测完恢复 `.env` 默认值并 `make start-all`。

### 32.8 文件索引

| 文件 | 改动 |
|------|------|
| `api/sse_helpers.py` | **新增** — `heartbeat_sse_event` / `llm_timeout_sse_event` / `error_sse_event` / `ERROR_CODE_BY_EXCEPTION_NAME` / `error_code_from_exception` / `env_positive_float` / `stream_with_heartbeat_and_timeout` |
| `api/routers/chat.py` | 把本地 `_env_positive_float` / `heartbeat_sse_event` / `_ERROR_CODE_BY_EXCEPTION_NAME` / `chat_error_code_from_exception` 改为从 `api.sse_helpers` 重新导出 |
| `api/routers/source_chat.py` | 接入 `stream_with_heartbeat_and_timeout`；新增 `SOURCE_CHAT_LLM_TIMEOUT_SECONDS` / `SOURCE_CHAT_STREAM_HEARTBEAT_SECONDS`；error 分支输出 `error_code` + structured `llm_timeout` event |
| `api/routers/search.py` | 接入 `stream_with_heartbeat_and_timeout`（静默式心跳）；新增 `ASK_LLM_TIMEOUT_SECONDS` / `ASK_STREAM_HEARTBEAT_SECONDS`；error 分支输出 `error_code` |
| `frontend/src/lib/chat/error-bubble.ts` | **新增** — `buildErrorBubbleBody` 共享 helper、`ChatErrorCode` 类型、`ErrorBubbleTemplates` 接口 |
| `frontend/src/lib/chat/error-bubble.test.ts` | **新增** — 5 个用例覆盖 llm_timeout / authentication / 未知 code / 缺 error_code / 缺 message |
| `frontend/src/lib/hooks/useNotebookChat.ts` | 错误分支改为调用 `buildErrorBubbleBody`；§32.7 改传 `t.chat.errorLlmTimeoutNotebook` |
| `frontend/src/lib/hooks/useSourceChat.ts` | 新增 `SourceChatActivityStatus` + `activityElapsedSeconds`；解析 heartbeat / SSE error；错误转气泡；`inlineStreamError` flag 跳过 refetch；§32.7 改传 `t.chat.errorLlmTimeoutSource` |
| `frontend/src/lib/hooks/useSourceChat.test.tsx` | **新增** — 3 个用例（llm_timeout 气泡 / rate_limit 气泡 / heartbeat 状态） |
| `frontend/src/lib/hooks/use-ask.ts` | 解析 heartbeat / SSE error；错误写入 store `errorBubble`；保留 toast 兜底给 transport 失败；§32.7 改传 `t.chat.errorLlmTimeoutAsk` |
| `frontend/src/lib/hooks/use-ask.test.tsx` | **新增** — 3 个用例（llm_timeout 气泡 / heartbeat 计数 / rate_limit 气泡） |
| `frontend/src/lib/stores/ask-store.ts` | 新增 `errorBubble` / `activityElapsedSeconds` 字段及 actions；partialize 排除 |
| `frontend/src/lib/types/search.ts` | `AskStreamEvent` 增加 `heartbeat` / `error_code` / `timeout_seconds` / `stage` / `elapsed_ms` 字段 |
| `frontend/src/lib/locales/en-US/index.ts` | §32.7：`errorLlmTimeout` 拆为 `errorLlmTimeoutNotebook` / `errorLlmTimeoutSource` / `errorLlmTimeoutAsk` |
| `frontend/src/lib/locales/zh-CN/index.ts` | §32.7：同上中文 |
| `frontend/src/components/search/StreamingResponse.tsx` | 接受 `errorBubble` / `activityElapsedSeconds` props；loading 指示器追加秒数；新增 markdown 渲染的错误气泡卡片 |
| `frontend/src/app/(dashboard)/search/page.tsx` | StreamingResponse 透传 `ask.errorBubble` / `ask.activityElapsedSeconds` |
| `frontend/src/app/(dashboard)/sources/[id]/page.tsx` | ChatPanel 透传 `chat.activityStatus` / `chat.activityElapsedSeconds` |
| `tests/test_sse_helpers.py` | **新增** — 11 个用例覆盖共享 helper 的全部公开 API |
| `tests/test_source_chat_heartbeat_sse.py` | **新增** — 源聊天 error_code / llm_timeout 路径回归 |
| `tests/test_ask_heartbeat_sse.py` | **新增** — Ask error_code / llm_timeout / 静默式心跳路径回归 |

---

## 33. 笔记本 Research Agent MVP（2026-07-10）

### 33.1 产品与范围决策

- **默认范围固定为当前笔记本**：Research Agent 只读取 `Notebook.get_sources()` / `get_notes()` 返回的可见来源和笔记，继续继承聚合笔记本与隐藏项规则。
- **跨笔记本发现必须显式开启**：前端开关默认关闭，授权只作为单次请求参数 `allow_cross_notebook_discovery` 发送，不持久化为长期授权。
- **不提供隐式全部来源模式**：全局 Research Agent 后续作为全局 Ask 页面的独立入口，不与笔记本 Agent 混用会话或权限。
- **Mira/玻尔采用 Markdown 导入**：现阶段不做网页自动化、内部接口转发或 `sub2api` 网关。用户从外部平台导出 Markdown 后按普通来源导入笔记本，Agent 将其作为二手证据处理。
- 设计记录：`docs/superpowers/specs/2026-07-10-research-agent-external-capability-integration-feasibility.md`。

### 33.2 后端实现

- `chat_session.mode` 支持 `quick | research`；旧会话缺少字段时按 `quick` 处理，更新会话接口不允许修改模式。
- Research Agent 使用独立 `research_chat_checkpoints.sqlite`，会话详情与消息数按模式选择 graph/checkpoint，避免与快速对话状态互相污染。
- 新增 `notebook_vector_search()`：向 SurrealDB 查询时直接传入当前笔记本来源/笔记 RecordID allowlist，不采用“先全库 top-k、再前端过滤”的低召回方案。
- 跨笔记本 allowlist 由认证用户生成：普通用户只包含 `created_by == 当前用户` 的其他笔记本，管理员可覆盖全部其他笔记本。`read_source` / `read_note` 也校验同一授权集合，不能通过猜测 ID 越界读取。
- 新增 `open_notebook/graphs/research_agent.py`，首批只读工具：
  - `list_notebook_sources`
  - `search_notebook_evidence`
  - `read_source`
  - `read_note`
  - `discover_across_notebooks`
  - 可选 `tavily_search`
- `read_source` / `read_note` 在读取前再次校验范围；§33.8 起改为默认每块最多 12000 字符，并返回 `next_start_char` 供 Agent 按需读取后续块，可通过 `RESEARCH_AGENT_READ_MAX_CHARS` 调整。
- 新增 `/api/chat/research/execute` SSE 入口；快速会话与 Research 会话误用对方端点时返回 409。流继续复用现有心跳、整体超时、结构化 `error_code`、`answer_complete` 与建议问题机制。

### 33.3 前端实现

- 笔记本聊天输入区新增“快速对话 / 科研 Agent”分段控件；源聊天不显示。
- Research 模式只展示 Research 会话，不预构造 `/chat/context` 全量上下文，直接由 Agent 工具按需检索和阅读。
- “跨笔记本发现”仅在 Research 模式出现，默认关闭；切换模式会恢复关闭并清理旧模式的临时消息状态。
- 笔记本导览卡和上下文 token/字符统计只在快速对话显示。
- 新增可见文案已同步到 9 个语言包；浏览器请求仍使用相对 `/api/chat/research/execute`。
- 手工实测后把“联网搜索、快速对话、科研 Agent、跨笔记本发现”合并到输入区同一设置行，四项前均显示 Checkbox，Checkbox 与整段文字标签都可点击。快速/科研仍互斥；在快速模式开启跨笔记本发现会自动切到科研模式。模型选择器继续位于该行右侧，窄宽度时整行允许自然换行。
- 手工实测发现推理模型的流式 `<think>` 标签会被 `rehypeRaw` 当作未知 HTML 元素。共享 Markdown 渲染入口现先调用 `stripThinkingContent()`，完整推理块、流式未闭合块、缺失开标签三种情况都不会进入 React DOM；普通 Markdown 与原始表格 HTML 保持不变。

### 33.4 验证

```text
UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_research_agent_scope.py tests/test_chat_heartbeat_sse.py -q
20 passed, 1 warning

cd frontend && npm test -- --run src/lib/hooks/useNotebookChat.test.tsx src/components/source/ChatPanel.test.tsx src/app/'(dashboard)'/notebooks/components/ChatColumn.test.tsx
36 passed

cd frontend && npm test
154 passed | 9 skipped

cd frontend && npm test -- --run src/lib/chat/thinking-content.test.ts src/components/source/ChatPanel.test.tsx src/lib/hooks/useNotebookChat.test.tsx src/lib/hooks/useSourceChat.test.tsx
42 passed

cd frontend && npm test -- --run src/components/source/ChatPanel.test.tsx src/lib/hooks/useNotebookChat.test.tsx src/lib/hooks/useSourceChat.test.tsx
39 passed

cd frontend && npx eslint src/lib/hooks/useNotebookChat.ts src/lib/hooks/useNotebookChat.test.tsx src/components/source/ChatPanel.tsx src/components/source/ChatPanel.test.tsx src/app/'(dashboard)'/notebooks/components/ChatColumn.tsx src/lib/api/chat.ts src/lib/types/api.ts
exit 0

UV_CACHE_DIR=/tmp/uv-cache uv run ruff check api/routers/chat.py open_notebook/config.py open_notebook/domain/notebook.py open_notebook/graphs/research_agent.py tests/test_research_agent_scope.py
All checks passed

cd frontend && npm run build
exit 0

git diff --check
exit 0
```

补充执行 `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/ -q`：`305 passed, 3 skipped, 23 failed`。失败项包括沙箱禁止访问 `127.0.0.1:8001` 的数据库用例、依赖外部 API 服务的 `test_integration_e2e.py`、`test_kg.py`，以及现存 `test_makefile_logging.py` 字符串断言。未在沙箱外重跑会创建笔记本/来源的完整 E2E，以免污染真实业务数据。全仓 Ruff 另有 `commands/__init__.py` 与 `tests/test_integration_e2e.py` 共 5 个既有格式错误；本次变更文件的 Ruff 检查全绿。

局域网运行时只读探测（`http://192.168.10.198:5056`）：

- `/openapi.json` 已包含 `/api/chat/research/execute`；
- `ExecuteResearchChatRequest.allow_cross_notebook_discovery.default == false`；
- `ChatSessionResponse.mode` 枚举为 `quick | research`，默认 `quick`；
- Research 入口已显式接入当前用户依赖；无认证请求返回 `401 {"detail":"Not authenticated"}`。
- 单元测试确认不存在的会话 ID 映射为 404。初版运行时探测曾发现错误映射为 500，已同时修复快速对话和 Research 入口的 `NotFoundError -> 404`，并增加两个回归用例。

浏览器实机烟测未执行：应用内浏览器策略拒绝访问 `http://127.0.0.1:3001`，未改用其它地址绕过。合并前仍需在真实笔记本中验证模式切换、跨笔记本复选框、至少一轮工具调用与移动端布局。

### 33.5 已知后续

1. MVP 依赖所选模型支持 LangChain tool calling；需要在项目实际配置的主要模型上建立兼容矩阵与降级文案。
2. 当前已增加工具状态事件，但 SSE 仍会转发 Agent 各轮模型流。后续如供应商在 tool call 前输出中间说明，应增加“仅最终回答流式”的过滤，避免把中间规划混入回答。
3. 历史笔记本若缺少 `created_by`，普通用户的跨笔记本发现不会纳入；管理员不受影响。需要在后续数据治理中补齐历史所有权，而不是放宽 Agent 查询。
4. 外部 Markdown 的 provider、导出时间、原任务链接目前由文档正文保留；后续可增加结构化 provenance，但不应阻塞首版。

### 33.6 文件索引

| 文件 | 改动 |
|------|------|
| `open_notebook/graphs/research_agent.py` | **新增** — Research Agent 状态图、工具、提示词调用与范围校验 |
| `prompts/research_agent/system.jinja` | **新增** — 科研方法、权限与引用约束 |
| `open_notebook/domain/notebook.py` | `ChatSession.mode` + notebook-scoped vector search |
| `open_notebook/config.py` | 独立 Research checkpoint 路径 |
| `api/routers/chat.py` | 会话模式响应/分流、Research SSE 入口、按模式读取 checkpoint |
| `frontend/src/lib/hooks/useNotebookChat.ts` | 模式会话隔离、Research 请求、单次跨笔记本授权 |
| `frontend/src/components/source/ChatPanel.tsx` | 笔记本专用模式控件、跨笔记本复选框与执行反馈锚点 |
| `frontend/src/components/source/ChatActivityFeed.tsx` | **新增** — 笔记本对话执行步骤、读秒、终态摘要与展开/收起 |
| `frontend/src/lib/chat/notebook-chat-activity.ts` | **新增** — Quick/Research 共用的阶段、步骤与终态类型 |
| `frontend/src/lib/chat/thinking-content.ts` | **新增** — 流式安全移除完整/未闭合/缺开标签的模型推理块 |
| `frontend/src/lib/chat/thinking-content.test.ts` | **新增** — 4 个推理标签清理回归用例 |
| `frontend/src/app/(dashboard)/notebooks/components/ChatColumn.tsx` | 模式属性接线、Research 模式隐藏快速对话导览/统计 |
| `frontend/src/lib/api/chat.ts` / `frontend/src/lib/types/api.ts` | Research API 与类型 |
| `frontend/src/lib/locales/*/index.ts` | 9 个语言包新增模式文案 |
| `tests/test_research_agent_scope.py` | **新增** — 默认模式、allowlist、越界读取、显式授权、checkpoint 隔离测试 |

### 33.7 笔记本对话实时执行反馈（2026-07-10）

#### 行为与协议

- 用户提交问题后，不等待会话创建、上下文构建或首个模型 token：前端立即插入用户消息，并显示“已接收问题”与当前活动步骤；独立 1 秒计时器持续显示本轮总耗时。
- Quick Chat 先显示“准备已选资料 / 已准备对话资料”，再进入联网检索或等待模型；Research Agent 从“分析问题并选择工具”开始，根据 LangGraph 的真实 `on_tool_start` / `on_tool_end` 事件切换研究范围确认、当前笔记本检索、证据阅读、跨笔记本发现、联网检索和综合结论等阶段。
- 后端新增 `chat_status` SSE：仅发送 `stage`、`status`、`elapsed_ms`。不发送模型思维链、工具参数、工具返回正文或来源原文，避免把内部推理和私域数据暴露到执行面板。
- 心跳不再在首个 AI chunk 后停止；工具调用、长时间检索或综合阶段静默时，仍按当前阶段发送 heartbeat。前端接受任意阶段心跳并以服务端耗时校正本地读秒。
- 执行反馈紧邻触发本轮的用户问题。执行中默认展开并连续追加步骤；成功、失败或用户停止后自动折叠为“步骤数 + 总耗时”摘要，可手动展开复查。
- 已知工具映射为固定本地化阶段；新增或未识别工具统一显示“正在调用研究工具”，不暴露内部工具名。

#### 验证

```text
uv run pytest tests/test_chat_heartbeat_sse.py tests/test_research_agent_scope.py -q
23 passed, 1 warning

cd frontend && npm test -- --run src/lib/hooks/useNotebookChat.test.tsx src/components/source/ChatPanel.test.tsx
39 passed

cd frontend && npm test
157 passed | 9 skipped

cd frontend && npx eslint src/lib/hooks/useNotebookChat.ts src/lib/hooks/useNotebookChat.test.tsx src/components/source/ChatActivityFeed.tsx src/components/source/ChatPanel.tsx src/components/source/ChatPanel.test.tsx src/app/'(dashboard)'/notebooks/components/ChatColumn.tsx src/lib/chat/notebook-chat-activity.ts src/lib/locales/*/index.ts
exit 0

uv run ruff check api/routers/chat.py tests/test_chat_heartbeat_sse.py
All checks passed

cd frontend && npm run build
exit 0

git diff --check
exit 0
```

前端用例覆盖提交后即时步骤、结构化状态序列、非 `awaiting_model` 阶段心跳、完成终态、消息下方锚定、自动折叠和手动展开；后端用例覆盖事件结构、Research 工具阶段顺序，以及首个回答 chunk 后静默期间继续心跳。

运行态页面检查尝试了应用内浏览器与现有 Chrome 会话，均被重定向到 `/login?redirect=%2Fnotebooks`，没有可复用的已登录会话。未读取本机配置或绕过认证，因此真实笔记本中的长回答视觉联调仍需登录后手工完成。

### 33.8 Quick/Research 协议安全上下文压缩（2026-07-10）

#### 问题与范围

- Research Agent 原实现直接执行 `messages[-20:]`；Quick Chat 使用相同性质的 `messages[-12:]`。启用工具后，固定位置切片可能保留 `ToolMessage` 却丢掉前置 `AIMessage(tool_calls)`，模型供应商会返回 `400: Messages with role 'tool' must be a response to a preceding message with 'tool_calls'`。
- Quick 默认不联网时通常没有工具消息，但开启联网搜索后同样经过 `ToolNode`，因此具有相同风险。本轮不只修 Research，而是让两个图共用 `open_notebook/graphs/message_history.py`。

#### 压缩与修复策略

- 完整 LangGraph checkpoint 保持不变，UI 仍可读取完整历史；只压缩单次交给模型的 payload。
- `AIMessage(tool_calls)` 与其后全部 `ToolMessage` 组成不可拆分原子组。窗口按最近优先选择完整原子组，绝不从工具返回处开始。
- 调用前校验旧 checkpoint：孤立 `ToolMessage`、缺少部分返回的不完整工具组，只从本轮模型 payload 中剔除并记录 `repaired_messages`，不删除用户历史数据。
- 同时使用消息数和 token 双预算：Quick 默认 `12 / 16000 tokens`，Research 默认 `20 / 32000 tokens`。最新用户问题始终保留；预算不足时丢弃完整旧工具组，而不是拆组。
- 被窗口丢弃的较早 `HumanMessage` 与无工具调用的最终 `AIMessage` 被压成确定性摘要并附加到 system prompt；摘要明确排除原始工具结果，不增加额外 LLM 调用。默认摘要字符上限分别为 Quick 6000、Research 8000。
- Research 的 `read_source` / `read_note` 默认单块从 30000 降为 12000 字符，新增 `start_char`、`end_char`、`next_start_char`、`total_chars`，Agent 仅在必要时继续读取下一块。
- 新增 `history_compressed` / `research_history_compressed` INFO 日志，记录总消息数、有效消息数、保留/丢弃/修复数量、估算 token、预算和摘要长度，不记录消息正文或工具结果。

可调整配置：

```text
CHAT_HISTORY_MAX_MESSAGES=12
CHAT_HISTORY_MAX_TOKENS=16000
CHAT_HISTORY_SUMMARY_MAX_CHARS=6000
RESEARCH_AGENT_HISTORY_MAX_MESSAGES=20
RESEARCH_AGENT_HISTORY_MAX_TOKENS=32000
RESEARCH_AGENT_HISTORY_SUMMARY_MAX_CHARS=8000
RESEARCH_AGENT_READ_MAX_CHARS=12000
```

#### 失败进度语义

- 执行失败时不再把所有活动步骤改为绿色完成。此前已收到后端完成事件的步骤保持绿色；失败发生时仍为 active 的步骤改为红色错误。用户停止时则显示 cancelled 状态。

#### 文件索引

| 文件 | 改动 |
|------|------|
| `open_notebook/graphs/message_history.py` | **新增** — 工具协议修复、原子消息组、token/消息双预算、确定性早期摘要 |
| `open_notebook/graphs/chat.py` | Quick Chat 接入共享历史压缩与可观测日志 |
| `open_notebook/graphs/research_agent.py` | Research 接入共享压缩；来源/笔记改为 12000 字符分页读取 |
| `prompts/research_agent/system.jinja` | 指示 Agent 仅在必要时使用 `next_start_char` 继续读取 |
| `frontend/src/lib/chat/notebook-chat-activity.ts` | 步骤状态增加 error / cancelled |
| `frontend/src/components/source/ChatActivityFeed.tsx` | 当前失败/停止步骤使用对应终态图标，不再显示绿色完成 |
| `.env.production.example` | 增加 Quick/Research 历史 token、摘要与读取块配置示例 |
| `tests/test_message_history.py` | **新增** — 协议修复、原子裁剪、摘要隐私、token 预算及两个模型节点回归 |

#### 验证

```text
uv run pytest tests/test_message_history.py tests/test_chat_context_budget.py tests/test_research_agent_scope.py tests/test_chat_heartbeat_sse.py -q
38 passed, 1 warning

uv run pytest tests/test_message_history.py tests/test_chat_context_budget.py tests/test_research_agent_scope.py tests/test_chat_heartbeat_sse.py tests/test_chat_suggestions_sse.py tests/test_chat_observability.py tests/test_tavily_search_timeout.py tests/test_graphs.py -q
63 passed, 6 warnings

cd frontend && npm test -- --run src/lib/hooks/useNotebookChat.test.tsx src/components/source/ChatPanel.test.tsx
40 passed

cd frontend && npm test
158 passed | 9 skipped

uv run ruff check open_notebook/graphs/message_history.py open_notebook/graphs/chat.py open_notebook/graphs/research_agent.py tests/test_message_history.py tests/test_chat_context_budget.py tests/test_research_agent_scope.py
All checks passed

cd frontend && npx eslint src/lib/hooks/useNotebookChat.ts src/lib/hooks/useNotebookChat.test.tsx src/components/source/ChatActivityFeed.tsx src/components/source/ChatPanel.test.tsx src/lib/chat/notebook-chat-activity.ts
exit 0

cd frontend && npm run build
exit 0

git diff --check
exit 0
```

补充尝试 `uv run pytest tests/ -q --tb=no`：运行到依赖真实模型的 `tests/test_kg.py` 长时间等待后手动停止；停止时已完成部分为 `156 passed, 3 skipped, 19 failed`。19 个失败主要是测试 API 未启动导致的 `test_integration_e2e.py` 连接失败；其中一次 `ContentSettings` 默认值用例失败，单独重跑后 `1 passed`。本次影响范围的 63 个后端测试全部通过。

---

> 最后更新：2026-07-10 | 新增 §33（笔记本 Research Agent MVP）、§33.7（实时执行反馈）与 §33.8（Quick/Research 协议安全上下文压缩）。默认当前笔记本、跨笔记本发现单次显式授权、Quick/Research 会话与 checkpoint 隔离；工具消息按原子组裁剪，旧 checkpoint 孤立工具消息在 payload 层修复。

---

## 34. 笔记本双对话 Tab 与会话生命周期（2026-07-11）

### 34.1 产品决策

- Quick Chat 与 Research Agent 改为 ChatPanel 顶部两个 Tabs，不再用输入区互斥 Checkbox 表示模式。
- Tab 本身已经表达模式，因此 Research 底部不重复“科研 Agent”开关；Quick 显示联网搜索和模型，Research 显示联网搜索、跨笔记本发现和模型。
- 两个 Tab 分别记住当前会话、输入草稿、待选模型和联网搜索状态；切换 Tab 不再把用户拉回另一模式的第一条会话。
- “保存”采用自动保存状态：发送中显示保存中，checkpoint 完成本轮后显示已保存，错误或取消显示保存失败；不增加会让用户误以为默认不持久化的手动保存按钮。
- “新会话”先进入本地空白草稿，第一条消息发送时才创建服务端会话并按问题生成标题，避免空会话记录。

设计与实施记录：

- `docs/superpowers/specs/2026-07-11-chat-tabs-session-lifecycle-design.md`
- `docs/superpowers/plans/2026-07-11-chat-tabs-session-lifecycle-implementation.md`

### 34.2 UI 与会话动作

- 顶部常驻当前模式 Tabs、当前会话下拉菜单和 Plus 新会话按钮；Plus 使用 Tooltip。
- 会话下拉菜单可以直接切换本模式会话，并提供管理会话和导出 Markdown。
- Markdown 导出包含当前会话的全部人类/AI transcript（分页实现见 §35），移除 `<think>` 推理块，不包含 ToolMessage、凭据或内部工具参数。
- 现有 SessionManager 继续负责重命名和删除；笔记本聊天的 Plus 直接进入本地草稿，源聊天继续使用原来的标题创建流程。
- 新会话创建后，在刷新后的会话列表尚未包含新 ID 前保持“待确认”状态，避免旧列表竞态把用户自动切回旧会话。

### 34.3 文件索引

| 文件 | 改动 |
|------|------|
| `frontend/src/components/source/NotebookChatToolbar.tsx` | **新增** — 双 Tabs、会话下拉、新会话、保存状态与导出入口 |
| `frontend/src/lib/chat/export-chat-markdown.ts` | **新增** — 安全构造并下载会话 Markdown |
| `frontend/src/lib/hooks/useNotebookChat.ts` | current session / pending model / save status 按模式隔离；新增本地新会话草稿 |
| `frontend/src/components/source/ChatPanel.tsx` | 接入顶部工具栏；Quick/Research 独立草稿和联网搜索状态；底部控件按模式渲染 |
| `frontend/src/components/source/SessionManager.tsx` | 支持笔记本直接进入本地新会话，同时保留源聊天标题创建 |
| `frontend/src/lib/locales/*/index.ts` | 9 个语言包增加会话、保存和导出文案 |

### 34.4 验证

```text
cd frontend && npm test -- --run src/lib/hooks/useNotebookChat.test.tsx src/components/source/ChatPanel.test.tsx src/lib/chat/export-chat-markdown.test.ts
45 passed

cd frontend && npm test
163 passed | 9 skipped

cd frontend && npx eslint src/lib/hooks/useNotebookChat.ts src/lib/hooks/useNotebookChat.test.tsx src/components/source/NotebookChatToolbar.tsx src/components/source/ChatPanel.tsx src/components/source/ChatPanel.test.tsx src/components/source/SessionManager.tsx src/lib/chat/export-chat-markdown.ts src/lib/chat/export-chat-markdown.test.ts src/app/'(dashboard)'/notebooks/components/ChatColumn.tsx
exit 0

cd frontend && npm run build
exit 0
```

本节提交时运行态检查因缺少登录会话受阻；服务重启后的登录实测已补充在 §35.4。

---

> 最后更新：2026-07-11 | 新增 §34。Quick/Research 改为独立 Tabs，并增加显式新会话、模式独立状态、自动保存反馈和安全 Markdown 导出。

---

## 35. 长会话 Transcript 持久化与分页（2026-07-11）

### 35.1 数据职责与兼容策略

- 新增 SurrealDB `chat_message` 作为用户可见 human / final AI transcript 的长期事实来源；LangGraph SQLite checkpoint 改为仅保存近期执行记忆、工具调用协议和滚动摘要。
- `chat_session` 增加 `transcript_initialized`、`message_count` 与 `last_message_preview`。已初始化会话的列表和详情不再逐会话扫描 checkpoint 计算消息数。
- 新会话创建时直接标记 transcript 已初始化。旧会话首次打开或继续对话时，从对应 Quick/Research checkpoint 懒迁移可见消息；ToolMessage、纯工具调用 AIMessage 和 `<think>` 内容不写入 transcript。
- 每轮模型完成后先持久化 transcript，再压缩 checkpoint。写入失败时 SSE 返回 `transcript_status=error`，前端显示保存失败，并保留完整 checkpoint，不执行破坏性裁剪。
- 删除会话时同步删除其 transcript。SQLite 中对应线程的物理清理仍作为后续维护项，不阻塞会话删除。

设计与实施记录：

- `docs/superpowers/specs/2026-07-11-chat-transcript-pagination-design.md`
- `docs/superpowers/plans/2026-07-11-chat-transcript-pagination-implementation.md`

### 35.2 分页、导出与执行记忆

- `GET /chat/sessions/{id}` 默认仅返回最新 50 条，支持 `limit` 与 `before_sequence`，响应增加 `has_more`、`next_cursor`；每页仍按从旧到新的阅读顺序返回。
- 消息区顶部按需显示“加载更早消息”。前插旧页时保持滚动位置，并按消息 ID 去重，不覆盖当前乐观消息或流式回答。
- Markdown 导出自动以每页 200 条遍历完整 transcript，不受当前页面已加载数量限制。
- transcript 保存成功后，Quick/Research 复用既有消息数与 token 预算选择近期协议安全窗口，通过 LangGraph `RemoveMessage` 裁剪已归档消息；较早 human/final AI 内容合并进 `conversation_summary`，原始工具输出不进入摘要。
- Quick/Research system prompt 同时接收滚动 `conversation_summary` 与本轮窗口摘要，长会话无需每轮携带完整原文，也不会拆断 AI tool call 与 ToolMessage 协议组。

### 35.3 文件索引

| 文件 | 改动 |
|------|------|
| `open_notebook/database/migrations/27.surrealql` | **新增** — `chat_message` 表及 session/sequence、session/message_id 唯一索引 |
| `api/chat_transcript_service.py` | **新增** — 幂等写入、懒迁移、游标分页、元数据、删除和 checkpoint 安全压缩 |
| `api/routers/chat.py` | 会话分页协议；Quick/Research SSE 接入先保存后压缩与 `transcript_status` |
| `open_notebook/domain/notebook.py` | ChatSession transcript 元数据 |
| `open_notebook/graphs/chat.py` / `research_agent.py` | 状态增加滚动摘要，并注入 system prompt |
| `frontend/src/lib/api/chat.ts` / `types/api.ts` | 分页参数、响应类型和完整导出遍历 |
| `frontend/src/lib/api/chat.test.ts` | **新增** — 完整导出跨页顺序与 cursor 请求回归 |
| `frontend/src/lib/hooks/useNotebookChat.ts` | 分页前插、去重、分页游标、完整导出及真实保存状态 |
| `frontend/src/components/source/ChatPanel.tsx` | 顶部加载旧消息并保持滚动锚点 |
| `frontend/src/lib/locales/*/index.ts` | 9 个语言包增加分页加载文案 |
| `tests/test_chat_transcript_service.py` / `test_chat_transcript_router.py` | **新增** — transcript、迁移失败、分页、列表快路径与安全压缩回归 |

### 35.4 验证

```text
UV_CACHE_DIR=/tmp/lumina-uv-cache uv run pytest -q tests/test_chat_transcript_service.py tests/test_chat_transcript_router.py tests/test_notebook_schema_migrations.py tests/test_message_history.py tests/test_chat_context_budget.py tests/test_research_agent_scope.py tests/test_chat_heartbeat_sse.py tests/test_chat_suggestions_sse.py tests/test_chat_observability.py tests/test_tavily_search_timeout.py tests/test_graphs.py
71 passed, 6 warnings

cd frontend && npm test
167 passed | 9 skipped

cd frontend && npm run lint
exit 0（4 个既有 warning，无 error）

cd frontend && npm run build
exit 0
```

服务重启后的登录实测：

- API 启动日志确认数据库版本为 27，migration 已生效。
- 使用 `admin` 进入现有 4 来源测试笔记本，Quick/Research Tabs 能分别恢复会话；Quick 底部仅显示联网搜索和模型，Research 显示联网搜索、跨笔记本发现和模型，浏览器无 React/Markdown 错误。
- 首次真实发送暴露 SurrealDB 禁止绑定保留变量 `$session`；已将 transcript 查询变量统一改为 `$session_record`，并增加回归断言。
- 热重载后重新创建 Quick 会话并发送“保存测试通过”：状态从保存中变为已保存；刷新页面后用户问题与 AI 回答仍完整存在，证明 transcript 写入和详情读取成功。
- 两个端到端测试会话均已从会话管理器删除；删除接口正常同步清理 transcript。现有数据中没有超过 50 条的单会话，因此“加载更早消息”的真实按钮和完整 Markdown 下载仍保留为长会话手工验收项，分页与跨页导出由自动测试覆盖。

---

> 最后更新：2026-07-11 | 新增 §35。笔记本长会话改为 SurrealDB transcript 分页归档与近期 checkpoint 执行记忆；先持久化后压缩，失败不裁剪；完整导出不受首屏 50 条限制。

---

## 36. Research Agent 工具执行与消息归并稳定性（2026-07-12）

### 36.1 问题与根因

- Research 状态新增 `conversation_summary` 后使用了 `Optional[str]`。在 `TypedDict` 中这只表示值可以为 `None`，键本身仍必填；旧会话和首轮请求没有该键时，LangGraph `InjectedState` 在工具调用前校验失败，模型因此误判 `list_notebook_sources`、`search_notebook_evidence` 等工具不可用。
- 流式 AI 消息使用本地 `ai-*` ID，持久化 transcript 使用 `${trace_id}-ai` ID。保存完成后的查询结果按 ID 合并时，两份相同回答被当成不同消息，形成“流式回答 / 用户问题 / 持久化回答”的错误顺序。
- 修复工具注入后，真实模型可能在证据已经足够时继续重复搜索，最终触发 LangGraph 默认递归上限；部分供应商即使声明不允许工具仍会把 DSML 工具标记输出为正文。

### 36.2 实现决策

- `ResearchState.conversation_summary` 改为 `NotRequired[Optional[str]]`，保持旧 checkpoint 和首轮状态兼容。
- 前端把发送期 `temp-*` 与普通 `ai-*` 视为瞬态消息；持久化 transcript 到达后用服务端 human/AI 消息整体替换瞬态副本。`ai-error-*` 错误气泡不参与替换，保存失败时也不再用空的服务端结果覆盖本地成功回答。该逻辑由 Quick/Research 共用，因此两种对话都覆盖。
- Research Agent 每轮默认最多执行 6 轮工具调用，可通过 `RESEARCH_AGENT_MAX_TOOL_ROUNDS` 调整；预算在每条新用户消息后重置。达到预算后执行一次终局综合，不再继续工具循环。
- 终局综合不复用 AI tool-call / ToolMessage 协议历史，而是把最新用户问题与当前轮成功工具证据整理为普通文本 payload；证据默认最多 60000 字符，可通过 `RESEARCH_AGENT_FINAL_EVIDENCE_MAX_CHARS` 调整。这样不依赖供应商对 `tool_choice=none` 的兼容性，也不会把 DSML 当作最终答案或让上一轮证据挤占当前轮预算。

### 36.3 文件索引

| 文件 | 改动 |
|------|------|
| `open_notebook/graphs/research_agent.py` | 可缺省摘要状态、工具轮数预算、终局证据综合节点 |
| `frontend/src/lib/hooks/useNotebookChat.ts` | 流式瞬态消息与持久化 transcript 归并；保存失败保留本地回答 |
| `tests/test_research_agent_scope.py` | 缺省摘要工具注入、轮数路由、扁平终局 payload 回归 |
| `frontend/src/lib/hooks/useNotebookChat.test.tsx` | 重复回答替换、顺序与保存失败保留回答回归 |

### 36.4 验证

```text
UV_CACHE_DIR=/tmp/lumina-uv-cache uv run pytest -q tests/test_research_agent_scope.py tests/test_chat_transcript_service.py tests/test_chat_transcript_router.py tests/test_message_history.py tests/test_chat_heartbeat_sse.py tests/test_chat_suggestions_sse.py tests/test_chat_observability.py
52 passed, 1 warning

cd frontend && npm test -- --run
167 passed | 9 skipped

cd frontend && npm run lint
exit 0（4 个既有 warning，无 error）

cd frontend && npm run build
exit 0

UV_CACHE_DIR=/tmp/lumina-uv-cache uv run ruff check open_notebook/graphs/research_agent.py tests/test_research_agent_scope.py
All checks passed
```

登录实测使用原问题“OCW-2L冲洗剂在盐水/海水条件下与本文降失水剂、缓凝剂的相容性如何？高温老化后界面润湿性是否仍稳定？”：

- 工具成功读取当前笔记本来源，不再输出“工具不可用”；6 轮工具后进入终局综合，36 秒内完成 7 个可见步骤并保存自然语言答案。
- 最终回答引用 5 个当前笔记本来源，明确区分产品声明、证据缺口和建议验证方案，没有 DSML 工具标记。
- 刷新后精确统计为 1 条用户问题、1 条对应回答标题，消息顺序正确且无重复回答。
- 实测过程中产生的 3 个失败/中间验证会话已删除，仅保留最终成功会话供复核。

---

> 最后更新：2026-07-12 | 新增 §36。修复 Research 工具状态注入与流式/持久化消息重复，并增加有界工具调用和供应商无关的终局证据综合。

### 36.5 正文工作区引用可点击（2026-07-12）

- 部分模型会把内部引用输出为转义 Markdown，例如 `\[1\]\(#ref-source-uuid\)`，或用反引号包成行内代码；ReactMarkdown 会将其显示为普通文字/代码，虽然回答末尾由前端生成的“工作区引用”仍可点击。
- 引用预处理会规范化指向 `#ref-source-*`、`#ref-note-*`、`#ref-source_insight-*` 的转义或代码包裹内部链接；Markdown code 渲染器也会把内容完全等于内部引用链接的代码节点转为引用按钮。正文编号和末尾工作区引用统一调用现有 `SourceDialog` / Note / Insight 模态框，不改变普通代码和外部链接行为。
- `ChatPanel` 回归测试覆盖转义正文引用的渲染与点击，确认 `[1]` 点击后以完整 ID 打开对应来源。

验证：

```text
cd frontend && npm test -- --run
168 passed | 9 skipped

cd frontend && npm run lint
exit 0（4 个既有 warning，无 error）

cd frontend && npm run build
exit 0
```

登录实测刷新原 Research 会话后，页面中 `[1](#ref-source-4qzydafkvwagspw0g9j7)` 字面文本从 2 处降为 0；点击正文编号 `[1]` 成功打开“测试查重-固井用油基泥浆冲洗剂OCW-2L-2024版”来源详情，并显示解析后的正文内容。

### 36.6 对话模式 Tab 单行显示（2026-07-12）

- Quick/Research 模式切换器不再参与工具栏剩余空间压缩，两个 Tab 标签统一使用 `whitespace-nowrap`。
- 窄宽度下优先由工具栏现有 `flex-wrap` 将右侧会话操作换行，避免“科研 Agent”被拆成两行并改变 Tab 高度。
- `ChatPanel` 组件测试增加两个模式 Tab 的单行样式断言。
- 完整前端验证：`npm test -- --run` 为 `168 passed | 9 skipped`；`npm run lint` 为 0 error、4 个既有 warning；`npm run build` 通过。
- 640px 浏览器视口实测：Research Tab 的 `white-space` 为 `nowrap`，高度 28px、内容滚动高度 26px，保持单行且没有纵向溢出。

### 36.7 切换模型保留本地失败轮次（2026-07-12）

- 供应商通过 SSE 返回 error 时，该轮 human / error AI 不会写入成功 transcript；此前用户问题仍使用 `temp-*`，切换模型触发会话详情刷新后会被瞬态消息归并逻辑删除，活动面板也因失去 human 锚点而消失。
- SSE error 到达后，用户问题改标为当前会话的本地失败消息；若已有部分 AI 输出，也统一改标为 `ai-error-*`。同一会话因模型更新或列表同步而 refetch 时保留问题、错误气泡和执行步骤。
- 首条消息自动创建会话后立即失败时，消息归属会在创建成功后立刻绑定到新 session，避免首次详情加载被误判为切换会话。
- 失败轮次仍遵循“保存失败”语义，不写入长期 transcript；主动切换到其他会话或刷新整个页面后不会伪装成已持久化消息。
- 完整前端验证：`npm test -- --run` 为 `169 passed | 9 skipped`；`npm run lint` 为 0 error、4 个既有 warning；`npm run build` 通过。

---

## 37. 全局 Ask 即时进度反馈（2026-07-12）

### 37.1 问题与决策

- Quick Chat 与 Research Agent 已通过本地即时反馈、结构化阶段事件和读秒面板解决“提交后像没反应”的体验问题；全局 Ask 仍只有较弱的 loading 行和 10 秒级 heartbeat，用户在规划/检索/最终综合阶段容易误判系统卡死。
- 本轮采用窄范围“方案 B”：不改 Ask 的检索策略、LangGraph 节点、覆盖率统计、历史记录或最终答案生成，只补用户可见进度反馈。
- 前端提交 Ask 后立即在响应区顶部显示进度面板，不等待 `/api/search/ask` 第一条 SSE；后端同时新增轻量 `status` SSE，阶段为 `received`、`planning`、`searching`、`writing`。
- `status` 事件只包含阶段和耗时，不暴露 LangGraph、向量检索、prompt、模型推理或来源原文。前端仍从既有 `coverage`、`strategy_reasoning_chunk`、`strategy`、`answer`、`final_answer`、`heartbeat` 事件推断阶段作为兜底。
- Ask 进度状态是 transient UI state，不写入 `ask-store-state` 持久化；恢复历史记录不会显示过期的“正在处理”状态。

### 37.2 文件索引

| 文件 | 改动 |
|------|------|
| `api/routers/search.py` | 新增 `status` SSE 事件和阶段耗时，保留原有 coverage/strategy/answer/final_answer/heartbeat/complete/error 协议 |
| `frontend/src/lib/stores/ask-store.ts` | 新增 transient Ask progress 状态与更新动作；`final_answer` 不再提前结束 streaming，等待 `complete` |
| `frontend/src/lib/hooks/use-ask.ts` | 提交瞬间设置 received 进度与本地读秒；消费 status/heartbeat 并从既有 Ask 事件兜底推进阶段 |
| `frontend/src/components/search/StreamingResponse.tsx` | 响应区顶部新增 Ask 进度面板，显示四步、当前状态和已用秒数 |
| `frontend/src/app/(dashboard)/search/page.tsx` | 将 Ask progress 传入响应组件 |
| `frontend/src/lib/locales/*/index.ts` | 9 个语言包新增 Ask 进度文案 |
| `frontend/src/lib/types/search.ts` | Ask SSE 类型新增 `status` |
| `tests/test_ask_heartbeat_sse.py`、`frontend/src/lib/hooks/use-ask.test.tsx`、`frontend/src/components/search/StreamingResponse.test.tsx` | 新增/更新 Ask status、progress state、进度面板回归 |

### 37.3 验证

```text
uv run pytest -q tests/test_ask_heartbeat_sse.py
4 passed, 1 warning

cd frontend && npm test -- --run src/lib/hooks/use-ask.test.tsx src/components/search/StreamingResponse.test.tsx
10 passed

uv run ruff check api/routers/search.py tests/test_ask_heartbeat_sse.py
All checks passed!

cd frontend && npm run lint
exit 0（4 个既有 warning，无 error）

cd frontend && npm run build
exit 0

git diff --check
exit 0
```

未验证项：

- 登录后的真实全局 Ask 页面手工检查：提交后响应区 0 秒内显示进度面板；长等待期间阶段和秒数持续可见；最终答案、覆盖率和历史记录仍正常。

---

## 38. “与来源对话”来源栏可折叠（2026-07-12）

### 38.1 问题与决策

- 来源详情页原来固定使用 `2fr / 1fr` 双栏，来源正文占据大部分宽度；长回答场景下右侧“与来源对话”区域偏窄。
- 原有关闭 `X` 由左侧 `SourceDetailContent` 渲染。若直接隐藏左栏，关闭入口也会同时消失。
- 桌面端新增来源栏折叠入口。折叠后保留 48px 竖向恢复栏，右侧聊天面板占据剩余宽度；来源详情组件保持挂载，只通过响应式样式隐藏，因此当前 Tab、已加载数据和组件状态不会因折叠被重置。
- 关闭 `X` 提升到页面级头部，并在右侧预留全局头像安全区；来源详情页不再显示内部重复 `X`。`SourceDialog` 弹窗仍保留原有内部关闭按钮。
- 折叠状态只在当前来源页面生命周期内有效，不写入全局或持久化 store。小于 `lg` 的视口始终显示来源正文，并隐藏展开/收起控件。

### 38.2 文件索引

| 文件 | 改动 |
|------|------|
| `frontend/src/app/(dashboard)/sources/[id]/page.tsx` | 来源详情/聊天改为桌面可折叠布局；新增 48px 恢复栏和常驻页面级关闭按钮 |
| `frontend/src/app/(dashboard)/sources/[id]/page.test.tsx` | **新增** — 折叠、恢复、来源/聊天保持挂载和关闭返回回归 |
| `frontend/src/components/source/SourceDetailContent.tsx` | 新增桌面折叠动作，并支持保留 `onClose` 回调但隐藏内部关闭按钮 |
| `frontend/src/components/source/SourceDetailContent.test.tsx` | 覆盖折叠回调、页面场景不重复显示内部 `X`，并保留弹窗关闭回归 |
| `frontend/src/lib/locales/*/index.ts` | 9 个语言包新增来源内容、展开和收起文案 |

### 38.3 验证

```text
cd frontend && npm test -- --run src/components/source/SourceDetailContent.test.tsx 'src/app/(dashboard)/sources/[id]/page.test.tsx'
8 passed

cd frontend && npm test -- --run
174 passed | 9 skipped

cd frontend && npx eslint 'src/app/(dashboard)/sources/[id]/page.tsx' 'src/app/(dashboard)/sources/[id]/page.test.tsx' src/components/source/SourceDetailContent.tsx src/components/source/SourceDetailContent.test.tsx
exit 0（2 个 SourceDetailContent 既有 img warning，无 error）

cd frontend && npm run lint
exit 0（4 个既有 warning，无 error）

cd frontend && npm run build
exit 0

git diff --check
exit 0
```

登录浏览器实测使用来源 `source:4qzydafkvwagspw0g9j7`：

- 1280px 展开状态下来源栏约 795px、聊天栏约 381px；折叠后恢复栏为 48px，聊天栏扩展到约 1128px，无水平溢出。
- 折叠时来源详情 DOM 仍保持挂载，聊天面板和页面级 `X` 保持可见；恢复后返回原双栏布局。
- 页面级 `X` 与全局头像预留约 24px 安全间距，避免原始实现中的重叠。
- 760px 视口下来源正文强制显示，展开/收起控件隐藏，无水平溢出。

未验证项：本轮浏览器实测使用暗色主题；浅色主题未单独重新截图，组件使用现有语义颜色与表面 token。

---

## 39. 模型 Provision 日志凭据脱敏（2026-07-12）

### 39.1 问题与决策

- `provision_langchain_model()` 原来把 Esperanto `LanguageModel` 对象直接写入 DEBUG 日志；OpenAI-compatible 模型的对象表示包含 `api_key` 和完整配置，因此普通 `make start-all` 终端输出会泄露模型凭据。
- 模型类型不匹配时的 `ConfigurationError` 也直接插入模型对象，存在同类潜在泄露路径。
- 日志改为只记录模型对象类型和不含凭据的选择原因，例如显式 `model_id` 或默认模型类型；类型不匹配异常只报告实际 Python 类型，不再序列化模型对象。
- 已出现在历史终端或附件中的密钥视为已泄露，必须由管理员在供应商侧轮换；代码脱敏不能使旧密钥重新安全。

### 39.2 文件索引

| 文件 | 改动 |
|------|------|
| `open_notebook/ai/provision.py` | 移除日志和类型错误中的模型对象序列化，只保留安全元数据 |
| `tests/test_model_provision_logging.py` | **新增** — 使用带假密钥的恶意 `repr` 验证 DEBUG 日志与异常文本均不包含凭据 |

### 39.3 验证

```text
.venv/bin/python -m pytest -q --noconftest tests/test_model_provision_logging.py
2 passed

uv run ruff check open_notebook/ai/provision.py tests/test_model_provision_logging.py
All checks passed

git diff --check
exit 0
```

未验证项：未使用真实供应商密钥重新触发模型请求；自动测试通过故意泄密的模型 `repr` 覆盖日志和异常路径。

---

## 40. Knowledge Graph 空关系搜索稳定性（2026-07-12）

### 40.1 问题与决策

- 全局 Ask 启用 Knowledge Graph 后，SurrealDB 对没有出边或入边的实体会把 traversal projection 返回为 `null`，而不是空数组。
- `graph_search()` 原来使用 `sg.get("outbound_edges", [])` 等默认值；字段存在但值为 `None` 时默认值不生效，随后 `zip(None, None)` 抛出 `TypeError`。异常虽被函数捕获并降级为空图结果，但会输出完整错误堆栈，并丢弃本次已命中的 KG 实体上下文。
- 子图结果、出入边和对应节点统一使用 `value or []` 规范化。没有关系的实体仍返回名称、类型和描述，关系段为空；真正的数据库异常继续沿用现有捕获与降级逻辑。
- 该问题来自 2026-04 的既有图搜索实现，与近期 Ask 进度反馈和来源对话 UI 改动无关。

### 40.2 文件索引

| 文件 | 改动 |
|------|------|
| `open_notebook/domain/notebook.py` | 规范化空子图及 `null` 出入边/节点集合，保留无关系实体上下文 |
| `tests/test_graph_search.py` | **新增** — 覆盖关系字段为 `None` 和整个子图结果为 `None` 的回归 |

### 40.3 验证

```text
.venv/bin/python -m pytest -q --noconftest tests/test_graph_search.py
2 passed

uv run ruff check open_notebook/domain/notebook.py tests/test_graph_search.py
All checks passed

git diff --check
exit 0
```

未验证项：未直接读取本机 SurrealDB 中触发日志的 KG 实体和关系记录；回归测试使用与日志堆栈一致的 `null` traversal projection 复现并验证修复。

---

## 41. 用户显示版本更新为 2.0.8（2026-07-13）

### 41.1 决策

- 项目版本从 `1.9.6` 更新为 `2.0.8`，并同步 editable package 的锁文件版本。
- `/api/config` 从项目元数据读取当前版本；前端登录页继续使用该接口返回值，因此服务重启后用户可见版本将显示为 `2.0.8`。
- `CHANGELOG.md` 新增 `2.0.8` 发布条目，概括 PR #33 至 #40 中用户可感知的 Research Agent、对话会话、执行反馈、来源栏折叠和稳定性改进；历史 `1.9.6` 条目保持不变。
- 本次不修改依赖版本、数据库 schema 或部署拓扑。

### 41.2 文件索引

| 文件 | 改动 |
|------|------|
| `pyproject.toml` | 项目版本更新为 `2.0.8` |
| `uv.lock` | `open-notebook` editable package 版本同步为 `2.0.8` |
| `CHANGELOG.md` | 新增 `2.0.8` 发布摘要 |

### 41.3 验证

```text
UV_CACHE_DIR=/tmp/lumina-uv-cache uv lock --check
Resolved 341 packages in 1ms

.venv/bin/python -c "from api.routers.config import get_version; version = get_version(); print(version); assert version == '2.0.8'"
2.0.8

curl -fsS --max-time 5 http://127.0.0.1:5056/api/config
{"version":"2.0.8","latestVersion":null,"hasUpdate":false,"dbStatus":"online"}

git diff --check
exit 0
```

未验证项：未重新构建 Docker 镜像或发布版本标签；本轮范围是仓库版本、锁文件、用户显示链路和发布记录。

---

## 42. AI 内容公式与 Insight 引用渲染（2026-07-14）

### 42.1 问题与决策

- 用户反馈中的 `$C_3A$` 与 `$$...$$` 原来只按普通 Markdown 文本展示。前端现统一接入 `remark-math`、`rehype-katex` 与 `katex`，覆盖笔记本/来源聊天、全局 Ask、Insight 预览、Transformation 输出和来源正文；仅模型输出面板执行单行块公式规范化。
- 模型常把块公式输出为单行 `$$formula$$`，而标准 Markdown 数学语法会把这种形态按行内公式处理。新增预处理只把非代码内容中的单行双美元公式规范化为块级语法；已经正确的多行块公式、行内代码、未闭合反引号和 fenced code block 保持原样。来源正文不执行该预处理，避免改变非模型原始资料。
- 模型输出 `[insight:<id>]` 时，引用解析器把 `insight` 作为 `source_insight` 的兼容别名。内部链接、模态框和已有 `source_insight` 协议不变，避免历史消息与现有 URL 行为分叉。
- 现有 `rehypeRaw` HTML 表格渲染保持不变，并增加全局 Ask 回归测试，确认公式插件接入没有破坏原始 HTML 表格。

### 42.2 文件索引

| 文件 | 改动 |
|------|------|
| `frontend/package.json`、`frontend/package-lock.json` | 新增 Markdown 数学与 KaTeX 生产依赖 |
| `frontend/src/lib/markdown/plugins.ts`、`normalize-math.ts` | 共享 Markdown 插件配置；逐行规范化模型常见的单行块公式并保护完整/未闭合代码内容 |
| `frontend/src/lib/utils/source-references.tsx` | 接受 `insight:` 别名并规范化到 `source_insight` |
| `frontend/src/components/source/ChatPanel.tsx`、`SourceInsightDialog.tsx`、`SourceDetailContent.tsx` | 聊天、Insight 与来源内容接入统一公式插件；仅模型输出执行单行块公式规范化 |
| `frontend/src/components/search/StreamingResponse.tsx` | Ask 分阶段答案、最终答案与错误气泡接入统一公式渲染 |
| `frontend/src/app/(dashboard)/transformations/components/TransformationPlayground.tsx` | Transformation 输出接入统一公式渲染 |
| `frontend/src/app/layout.tsx` | 全局加载 KaTeX 样式 |
| `frontend/src/lib/markdown/normalize-math.test.ts`、`frontend/src/lib/utils/source-references.test.ts`、`frontend/src/components/source/ChatPanel.test.tsx`、`frontend/src/components/search/StreamingResponse.test.tsx` | 覆盖行内/块级公式、代码保护、Insight 导航与 HTML 表格回归 |

### 42.3 验证

```text
cd frontend && npm test -- --run src/lib/markdown/normalize-math.test.ts src/lib/utils/source-references.test.ts src/components/source/ChatPanel.test.tsx src/components/search/StreamingResponse.test.tsx
40 passed

cd frontend && npm test -- --run src/components/source/SourceDetailContent.test.tsx
7 passed

cd frontend && npm test
184 passed | 9 skipped

cd frontend && npx eslint src/lib/markdown/plugins.ts src/lib/markdown/normalize-math.ts src/lib/markdown/normalize-math.test.ts src/lib/utils/source-references.tsx src/lib/utils/source-references.test.ts src/components/source/ChatPanel.tsx src/components/source/ChatPanel.test.tsx src/components/search/StreamingResponse.tsx src/components/search/StreamingResponse.test.tsx src/components/source/SourceInsightDialog.tsx 'src/app/(dashboard)/transformations/components/TransformationPlayground.tsx' src/components/source/SourceDetailContent.tsx src/app/layout.tsx
exit 0（2 个 SourceDetailContent 既有 no-img-element warning）

cd frontend && npm run build
exit 0
```

未验证项：尚未在真实登录态笔记本中使用客户原始回答进行浏览器视觉验收；自动测试已验证 KaTeX DOM、块级公式、Insight 点击和原始 HTML 表格。`npm install` 报告当前依赖树存在 15 个 audit findings，本轮未执行自动升级，避免引入无关依赖变更。

---

## 43. 笔记本对话上下文窗口用量（2026-07-14）

### 43.1 问题与决策

- 原有笔记本快速对话只统计用户勾选的来源/笔记字符与词元，不能回答“本轮实际发送给模型的上下文占模型窗口多少”。该来源统计继续保留；新增的上下文窗口用量是独立指标，不改变上下文选择或截断策略。Quick 展示已在第 45 节合并为单行摘要。
- Quick 模式在模型调用前，对最终模型 payload（系统提示、压缩后的历史消息、当前问题和已选择上下文）进行词元估算，并通过 `context_usage` SSE 返回实际选中的模型、估算输入词元和窗口上限。该值明确标为估算值，不冒充供应商账单中的精确 token usage。
- Research Agent 采用按需工具检索，没有一个可在提交时稳定定义的固定上下文分母，因此只显示模型和“按需检索上下文”，不显示虚假的百分比。
- 模型窗口上限优先使用管理员在 API Keys 模型列表中维护的正整数覆盖值；仅内置已确认的 `deepseek/deepseek-v4-pro = 1,000,000`。未知模型不猜测上限，界面显示“上限未知”。
- 模型窗口覆盖使用既有相对 `/api/models/{id}` PATCH 链路且仅管理员可调用；不新增生产依赖或部署服务。数据库迁移 28 为 `model` 增加可空的 `context_window_tokens` 字段。

### 43.2 文件索引

| 文件 | 改动 |
|------|------|
| `open_notebook/database/migrations/28*.surrealql` | 模型上下文窗口覆盖字段及回滚迁移 |
| `open_notebook/ai/model_context.py`、`models.py`、`provision.py` | 解析内置/管理员窗口上限，并让实际模型选择与统计元数据使用同一次解析结果 |
| `open_notebook/graphs/chat.py`、`api/routers/chat.py` | 模型调用前发出经过白名单过滤的 `context_usage` 自定义事件/SSE |
| `api/models.py`、`api/routers/models.py` | 模型 API 返回有效窗口与来源；新增管理员专用 PATCH 更新入口 |
| `frontend/src/lib/hooks/useNotebookChat.ts`、`use-models.ts`、`api/models.ts` | 消费上下文 SSE，并通过相对 API 更新模型窗口配置 |
| `frontend/src/components/common/ContextIndicator.tsx`、`ContextWindowMeter.tsx`、`ChatPanel.tsx`、`ChatColumn.tsx` | Quick 在单行摘要中展示估算用量/窗口/百分比，Research 展示按需检索语义 |
| `frontend/src/app/(dashboard)/settings/api-keys/page.tsx` | 管理员在语言模型徽标旁维护上下文窗口覆盖值 |
| `frontend/src/lib/locales/*/index.ts` | 9 个语言包新增上下文窗口和配置文案 |
| `tests/test_model_context.py`、`test_message_history.py`、`test_chat_heartbeat_sse.py` 及对应前端测试 | 覆盖模型选择、窗口来源、SSE 白名单、Hook 状态和界面语义 |

### 43.3 验证

```text
uv run pytest tests/test_model_context.py tests/test_model_provision_logging.py tests/test_models_api.py tests/test_message_history.py tests/test_chat_context_budget.py tests/test_chat_heartbeat_sse.py -q
44 passed, 6 warnings

uv run ruff check api/models.py api/routers/chat.py api/routers/models.py open_notebook/ai/model_context.py open_notebook/ai/models.py open_notebook/ai/provision.py open_notebook/graphs/chat.py tests/test_model_context.py tests/test_message_history.py tests/test_chat_heartbeat_sse.py
All checks passed

cd frontend && npm test
187 passed | 9 skipped

cd frontend && npm run build
exit 0

make start-all
API initialization completed successfully；Current database version: 28；Next.js `/api/*` 代理到 `http://127.0.0.1:5056/api/*`

curl -sS -i --max-time 5 http://127.0.0.1:3001/api/models
HTTP 200；`deepseek-v4-pro` 返回 `context_window_tokens=1000000`、`context_window_source=builtin`；未知模型返回 null
```

未验证项：浏览器控制连接初始化失败，因此未自动操作登录页面，也未发送真实模型请求核对 SSE 百分比或修改管理员配置；供应商返回的精确输入 token 不属于本轮数据源，界面展示的是项目现有 tokenizer 对最终 payload 的估算。为避免改变用户现有模型记录，运行时验证只读取 `/api/models`，未调用 PATCH。

---

## 44. 用户与管理员 AI Token 用量审计（2026-07-14）

### 44.1 问题与决策

- 新增不可变 `ai_token_usage` 审计账本，记录用户、凭据名称快照、服务商、模型、工作流、成功/失败、耗时和输入/输出/总词元；不记录提示词、回答、来源内容、Authorization、原始 API Key 或异常正文。
- 语言模型调用统一在 `provision_langchain_model()` 返回的每次调用副本上附加 LangChain callback。优先采用服务商返回的 usage metadata；缺失时只提取消息中的可见文本并使用现有 tokenizer 估算，结果标记为 `estimated`，避免把 Python 结构表示或图片 data URL 计入，也不把估算值冒充账单精确值。
- Embedding 接口当前不返回 usage metadata，因此按成功批次记录估算输入词元。TTS/STT 的计费单位并非本系统定义的 token，本轮明确不纳入，避免生成错误账单口径。
- 同步 HTTP/SSE 请求由认证中间件写入用户与请求上下文；来源处理、Transformation、Knowledge Graph 和 Embedding 后台命令显式传递发起用户。没有真实请求上下文时不向旧命令 payload 注入空字段，保持现有命令契约。
- `GET /api/usage` 只允许普通用户查询本人；管理员可查询全部用户或筛选单个用户。返回汇总、每日序列、按 Key、按用户和最近 50 条安全元数据，不返回密钥值。
- 新增 `/usage` 工作型 Dashboard：普通用户查看自己的 7/30/90 天用量，管理员增加“全部用户”和用户筛选；图表使用现有 CSS/颜色 token，不新增生产依赖，浏览器请求继续走相对 `/api`。
- 审计只覆盖迁移 29 之后的调用，不追溯历史用量，也不尝试换算货币或对账服务商发票。

### 44.2 文件索引

| 文件 | 改动 |
|------|------|
| `open_notebook/database/migrations/29*.surrealql` | `ai_token_usage` SCHEMAFULL 账本、查询索引和回滚迁移 |
| `open_notebook/ai/usage_audit.py`、`models.py`、`provision.py` | 审计上下文、模型/凭据安全元数据、provider/estimated 统计和每次调用 callback |
| `api/auth.py`、`commands/*_commands.py`、`open_notebook/domain/notebook.py`、`open_notebook/graphs/source.py` | 同步、流式及后台任务的用户审计身份传播 |
| `open_notebook/utils/embedding.py` | Embedding 成功批次的估算输入词元审计 |
| `api/routers/usage.py`、`api/main.py` | 本人/管理员授权、7/30/90 天聚合 API 与路由注册 |
| `frontend/src/app/(dashboard)/usage/` | 用量 Dashboard、CSS 日图、按 Key/用户汇总、最近活动和角色行为测试 |
| `frontend/src/lib/{api,hooks,types}/usage.*` | 相对 API client、TanStack Query hook 和响应类型 |
| `frontend/src/components/layout/AppSidebar.tsx`、`frontend/src/lib/locales/*/index.ts` | 全用户侧栏入口和 i18n 文案 |
| `tests/test_usage_audit.py` 及模型/Embedding/聊天回归测试 | 安全字段、回调副本、统计来源、授权聚合、时间范围和兼容性覆盖 |
| `docs/superpowers/specs/2026-07-14-token-usage-audit-design.md`、`plans/2026-07-14-token-usage-audit-implementation.md` | 数据边界、界面与实施记录 |

### 44.3 验证

```text
uv run ruff check <本轮变更的 Python 文件>
All checks passed

uv run pytest tests/ -m 'not e2e' -q
346 passed, 33 deselected, 6 warnings

cd frontend && npm test
189 passed | 9 skipped

cd frontend && npm run lint
exit 0（4 个既有 warning，无 error）

cd frontend && npm run build
exit 0；生成静态 `/usage` 路由

make start-all
API initialization completed successfully；Current database version: 29；Next.js `/api/*` 代理到 `http://127.0.0.1:5056/api/*`

curl 未认证访问 http://127.0.0.1:5056/api/usage?days=7&scope=mine
HTTP 401

curl 使用本机管理员凭据访问 http://127.0.0.1:5056/api/usage?days=7&scope=all
HTTP 200；返回 scope=all、days=7、用户/调用/词元聚合且无密钥值

curl 使用本机管理员凭据访问 http://127.0.0.1:5056/api/usage?days=8&scope=all
HTTP 422

git diff --check
exit 0
```

未验证项：浏览器控制运行时初始化报错，因此未完成登录态 Dashboard 的自动截图和移动端视觉验收；Next.js 生产构建与组件测试已覆盖路由、角色控件、汇总、工作流标签和表格。`tests/test_integration_e2e.py` 固定连接 `localhost:5055` 且不携带当前认证，本机服务为 `5056`，完整 `uv run pytest tests/ -q` 因此有 18 个既有 E2E 连接失败；与 CI 一致的 `-m 'not e2e'` 范围全部通过。未调用真实供应商接口专门制造一笔测试账单，但本机现有真实 AI 操作已在管理员聚合 API 中形成迁移后的审计记录。

---

## 45. 笔记本 Quick 上下文摘要单行化（2026-07-14）

### 45.1 问题与决策

- 原 Quick 对话输入区上方先显示来源/笔记词元与字符数，再用独立条带显示模型、上下文窗口用量、整行进度条和更新提示，占用三行高度且信息顺序与用户阅读顺序不一致。
- Quick 模式合并为一行三列等宽布局：左侧展示上下文选择数量，中间展示已选来源/笔记词元，右侧展示最终模型 payload 的估算输入词元、窗口上限、紧凑进度条和百分比；三列分别左对齐、居中和右对齐。
- 左侧保持原统计口径，不合并成含义模糊的总数：灯泡为以 `insights` 模式选入的来源数，文档为以 `full` 模式选入的来源数，便签为以 `full` 模式选入的笔记数。该数值不是回答中实际生成的引用数。
- 中间不再显示字符数，但 `useNotebookChat` 仍保留字符统计，不改变 `/chat/context` 数据契约和上下文构建行为。
- 右侧移除重复的模型名称和单独的“下次提问后更新”提示；首次提问前显示 `-- / 上限`，收到 `context_usage` 后以 `≈` 标明估算值并显示进度。模型选择器仍是模型名称的单一可见入口。
- Research 模式继续单独显示模型与“按需检索上下文”，不展示固定百分比。未新增生产依赖、API 或部署服务，所有可见文案复用既有 i18n 键。

### 45.2 文件索引

| 文件 | 改动 |
|------|------|
| `frontend/src/components/common/ContextIndicator.tsx` | Quick 三列摘要、三类计数、来源词元、估算窗口用量与紧凑进度条 |
| `frontend/src/components/common/ContextWindowMeter.tsx` | 收窄为 Research 按需上下文提示，不再为 Quick 生成第二条带 |
| `frontend/src/components/source/ChatPanel.tsx`、`frontend/src/app/(dashboard)/notebooks/components/ChatColumn.tsx` | 合并 Quick 展示数据并停止向可见摘要传递字符数 |
| `frontend/src/components/common/ContextIndicator.test.tsx`、`ContextWindowMeter.test.tsx` | 覆盖三栏信息顺序、首次提问前状态、估算进度和 Research 语义 |

### 45.3 验证

```text
cd frontend && npm test -- --run src/components/common/ContextIndicator.test.tsx src/components/common/ContextWindowMeter.test.tsx 'src/app/(dashboard)/notebooks/components/ChatColumn.test.tsx'
6 passed

cd frontend && npx eslint src/components/common/ContextIndicator.tsx src/components/common/ContextIndicator.test.tsx src/components/common/ContextWindowMeter.tsx src/components/common/ContextWindowMeter.test.tsx src/components/source/ChatPanel.tsx 'src/app/(dashboard)/notebooks/components/ChatColumn.tsx' 'src/app/(dashboard)/notebooks/components/ChatColumn.test.tsx'
exit 0

cd frontend && npm test
191 passed | 9 skipped

cd frontend && npm run lint
exit 0；4 个既有 warning，无 error

cd frontend && npm run build
exit 0；Next.js 生产构建与 TypeScript 检查通过

git diff --check
exit 0
```

未验证项：应用内浏览器控制运行时初始化失败，尚未完成真实登录态笔记本的桌面端和移动端截图验收；本地 Next.js `3001` 与 API `5056` 服务均可访问。未发送新的真实模型请求，右侧数据链路沿用第 43 节已验证的 `context_usage` SSE。

---

## 46. 项目指引与当前运行架构校准（2026-07-15）

### 46.1 问题与决策

- 根 `AGENTS.md` 的架构、鉴权、API 路由、长任务和迁移示例仍保留部分上游或早期默认，已与当前 `make start-all`、JWT 多用户、SSE 心跳/超时、长期 transcript 和真实 migration 目录产生偏差。
- 根指引现明确区分本机源码端口（Next.js `3001`、API `5056`、SurrealDB 宿主机 `127.0.0.1:8001`）和标准容器端口（`3000/5055/8000`）。
- 浏览器默认只使用相对 `/api`，由 Next.js 将请求代理到 `INTERNAL_API_URL`；除非部署拓扑明确改变，不向局域网浏览器下发服务器本机 `localhost` API 地址。
- 鉴权说明校准为 JWT 账号体系、注册审批、角色/状态校验，并保留 `OPEN_NOTEBOOK_PASSWORD` 超级管理员兼容通道。
- 来源入库说明校准为“API 建立记录并关联笔记本 → worker 抽取/Vision 处理并保存正文 → 再提交 embedding、KG 和 Transformation 后台任务”，避免继续用“同步 extract → embed → save”概括当前链路。
- 对话持久化说明区分 SurrealDB `chat_message` 长期可见 transcript 与 Quick/Source/Research 独立 SQLite checkpoint 执行记忆，不再笼统描述为“所有会话只保存在 SQLite”。
- 数据库迁移示例改为真实目录 `open_notebook/database/migrations/`；默认后端回归范围明确排除需要真实 API、鉴权、模型和可抛弃数据的 E2E 用例。
- 本总账顶部新增阅读规则：早期条目是历史快照，冲突时以后续章节与当前代码为准。例如 §17 文件格式限制已被 §27 覆盖，§29 的单 Chat 心跳已被 §32 扩展到三条 SSE 流，§33 的早期模式控件已被 §34 Tabs 取代，§43 的 Quick 独立窗口条已被 §45 单行摘要取代。

### 46.2 文件索引

| 文件 | 改动 |
|------|------|
| `AGENTS.md` | 校准端口、代理、worker、鉴权、SSE、transcript、来源处理、测试和 migration 指引 |
| `docs/8-CUSTOMIZATION/00-index.md` | 新增历史总账阅读规则并记录本轮文档校准 |

### 46.3 验证

```text
git diff --check
make codex-quick-check
```

未验证项：本轮仅修改项目维护文档，未启动或重启服务，未运行前后端业务测试，也未读取 `.env`、真实数据库或供应商凭据。

---

## 47. Research Agent 科研数据库连接器 P0（2026-07-15）

### 47.1 问题与决策

- Research Agent 原有外部能力只有 Tavily 联网搜索，无法以稳定记录 ID、结构化字段和数据库原生语义查询科研文献与化学数据库。P0 新增统一连接器注册表，首批接入 OpenAlex、Crossref、Semantic Scholar、arXiv 和 PubChem。
- 模型只看到三个稳定工具：列出数据库、搜索指定数据库、按原生 ID 读取记录；新增数据库不需要扩张为一组新的模型工具。搜索与读取结果统一为 `external:<database>:<record_id>` 证据 ID，并携带标题、作者、摘要、规范链接、DOI、检索词、检索时间、数据条款和受限原始字段。
- 科研数据库是与 Tavily、跨笔记本发现相互独立的外发能力。API 请求字段 `enable_scientific_databases` 默认 `false`；默认状态下模型不绑定三个工具，工具实现也检查 LangGraph 注入状态，避免旧 checkpoint 或伪造工具调用绕过授权。
- Research 输入区新增“科研数据库”开关，只在 Research Tab 可见，不写入 `localStorage`、会话或数据库。页面初始、创建新 Research 会话以及从其它模式重新进入 Research 时均恢复关闭；每次请求显式发送当前值。
- 连接器使用项目已有 `httpx` 与 Python 标准库，不新增生产依赖或部署服务。共享 HTTP 层提供超时、重试/退避、`Retry-After`、响应体大小限制和服务端 User-Agent；arXiv 额外串行化请求并遵守至少 3 秒的礼貌间隔。
- `OPENALEX_MAILTO`、`CROSSREF_MAILTO` 和 `SEMANTIC_SCHOLAR_API_KEY` 是可选的服务端环境配置；不会返回浏览器、模型工具输出或日志。上游数据许可和 API 条款保持数据库各自口径，不继承应用许可证。
- SSE 新增“确认科研数据库 / 检索科研数据库 / 读取科研记录”三个语义阶段，9 个语言包均使用 i18n 文案。最终综合提示要求保留外部证据 ID，并明确数据库记录、预印本和化学属性不等同于实验验证。

### 47.2 文件索引

| 文件 | 改动 |
|------|------|
| `open_notebook/scientific_connectors/` | 统一类型、注册表、受控 HTTP 客户端及 OpenAlex/Crossref/Semantic Scholar/arXiv/PubChem 适配器 |
| `open_notebook/graphs/scientific_database_tools.py`、`research_agent.py` | 三个归一化工具、双层授权、条件工具绑定和最终证据归并 |
| `api/routers/chat.py`、`prompts/research_agent/system.jinja` | 默认关闭的逐请求字段、LangGraph 状态注入、SSE 阶段、权限与引用规则 |
| `frontend/src/lib/hooks/useNotebookChat.ts`、`types/api.ts`、`chat/notebook-chat-activity.ts` | 非持久化授权状态、请求传播、重置逻辑和活动阶段类型 |
| `frontend/src/components/source/ChatPanel.tsx`、`ChatActivityFeed.tsx`、`ChatColumn.tsx` | Research 专用开关、进度展示和页面接线 |
| `frontend/src/lib/locales/*/index.ts` | 9 个语言包的科研数据库与进度文案 |
| `tests/test_scientific_connectors.py`、`test_research_agent_scope.py` 及对应前端测试 | HTTP 重试、五个适配器、注册表、授权、API、Hook、SSE 和界面行为 |
| `docs/superpowers/specs/2026-07-15-scientific-database-connectors-p0-design.md`、`plans/2026-07-15-scientific-database-connectors-p0-implementation.md` | P0 边界、证据契约、风险控制和实施记录 |

### 47.3 验证

```text
uv run pytest tests/test_scientific_connectors.py tests/test_research_agent_scope.py tests/test_message_history.py -q
36 passed, 1 warning

uv run pytest tests/ -m 'not e2e' -q
356 passed, 33 deselected, 6 warnings

uv run ruff check open_notebook/scientific_connectors open_notebook/graphs/scientific_database_tools.py open_notebook/graphs/research_agent.py api/routers/chat.py tests/test_scientific_connectors.py tests/test_research_agent_scope.py
All checks passed

cd frontend && npm test
192 passed, 9 skipped

cd frontend && npm run lint
exit 0；4 个既有 warning，无 error

cd frontend && npm run build
exit 0；Next.js 生产构建与 TypeScript 检查通过

git diff --check
exit 0
```

登录态浏览器验证：Quick Tab 只显示联网搜索；Research Tab 显示联网搜索、跨笔记本发现、科研数据库三项，科研数据库默认关闭且可开启；切回 Quick 后不可见，再进入 Research 恢复关闭；桌面布局未挤压模型选择器和输入框。

未验证项：自动测试未访问真实 OpenAlex、Crossref、Semantic Scholar、arXiv 或 PubChem 服务，尚未覆盖真实上游限流、地域网络差异和数据字段漂移；未使用真实模型发起一次带科研数据库工具调用的完整 Research 回答，因此外部证据引用质量仍需运行时验收。P0 不包含 UniProt/PDB/Ensembl/ChEMBL、技能运行时、云计算、训练/评估或把外部记录自动保存进笔记本。

---

## 48. Research Agent 精选科研方法 Skills P1（2026-07-19）

### 48.1 问题与决策

- Research Agent 原系统提示只有通用研究步骤，缺少可选择、可版本化和可审阅的方法资产。P1 首批增加 10 个项目自编方法：文献检索与 DOI 核验、证据分级与论文批判、假设生成与竞争性假设、DOE 与统计分析计划、化学身份与性质核验、配方相容性风险矩阵、高温高压与盐水验证设计、放大风险与验证 Gate、科研报告结构化写作、油井水泥外加剂异常诊断。
- Skill 是只读的方法说明，不是可执行插件或事实证据。每个目录只允许 `manifest.json` 与 `SKILL.md`，不运行脚本、不安装依赖、不修改笔记本或来源、不读取凭据、不发起费用操作，也不能启用 Web、科研数据库或跨笔记本权限。
- 每个清单固定 ID、`1.0.0` 版本、分类、短描述、项目来源、MIT 许可证、`approved` 审阅状态、允许工具、顺序和正文 SHA-256。注册表要求恰好 10 个真实目录，并校验字段、重复项、正文 8,000 字符上限、哈希、未知工具、额外文件、符号链接和权限提升/提示注入/依赖安装/命令执行/费用/凭据/写入等危险语句。
- Research 请求新增 `research_skill_mode=auto|off|selected` 与 `research_skill_ids`。`auto` 是默认值，模型常驻上下文只获得目录元数据，按需调用一个只读加载工具，整轮最多 2 个；`selected` 由用户显式选择 1–3 个并在本轮预加载正文；`off` 不暴露目录或正文。服务端拒绝未知、重复、越界以及模式与 ID 不一致的请求。
- 自动限制同时检查单次参数、此前工具轮次和同一模型消息中的并行加载调用，避免用多个工具调用绕过整轮最多 2 个的约束。`allowed_tools` 只与请求实际启用工具取交集，不产生新授权。
- 最终合成将 `load_research_skills` 的方法内容与真实证据工具输出分栏处理。方法只决定分析流程和报告结构，事实结论仍只能引用工具返回的 `[source:*]`、`[note:*]` 或 `[external:*]`；使用方法时回答列出精确 Skill ID、版本和用途。
- Research 输入区新增“科研方法”下拉选择器，支持自动、关闭和显式多选，流式生成时禁用。显式选择只用于当前请求，请求结束后恢复自动；创建新 Research 会话或重新进入 Research 也恢复默认。目录通过相对 `/api/chat/research/skills` 获取，目录响应不含正文。
- 自动加载新增“正在加载科研方法”SSE 活动阶段。选择器、10 个方法名、数量限制和活动文案已进入 9 个现有语言包；未新增生产依赖或部署服务。

### 48.2 文件索引

| 文件 | 改动 |
|------|------|
| `open_notebook/research_skills/` | 只读模型、注册表、安全校验和 10 个固定版本方法目录 |
| `open_notebook/graphs/research_skill_tools.py` | 目录按需加载、整轮数量限制、实际权限交集和非证据输出 |
| `open_notebook/graphs/research_agent.py`、`prompts/research_agent/system.jinja` | 模式化目录/正文注入、条件工具绑定、方法与证据分离及版本披露 |
| `api/routers/chat.py` | 目录 GET 接口、Research 请求严格校验、state 传播、日志和 SSE 阶段 |
| `pyproject.toml` | 将 Skill 清单与 Markdown 正文纳入 Python 包数据 |
| `frontend/src/components/source/ResearchSkillSelector.tsx`、`ChatPanel.tsx`、`ChatActivityFeed.tsx` | Research 方法选择器、数量限制、生成期禁用和活动展示 |
| `frontend/src/lib/hooks/useNotebookChat.ts`、`api/chat.ts`、`types/api.ts`、`chat/notebook-chat-activity.ts` | 相对 API 目录读取、一次性选择状态、请求传播、自动恢复和阶段类型 |
| `frontend/src/lib/locales/*/index.ts` | 9 个语言包的模式、方法名、限制和进度文案 |
| `tests/test_research_skills.py`、`test_research_agent_scope.py` 及对应前端测试 | 注册表篡改/危险内容/额外文件、自动与显式限制、权限交集、证据分离、API、Hook 和 UI 覆盖 |
| `docs/superpowers/specs/2026-07-19-curated-research-method-skills-p1-design.md`、`plans/2026-07-19-curated-research-method-skills-p1-implementation.md` | 产品场景、安全边界、交互、架构、风险和实施记录 |

### 48.3 验证

```text
uv run python -c "<加载注册表并打印 10 个 Skill 的顺序、ID 和正文长度>"
10 个 Skill 全部加载；正文长度 638–839 字符

uv run python -c "<渲染 selected 模式 Research Agent 系统提示>"
exit 0；生成 3875 字符提示

uv run pytest tests/test_research_skills.py tests/test_research_agent_scope.py -q
33 passed, 1 warning

uv run pytest tests/ -m 'not e2e' -q
368 passed, 33 deselected, 6 warnings

uv run ruff check open_notebook/research_skills open_notebook/graphs/research_skill_tools.py open_notebook/graphs/research_agent.py api/routers/chat.py tests/test_research_skills.py tests/test_research_agent_scope.py
All checks passed

cd frontend && npm test -- --run src/lib/api/chat.test.ts src/components/source/ResearchSkillSelector.test.tsx src/components/source/ChatPanel.test.tsx src/lib/hooks/useNotebookChat.test.tsx 'src/app/(dashboard)/notebooks/components/ChatColumn.test.tsx'
60 passed

cd frontend && npm test
196 passed, 9 skipped

cd frontend && npx eslint <本轮前端文件与 9 个 locale>
exit 0

cd frontend && npm run lint
exit 0；4 个既有 warning，无 error

cd frontend && npm run build
exit 0；Next.js 生产构建与 TypeScript 检查通过

git diff --check
exit 0
```

未验证项：尚未在真实登录态浏览器中完成选择器的桌面端/窄屏视觉和键盘操作验收；尚未使用真实模型分别完成一次 `auto` 自动加载和 `selected` 显式方法的完整 Research 回答，因此真实模型的选法准确性、最终“本轮科研方法”披露质量及方法对回答质量的提升仍需手工验证。Skill 本身不访问外部数据库，本轮未重复 P0 的真实上游联网测试。

---

## 49. Token 用量页翻译访问保护误报修复（2026-07-19）

### 49.1 问题与决策

- Token 用量页会展示最多 50 条近期调用记录。旧实现每渲染一行都会重新构造包含 14 个工作流名称的翻译映射，因此单次满页渲染会重复读取 `t.usage` 数百次；Next.js 开发环境在一秒窗口内重复渲染时，可能超过 `useTranslation` 的 1,000 次访问保护阈值并报告 `INFINITE LOOP DETECTED on key: "usage"`。
- 该现象是页面侧重复解析翻译命名空间造成的保护误报，不是真实递归，也不是语言包缺少 `usage` 字段。保留全局保护器及其阈值，避免用放宽保护掩盖页面热点。
- PR #49 首轮只缓存了工作流标签映射，虽然一次满页测试把 `t.usage` 访问从 830 次降到 250 次以内，但来源/状态、统计卡、日期序列和按密钥统计仍直接访问 Proxy；真实 Next.js 开发环境连续重渲染后仍会越过阈值。保护器随后把对象节点替换成字符串 `"usage"`，使 `failedCalls` 或 `callsCount` 变为 `undefined`，最终在 `.replace()` 处触发页面崩溃。
- 后续修复改为通过 `t('usage', { returnObjects: true })` 一次性取得普通翻译对象，页面、列表和工作流标签全部读取该快照；不再存在 `t.usage` 属性链，未知工作流继续使用既有 `surfaceUnknown` i18n 文案，没有新增硬编码可见文本。
- 回归测试使用 API 真实上限的 50 条近期记录并连续重渲染 11 次。首轮修复在该场景仍产生 1,431 次 `t.usage` 属性访问；最终实现要求属性访问为 0、完整翻译对象只解析 1 次。

### 49.2 文件索引

| 文件 | 改动 |
|------|------|
| `frontend/src/app/(dashboard)/usage/page.tsx` | 一次性解析完整 `usage` 翻译对象，页面和列表不再直接遍历翻译 Proxy |
| `frontend/src/app/(dashboard)/usage/page.test.tsx` | 增加 50 条近期记录、连续 11 次渲染和对象/属性访问次数回归测试 |

### 49.3 验证

```text
cd frontend && npm test -- --run 'src/app/(dashboard)/usage/page.test.tsx'
3 passed

cd frontend && npx eslint 'src/app/(dashboard)/usage/page.tsx' 'src/app/(dashboard)/usage/page.test.tsx'
exit 0

cd frontend && npm test
197 passed, 9 skipped

cd frontend && npm run lint
exit 0；4 个既有 warning，无 error

cd frontend && npm run build
exit 0；Next.js 生产构建与 TypeScript 检查通过

git diff --check
exit 0
```

登录态浏览器验证：真实 `/usage` 30 天页面成功展示汇总卡、按密钥统计和最近 50 条记录；依次切换 7 天、90 天、30 天均正常完成重渲染，期间没有新增控制台错误，也未重新出现 Next.js 错误弹层。

未验证项：本轮保留了全局 `useTranslation` Proxy 及其 1,000 次保护阈值，没有扩展审计其它页面是否存在相同的高频属性访问；如后续在其它路由出现相同 key 的保护误报，应单独评估全局翻译访问接口，而不是继续提高阈值。

---

## 50. Next.js 开发进程风暴防复发（2026-07-30）

### 50.1 事故与根因边界

- 本机执行 `make start-all` 后，`frontend/package.json` 的 `next dev` 在 Next.js 16.1.7 下默认启用 Turbopack。Turbopack 检测到多个 lockfile，并错误选择 `/Users/leiwng/package-lock.json` 所在的家目录作为工作区根，而不是项目的 `frontend` 目录。
- `logs/frontend.log` 随后从错误根目录解析 `tailwindcss`，在 15:05:45–15:18:05 之间重复报告 1,177 次模块解析失败。WindowServer stackshot 在 15:18:38 记录到 6,458 个 Node 进程，累计 RSS 约 305.10 GiB；其中 6,456 个与 cmux 同属一个 Jetsam/resource coalition。`cmux` 自身约 229.6 MiB，`make` 自身约 1.4 MiB，系统弹窗中的 cmux 304 GB 是子进程资源归集，不是 cmux 单进程占用。
- 15:18:57 的 Jetsam 报告只剩约 247.5 MiB 可用内存，总进程数为 13,053；WindowServer 主线程同时已 40 秒没有响应。现有证据足以确认 Next/Turbopack Node 进程风暴是系统失去响应的直接资源原因，不支持 Docker、API、worker、过热或硬件故障作为主因。
- 累计 RSS 会重复计算共享页面，不等于真实独占物理内存。系统诊断没有保留完整父 PID/argv/Turbopack trace，因此“错误解析如何被放大为数千 worker”的内部重试或重生机制仍未百分之百确认。本轮明确不在主力机器上复现 Turbopack 故障。

### 50.2 修复决策

- 默认开发命令从 `next dev` 改为 `next dev --webpack`。`make run`、`make frontend` 和 `make start-all` 都通过该 npm script 启动，因此三个入口统一退出 Next 16 默认 Turbopack。
- `next.config.ts` 同时把 `turbopack.root` 固定为配置文件所在的绝对 `frontend` 目录。该设置在默认 Webpack 开发路径中不参与执行，只保护未来显式启用 Turbopack 的场景不再受家目录 lockfile 影响。
- 新增配置回归测试，分别锁定默认开发 bundler 和 Turbopack 根目录。没有新增依赖、可见前端文案、API、数据库 migration 或部署服务。
- 家目录的 `package.json`、`package-lock.json` 和 `node_modules` 属于独立的 `docx` 工具环境，本轮不移动或删除；项目修复不再依赖机器级清理。

### 50.3 文件索引

| 文件 | 改动 |
|------|------|
| `frontend/package.json` | 默认开发服务器固定使用 `next dev --webpack` |
| `frontend/next.config.ts` | 显式 Turbopack 运行固定使用绝对 `frontend` 根目录 |
| `frontend/next.config.test.ts` | 覆盖 Webpack 默认值与 Turbopack 根目录 |
| `docs/8-CUSTOMIZATION/00-index.md` | 记录事故证据、根因边界、修复、验证与未尽事项 |

### 50.4 验证

```text
cd frontend && npm test -- --run next.config.test.ts
4 passed

cd frontend && npx eslint next.config.ts next.config.test.ts
exit 0

cd frontend && NODE_OPTIONS=--no-experimental-webstorage npm test
199 passed, 9 skipped

cd frontend && npm run lint
exit 0；4 个既有 warning，无 error

cd frontend && npm run build
Next.js 16.1.7 (webpack)；生产构建与 TypeScript 检查通过

cd frontend && INTERNAL_API_URL=http://127.0.0.1:5056 npm run dev -- -H 127.0.0.1 -p 3101
Next.js 16.1.7 (webpack)；1.188 秒 Ready

curl --max-time 10 http://127.0.0.1:3101/login
HTTP 200

lsof -nP -iTCP:3101 -sTCP:LISTEN
仅 1 个 Node 监听进程；烟测后 Ctrl+C 正常停止且端口释放

memory_pressure -Q
System-wide memory free percentage: 95%

git diff --check
exit 0
```

当前机器使用 Node 26.5.0。直接执行 `npm test` 时，Node 实验性 Web Storage 全局会覆盖 jsdom 的 `localStorage`，导致依赖存储的既有测试在初始化阶段失败；仅对测试进程设置 `NODE_OPTIONS=--no-experimental-webstorage` 后全部通过。该环境兼容问题与本轮启动配置无关，没有借机扩展修复范围。

未验证项：没有重新执行 `make start-all`，没有启动 Turbopack，也没有生成 `NEXT_TURBOPACK_TRACING` 复现 trace；这是防止主力机器再次失去响应的明确安全边界。受控烟测只验证 Webpack 前端启动、页面编译、HTTP 响应、单监听进程和停止清理，没有联动 API、worker、数据库或登录后的完整业务流程。

---

## 51. Chat 真实模型流与首个输出观测（2026-07-31）

### 51.1 问题与实现边界

- Quick Chat、Research Agent 和 Source Chat 已通过 `streaming=True` 配置模型，并由 LangGraph `astream_events(version="v2")` 转发 `on_chat_model_stream` / `on_llm_stream`；前端也已用 `ReadableStream` 和 `TextDecoder` 增量消费 SSE。三个接口均返回 `X-Accel-Buffering: no`，因此不需要改变浏览器 API 路由或部署拓扑。
- 原后端在没有收到模型 chunk 时，会在 `on_chat_model_end` 或 LangGraph 最终状态中取得完整答案，再按每 50 字符拆分成多条 `ai_message`。这只能模拟视觉打字效果，不能改善真实首字时间，还会把不支持流式的供应商误报成流式。
- 本轮保留 Lumiton 已验证的 `streaming=True`、`astream_events`、立即下发模型 chunk 和首 token 计时思路；不沿用其仍存在的 50 字符伪切片回退。

### 51.2 协议与可观测性

- 模型实时 chunk 立即发送为 `ai_message`，并标记 `stream_mode="delta"`。
- 如果供应商或适配器没有产生任何 stream event，只在模型结束时发送一次完整 `ai_message`，并标记 `stream_mode="buffered"`；不再人为切片或插入延迟。
- 前端继续按既有 `ai_message.content` 拼接，不新增文案、状态或持久化字段；`stream_mode` 是向后兼容的诊断字段。
- Quick Chat / Research Agent 的 `first_ai_chunk` 日志增加 `stream_mode`；Source Chat 增加不记录回答正文的 `first_ai_output` 日志，包含 session/source、耗时、首块字符数和 stream mode。远程验收可据此区分真实 TTFT 与整段回退。

### 51.3 文件索引

| 文件 | 改动 |
|------|------|
| `api/routers/chat.py` | 真实 delta 与单次 buffered 回退；首块日志增加 stream mode |
| `api/routers/source_chat.py` | 统一内容过滤与 SSE 输出；删除伪切片；增加首输出耗时日志 |
| `tests/test_real_streaming_sse.py` | 覆盖 Chat/Source Chat 的真实 delta 和完整 buffered 回退 |

### 51.4 验证

```text
.venv/bin/python -m pytest tests/test_real_streaming_sse.py tests/test_chat_heartbeat_sse.py tests/test_source_chat_heartbeat_sse.py -q
16 passed

.venv/bin/python -m ruff check api/routers/chat.py api/routers/source_chat.py tests/test_real_streaming_sse.py
All checks passed

.venv/bin/python -m pytest tests/test_real_streaming_sse.py tests/test_chat_heartbeat_sse.py tests/test_source_chat_heartbeat_sse.py tests/test_chat_suggestions_sse.py tests/test_chat_observability.py tests/test_research_agent_scope.py tests/test_message_history.py tests/test_graphs.py -q
70 passed

.venv/bin/python -m pytest tests/ -m "not e2e" -q
371 passed, 33 deselected

.venv/bin/python -m ruff format --check tests/test_real_streaming_sse.py
1 file already formatted

git diff --check
exit 0
```

未验证项：开发机没有发送新的真实供应商模型请求。真实 provider 首字时间、`stream_mode` 和代理分流将在用户 Mac Studio 上结合服务端日志与浏览器逐项验收；若某个 provider 始终为 `buffered`，再以该 provider 的实测证据检查 Esperanto/LangChain 适配层，不在本轮预先修改所有供应商。

---

## 52. Ask 最终综合答案真实流式（2026-07-31）

### 52.1 实现

- Ask 的策略 reasoning 原已转发模型 chunk，但 `write_final_answer` 只在节点结束后发送完整 `final_answer`，所以最终综合阶段虽然显示“正在撰写”，正文没有真实增量。
- 最终答案模型显式启用 `streaming=True`。`write_final_answer` 的真实模型 chunk 立即发送为 `final_answer_delta`，前端逐块追加；首块到达时立即进入 writing 阶段。
- 节点完成后继续发送既有 `final_answer`，用清理后的完整结果覆盖增量草稿。旧客户端仍可只消费 `final_answer`，新客户端不会因最终事件重复追加内容。
- 没有模型 chunk 时不伪造流式，只发送一次 `final_answer` 并标记 `stream_mode="buffered"`；有真实 chunk 时 delta 与最终规范事件均标记 `stream_mode="delta"`。
- 服务端记录 `first_final_answer_output` 的耗时、首块字符数和 stream mode，不记录问题、检索证据或答案正文。检索策略、逐查询答案、覆盖率、心跳、超时、历史记录与最终 complete 契约保持不变。

### 52.2 文件索引

| 文件 | 改动 |
|------|------|
| `open_notebook/graphs/ask.py` | 最终综合模型显式启用 streaming |
| `api/routers/search.py` | 转发最终答案 delta、规范最终值与首输出日志 |
| `frontend/src/lib/hooks/use-ask.ts` | 增量追加 `final_answer_delta`，最终值仍覆盖 |
| `frontend/src/lib/types/search.ts` | Ask SSE 类型增加 delta 与 stream mode |
| `tests/test_ask_heartbeat_sse.py`、`frontend/src/lib/hooks/use-ask.test.tsx` | 覆盖真实 delta、buffered 回退和最终覆盖不重复 |

### 52.3 验证

```text
.venv/bin/python -m pytest tests/test_ask_heartbeat_sse.py -q
4 passed

.venv/bin/python -m ruff check api/routers/search.py open_notebook/graphs/ask.py tests/test_ask_heartbeat_sse.py
All checks passed

cd frontend && NODE_OPTIONS=--no-experimental-webstorage npm test -- --run src/lib/hooks/use-ask.test.tsx
5 passed

cd frontend && npx eslint src/lib/hooks/use-ask.ts src/lib/hooks/use-ask.test.tsx src/lib/types/search.ts
exit 0

.venv/bin/python -m pytest tests/ -m "not e2e" -q
371 passed, 33 deselected

cd frontend && NODE_OPTIONS=--no-experimental-webstorage npm test
199 passed, 9 skipped

cd frontend && npm run lint
exit 0；4 个既有 warning，无 error

cd frontend && npm run build
exit 0；Next.js 16.1.7 Webpack 生产构建与 TypeScript 检查通过

git diff --check
exit 0
```

未验证项：开发机未发送真实 Ask 模型请求。用户 Mac Studio 验收需同时观察页面逐字出现、SSE `final_answer_delta`、服务端 `stream_mode=delta` 与首输出耗时；特定供应商若只返回 buffered，再单独检查 provider 适配层。

---

## 53. 有效 Chat 流式透传与安全推理状态（2026-07-31）

### 53.1 二次定位与根因修正

- §51–52 已确认后端能够产生真实模型 delta，但开发机录屏仍表现为长时间等待后整段出现。对同一请求的服务端日志显示，首个 `ai_message` 在约 13.5 秒产生、模型约 65.7 秒结束、请求约 73.7 秒完成；页面却直到接近请求结束才显示正文，说明剩余阻塞位于 API 到浏览器之间，而不是模型或 LangGraph 内部。
- 使用一个每 500 ms 发送一次、共 4 次事件的无模型 SSE 探针复核：直接请求 FastAPI 时到达时间约为 523 / 1017 / 1518 / 2019 ms；经过 Next.js 16 通用 `rewrites()` 的 `/api` 代理时，4 个事件同时在约 2023 ms 到达。由此确认通用 rewrite 在当前运行时组合中缓冲了 SSE 响应。
- §51 中“已有 `X-Accel-Buffering: no`，因此不需要改变浏览器 API 路由”的判断不完整：该响应头无法阻止 Next.js 通用 rewrite 自身的缓冲。本轮不改变浏览器相对 `/api` 契约，也不改变部署拓扑；仅由四个精确 Route Handler 接管流式 POST，其它 `/api/*` 继续使用既有 rewrite。
- 相同探针经过定向 Route Handler 后，到达时间约为 1235 / 1724 / 2224 / 2728 ms；首块包含开发环境约 685 ms 的路由编译时间，之后三个间隔为 489 / 500 / 504 ms，证明数据在上游连接尚未结束时已逐块抵达浏览器侧代理。

### 53.2 安全推理与答案边界

- 部分推理模型通过 `reasoning_content` 等 provider metadata 返回推理过程，另一些模型把推理包在正文 `<think>...</think>` 中。二者均不得作为 `ai_message` 暴露、拼入最终回答、计入首个可见答案、写入聊天 transcript 或记录到日志。
- 首次检测到推理时，后端只发送不含正文的 `reasoning_status`：`{"type":"reasoning_status","status":"active"}`。前端复用现有 i18n 活动文案与 `synthesizing` 阶段展示“正在组织回答”，不新增或硬编码可见文案。
- `SafeModelContentStream` 在服务端累计 provider 内容并只发出新增的安全可见部分。过滤器会保留可能尚未完成的 `<think>` / `</think>` 标签前缀，因此标签即使跨多个 chunk 拆分，也不会提前泄漏；无真实 stream event 的 buffered 回退同样先进行规范过滤。
- `first_ai_chunk` / `first_ai_output`、`stream_mode`、前端首个 AI 气泡和 transcript 持久化现在都以首个公开答案 delta 为准，而不是 provider 推理 token。Source Chat 与 Notebook Quick/Research Chat 使用同一安全边界。

### 53.3 文件索引

| 文件 | 改动 |
|------|------|
| `frontend/src/lib/server/sse-proxy.ts` | 流式 POST 透传、认证/追踪头转发、禁用缓存和代理缓冲 |
| `frontend/src/app/api/chat/execute/route.ts`、`chat/research/execute/route.ts` | Quick Chat / Research Agent 定向 SSE Route Handler |
| `frontend/src/app/api/search/ask/route.ts` | Ask 定向 SSE Route Handler |
| `frontend/src/app/api/sources/[sourceId]/chat/sessions/[sessionId]/messages/route.ts` | Source Chat 动态路径定向 SSE Route Handler |
| `api/sse_helpers.py` | 安全推理状态、provider metadata 识别和跨 chunk `<think>` 过滤 |
| `api/routers/chat.py`、`api/routers/source_chat.py` | 推理/答案分流，只传输和持久化公开答案 |
| `frontend/src/lib/hooks/useNotebookChat.ts`、`useSourceChat.ts`、`types/api.ts` | 消费安全推理状态并复用既有活动 UI |
| `tests/test_sse_helpers.py`、`test_real_streaming_sse.py` 及对应前端测试 | 跨 chunk 防泄漏、协议顺序、真实透传和 UI 状态回归 |

### 53.4 验证

```text
无模型 SSE 探针，FastAPI 直连
4 个事件到达：523 / 1017 / 1518 / 2019 ms

无模型 SSE 探针，Next.js 通用 rewrite（修复前）
4 个事件均在约 2023 ms 到达，确认整段缓冲

无模型 SSE 探针，定向 Route Handler（修复后）
4 个事件到达：1235 / 1724 / 2224 / 2728 ms；后续间隔 489 / 500 / 504 ms

.venv/bin/python -m pytest tests/test_sse_helpers.py tests/test_real_streaming_sse.py tests/test_chat_heartbeat_sse.py tests/test_source_chat_heartbeat_sse.py tests/test_ask_heartbeat_sse.py tests/test_chat_suggestions_sse.py tests/test_chat_observability.py -q
48 passed, 1 warning

.venv/bin/python -m ruff check api/sse_helpers.py api/routers/chat.py api/routers/source_chat.py tests/test_sse_helpers.py tests/test_real_streaming_sse.py
All checks passed

.venv/bin/python -m pytest tests/ -m "not e2e" -q
378 passed, 33 deselected, 6 warnings

cd frontend && NODE_OPTIONS=--no-experimental-webstorage npm test -- --run
202 passed, 9 skipped

cd frontend && npm run lint
exit 0；4 个既有 warning，无 error

cd frontend && npm run build
exit 0

git diff --check
exit 0
```

---

## 67. 推理模型 reasoning_content 提取：思考期不再"干等"（新增 2026-08-04）

### 67.1 问题

- deepseek-v4-pro 等推理模型在产出可见文字前会流出大量 `reasoning_content`（思考链）。Esperanto 对所有 OpenAI-compatible 供应商统一返回 `ChatOpenAI`，而 `langchain_openai` 明确不提取第三方 `reasoning_content` 字段（见其 base.py 文档），导致思考内容被丢弃。
- 结果：SSE 流在整个思考期（实测 20-40s）只发心跳，`reasoning_status` 事件不触发，前端无任何"思考中"提示，用户感知为首返极慢。

### 67.2 修复

- 新增 `open_notebook/ai/reasoning_chat.py`：`ReasoningAwareChatOpenAI(ChatOpenAI)` 覆写 `_convert_chunk_to_generation_chunk`（流式）与 `_create_chat_result`（非流式），从 delta/message 提取 `reasoning_content`/`reasoning` 写入 `additional_kwargs["reasoning_content"]`；`maybe_make_reasoning_aware()` 对 `ChatOpenAI` 实例做 class-swap（无新增字段，安全）。
- `open_notebook/ai/provision.py`：`provision_langchain_model_with_info` 与 `provision_langchain_model` 在 `model.to_langchain()` 后、`attach_usage_callback` 前调用 `maybe_make_reasoning_aware()`，一处覆盖全部 13 个语言模型。
- 现有 `api/sse_helpers.py extract_reasoning_content()` 已查 `additional_kwargs.reasoning_content`，无需改动即生效。

### 67.3 验证

- `ruff check` 通过；`tests/test_graphs.py + test_utils.py + test_models_api.py` 49 条通过。
- 单元式验证：流式 chunk 与非流式响应均正确提取 `reasoning_content`；普通内容 chunk 不误判；`model_copy()` 保留 swap 后的类；`extract_reasoning_content` 可读到提取结果。

---

## 68. 询问与搜索页崩溃修复：分数空值 + i18n 循环检测误报（新增 2026-08-04）

### 68.1 问题

- `/search` 页两类错误（与 §67 后端改动无关，前端既有 bug）：
  - **(A) 硬崩溃**：文本/子串搜索结果只带 `relevance` 不带 `final_score`（见 §63 子串兜底 SQL），`result.final_score.toFixed(2)` 抛 `TypeError` → React ErrorBoundary（"Error / Please try refreshing"）。
  - **(B) dev 弹层**：结果 `.map()` 每条访问 `t.searchPage.matches`（2 次 Proxy get），100 条 × StrictMode/重渲染在 1s 内超过 `use-translation.ts` 的 1000 阈值 → `console.error` 触发 Next dev 全屏弹层（"INFINITE LOOP DETECTED on key: searchPage"），属误报。

### 68.2 修复

- `frontend/src/app/(dashboard)/search/page.tsx`：
  - 分数 Badge 安全化：`const score = result.final_score ?? result.relevance ?? result.similarity ?? result.score`，仅当 `typeof score === 'number' && !Number.isNaN(score)` 时渲染 `score.toFixed(2)`。
  - 将 `t.searchPage.matches` 提升为循环外 `matchesTemplate`，map 内复用，消除每条结果的 Proxy get。
- `frontend/src/lib/hooks/use-translation.ts`：循环检测阈值 `1000`→`5000`，`console.error`→`console.warn`（保留防护但不再级联 dev 弹层）。

### 68.3 验证

- `npx tsc --noEmit` 对改动两文件无错（既有错误均在无关测试文件）。
- `vitest run src/components/search/StreamingResponse.test.tsx` 7 通过；`use-translation.test.ts` 2 通过。
- `npx eslint` 对两文件 0 错。

未验证项：开发机没有在修复后再次消耗真实 provider 配额，也尚未补录登录态浏览器对比视频。下一步本机验收应同时观察正文逐块出现、活动状态从“正在组织回答”切换到模型输出、页面自动滚动及服务端首个公开答案耗时；用户 Mac Studio 部署后还需确认其外层代理没有重新缓冲 `text/event-stream`。特定 provider 若始终只产生 `stream_mode=buffered`，再依据该 provider 的实测事件检查 Esperanto/LangChain 适配层。

### 53.5 本机验收后的状态与滚动修正

- 本机真实模型验收确认正文已经逐块输出，但暴露出两个独立问题。`make status` 的 API 项原来通过 macOS `pgrep` 检查 `run_api.py\|uvicorn api.main:app`；`pgrep` 使用扩展正则，转义后的 `\|` 被当成字面量，因此即使 5056 已有 API 监听也会误报 `Not running`。状态检查现改为请求启动流程已经使用的 `http://127.0.0.1:5056/api/config`，报告的是 API 真实可用性，而不是易受父进程命令行影响的进程名。
- ChatPanel 原有自动滚动只在 React `messages` 数组变化时安排一次滚动。真实 token 流持续更新 Markdown 时，内容实际高度可能在该次 effect 之后继续变化，视口因此停留在旧底部，需要用户滚轮才能看到最新输出。
- ChatPanel 现在使用 `ResizeObserver` 监听消息内容容器的真实高度。流式期间、且用户仍停留在自动跟随模式时，每次高度增长都把局部聊天视口推进到最新内容；用户主动向上滚动后立即停止跟随，回到底部后才恢复，避免阅读历史时被强制拉走。
- 没有新增前端文案、依赖、API 契约或部署拓扑。该滚动修复同时覆盖 Notebook Quick/Research Chat 和 Source Chat，因为三者共用 `ChatPanel`。

补充验证：

```text
make status
Database / API Backend / Background Worker / Next.js Frontend 均显示 Running

.venv/bin/python -m pytest tests/test_makefile_logging.py -q
5 passed

cd frontend && NODE_OPTIONS=--no-experimental-webstorage npm test -- --run src/components/source/ChatPanel.test.tsx
29 passed

cd frontend && NODE_OPTIONS=--no-experimental-webstorage npm test -- --run
204 passed, 9 skipped

cd frontend && npx eslint src/components/source/ChatPanel.tsx src/components/source/ChatPanel.test.tsx
exit 0

cd frontend && npm run build
exit 0；Next.js 16.1.7 Webpack 生产构建与 TypeScript 检查通过
```

未验证项：`make status` 已在当前真实服务进程上复核；ResizeObserver 的跟随与用户上滚保护已有组件回归测试，但仍需用户在当前登录态页面再发送一次长回答，确认实际浏览器视口能够持续跟上输出。

---

## 54. DeepSeek V4 Flash 上下文上限与引用摘要归组（2026-08-01）

### 54.1 问题与决策

- 本机切换到 `deepseek-v4-flash` 后，Quick Chat 摘要右侧显示“未配置上下文上限”；同一位置使用 `deepseek-v4-pro` 时能正常显示当前 payload、1M 上限和百分比。数据库实查确认 Flash 模型记录的 `provider=deepseek`、管理员覆盖字段为 `null`，不是前端模型 ID 匹配失败。
- 根因是第 43 节实施时只把 `deepseek/deepseek-v4-pro = 1,000,000` 加入内置白名单。DeepSeek 当前官方 Models & Pricing 文档已经明确 V4-Flash 与 V4-Pro 的 Context Length 均为 1M，因此本轮把 `deepseek-v4-flash` 同样加入已确认的内置值；管理员正整数覆盖仍保持最高优先级，未知模型继续不猜测。官方依据：`https://api-docs.deepseek.com/quick_start/pricing/`。
- Quick 摘要原为三列：左侧来源/笔记类型数量、中间所选内容总词元、右侧模型 payload/窗口。所选总词元与三类数量属于同一份引用选择统计，本轮按用户反馈把词元尾随在数量徽标之后；外层收敛为左右两列，右侧模型窗口用量语义不变。
- 移动后的词元仍使用既有 `sources.contextTokens` i18n 文案和 K/M 格式；没有新增可见文本、依赖、API、数据库迁移或部署拓扑。Quick/Research 的数据边界、上下文构建和 `context_usage` SSE 均未改变。

### 54.2 文件索引

| 文件 | 改动 |
|------|------|
| `open_notebook/ai/model_context.py` | 增加已由官方确认的 DeepSeek V4 Flash 1M 内置窗口 |
| `tests/test_model_context.py` | 同时覆盖 Flash/Pro、大小写规范化和管理员覆盖优先级 |
| `frontend/src/components/common/ContextIndicator.tsx` | 词元总量归入来源/笔记数量组，三列改为左右两列 |
| `frontend/src/components/common/ContextIndicator.test.tsx` | 锁定词元 DOM 归属、元素顺序、窗口用量和首次提问状态 |

### 54.3 验证

```text
当前数据库 deepseek-v4-flash 记录只读实查
provider=deepseek；configured=null；effective=[1000000, builtin]

.venv/bin/python -m pytest tests/test_model_context.py tests/test_models_api.py tests/test_message_history.py tests/test_chat_heartbeat_sse.py -q
37 passed, 6 warnings

.venv/bin/python -m ruff check open_notebook/ai/model_context.py tests/test_model_context.py
All checks passed

cd frontend && NODE_OPTIONS=--no-experimental-webstorage npm test -- --run src/components/common/ContextIndicator.test.tsx 'src/app/(dashboard)/notebooks/components/ChatColumn.test.tsx'
4 passed

cd frontend && NODE_OPTIONS=--no-experimental-webstorage npm test -- --run
204 passed, 9 skipped

cd frontend && npm run lint
exit 0；4 个既有 warning，无 error

cd frontend && npm run build
exit 0；Next.js 16.1.7 Webpack 生产构建与 TypeScript 检查通过

git diff --check
exit 0
```

未验证项：后端热重载与真实模型记录的有效窗口解析已经验证；生产构建也已通过。仍需用户强制刷新当前登录态页面，确认 Flash 右侧显示 `≈已用 / 1M`，并视觉确认所选词元已紧跟引用类型数量、摘要在实际窗口宽度下没有拥挤或换行异常。

---

## 55. 模型测试时自动保存上下文窗口元数据（2026-08-01）

### 55.1 边界与决策

- 最小生成请求只能证明模型可调用，成功响应通常不携带模型上下文上限。本轮没有通过逐步发送超长 prompt 来试探限制，避免额外费用、限流和生产服务压力。
- 单模型测试成功后，再读取供应商明确提供的模型元数据：Google Gemini 使用 `inputTokenLimit`，OpenRouter 使用 `context_length`，Mistral 使用 `max_context_length`，Ollama 使用 `/api/show` 返回的架构级 `*.context_length`；OpenAI-compatible / Azure 等兼容接口仅在返回已知的显式字段时采用。供应商没有返回可靠字段时，才使用项目中已经由官方文档核验的内置目录；其余模型继续保持未知，不根据名称猜测。
- `model.context_window_tokens` 新增配套来源字段 `context_window_source`。管理员手工填写标为 `configured`，供应商元数据标为 `provider`，已核验内置目录标为 `builtin`。单模型测试可以刷新此前的 `provider` / `builtin` 自动值，但绝不覆盖 `configured` 手工值；旧记录只有数值、没有来源时按手工配置处理，保持向后兼容。
- 通过凭据发现并注册模型时，如果发现响应已经包含上下文上限，会在创建模型记录时一并保存。手工输入的自定义模型没有可靠元数据，仍保存为空，等待单模型测试或管理员填写。
- 测试结果弹窗现在显示有效上下文上限；本次自动写入时显示 i18n 提示。若测试成功但供应商、内置目录均没有可确认值，则明确沿用“未配置上下文上限”。

### 55.2 文件索引

| 文件 | 改动 |
|------|------|
| `open_notebook/ai/model_context.py` | 统一解析供应商显式字段、内置目录和 `configured/provider/builtin` 来源优先级 |
| `api/credentials_service.py`、`open_notebook/ai/model_discovery.py` | 凭据发现、Ollama 详情读取、单模型元数据刷新与注册时保存 |
| `open_notebook/ai/models.py`、`open_notebook/database/migrations/30*.surrealql` | 持久化上下文窗口来源并保持旧记录兼容 |
| `api/models.py`、`api/routers/credentials.py`、`api/routers/models.py` | 扩展发现、注册和单模型测试响应契约 |
| `frontend/src/components/settings/ModelTestResultDialog.tsx`、模型/凭据 API 类型与 hooks | 显示测试取得的窗口并在保存后刷新模型列表 |
| `frontend/src/lib/locales/*/index.ts` | 九种语言的自动保存提示 |
| `tests/test_model_context.py`、`ModelTestResultDialog.test.tsx` | 显式字段解析、来源优先级、手工值保护和结果 UI 回归 |

### 55.3 验证

```text
.venv/bin/python -m ruff check api/credentials_service.py api/models.py api/routers/credentials.py api/routers/models.py open_notebook/ai/model_context.py open_notebook/ai/model_discovery.py open_notebook/ai/models.py tests/test_model_context.py
All checks passed

.venv/bin/python -m pytest tests/test_model_context.py tests/test_models_api.py -q
29 passed, 6 warnings

.venv/bin/python -m pytest tests/ -m "not e2e" -q
390 passed, 33 deselected, 6 warnings

cd frontend && NODE_OPTIONS=--no-experimental-webstorage npm test -- --run
206 passed, 9 skipped

cd frontend && npm run lint
exit 0；4 个既有 warning，无 error

cd frontend && npm run build
exit 0；Next.js 16.1.7 Webpack 生产构建与 TypeScript 检查通过
```

未验证项：当前测试没有消耗真实供应商配额，也没有直接修改现有生产模型记录。API 重启后会自动应用第 30 号迁移；本机验收时应分别测试一个会返回元数据的模型和一个不返回元数据的模型，并确认手工填写的窗口不会被后续测试覆盖。

---

## 56. 可迁移的模型上下文目录与启动补齐（2026-08-01）

### 56.1 目录范围与优先级

- 新增随代码发布的 `model_context_catalog.json`，按模型原始开发商分组，记录精确模型 ID / 别名、语言模型上下文值、取值依据、核验日期和官方资料地址。初始目录覆盖本机已配置的 GLM、Qwen、DeepSeek、MiniMax、Gemma、Intern、Doubao、StepFun 语言模型，并补充 Gemini 2.5 及之后的通用生成模型。
- 目录值的取值依据分为 `official` 与 `default`：官网能确认上下文限制时写入官网值；已经检查官网但仍无法确认限制的模型写入统一 256K（262,144）缺省值。当前 Intern-S1-Pro 和三个 Doubao Seed 2.0 路由按 `default` 登记。此规则是目录维护时的人工官网核验结果，不以运行时模型 API 查询失败作为判定条件。
- 目录只做精确 ID / 别名匹配，不按名称片段猜测任意未知模型。`text-embedding-v4` 属于嵌入模型、`doubao-seedance-2-0-fast-260128` 属于视频生成模型，均不参与对话上下文窗口配置。
- 有效值优先级保持为：管理员手工值 `configured` > 模型测试取得的供应商元数据 `provider` > 随代码发布的目录值 `builtin`。供应商测试可刷新旧的 `provider` / `builtin` 自动值，但永不覆盖手工值；旧记录有数值但没有来源时继续按手工值保护。
- 智谱官方当前明确标注 `GLM-5.2` 原生窗口为 1M，因此目录直接登记 1,000,000，不套用 256K 缺省值。

### 56.2 启动、创建与迁移语义

- API 完成数据库迁移后扫描现有的语言模型记录。只对 `context_window_tokens` 为空且目录精确命中的记录写入 `builtin` 值；已有值不更新，未命中不处理，也绝不根据目录创建新的模型或凭据记录。重复启动因此是幂等的。
- 手工创建模型、凭据发现后注册模型、供应商自动同步模型时也应用同一目录，避免模型在 API 启动之后新增而必须再次重启。供应商发现结果已经携带明确限制时仍优先保存为 `provider`。
- 目录文件被加入 Python 包数据，现场服务器只需部署同一版本代码并重启 API；不需要复制开发机 SurrealDB。启动补齐失败按非致命告警处理，不阻止 API 提供其他功能。
- 在改动合并并推送到 `origin/main` 后，现场执行 `git pull origin main` 与 `make start-all` 即会先启动 SurrealDB、启动 API、应用 migration 30、补齐目录命中的空值，再在 API Ready 后启动前端。若 API 启动失败，前端不会继续启动，应检查 `logs/api.log` 中的 migration / catalog seed 日志。
- Quick 笔记本问答统计条左侧展示的是用户选中的来源全文、来源见解和笔记引用，不是最终发送给模型的完整上下文；标签从“上下文：”改为“引用：”，右侧模型 payload / 上下文窗口统计保持不变。

### 56.3 文件索引

| 文件 | 改动 |
|------|------|
| `open_notebook/ai/model_context_catalog.json` | 按原始开发商组织的官方核验目录、别名和路由覆盖值 |
| `open_notebook/ai/model_context.py` | 目录加载校验、精确匹配、类型过滤、来源优先级与启动补齐 |
| `api/main.py` | 数据库迁移完成后幂等补齐现有语言模型记录 |
| `api/credentials_service.py`、`api/routers/models.py`、`open_notebook/ai/model_discovery.py` | 创建、凭据注册、自动同步和模型测试统一采用目录回退 |
| `open_notebook/ai/models.py` | 有效窗口解析显式携带模型类型，排除嵌入模型 |
| `pyproject.toml` | 将 JSON 目录纳入 Python 包数据 |
| `frontend/src/components/common/ContextIndicator.tsx`、`frontend/src/lib/locales/{en-US,zh-CN}/index.ts` | Quick 统计条标签语义从“上下文”改为“引用” |
| `tests/test_model_context.py`、`tests/test_models_api.py` | 目录结构、GLM-5.2、Gemini、路由覆盖、手工值保护、启动补齐和嵌入模型回归 |

### 56.4 验证

```text
.venv/bin/python -m ruff check api/main.py api/credentials_service.py api/routers/models.py open_notebook/ai/model_context.py open_notebook/ai/model_discovery.py open_notebook/ai/models.py tests/test_model_context.py tests/test_models_api.py
All checks passed

.venv/bin/python -m pytest tests/test_model_context.py tests/test_models_api.py -q
42 passed, 6 warnings

.venv/bin/python -m pytest tests/ -m "not e2e" -q
403 passed, 33 deselected, 6 warnings

cd frontend && NODE_OPTIONS=--no-experimental-webstorage npm test -- --run
206 passed, 9 skipped

cd frontend && npm run lint
exit 0；4 个既有 warning，无 error

cd frontend && npm run build
exit 0；Next.js 16.1.7 Webpack 生产构建与 TypeScript 检查通过

uv build --wheel --out-dir /tmp/lumina-omax-wheel-verify-20260801
构建成功；wheel 包含 open_notebook/ai/model_context_catalog.json
```

真实供应商接口仍需现场用对应凭据验证；若第三方路由返回明确的上下文字段，模型测试会以该路由值更新 DB。

---

## 57. Research Agent 超时根因观测（2026-08-02）

### 57.1 复现与根因边界

- 登录态浏览器在独立 Research 新会话中关闭联网搜索、跨笔记本发现和科研数据库，仅要求读取当前笔记本内一份明确来源。真实 trace `92ba8d0f6768` 的首个公开回答增量为 4.355 秒，主回答 19.909 秒完成，包含建议问题的请求总耗时 23.177 秒；页面显示 7 个步骤、保存成功、工作区引用可用，浏览器没有新增 warning/error。这说明短任务下的 Research Agent、SSE、工具调用、最终综合和 transcript 链路正常。
- 另一个已有真实 trace `92ca069db433` 带 19 条历史消息并启用联网、跨笔记本和科研数据库：144.218 秒出现首个公开回答增量，随后在 146、154、205 秒仍进入新的研究轮次，但整个 LangGraph 在 240 秒被 `CHAT_LLM_TIMEOUT_SECONDS` 强制取消。
- Git 历史确认 240 秒总预算于 2026-06-28 为 Quick Chat 加入，当时依据单轮大上下文调用 30–40 秒总耗时校准；Research Agent 于 2026-07-11 通过参数化复用 `stream_chat_response()`，没有重新定义多轮“模型 → 工具 → 模型”工作流的超时边界。直接根因是 Quick Chat 固定总预算被 Research Agent 继承后的语义错配，不是 SSE 或 transcript 整体失效。
- DeepSeek 延迟、历史长度和启用工具数量是已观察到的耗时相关因素，但旧日志无法分解每轮模型与工具耗时，暂不把其中任何一项单独认定为根因。`first_ai_chunk` 记录的是过滤推理内容后的首个公开答案增量，也不能严格等同于供应商网络首字节。
- 现有超时测试只覆盖 producer 完全挂起；Research 测试覆盖工具状态与心跳，但没有覆盖“总耗时超过 Quick 预算、各研究轮次仍持续推进”的场景。本轮先补观测证据，不直接调整时限或取消语义。

### 57.2 只读观测决策

- 每次 Research 模型调用增加 `research_model_call_start` / `research_model_call_end` INFO 日志，记录 trace、`agent/final` 阶段、本轮序号、历史/选中消息数量、历史估算 token、payload 字符数、可用工具数量、三类外部能力开关、调用耗时、响应字符数、tool call 数量或错误类型；超时触发的 `CancelledError` 也会记录 `status=cancelled` 后原样继续传播，不吞掉或改写取消语义。
- Research 工具事件增加 `research_tool_start` / `research_tool_end` INFO 日志，按 LangChain `run_id` 关联并记录工具名称、请求内序号、成功/失败和耗时；支持并发工具运行，不改变原有 `chat_status` SSE 顺序或内容。
- 日志明确不记录用户问题、回答正文、工具参数、工具返回、来源原文、模型推理、凭据或异常正文。回归测试使用带有 `private` 标记的内容，锁定这些文本不会进入日志。
- Quick Chat 继续使用原有路径，只有 `chat_mode == "research"` 才记录工具耗时。`CHAT_LLM_TIMEOUT_SECONDS=240`、`asyncio.wait_for()`、Research 最大 6 轮工具调用、模型配置、前端协议、i18n、API 路由、数据库和部署拓扑均未改变。
- 服务热重载后已采集三类真实 trace，观测字段和隐私边界均按预期工作：

| 场景 | trace | 主要证据 |
|------|-------|----------|
| 当前笔记本最小任务 | `19965d7169f6` | 1 条历史消息；3 轮模型分别为 2.069、1.893、6.275 秒；3 个笔记本工具最长 0.830 秒；主回答 11.249 秒、含建议问题总计 15.665 秒 |
| 长历史、外部能力关闭 | `c7d0ec5bb09c` | 13 条历史消息、历史估算 24,153 token、payload 47,701 字符；不调用工具，单轮模型 7.757 秒；主回答 7.788 秒、总计 13.945 秒 |
| 联网 + 科研数据库 | `dca5cb5683b6` | 1 条起始历史消息；6 轮 agent + 1 轮 final；23 次工具调用多数并发；模型调用累计 170.658 秒，主链路 188.402 秒、总计 192.339 秒；发送 22 次心跳并持续产生研究进度 |

- 外部能力 trace 中，模型轮次耗时从 7.353 秒逐步增长到 37.382 秒，最终综合为 66.041 秒；历史在第 6 轮达到 24 条并触发压缩，选中 payload 仍达到 89,926 字符。按并发工具每批最长耗时估算，工具墙钟时间约 17.5 秒，而模型累计约占主链路的 90.6%。因此新的代码级结论是：**主要耗时来自外部证据不断扩张 payload 后的多轮模型调用累积，不是某一个检索工具卡住**；长历史本身也不是 240 秒超时的充分条件。
- 三组浏览器验证均正常保存，最后一组在 192.3 秒自然完成且无新增 console warning/error。结合旧失败 trace 在 205 秒仍有研究轮次、240 秒被统一总预算取消的事实，后续架构方向优先考虑 **Research 的“有效进度停滞超时 + 独立整体硬上限”**，而不是只把 240 秒固定总时限简单调大。SSE transport heartbeat 不能单独视为有效进度；可重置停滞计时的候选信号应限定为模型轮次完成、工具开始/结束或公开回答增量。具体停滞时长和硬上限仍需在独立行为变更中用失败/卡死测试校准，本轮不改变运行语义。

### 57.3 文件索引

| 文件 | 改动 |
|------|------|
| `open_notebook/graphs/research_agent.py` | 记录 Research 模型轮次、payload 规模、工具数量、耗时和安全结果元数据 |
| `api/routers/chat.py` | 关联 Research 工具 run 并记录开始、结束、状态和耗时 |
| `tests/test_research_agent_scope.py` | 覆盖模型轮次日志字段及问题/参数/证据/回答正文不泄漏 |
| `tests/test_chat_heartbeat_sse.py` | 覆盖工具计时日志，同时保持既有 Research SSE 状态序列 |
| `docs/8-CUSTOMIZATION/00-index.md` | 记录复现、根因、只读观测边界、验证与后续决策门槛 |

### 57.4 验证

```text
.venv/bin/python -m pytest tests/test_research_agent_scope.py tests/test_chat_heartbeat_sse.py tests/test_chat_observability.py -q
39 passed, 1 warning

.venv/bin/python -m ruff check api/routers/chat.py open_notebook/graphs/research_agent.py tests/test_research_agent_scope.py tests/test_chat_heartbeat_sse.py tests/test_chat_observability.py
All checks passed

.venv/bin/python -m pytest tests/ -m "not e2e" -q
405 passed, 33 deselected, 6 warnings

git diff --check
exit 0
```

真实浏览器验证：

- `chat_session:kw8c7y4lgi18jcw8ttxg` / trace `19965d7169f6`：最小当前笔记本任务，外部能力关闭，7 个页面步骤，保存成功。
- `chat_session:xrjo41ua80icvziib574` / trace `c7d0ec5bb09c`：13 条消息的长历史续问，外部能力关闭，3 个页面步骤，保存成功。
- `chat_session:2sjuxf5ba1vjt6lmjguo` / trace `dca5cb5683b6`：公开标准比较，联网和科研数据库开启、跨笔记本关闭，持续进度与心跳正常，保存成功。
- 三个会话均保留用于后续证据复核，未擅自删除。未验证项仅剩下一阶段的超时行为变更及其卡死/持续推进测试；本轮没有修改任何 timeout 参数。

---

## 58. LibreOffice 缺失根因调查与老 .doc 解析恢复（新增 2026-08-02）

### 58.1 用户报告与根因

用户报告「测 低缓凝型降失水剂调整实验记录-2020.4.17.doc」上传后解析失败。备份日志（`/Users/omax/YinShiMaintenance/lumina-omax/debug/logs/`，覆盖 7-19 ~ 8-02）确认失败链路：

```text
LibreOffice conversion failed: /Applications/LibreOffice.app/Contents/MacOS/soffice: No such file or directory
→ MinerU: Error: No supported documents found under ...doc（MinerU 不支持老 .doc 二进制格式）
→ Falling back to simple engine → Unable to determine file type for: ...doc
→ Command open_notebook.process_source failed after 15 attempt(s)
```

共 8 个 .doc 源同因失败，每次重试 15 次。根因：`/opt/homebrew/bin/soffice` wrapper 指向 `/Applications/LibreOffice.app`，但该 app 缺失（brew caskroom 26.2.4 目录只有 LICENSEs/READMEs/wrapper 无 .app 本体）。

### 58.2 LibreOffice 消失时间线重建（只读调查）

| 时间 | 事件 | 证据 |
|------|------|------|
| 2026-05-10 13:53 | 首次安装 26.2.3 成功 | `INSTALL_RECEIPT.json` mtime + 内容（version 26.2.3） |
| 2026-06-20 19:44 | 升级 26.2.4 完成 | `soffice.wrapper.sh`、`.metadata/26.2.4/`、LICENSEs quarantine 时间戳 `1781955833` 吻合 |
| 2026-07-06 16:18 | LibreOffice 仍在运行 | `~/Library/Application Support/LibreOffice/4/user/registrymodifications.xcu` 最后更新 |
| 2026-07-24 15:06 | 26.2.5 dmg 下载到缓存 | `recentcksum @1784876781`，sha256 与官方一致 |
| 2026-07-29 12:20 | app 已消失 | worker 日志 `soffice: No such file or directory` |

**结论**：app 在 7/6 ~ 7/29 之间消失，最可能发生在 7/24 15:06 的 26.2.5 升级尝试（先卸载旧 app、再装新版，中途失败/中断则留下残缺状态）。8/2 21:00 用户重装尝试失败（21:10:07 挂载 26.2.5 dmg → 21:10:14 卸载，仅 7 秒，无 /Applications 拷贝痕迹），brew 因 metadata 存在判定已安装后快速回滚。

### 58.3 修复与回归验证

- 用户手动执行 `brew install --cask libreoffice` 成功安装 **26.2.5**（`/Applications/LibreOffice.app` 就位，`soffice --headless --version` 正常）。
- **Step 1 单元验证**：`convert_to_modern_office_format()` 转换用户报告文件成功生成 PDF（2 页，内容完整含表格）。
- **Step 2 端到端回归**：对 DB 中仍处于失败状态的 `source:pkbfuc1bnflbs7zdxnnl`（2020.4.17.doc）直接提交 `open_notebook.process_source` worker 命令（retry API 因源无 notebook 引用被拒，改用 command_service 直提）：
  - `Successfully processed source in 59.33s`（7/29 时 15 次重试全败）
  - 写入 `full_text`（Markdown 化，含公式与表格），13 个 embedding chunks 落库
  - KG 抽取 42 实体 / 40 关系落库
- **Step 3 代码加固**：`open_notebook/utils/office_converter.py` 失败分支区分三种根因并输出可操作日志（命令缺失 / 转换退出码 / 退出 0 但无输出），行为契约不变（仍回退返回原路径，不破坏下游）。

### 58.4 文件索引

| 文件 | 改动 |
|------|------|
| `open_notebook/utils/office_converter.py` | 新增 `_log_conversion_failure()`；缺失命令预检；CalledProcessError 携带 stderr；退出 0 无输出检测；FileNotFoundError 分支 |
| `tests/test_office_converter.py` | 新增 3 个失败分支测试（命令缺失 / 转换失败 / 无输出），断言 fallback 与可操作日志 |
| `docs/8-CUSTOMIZATION/00-index.md` | 本节记录 |

### 58.5 验证

```text
.venv/bin/python -m pytest tests/test_office_converter.py -q
12 passed（含 3 个新增）

.venv/bin/python -m pytest tests/test_office_converter.py tests/test_excel_source_cleanup.py tests/test_sources_duplicates.py -q
20 passed

.venv/bin/python -m pytest tests/test_graphs.py::TestSaveSourceTitlePreservation tests/test_vision_descriptions.py -q
27 passed

.venv/bin/python -m pytest tests/ -m "not e2e" -q
408 passed, 33 deselected, 6 warnings

.venv/bin/python -m ruff check open_notebook/utils/office_converter.py tests/test_office_converter.py
All checks passed

git diff --check
exit 0
```

### 58.6 未尽事宜

1. **DB 中其余 12 个未解析 .doc 源**：本轮只回归了用户报告的 1 个（pkbfuc1bnflbs7zdxnnl）。其余失败源（如 `mlqpojyj0vsp82j0f7m4`、`okq5fau4lkpwaoah72eq`、`v8wjxersfgpst73izaxn` 等）仍停留在 `full_text=null`，需用户从界面逐个重试或删除重建。
2. **LibreOffice 升级健壮性**：7/24 升级中断导致 app 缺失的机制仍未在代码层防护（brew 层行为）。如需自动告警，可考虑 API 启动时探测 `_resolve_libreoffice_command()` 可用性并记录明确告警日志（当前仅在调用时失败才报错）。
3. **`.doc` 直传回归**：MinerU 输出已确认包含公式（`$( \mathsf { 9 0 ^ { \circ } C } )$`），与 §42 公式渲染链路配合效果待用户浏览器端目检。

---

## 59. Research Agent 停滞超时与独立整体硬上限（新增 2026-08-02）

§57 观测结论落地：Research 不再继承 Quick Chat 的 `CHAT_LLM_TIMEOUT_SECONDS=240` 一刀切预算，改为「有效进度停滞超时 + 独立整体硬上限」双机制。

### 59.1 行为决策

- 新增 `RESEARCH_AGENT_HARD_TIMEOUT_SECONDS`（默认 `600` 秒）：Research 整体硬上限，替代 Quick 语义的 240s。达到上限发送 `error_code=research_hard_timeout` SSE 错误。
- 新增 `RESEARCH_AGENT_STALL_TIMEOUT_SECONDS`（默认 `120` 秒）：有效进度停滞窗口。停滞时钟**仅**由以下信号重置：
  - 模型轮次完成（`on_chat_model_end`）
  - 工具开始 / 结束 / 错误（`on_tool_start` / `on_tool_end` / `on_tool_error`）
  - 公开回答增量（`ai_message` delta）
  - **心跳和状态事件不计入有效进度**（§57 明确排除）。
- 停滞触发时：取消 producer，发送 `error_code=research_stall` SSE 错误（含 `stall_seconds`），并跳过后续 transcript / 建议问题 / complete 流程。
- Quick Chat 行为完全不变：仍走 `llm_timeout`（240s），停滞 watchdog 不启用（`chat_mode != "research"` 直接返回）。
- 停滞检查周期 = `min(stall/3, 5s)`，下限 0.1s，避免高频轮询。
- `finalize_task` 中 producer 被停滞取消产生的 `CancelledError` 视为预期（不重新抛出）；只有真实异常继续向外传播。

### 59.2 前端

- `error-bubble.ts`：`ChatErrorCode` 增加 `research_stall` / `research_hard_timeout`；`ErrorBubbleTemplates` 增加 `errorResearchStall` / `errorResearchHardTimeout`，按 code 分发本地化模板，未知 code 继续走 `errorGeneric` 兜底。
- `useNotebookChat.ts` / `useSourceChat.ts` / `use-ask.ts` 三个调用点传入新模板键（Ask/Source Chat 不会收到这两个 code，但模板接口统一）。
- i18n：`zh-CN` / `en-US` 各新增 2 条文案，指引用户拆分问题或减少启用能力；其余 7 个 locale 沿用 en-US fallback（与既有约定一致）。

### 59.3 验证

```text
.venv/bin/python -m pytest tests/test_research_stall_timeout.py -q
5 passed（停滞触发 / 工具重置 / 模型轮次+回答增量重置 / 硬上限 / Quick 不受影响）

.venv/bin/python -m pytest tests/ -m "not e2e" -q
413 passed, 33 deselected, 6 warnings

.venv/bin/python -m ruff check api/routers/chat.py tests/test_research_stall_timeout.py
All checks passed

cd frontend && NODE_OPTIONS=--no-experimental-webstorage npm test
208 passed | 9 skipped

cd frontend && npm run lint
0 errors, 4 pre-existing warnings

cd frontend && npm run build
exit 0

git diff --check
exit 0
```

### 59.4 未尽事宜

1. **真实长 Research 回归**：默认 120s 停滞 / 600s 硬上限仍需在真实笔记本中用长 Research 任务校准；§57 观测的最长自然完成 192s 远低于 600s 上限，120s 停滞窗口可覆盖单轮综合（66s）+ 工具墙钟（17.5s）的最坏组合，但真实模型波动下的误杀率待观察。
2. **参数可调**：两个环境变量已加入 `.env.production.example`；如用户场景频繁触发停滞，可先调大 `RESEARCH_AGENT_STALL_TIMEOUT_SECONDS`。
3. **错误气泡文案验收**：`research_stall` / `research_hard_timeout` 气泡的中文文案与诊断段需用户在真实浏览器中目检一次。

### 59.5 文件索引

| 文件 | 改动 |
|------|------|
| `api/routers/chat.py` | `RESEARCH_AGENT_HARD_TIMEOUT_SECONDS` / `RESEARCH_AGENT_STALL_TIMEOUT_SECONDS`；`mark_research_progress()`；`run_stall_watchdog()`；`finalize_producer` 按模式选择超时；`research_stall` / `research_hard_timeout` SSE 错误；停滞后跳过 transcript/建议流程；`CancelledError` 预期处理 |
| `.env.production.example` | 两个 Research 超时环境变量说明 |
| `frontend/src/lib/chat/error-bubble.ts` | 新 error code 类型与模板接口 |
| `frontend/src/lib/hooks/useNotebookChat.ts` / `useSourceChat.ts` / `use-ask.ts` | 传入新模板键 |
| `frontend/src/lib/locales/en-US/index.ts` / `zh-CN/index.ts` | `errorResearchStall` / `errorResearchHardTimeout` 文案 |
| `frontend/src/lib/chat/error-bubble.test.ts` | 新增 research_stall / research_hard_timeout 渲染用例 |
| `tests/test_research_stall_timeout.py` | **新增** — 停滞触发、进度重置（工具/模型轮次/回答增量）、硬上限、Quick 回归 |

---

## 60. 新加入笔记本的源默认改为引用见解（新增 2026-08-02）

### 60.1 问题与决策

- 用户习惯把大量文档作为单个笔记本的源。§21.5 曾把「新增来源默认参考全文」，导致首次提问时一次性携带全部来源全文，上下文膨胀、首次回答等待时间过长，影响首用体验。
- 现将新加入笔记本的源**默认设为「引用见解」（insights）**，而非「全文」（full）。用户仍可在每个源卡片上手动切换为全文/不参考，行为不变。
- 笔记默认仍为全文（未改动）；`localStorage` 中已持久化的历史选择不受影响，仅对新出现的源（`contextSelections` 中无记录）应用新默认。

### 60.2 文件索引

| 文件 | 改动 |
|------|------|
| `frontend/src/app/(dashboard)/notebooks/[id]/page.tsx` | 新源默认 `'full'` → `'insights'`（含注释说明） |

### 60.3 验证

```text
cd frontend && NODE_OPTIONS=--no-experimental-webstorage npm test
208 passed | 9 skipped

cd frontend && npm run lint
0 errors, 4 pre-existing warnings

cd frontend && npm run build
exit 0

git diff --check
exit 0
```

### 60.4 未尽事宜

1. 后端 `/chat/context` 的 `insights` 模式依赖该源已有 insights 生成；新上传源在嵌入/insight 未完成时提问，insights 模式可能取到空见解。行为是否可接受需在真实笔记本中目检。
2. 已存在笔记本的旧 `localStorage` 缓存中源仍为 `full`；如需整体切换可引导用户清除浏览器存储或逐个切换。

---

## 61. 设置页 Firecrawl API Key 入口与 URL 导入恢复（新增 2026-08-03）

### 61.1 问题与根因

- 用户导入微信公众号文章 URL（`mp.weixin.qq.com/s/...`）失败。worker 日志失败链路：`Engine doc: mineru, URL: firecrawl` → `Firecrawl extraction failed ... No API key provided` → `Could not extract any text content from this source`。
- **第一层根因（配置错配，影响所有 URL 导入）**：DB `open_notebook:content_settings` 中 `default_content_processing_engine_url=firecrawl`（设置页显式配置过），但 `.env` 无 `FIRECRAWL_API_KEY`。content_core `extract_url()` 对**显式指定**的 `firecrawl` 引擎没有回退链（回退链只存在于 `auto` 模式：firecrawl → Jina → crawl4ai → bs4），Firecrawl SDK 以 `api_key=None` 初始化直接抛错。
- **第二层（微信反爬）**：实测同一 URL 在无浏览器环境下，`simple`/bs4 仅提取 36 字符页面底部工具栏文字，`jina` 返回 325 字符且含 `Warning: This page maybe requiring CAPTCHA`；原始 HTML 仅 18KB，是微信「环境异常，完成验证后即可继续访问」反爬验证页（无 `js_content`/`og:title`）。即免费引擎拿不到微信正文，只有具备浏览器渲染+反爬能力的 Firecrawl 有成功可能。
- **第三层（体验）**：提取失败统一报通用文案，无法区分「配置缺失」与「内容不可达」。

### 61.2 决策与实现

- 采纳「设置页入口」方案：为 `FIRECRAWL_API_KEY` 增加设置页配置能力，照 Tavily 先例（`tavily_api_key` 已在设置页配置、由 `ContentSettings` 持久化）。DB-first 语义，运行时注入环境变量（content_core 只读 `os.environ`，与 `key_provider` 的 database-first 模式一致）。
- 本轮不做「无 key 时 firecrawl → auto 降级」守卫：设置页有了 key 入口后误配概率大幅降低，避免范围膨胀；如后续仍出现同类失败可单独补守卫。
- 已知限制：微信链接导入能否成功取决于 Firecrawl 对反爬验证页的穿透能力；即使配置了 key 仍可能失败，届时需改用 Firecrawl 自托管或浏览器人工复制内容。

### 61.3 文件索引

| 文件 | 改动 |
|------|------|
| `open_notebook/domain/content_settings.py` | 新增 `firecrawl_api_key: Optional[str]` 字段（与 `tavily_api_key` 同模式） |
| `api/models.py` | `SettingsResponse` / `SettingsUpdate` 各加 `firecrawl_api_key` |
| `api/routers/settings.py` | GET 返回 + PUT 写入透传 |
| `open_notebook/graphs/source.py` | 新增 `provision_firecrawl_api_key()`；`content_process()` 提取前注入 env（DB 有值覆盖，空值不动 env） |
| `frontend/src/app/(dashboard)/settings/components/SettingsForm.tsx` | URL 引擎下拉下方新增密码类型输入框 + zod schema + defaultValues + reset |
| `frontend/src/lib/types/api.ts` | `SettingsResponse` 加 `firecrawl_api_key` |
| `frontend/src/lib/locales/en-US/index.ts` / `zh-CN/index.ts` | `firecrawlApiKey` / `firecrawlApiKeyPlaceholder` 文案（其余 7 locale 走 en-US fallback） |
| `tests/test_firecrawl_key_settings.py` | **新增** — env 注入语义（有值覆盖/空值保留/无操作）与 `/api/settings` GET/PUT round-trip（含清空） |
| `tests/test_domain.py` | ContentSettings 默认值断言补 `firecrawl_api_key is None` |
| `frontend/src/app/(dashboard)/settings/components/SettingsForm.test.tsx` | **新增** — Firecrawl key 输入框渲染回显 + 提交透传 |

### 61.4 验证

```text
.venv/bin/python -m ruff check api/models.py api/routers/settings.py open_notebook/domain/content_settings.py open_notebook/graphs/source.py tests/test_firecrawl_key_settings.py tests/test_domain.py
All checks passed

.venv/bin/python -m pytest tests/test_firecrawl_key_settings.py tests/test_domain.py -q
27 passed（两种文件顺序均通过；ContentSettings 单例隔离 fixture）

.venv/bin/python -m pytest tests/ -m "not e2e" -q
421 passed, 33 deselected, 8 warnings

cd frontend && NODE_OPTIONS=--no-experimental-webstorage npm test -- --run src/app/\(dashboard\)/settings/components/SettingsForm.test.tsx
2 passed

cd frontend && NODE_OPTIONS=--no-experimental-webstorage npm test -- --run
210 passed | 9 skipped

cd frontend && npm run lint
exit 0；0 errors，4 个既有 warning

cd frontend && npm run build
exit 0

git diff --check
exit 0
```

### 61.5 验收步骤与未尽事宜

1. **真实验收**：在设置页填入 Firecrawl API Key 保存 → `GET /api/settings` 确认持久化 → 对之前失败的微信源（`source:9188fu4ly1sx3wp8kx4d`）在 UI 重试，确认导入/嵌入/KG 链路。此步需用户提供有效 Firecrawl Key，本轮未执行。
2. **无 key 时仍会失败**：若设置页未填 key 而 url 引擎为 firecrawl，失败表现与本轮修复前相同；后续如需彻底防呆可补「无 key 降级 auto」守卫。
3. **微信反爬不确定性**：Firecrawl 对微信验证页的穿透能力未在本轮验证，若失败按 61.2 已知限制处理。

---

## 62. Research Agent 语义检索静默为空：surrealdb 客户端多语句截断修复（新增 2026-08-03）

### 62.1 问题现象

- 笔记本中使用「科研 Agent」提问时，回答中出现「语义检索未返回结果，说明该笔记本内可能未对 PDF 内容做全文语义索引」。
- 实查发现笔记本 5 个源全部有嵌入（160 条 `source_embedding`，1024 维，与当前嵌入模型一致），真实余弦相似度 0.21-0.81，数据完全正常；`search_notebook_evidence` 工具确实执行了（trace `3c42f57fc804` 中 863ms 完成），但**工具始终拿到空结果**。
- 那句话是 LLM 对空工具结果的推测性解释，不是系统检测，误导性较强。

### 62.2 根因

- `scoped_vector_search`（`open_notebook/domain/notebook.py:911-950`）使用 `LET $source_chunks = (...); ...; RETURN SELECT ...` 多语句查询。
- `surrealdb` Python 客户端（1.0.7 / 1.0.8 / 2.0.0 均如此，`async_ws.py` 的 `query()` 固定 `return response["result"][0]["result"]`）**只返回第一条语句的结果**；`LET` 语句的结果是 `None`，后续 `RETURN` 的结果被静默丢弃。
- 服务器本身正确返回全部语句结果（实测 `LET ...; RETURN array::len(...); RETURN 'after'` → 三条结果齐全）。这是客户端设计行为，不是 1.0.8 的回归；v3.0.0（alpha）才改为返回全部语句（破坏性 API，不适合生产）。
- 全库唯一使用多语句查询的代码就是 `scoped_vector_search`，因此只影响 Research Agent 的 `search_notebook_evidence` 与 `discover_across_notebooks`；Ask 全局搜索走 `fn::vector_search` 单语句不受影响。`repo_transaction` 无影响（服务器把 BEGIN/CREATE/COMMIT 折叠为单条结果）。

### 62.3 决策与实现

- **不升级客户端**：最新稳定版 2.0.0 源码确认 `query()` 同款截断，升级解决不了问题；3.0.0-alpha 是破坏性变更不适合生产。
- **方案 A（实施）**：`repo_query` 改用 `connection.query_raw()` 自行解析完整响应，新增 `_extract_query_results()`：
  - 响应级 `error` → `RuntimeError`（保持事务冲突重试语义，`_is_transaction_conflict` 依赖消息关键字）
  - 逐条检查语句 `status == "ERR"` → `RuntimeError`（比原实现对后续语句错误的检查更完整）
  - 返回**最后一条语句**的 `result`（多语句惯例：数据在末尾 RETURN；单语句与原先 `[0]` 完全等价）
- 客户端版本无关：将来升级 2.0.0 或迁移 3.0.0 均不受影响。

### 62.4 文件索引

| 文件 | 改动 |
|------|------|
| `open_notebook/database/repository.py` | 新增 `_extract_query_results()`；`repo_query` 改用 `query_raw` 并解析末语句结果 |
| `tests/test_repository_query.py` | **新增** — 解析函数单测（单语句/多语句/末语句 None/语句级 ERR/响应级 ERR/非 dict 透传）+ repo_query 用 query_raw 的 mock 测试 |

### 62.5 验证

```text
真实 DB 回归：
  LET+RETURN len  -> 3（修复前 None）
  单语句 RETURN   -> [1,2,3]（行为不变）
  事务 round-trip -> 返回创建的记录（行为不变）
  响应级语法错误  -> RuntimeError 抛出
  notebook_vector_search('高温缓凝型降失水剂') -> 9 条（修复前 0 条），
    相似度 0.71-0.81，含 source chunks 与 source_insight

.venv/bin/python -m pytest tests/test_repository_query.py -q
9 passed

.venv/bin/python -m pytest tests/ -m "not e2e" -q
430 passed, 33 deselected, 8 warnings

.venv/bin/python -m ruff check open_notebook/database/repository.py tests/test_repository_query.py
All checks passed

git diff --check
exit 0
```

### 62.6 未尽事宜

1. **真实 Research Agent 回归**：语义检索链路已在函数级验证；建议在浏览器中用真实笔记本再跑一次科研 Agent，确认回答引用真实文档内容、不再出现「语义检索未返回结果」误导文案（此文案只在检索真为空时才会合理出现）。
2. **历史回答**：此前基于空检索生成的回答仍保留在会话记录中，不会自动修正。
3. **客户端升级**：本次不升级 surrealdb 客户端；如后续升级 2.0.0，`repo_query` 修复继续有效，无需联动改动。

---

## 63. 全局文本搜索中文漏匹配：子串兜底（新增 2026-08-03）

### 63.1 问题现象与根因

- 用户反馈：源列表筛选「中海油冲洗剂」12 条，全局文本搜索（`/api/search` type=text）只有 3 条。
- 两种搜索语义不同：源列表用 `string::contains(lowercase(title), ...)` **子串包含**（sources.py:270）；文本搜索走 `fn::text_search` 的 **BM25 词元精确匹配**（migrations/1.surrealql:65-72 `my_analyzer`）。
- 根因是平台能力限制：`my_analyzer` 分词器 `blank,class,camel,punct + snowball(english), lowercase` **无中文分词**（SurrealDB 2.6.5 文档确认：snowball 支持语言无中文，无 jieba）。连续汉字「中海油冲洗剂研发报告2025.7.7」被 class 分词器切为**一个整体 token**，与查询词元「中海油冲洗剂」不相等 → BM25 不命中。
- 3 条命中不是模糊匹配，而是文档恰好存在**词元边界**把关键词切了出来（实测 `search::analyze` 定位）：
  1. title 含全角括号的「（近期白油对比）」→ punct 切出独立 token；
  2. 两份报告 full_text 中 `<td>中海油冲洗剂</td>` HTML 表格标签的 `<`/`>` 切出独立 token。
  3. 佐证：查询「冲洗剂」（中间子串）命中 11 条，因正文有「1.冲洗剂」数字编号标点边界；「冲洗剂研发」（无边界）0 条。

### 63.2 决策与实现

- **方案 A（实施）：查询层子串兜底**——`text_search()` 在 BM25 结果之后追加 `CONTAINS` 子串查询（source.title / source.full_text / source_insight.content / note.title / note.content），Python 侧去重合并：
  - BM25 命中保持在前（真实 relevance），子串兜底统一 `relevance=0.5` 排后，最终截断 `results` 条；
  - 尊重 `source` / `note` 开关（source=False 跳过 source+insight 扫描，note=False 跳过 note 扫描）；
  - 全空白关键词跳过子串扫描（避免 `CONTAINS ''` 命中全表）；
  - **不扫 `source_embedding.content`**（11750 行大文本全表扫描成本高，chunk 级检索由 BM25 负责）；
  - 字段契约不变：`id / parent_id / title / relevance`（前端把 relevance 映射为 final_score）。
- 实施中的 SurrealDB 2.6.5 坑：
  - **不支持 SQL `UNION`**（三种语法变体均报 Parse error）→ 改为 Python 侧逐分支查询合并；
  - `string::lowercase(NONE)` 抛运行时错误 → 所有字段加 `?? ''` 兜底（source 的 full_text、note 的 title/content 都可能为 NONE）。
- 未做方案 B（ngram analyzer 索引层改造）：需 REBUILD 11750 行 embedding 索引、索引膨胀、英文搜索行为变化，风险高，留作数据量增大后的长期优化。

### 63.3 文件索引

| 文件 | 改动 |
|------|------|
| `open_notebook/domain/notebook.py` | 新增 3 条子串兜底 SQL 常量；`text_search()` 合并去重逻辑、开关与空白防护 |
| `tests/test_text_search_substring.py` | **新增** — 合并去重、优先级、开关、空白防护、截断 4 条 |

### 63.4 验证

```text
真实 DB（本地库）：
  「中海油冲洗剂」-> 14 条（修复前 3 条；12 title + 2 insight 子串，BM25 3 条排前）
  「冲洗剂」      -> 30 条
  「中海油」      -> 27 条
  「缓凝剂」      -> 20 条
  「deep learning」-> 0 条（库中无相关文档，行为合理）

.venv/bin/python -m pytest tests/test_text_search_substring.py -q
4 passed

.venv/bin/python -m pytest tests/ -m "not e2e" -q
434 passed, 33 deselected, 8 warnings

.venv/bin/python -m ruff check open_notebook/domain/notebook.py tests/test_text_search_substring.py
All checks passed

git diff --check
exit 0
```

### 63.5 未尽事宜

1. **性能**：子串兜底对 source/note/insight 表做全表扫描（数百行级），当前可接受；数据量显著增长后可考虑方案 B（ngram 索引）或限制子串扫描范围。
2. **Ask 全局提问的「无意义字符串」问题**（用户此前反馈）尚未处理：调查中发现 `dhwwf9u93up` 实为真实源 `source:bpqgzxbzzdhwwf9u93up`（中海油冲洗剂研发报告2025.6.20）ID 的一部分，此前"模型幻觉假 ID"的判断有误，需另行复检（待用户确认后继续）。

---

## 64. 引用 ID 被模型截短：后端修复 + 前端兜底（新增 2026-08-03）

### 64.1 问题与根因

- 用户反馈：回答中的「工作区引用」source-id 被截短，点击引用链接无法打开。日志铁证（17:47:39）：

  ```
  ERROR api.routers.sources:get_source:910 - Error fetching source source:lh9mbu:
        source with id source:lh9mbu not found
  ```

  真实 ID 是 `source:lh9mbuyd1m9g4bh56u36`；`dhwwf9u93up` 同理是 `source:bpqgzxbzzdhwwf9u93up` 的片段。
- **根因**：模型生成引用时截短了 SurrealDB 的 20 字符随机 record id（截前部/尾部/中间都可能，长随机串对 LLM 复制不可靠）。前端 `parseSourceReferences` 等正常解析模型写出的（截短）ID → 参考文献列表展示截短 ID → 点击 `GET /sources/source:lh9mbu` → 404。**前端渲染无 bug，数据（模型输出）就是截短的**。

### 64.2 决策与实现

- **方案 A（主修复）：后端引用 ID 唯一匹配修复**——新增 `open_notebook/utils/reference_repair.py`：
  - `repair_reference_ids(text, known_ids)`：对 `(source_insight|insight|note|source):([a-zA-Z0-9_]+)` 引用，若 ID 不在已知集，按类型过滤后做唯一匹配（`startswith` / `endswith` / 包含）；唯一候选则替换为完整 ID，歧义/无匹配保留原样；`insight:` 别名归一化到 `source_insight:`。
  - Chat 接入：`api/routers/chat.py` 的 `stream_chat_response` 从 context（sources/notes/insights 的 id）构建 `known_reference_ids`，`emit_ai_content` 逐 chunk 修复（引用通常在单 chunk 内完整出现）。
  - Ask 接入：`open_notebook/graphs/ask.py` 的 `provide_answer` 返回值新增 `ids`（全部检索结果 id，含 insight/note）；`api/routers/search.py` 在 `provide_answer` 的 `on_chain_end` 事件收集 `ids` 为 `known_reference_ids`，`emit_final_answer_delta` 逐 chunk 修复、`write_final_answer` 的 buffered 最终答案整体修复、局部 `answer` 事件同样修复。
- **方案 B（辅助）：prompt 强化**——`prompts/chat/system.jinja`、`prompts/ask/final_answer.jinja`、`prompts/ask/query_process.jinja` 均追加警告：ID 为 20 字符随机串，必须完整复制，截短导致引用失效，不确定则省略引用。
- **方案 C（前端兜底）**：新增 `frontend/src/lib/utils/reference-exists.ts`（按类型 GET `/sources/{id}`、`/notes/{id}`、`/insights/{id}` 校验存在性）；`ChatPanel.handleReferenceClick` 与 `StreamingResponse.handleReferenceClick` 改为异步：校验失败 toast `itemNotFound`（「未找到该 {type}」），成功才 `openModal`，替代原先打开一个只显示"未找到"的空模态框。
- 未做方案 D（编号引用 + 映射下发）：改动 prompt/SSE/前端三处、风险高，留作模型截短问题复发后的彻底重构选项。

### 64.3 文件索引

| 文件 | 改动 |
|------|------|
| `open_notebook/utils/reference_repair.py` | **新增** — `repair_reference_ids()` 唯一匹配修复 |
| `api/routers/chat.py` | context 构建 known IDs；`emit_ai_content` 逐 chunk 修复 |
| `api/routers/search.py` | Ask 收集检索 ids；delta/buffered/局部 answer 三处修复 |
| `open_notebook/graphs/ask.py` | `provide_answer` 返回 `ids` |
| `prompts/chat/system.jinja`、`prompts/ask/final_answer.jinja`、`prompts/ask/query_process.jinja` | ID 完整性警告 |
| `frontend/src/lib/utils/reference-exists.ts` | **新增** — 引用存在性校验 |
| `frontend/src/components/source/ChatPanel.tsx`、`frontend/src/components/search/StreamingResponse.tsx` | 引用点击异步校验 + 404 toast |
| `tests/test_reference_repair.py` | **新增** — 前缀/后缀/中间截短、歧义、类型隔离、alias、批量 11 条 |
| `frontend/src/components/source/ChatPanel.test.tsx`、`frontend/src/components/search/StreamingResponse.test.tsx` | mock referenceExists + waitFor 适配异步点击 |

### 64.4 验证

```text
.venv/bin/python -m pytest tests/test_reference_repair.py -q
11 passed

.venv/bin/python -m pytest tests/ -m "not e2e" -q
445 passed, 33 deselected, 8 warnings

.venv/bin/python -m ruff check api/routers/chat.py api/routers/search.py open_notebook/graphs/ask.py open_notebook/utils/reference_repair.py tests/test_reference_repair.py
All checks passed

cd frontend && NODE_OPTIONS=--no-experimental-webstorage npm test -- --run
210 passed | 9 skipped

cd frontend && npm run lint
exit 0；0 errors，4 个既有 warning

cd frontend && npm run build
exit 0

git diff --check
exit 0
```

真实案例回归（函数级）：`[source:lh9mbu]` → `[source:lh9mbuyd1m9g4bh56u36]`（前缀匹配）；`[source:dhwwf9u93up]` → `[source:bpqgzxbzzdhwwf9u93up]`（后缀匹配）。

### 64.5 未尽事宜

1. **跨 chunk 引用**：流式修复按 chunk 处理，极少数引用横跨两个 chunk 时可能漏修（前端 404 toast 兜底）。
2. **歧义保留**：多个真实 ID 共享同一截短片段时修复放弃（如两个源都以 `u93up` 结尾），保持不误替换。
3. **历史消息**：已保存的 transcript/Ask 历史中的截短引用不会自动修复。
4. **方案 D 备选**：若后续模型截短仍频繁，可评估编号引用 + SSE 下发编号→ID 映射的彻底重构。

---

## 65. 三项体验修复：引用渲染、导览卡片、Research 停滞误杀与文案（新增 2026-08-04）

### 65.1 问题一：引用显示为非链接 `[[1](#ref-source-xxx), [2](#ref-source-yyy)]`

- **根因（两层）**：1) 模型格式漂移——chat 提示词要求本地引用用 `[source:xxx]`，模型却输出编号 + `#ref-` 锚点链接且用外层方括号+逗号合并多个引用；2) 前端二次转换 bug——`convertReferencesToCompactMarkdown` / `convertReferencesToMarkdownLinks` 的引用解析正则匹配到 **`#ref-` 锚点 href 内部的** `source:xxx`，再次转换为嵌套链接 `[1](#ref-[1](#ref-source-xxx))` → ReactMarkdown 解析失败 → 显示为纯文本。
- **修复**：
  - `frontend/src/lib/utils/source-references.tsx` 新增 `protectInternalReferenceLinks()`（解析前把已存在的 `#ref-` 锚点链接替换为占位符、解析后恢复）与 `normalizeBracketedReferenceList()`（去掉 `[[n](href), [m](href)]` 外层方括号）；两个转换函数均接入保护逻辑；
  - `prompts/chat/system.jinja` 本地引用段追加 FORMAT 约束：不得编号、不得用 markdown 链接包裹、不得方括号合并多个引用。
- **测试**：`source-references.test.ts` 新增 4 条（锚点不被二次转换 ×2、双括号列表规范化、裸 `[source:abc]` 与锚点共存）。

### 65.2 问题二：导览卡片「正在生成」后静默消失

- **根因**：`generate_notebook_guide` → `parse_guide_json` 解析模型 JSON 失败（日志反复 `Failed to parse notebook guide JSON`；模型输出被 `max_tokens=768` 截断或格式漂移）→ 返回 `status=error` → 前端仅 `status==='ready'` 渲染卡片，失败后无任何状态 → 静默。
- **修复**：
  - `api/notebook_guide_service.py`：`_parse_json_object()` 重写——优先取完整 `{...}`，否则取首个 `{` 到文末（截断情形），并做启发式修复（未闭合字符串补 `"`、未闭合括号/数组补 `]`/`}`）；`parse_guide_json` 剥离任意位置代码块围栏；解析仍失败时 `_extract_questions_fallback()` 宽松提取 questions 列表（宁给建议不给空）；
  - `_invoke_json_model` `max_tokens` 768 → 1024（降低截断概率）；
  - `frontend/src/components/source/ChatPanel.tsx` 新增失败态：`status=error` 时显示「导览暂不可用」+ 说明 + 重新生成按钮（新增 `guideUnavailableDesc` i18n，zh-CN/en-US）。
- **测试**：`tests/test_guide_json_parsing.py` 新增 12 条（围栏/前置文字/截断补全/字符串未闭合/兜底提取/上限/类型过滤）。

### 65.3 问题三：Research Agent research_stall 误杀 + 文案

- **根因（第一层：报错不应该）**：trace `f8d75344cf61` 铁证——11:23:26 模型调用开始（payload 38K 字符 + 10 工具 + 联网/科研库/跨笔记本全开）→ 11:25:26 恰好 120s 被停滞检测取消（`research_model_call_end status=cancelled`）。**模型单轮正常生成 >120s 无首输出被误杀**：watchdog 进度信号不含模型调用开始，且 reasoning 输出仅在**首次**触发进度（持续思考输出不算），模型调用进行中全部计入停滞时间。
- **修复（3a）**：`api/routers/chat.py`——
  - `on_chat_model_start` 触发 `mark_research_progress()`（模型调用开始 = 有效工作，不因响应慢而被误杀；模型真挂起由 600s 硬超时兜底）；
  - `on_chat_model_stream` / `on_llm_stream` 任意流式输出（含 reasoning-only chunk）都重置停滞时钟（修掉"仅首次 reasoning 算进度"缺口）；
  - `emit_reasoning_started` 同样重置（buffered 路径兜底）；
  - 默认停滞窗口 120s → **180s**（`RESEARCH_AGENT_STALL_TIMEOUT_SECONDS`）。
- **修复（3b：文案中文化）**：`frontend/src/lib/chat/error-bubble.ts` 对 `research_stall` / `research_hard_timeout` **隐藏英文 server message**——气泡中文主体（`errorResearchStall` / `errorResearchHardTimeout`，§59 已提供「科研 Agent 已长时间没有有效进展…请拆分问题/减少启用能力」）已用用户可懂的语言完整解释原因与做法；`_Diagnostic_: error_code=...` 保留作为技术支持标识。其它错误类型不变。
- **测试**：`tests/test_research_stall_timeout.py` 新增——模型开始 + 持续 reasoning 输出（30 × 0.1s，远超 0.2s 测试窗口）期间不触发 stall，generator 正常结束。

### 65.4 文件索引

| 文件 | 改动 |
|------|------|
| `frontend/src/lib/utils/source-references.tsx` | `protectInternalReferenceLinks` + `normalizeBracketedReferenceList` + 两个转换函数接入 |
| `prompts/chat/system.jinja` | 本地引用 FORMAT 约束 |
| `api/notebook_guide_service.py` | `_parse_json_object` 截断修复、任意位置围栏剥离、questions 兜底、max_tokens 1024 |
| `frontend/src/components/source/ChatPanel.tsx` | 导览失败态（不可用 + 重试按钮） |
| `frontend/src/lib/locales/{zh-CN,en-US}/index.ts` | `guideUnavailableDesc` |
| `api/routers/chat.py` | `on_chat_model_start`/流式输出/reasoning 计入进度；默认窗口 180s |
| `frontend/src/lib/chat/error-bubble.ts` | research_stall/hard_timeout 隐藏英文 server message |
| `frontend/src/lib/utils/source-references.test.ts` | 新增锚点保护/双括号列表测试 |
| `tests/test_guide_json_parsing.py` | **新增** 12 条 |
| `tests/test_research_stall_timeout.py` | 新增模型开始+reasoning 进度测试 |

### 65.5 验证

```text
.venv/bin/python -m pytest tests/ -m "not e2e" -q
458 passed, 33 deselected, 8 warnings

.venv/bin/python -m ruff check api/notebook_guide_service.py api/routers/chat.py tests/test_guide_json_parsing.py tests/test_research_stall_timeout.py
All checks passed

cd frontend && NODE_OPTIONS=--no-experimental-webstorage npm test -- --run
214 passed | 9 skipped

cd frontend && npm run lint
exit 0；0 errors，4 个既有 warning

cd frontend && npm run build
exit 0

git diff --check
exit 0
```

### 65.6 未尽事宜

1. **慢模型观测**：180s 停滞窗口 + 模型调用/流式输出算进度的组合仍需真实长 Research 任务回归；若仍触发，可先调大 `RESEARCH_AGENT_STALL_TIMEOUT_SECONDS`。
2. **导览失败率**：截断修复与 1024 token 已覆盖主要失败模式；仍失败时前端会显示「导览暂不可用」+ 重试，不再静默。
3. **引用格式**：prompt 约束 + 前端容错双保险；若模型仍输出非标准格式，可再评估编号引用彻底重构（§64 未尽事宜 4）。

---

## 66. Ask 路径引用反引号转义未还原（2026-08-04 追加）

### 66.1 问题

- 用户反馈 Ask 回答中引用显示为反引号代码样式（如 `` `[1](#ref-source-6462jcxkee5dqz25avy8)` ``），不可点击。
- **根因**：模型输出被反引号转义的内部锚点链接时，`normalizeInternalReferenceLinks()` 负责还原——但仅 `convertReferencesToCompactMarkdown`（Chat 路径）调用它；`convertReferencesToMarkdownLinks`（Ask 路径，`StreamingResponse.tsx` 唯一调用点）在 §65 只补了 `#ref-` 锚点保护，**漏了 normalize 还原**，反引号保留 → ReactMarkdown 渲染为行内 `<code>`。

### 66.2 修复

- `frontend/src/lib/utils/source-references.tsx`：`convertReferencesToMarkdownLinks` 开头调用 `normalizeInternalReferenceLinks(text)`（顺序：normalize → protect → parse → restore）。
- `frontend/src/lib/utils/source-references.test.ts` 新增 3 条：反引号锚点在 markdown-links 与 compact 两条路径均还原、与裸 `[source:xxx]` 共存。

### 66.3 验证

```text
cd frontend && NODE_OPTIONS=--no-experimental-webstorage npm test -- --run src/lib/utils/source-references.test.ts
9 passed

cd frontend && NODE_OPTIONS=--no-experimental-webstorage npm test -- --run
217 passed | 9 skipped

cd frontend && npm run lint
exit 0；0 errors，4 个既有 warning

cd frontend && npm run build
exit 0

git diff --check
exit 0
```

---

## 69. 导览卡片生成失败根因：模型不遵循 JSON + 新增可配置导览模型（新增 2026-08-05）

### 69.1 问题与根因

- 用户反馈：导览卡片始终生成失败，停留在「导览暂不可用」。§65 的解析鲁棒性增强未解决问题。
- 实测复现：`_invoke_json_model(_build_guide_prompt(...))` 默认用 `default_chat_model`（gemini-3.5-flash via jp.pincc.ai 中转），模型返回 **115 字符的非 JSON 内容**（prompt 指令回声 + 一个问题开头），`_parse_json_object` 的截断修复/围栏剥离/兜底均无能为力（输出根本不是 JSON 结构）。
- **根因不是 prompt、不是解析代码、不是 max_tokens**——是 **gemini-3.5-flash via jp.pincc.ai 中转不遵循 "Return strict JSON only" 指令**，返回极短的非结构化内容。

### 69.2 模型对比实测

对同一导览 prompt 实测 7 个模型：

| 模型 | 供应商 | raw 长度 | JSON? | 解析 |
|------|--------|---------|-------|------|
| deepseek-v4-pro | DeepSeek 官方 | 464 | ✅ | ✅ 成功 |
| **deepseek-v4-flash** | DeepSeek 官方 | 470 | ✅ | ✅ 成功 |
| qwen3.7-plus | Qwen(dashscope) | 0 | ❌ | ❌ 空响应 |
| qwen3.7-max | Qwen(dashscope) | 0 | ❌ | ❌ 空响应 |
| qwen3.6-flash | Qwen(dashscope) | 0 | ❌ | ❌ 空响应 |
| glm-5.2 | 火山引擎 | — | — | ❌ 429 配额超限 |
| gemini-3.5-flash | Google(中转) | 41 | ❌ | ❌ 非 JSON 乱码 |

**结论**：DeepSeek 系列是当前环境唯一验证可靠的 JSON 输出模型（v4-pro 和 v4-flash 都行）。

### 69.3 max_tokens 与上下文窗口的澄清

- 用户疑问：模型上下文 1MB/250KB，为何 max_tokens 默认 1024？
- **两者独立**：上下文窗口 = 输入+输出总量；max_tokens = 输出 token 上限。1M 上下文模型完全可以读 999K 输入 + 只允许写 1024 输出。
- 1024 是导览输出的合理上限：摘要 ~300 token + 3 问题 ~300 token + JSON 语法 ~50 token ≈ 700 token，1024 留 ~50% 余量。设上限还控制成本/延迟/防发散。
- gemini 失败（115 字符）**不是 max_tokens 截断**——模型主动返回非 JSON 短内容后停止。

### 69.4 §65 修复保留决策

- §65 的解析鲁棒性增强（截断修复/围栏剥离/questions 兜底/前端失败态）**不清理，全部保留**——它们针对的是不同的失败模式（截断/格式漂移），与本次根因（模型不遵循 JSON）互补，是多层防御。换 deepseek 后偶发截断/围栏仍由 §65 兜底。

### 69.5 决策与实现（方案 A：可配置导览模型）

- **新增 `default_guide_model` 字段**（可配置，不硬编码 model id）：
  - migration 31：`DEFINE FIELD default_guide_model ON TABLE default_models TYPE option<string>`
  - `DefaultModels` 加 `default_guide_model: Optional[str]`
  - `DefaultModelsResponse` + `api/routers/models.py` GET/PUT 透传
  - `generate_notebook_guide`：优先用 `default_guide_model`，空则回退 `default_chat_model`（向后兼容）
- **前端配置入口**：`/settings/api-keys` 页面「高级」区新增「导览模型」下拉（与转换/工具/大上下文/视觉同组，不设必填）；新增 `guideModelLabel` / `guideModelDesc` i18n（zh-CN/en-US）。
- 管理员在设置页把导览模型配成 deepseek-v4-flash（或 pro）即可；留空维持现状。

### 69.6 文件索引

| 文件 | 改动 |
|------|------|
| `open_notebook/database/migrations/31.surrealql` + `31_down.surrealql` | **新增** — default_guide_model 字段 |
| `open_notebook/ai/models.py` | DefaultModels 加字段 |
| `api/models.py` | DefaultModelsResponse 加字段 |
| `api/routers/models.py` | GET/PUT 透传 |
| `api/notebook_guide_service.py` | generate_notebook_guide 优先用 guide model，回退 chat model |
| `frontend/src/app/(dashboard)/settings/api-keys/page.tsx` | advancedConfigs 加导览模型项 |
| `frontend/src/lib/types/models.ts` | ModelDefaults 加字段 |
| `frontend/src/lib/locales/{zh-CN,en-US}/index.ts` | guideModelLabel / guideModelDesc |

### 69.7 验证

```text
真实 DB 端到端：
  UPDATE default_guide_model = 'model:rzv6gun8oukhukiwir0r' (deepseek-v4-flash)
  generate_notebook_guide(notebook:yftlcwunmlqpgbtno3aw, force=True)
    -> status: ready, summary + 3 个完整问题 ✅
  （已还原为 NONE，待用户在设置页配置）

.venv/bin/python -m pytest tests/ -m "not e2e" -q
458 passed, 33 deselected, 8 warnings

.venv/bin/python -m ruff check api/notebook_guide_service.py api/routers/models.py api/models.py open_notebook/ai/models.py
All checks passed

cd frontend && NODE_OPTIONS=--no-experimental-webstorage npm test -- --run
217 passed | 9 skipped

cd frontend && npm run lint
exit 0；0 errors，4 个既有 warning

cd frontend && npm run build
exit 0

git diff --check
exit 0
```

### 69.8 验收步骤

1. API 重启后 migration 31 自动应用（字段已就位，实测 `default_guide_model = None`）
2. 设置 → API Keys → 高级 → 导览模型 → 选 `deepseek-v4-flash`（或 pro）→ 保存
3. 打开笔记本（或点击「重新生成导览」）→ 导览卡片应正常生成
4. 留空导览模型 → 维持现状（用聊天模型，仍可能失败）

### 69.9 未尽事宜

1. **Qwen 空响应**：dashscope 兼容模式对导览 prompt 返回空响应（raw_len=0），是独立问题，不在本轮范围；日常 chat 用 Qwen 若正常，可能是导览的 `streaming=False` + `temperature=0` 组合在 dashscope 兼容端点行为异常，需单独排查。
2. **glm-5.2 配额**：429 超限无法验证 JSON 能力，配额恢复后可补充测试。
3. **导览模型可配置**：本方案不硬编码模型，管理员可随时在设置页更换；将来若有更优 JSON 模型可直接切换。

---

## 70. 全局 Ask 并行检索状态归并修复（新增 2026-08-05）

### 70.1 问题与根因

- 用户实测全局 Ask 报错：`⚠️ 系统提示：模型供应商返回错误 … error_code=external_service … At key 'ids': Can receive only one value per step. Use an Annotated key to handle multiple values. INVALID_CONCURRENT_GRAPH_UPDATE`。截屏与录屏见用户桌面 2026-08-04 17:10/17:11 文件。
- 根因：§64 为引用修复让 `provide_answer` 节点返回值新增 `"ids"`，但 Ask 图父状态 `ThreadState` 只给 `answers` / `retrieved_source_ids` 声明了 `Annotated[list, operator.add]` 归并器，未声明 `ids`。Ask 通过 `Send` 对每个检索词并行派发 `provide_answer`（最多 5 路），策略生成 ≥2 个检索词时多路同一步写 `ids`，LangGraph 抛 `InvalidUpdateError`。单检索词提问不触发，表现为"有时正常、有时报错"。
- 该异常在图运行时层抛出（节点本身正常返回），被 router 的 `classify_error` 兜底误分类为 `ExternalServiceError`，用户因此看到误导性的"模型供应商返回错误"。

### 70.2 决策

- `open_notebook/graphs/ask.py` — `ThreadState` 增加 `ids: Annotated[list, operator.add]`，与 `retrieved_source_ids` 同模式；并行更新改为拼接归并。`api/routers/search.py` 从节点输出事件收集 ids 且已去重，无需改动；`write_final_answer` 不消费状态中的 `ids`，跨检索词重复无害。
- `open_notebook/utils/error_classifier.py` — 新增首条规则：`can receive only one value per step` / `invalid_concurrent_graph_update` / `invalidupdateerror` 归类为 `OpenNotebookError` 基类（SSE wire 上映射 `internal_error`），内部图错误不再误报为"模型供应商返回错误"；前端已有 `errorInternal` 模板，无新增 i18n。
- 不改 Ask 检索策略、覆盖率统计、心跳/超时与引用修复链路；前端零改动。

### 70.3 文件索引

| 文件 | 改动 |
|------|------|
| `open_notebook/graphs/ask.py` | `ThreadState` 增加 `ids` 归并器 |
| `open_notebook/utils/error_classifier.py` | LangGraph 运行时错误归为内部错误规则 |
| `tests/test_ask_parallel_search.py` | **新增** — 双检索词全图并行回归（ids 并集/answers/final_answer）+ 单检索词回归 |
| `tests/test_error_classifier.py` | 新增 3 条 LangGraph 内部错误分类断言 |
| `docs/8-CUSTOMIZATION/00-index.md` | 本节记录 |

### 70.4 验证

```text
.venv/bin/python -m pytest tests/test_ask_parallel_search.py tests/test_error_classifier.py -q
30 passed, 1 warning

.venv/bin/python -m pytest tests/ -m "not e2e" -q
463 passed, 33 deselected, 8 warnings

.venv/bin/python -m ruff check open_notebook/graphs/ask.py open_notebook/utils/error_classifier.py tests/test_ask_parallel_search.py tests/test_error_classifier.py
All checks passed

git diff --check
exit 0
```

回归有效性：临时还原 `ask.py`（stash 归并器）后 `test_parallel_searches_merge_ids_without_invalid_update` 失败，恢复后通过，证明测试真实覆盖该并发缺陷。

未验证项：需重启 API 后在浏览器对全局 Ask 提一个会触发多检索词策略的问题做真实回归；若再次失败，错误气泡应显示 `internal_error` 而非 `external_service`。

---

## 71. 「询问与搜索」菜单文案统一为「提问与搜索」（新增 2026-08-05）

### 71.1 问题与决策

- 用户反馈侧边栏菜单显示「询问与搜索」，打开 `/search` 页面标题却是「提问与搜索」，同一页面名称两处不一致。
- 根因：`navigation.askAndSearch` 与 `searchPage.askAndSearch` 两个 i18n 键文案不同步。菜单（`AppSidebar`、`CommandPalette`）读前者，页面标题读后者。
- 按用户要求将「询问」统一为「提问」：`zh-CN` 导航键改为「提问与搜索」；`zh-TW` 存在同样的不一致（「詢問與搜尋」vs「提問與搜尋」），同步统一为「提問與搜尋」。
- 不改 `searchPage.ask`（嵌入选项 always/ask/never 的「询问」，语义为「每次询问」，非页面名称）与 `accessibility.enterQuestion` 占位文案；其余 7 个 locale 两键原本一致或无「询问」措辞问题，不动。历史文档（总账 §68 标题、旧周报）中的「询问与搜索」表述属历史快照，不回写。
- 现行用户帮助文档与开发文档中功能概念名「Ask（询问）」同步为「Ask（提问）」，与页面名称口径一致。

### 71.2 文件索引

| 文件 | 改动 |
|------|------|
| `frontend/src/lib/locales/zh-CN/index.ts` | `navigation.askAndSearch` 「询问与搜索」→「提问与搜索」 |
| `frontend/src/lib/locales/zh-TW/index.ts` | `navigation.askAndSearch` 「詢問與搜尋」→「提問與搜尋」 |
| `docs/2-CORE-CONCEPTS/index.md`、`docs/user_docs/2-CORE-CONCEPTS/index.md` | 功能概念名「Ask（询问）」→「Ask（提问）」 |
| `docs/2-CORE-CONCEPTS/chat-vs-transformations.md`、`docs/user_docs/2-CORE-CONCEPTS/chat-vs-transformations.md` | 同上 |
| `docs/8-CUSTOMIZATION/00-index.md` | 本节记录 |

### 71.3 验证

```text
cd frontend && NODE_OPTIONS=--no-experimental-webstorage npm test -- --run
217 passed | 9 skipped

cd frontend && npm run lint
0 errors, 4 pre-existing warnings

cd frontend && npm run build
exit 0
```

未验证项：浏览器目检菜单与页面标题一致（纯文案键值变更，自动测试与构建已覆盖渲染链路）。

---

## 72. 老 .doc 在 auto 引擎下不转 PDF 导致解析失败（新增 2026-08-10）

### 72.1 问题与根因

- 用户新上传两份老二进制 .doc（`低缓凝型降失水剂调整实验记录-2020.5.21_260810154519.doc`、`测 低缓凝型降失水剂调整实验记录-2020.4.17_260810153908.doc`），嵌入与图谱抽取长时间不完成。worker.log 显示两个源反复重试后放弃：`Error during content extraction ... Unable to determine file type for: ...doc` → `Command open_notebook.process_source failed after 15 attempt(s)`。
- 文件确认为 OLE2 复合文档（`file` 输出 `Composite Document File V2`，magic `d0cf 11e0`），content_core 的 auto 引擎无法识别。
- 根因：`open_notebook/graphs/source.py:_sync_extract` 的 `.doc→PDF` 转换只在 `engine == "mineru"` 分支（1152 行，内部 1156 调 `convert_to_modern_office_format`）和 `.xls` 分支（原 1253 行）发生。`.doc` + `engine=auto` → 两条件都不满足 → 原始 .doc 直送 `extract_content`（1266 行）→ "Unable to determine file type" → 重试 15 次后放弃 → `full_text=null` → 嵌入/KG 永不执行。
- 配置漂移：`.env` 未设 `CCORE_DOCUMENT_ENGINE`，DB `content_settings` 文档引擎字段为空 → 回退 `auto`（worker.log 实测 `Engine doc: auto`）。§58 时引擎是 `mineru`（走 1152 分支会先转 PDF）所以能成功；之后引擎变 `auto`，auto 路径不转 .doc 的缺口暴露。LibreOffice 26.2.5 正常，非 §58 的缺失问题。
- 重试接口 `POST /sources/{id}/retry`（sources.py:1165-1168）要求源关联笔记本；这两个源 worker.log 显示 `notebook_ids: []`（上传到全局来源库），故 UI 重试会被拒。

### 72.2 决策

- `open_notebook/graphs/source.py:1253` — 把 `endswith(".xls")` 扩为 `endswith((".doc", ".ppt", ".xls"))`，让 auto/simple/docling 路径也把老二进制 `.doc/.ppt` 经 LibreOffice 转 PDF 再交 content_core（与 mineru 分支 1156 一致、符合 §27.1 意图）。
- `.docx/.pptx` 不纳入：content_core 原生支持，转 PDF 反而丢结构。`convert_to_modern_office_format` 对非 Office 扩展名 no-op、失败优雅回退原路径，安全；mineru 成功时 file_path 已是 .pdf 不会重复转换，mineru 失败回退 simple 时 .doc 也会被正确转换。
- 不改引擎配置（仍 auto）、不改 office_converter、不改重试接口；前端零改动。

### 72.3 文件索引

| 文件 | 改动 |
|------|------|
| `open_notebook/graphs/source.py` | `_sync_extract` auto 分支转换元组扩展含 `.doc`/`.ppt` |
| `tests/test_source_office_conversion.py` | **新增** — auto 引擎下 .doc/.ppt 转 PDF、.docx 不转换三条回归 |
| `docs/8-CUSTOMIZATION/00-index.md` | 本节记录 |

### 72.4 验证

```text
.venv/bin/python -m pytest tests/test_source_office_conversion.py -q
3 passed

.venv/bin/python -m pytest tests/ -m "not e2e" -q
466 passed, 33 deselected, 8 warnings

.venv/bin/python -m ruff check open_notebook/graphs/source.py tests/test_source_office_conversion.py
All checks passed

git diff --check
exit 0
```

回归有效性：临时还原 `source.py`（stash 修复）后 `.doc`/`.ppt` 两条用例失败、`.docx` 仍通过，证明测试真实覆盖该缺口。

### 72.5 实机回归

只重启 worker（修复仅在 `source.py`，被 worker 的 `content_process` 使用；API/前端/DB 未重启），对两个失败源 `source:oqd8gy611ill0v09vn83`、`source:bhemgganqcib6v901tv0` 经 `CommandService.submit_command_job("open_notebook","process_source",...)` 直提（源 0 笔记本，UI 重试会 400）。新 worker（修复后代码）结果：

| 源 | content_process | embedding | insight | KG（DB 实查） |
|----|---|---|---|---|
| oqd8gy611ill0v09vn83 | 5.01s 成功 | embedded=True，4 chunks | 已建已嵌 | 84 实体 / 274 关系 |
| bhemgganqcib6v901tv0 | 5.31s 成功 | embedded=True，12 chunks | 已建已嵌 | 80 实体 / 211 关系 |

最终源详情：`embedded=True`、`kg_extracted=True`、`full_text` 1848/5000 字符。先前 worker（旧代码）对同样 .doc 反复 "Unable to determine file type" 重试 15 次放弃；修复后一次成功，证明根因消除。

注：oqd8 因重提命令被处理两次（幂等保存 + KG UPSERT 去重，无害）。KG 实体/关系存于 `kg_entity`/`kg_relation` 表，前端通过源 `kg_extracted` 标志确认；无按源的 `/knowledge-graph` 读取端点（先前 curl 命中 404，非持久化失败）。worker 现为独立进程（非 make 托管），下次 `make start-all` 会自然归一。

---

## 73. 设置页 API 密钥/白名单被清空：掩码哨兵 + PATCH 语义修复（新增 2026-08-11）

### 73.1 问题与根因

- 用户以管理员登录查看设置页，发现 Tavily API Key、Firecrawl API Key、Tavily 域名白名单等项全空白。DB 实查 `open_notebook:content_settings` 记录中 `tavily_api_key`、`tavily_include_domains`、`firecrawl_api_key` 均为空串，`url_engine` 从 §61 时的 `firecrawl` 变为 `auto`。**密钥已丢失**（`.env` 无 `TAVILY_API_KEY`/`FIRECRAWL_API_KEY` 兜底，二者为 DB-only）。
- 清空由两个叠加 bug 造成：
  1. **前端 `SettingsForm.tsx:72` reset 守卫**：表单填充 `useEffect` 写成 `settings && settings.default_content_processing_engine_doc && ...`，要求"文档引擎"字段有值才填充。当 DB 该字段为空（env 回退 `auto` 的场景）时 **reset 永不触发**，表单保持 `defaultValues` 的空串（`tavily_api_key:''`、`firecrawl_api_key:''`、`tavily_include_domains:''`）。
  2. **后端 `settings.py:76-81` PUT 守卫**：用 `is not None`——前端提交空串（非 null）被当真值覆盖。用户在表单未填充状态下改了某个不相关字段并保存 → 空串覆盖 DB 里真实 key → 清空。
- 先前看到的"********************"是表单正常填充时 password 输入框的浏览器掩码点（key 有值即显示点）；DB 被清空后字段就空了。

### 73.2 决策（正确做法）

- **后端 `api/routers/settings.py`**：
  - 新增 `MASKED_SECRET = "*" * 20` 与 `_mask_secret()`。GET 对 `tavily_api_key`、`firecrawl_api_key` 返回哨兵（已配置）或 `""`（未配置），**原始 key 永不下发浏览器**（与 credentials 路由"Never returns api_key"一致）。`tavily_include_domains`（白名单，非密钥）仍返回原值。
  - PUT 对两个密钥字段增加 `!= MASKED_SECRET` 守卫——即便客户端误回传哨兵也不把它存成真实 key（防御性，与前端 PATCH 语义双保险）。
- **前端 `SettingsForm.tsx`**：
  - reset 守卫改为 `settings && !hasResetForm && !isFetching`（去掉 `default_content_processing_engine_doc` 真值依赖），表单始终用 GET 结果填充。
  - `onSubmit` 对 `tavily_api_key`/`tavily_include_domains`/`firecrawl_api_key` 改为 PATCH 语义：字段值与 GET 原值相等则发 `null`（后端 `is not None` 跳过、不覆盖），用户改了才发新值，清空发 `""`。这样即使用户只改了不相关字段并保存，未改动的密钥也不会被空串覆盖。
- 不改 `ContentSettings` 模型、迁移、引擎配置；前端零新增 i18n（沿用既有 placeholder 文案）。

### 73.3 文件索引

| 文件 | 改动 |
|------|------|
| `api/routers/settings.py` | `MASKED_SECRET`/`_mask_secret()`；GET 掩码密钥；PUT `!= MASKED_SECRET` 守卫 |
| `frontend/src/app/(dashboard)/settings/components/SettingsForm.tsx` | reset 守卫去掉 doc 真值依赖；onSubmit 对三个字段发 null（未改动） |
| `tests/test_firecrawl_key_settings.py` | GET 掩码断言（firecrawl+tavily）、PUT 存原值响应掩码、PUT 哨兵不覆盖、PUT 缺字段不覆盖 |
| `frontend/src/app/(dashboard)/settings/components/SettingsForm.test.tsx` | 填充哨兵显示、新 key 提交、未改动发 null、doc 为空也填充 |
| `docs/8-CUSTOMIZATION/00-index.md` | 本节记录 |

### 73.4 验证

```text
.venv/bin/python -m pytest tests/test_firecrawl_key_settings.py -q
11 passed

.venv/bin/python -m pytest tests/ -m "not e2e" -q
469 passed, 33 deselected, 10 warnings

.venv/bin/python -m ruff check api/routers/settings.py tests/test_firecrawl_key_settings.py
All checks passed

cd frontend && NODE_OPTIONS=--no-experimental-webstorage npm test
219 passed | 9 skipped

cd frontend && npm run lint   # 0 errors, 4 既有 warning
cd frontend && npm run build  # exit 0

git diff --check
exit 0
```

回归有效性：临时 stash `SettingsForm.tsx` 修复后"doc 为空也填充"与"未改动发 null"两条用例失败、另两条仍通过，证明测试真实覆盖该缺口。

### 73.5 测试隔离修复（避免污染生产 DB）

- 首轮运行 `test_put_settings_*` 后实查 DB，发现 `tavily_api_key="tvly-kept"`、`firecrawl_api_key="fc-kept"`、`tavily_include_domains="example.com"`——测试值被写进了生产 `open_notebook:content_settings` 记录。
- 根因：`conftest.py` 加载 `.env`，测试连真实 SurrealDB（127.0.0.1:8001）；PUT 测试用 `patch.object(settings, "update", AsyncMock())` 想挡住 `await settings.update()`，但 **pydantic 模型实例上 patch 一个继承来的非字段方法不生效**（类方法优先 / `__setattr__` 不挡），handler 的 `await settings.update()` 走了真实 `RecordModel.update → repo_upsert` → 写生产 DB。§61 既有 PUT 测试同款潜在 bug。
- 修复：PUT 测试改用**类级** `patch.object(ContentSettings, "update", AsyncMock())`（挡类方法，所有实例生效）。验证：单独跑 `test_put_settings_omitted_fields_are_not_overwritten` 后 DB 保持空；全量 `tests/ -m "not e2e"` 后 DB 仍保持空。
- 已清理本次污染（三字段重置为空串）。未来测试不应再写 content_settings。

### 73.6 数据与未尽事宜

- **密钥丢失**：Tavily/Firecrawl API key 与白名单已无 DB/env 备份，需用户在修复部署后于设置页重新录入。重新录入后：GET 显示掩码点（已配置指示），保存时新值正常落库（不再被空串覆盖）。
- `default_content_processing_engine_url` 从 `firecrawl` 变 `auto` 是先前一次保存（用户选择）的结果，非 bug；用户若需 firecrawl 可在设置页重新选。
- 实机已验证：重启 API 后 `GET /api/settings` 对空密钥返回 `""`（未配置），掩码路径生效；密钥配置后将返回 `********************`。
- 未验证项：浏览器登录态目检设置页——重新录入密钥后显示掩码点、改其它字段保存不抹掉密钥。

---

## 74. 设置页提交按钮文案改为「保存设置」（新增 2026-08-11）

- 用户反馈设置页底部提交按钮显示为「设置」（沿用 `t.navigation.settings`），语义不清；改为「保存设置」。
- `frontend/src/app/(dashboard)/settings/components/SettingsForm.tsx` 提交按钮非 pending 态文案从 `t.navigation.settings` 改为新增键 `t.settings.saveSettings`；pending 态仍为 `t.common.saving`。
- 9 个语言包 `settings` 区段新增 `saveSettings`：zh-CN「保存设置」、en-US「Save Settings」、zh-TW「儲存設定」、ja-JP「設定を保存」、fr-FR「Enregistrer les paramètres」、ru-RU「Сохранить настройки」、pt-BR「Salvar configurações」、it-IT「Salva impostazioni」、bn-IN「সেটিংস সংরক্ষণ করুন」。
- 验证：`SettingsForm.test.tsx` 4 通过（既有 `/settings/i` 断言匹配 "Save Settings"）；全量 `npm test` 219 通过；`npm run lint` 0 错误；`npm run build` 通过。
