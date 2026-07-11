# Lumina OMax — Custom Development Changelog

本文档记录在 [lfnovo/open-notebook](https://github.com/lfnovo/open-notebook) 基础上进行的二次开发变更，包括功能增强、Bug 修复、架构决策等。按主题分类，每个条目标注涉及文件和关键决策。

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
- Markdown 导出只包含当前 UI 可见的人类/AI 消息，移除 `<think>` 推理块，不包含 ToolMessage、凭据或内部工具参数。
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

---

> 最后更新：2026-07-11 | 新增 §34。Quick/Research 改为独立 Tabs，并增加显式新会话、模式独立状态、自动保存反馈和安全 Markdown 导出。
