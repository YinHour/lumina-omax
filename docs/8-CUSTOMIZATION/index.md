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
- `open_notebook/domain/user.py` — 新增 `User` 域名模型，PBKDF2-HMAC-SHA256 密码哈希（100,000 轮迭代 + 16 字节随机盐）
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

## 文件索引（关键变更文件）

| 文件 | 涉及主题 |
|------|----------|
| `open_notebook/graphs/source.py` | MinerU 集成、Excel 修复、Vision LLM、进度日志 |
| `open_notebook/ai/models.py` | `default_vision_model`、`get_vision_model()` |
| `open_notebook/utils/office_converter.py` | Office → PDF 转换、Excel 排除 |
| `open_notebook/utils/context_builder.py` | Notes 优先级反转、截断阈值 |
| `open_notebook/utils/jwt_config.py` | JWT 密钥公共模块（§12 新增） |
| `open_notebook/domain/notebook.py` | `original_filename`、`origin_notebook_id`、`uploaded_by`/`uploader_name`（§12） |
| `open_notebook/domain/user.py` | 用户域名模型，PBKDF2 密码哈希（§12 新增） |
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
| `pyproject.toml` | 注册 e2e marker |

---

> 最后更新：2026-06-01 | 新增 §12 多用户认证系统。前期变更基于分支 `bugfix/user_feedback_0529`（已合入 main，PR #10），以及 `enhancement_0526_feedback`、`feat_picture_parse_0528`。
