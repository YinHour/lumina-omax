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

### 服务端路由守卫（Middleware）
- `frontend/src/middleware.ts` — **新增文件**（替代废弃的 `src/proxy.ts`）
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
| `frontend/src/middleware.ts` | 服务端路由守卫，Cookie 鉴权（§12 新增） |
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
- SSE 流式中 Zstand store 每 chunk 更新触发渲染 → effect 连锁执行 → 1000+ 次 `t.searchPage` 访问

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

> 最后更新：2026-06-07 | 新增 §18（用户反馈驱动优化），分支 `enhance_sourcepage_optim_0605`。
