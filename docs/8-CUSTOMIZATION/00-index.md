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

> 最后更新：2026-06-14 | 新增 §25（添加来源数量上限设置）。当前分支 `codex/source-add-limit-setting` 将该设置定义为单个笔记本来源总数上限，覆盖新添加来源和添加现有来源两个前端入口，不新增后端批量创建语义。
