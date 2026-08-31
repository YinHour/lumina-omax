export interface NotebookResponse {
  id: string
  name: string
  description: string
  archived: boolean
  created: string
  updated: string
  source_count: number
  note_count: number
  password?: string | null
  creator_name?: string | null
  created_by?: string | null
  is_aggregated: boolean
  aggregated_notebooks?: string[]
}

export type NotebookGuideStatus = 'empty' | 'ready' | 'error'

export interface NotebookContextWindowUsage {
  model_id: string
  model_name: string
  provider: string
  input_tokens: number
  context_window_tokens?: number | null
  context_window_source?: 'configured' | 'builtin' | null
  estimated: boolean
}

export interface NotebookGuideResponse {
  notebook_id: string
  source_count: number
  generated_at?: string | null
  summary?: string | null
  questions: string[]
  status: NotebookGuideStatus
}

export interface NoteResponse {
  id: string
  title: string | null
  content: string | null
  note_type: string | null
  created: string
  updated: string
}

export interface SourceListResponse {
  id: string
  title: string | null
  topics?: string[]                  // Make optional to match Python API
  asset: {
    file_path?: string
    url?: string
    original_filename?: string | null
  } | null
  embedded: boolean
  embedded_chunks: number            // ADD: From Python API
  kg_extracted: boolean              // ADD: From Python API
  insights_count: number
  created: string
  updated: string
  file_available?: boolean
  // ADD: Async processing fields from Python API
  command_id?: string
  status?: string
  processing_info?: Record<string, unknown>
  notebook_count: number
  origin_notebook_id?: string | null
  origin_notebook_name?: string | null
  imported_at?: string | null
  uploader_name?: string | null
  uploaded_by?: string | null
}

export interface SourceListPaginatedResponse {
  items: SourceListResponse[]
  total: number
}

export interface SourceDetailResponse extends SourceListResponse {
  full_text: string
  notebooks?: string[]  // List of notebook IDs this source is linked to
}

export type SourceResponse = SourceDetailResponse

export interface SourceStatusResponse {
  status?: string
  message: string
  processing_info?: Record<string, unknown>
  command_id?: string
}

export interface SettingsResponse {
  default_content_processing_engine_doc?: string
  default_content_processing_engine_url?: string
  default_embedding_option?: string
  auto_delete_files?: string
  source_batch_limit?: number
  youtube_preferred_languages?: string[]
  tavily_api_key?: string | null
  tavily_include_domains?: string | null
  tavily_search_max_calls?: number
  firecrawl_api_key?: string | null
  redaction_enabled?: boolean
}

export type RedactionCategory =
  | 'company'
  | 'address'
  | 'person'
  | 'phone'
  | 'well'
  | 'product'
  | 'custom'

export interface RedactionRule {
  id: string
  original: string
  alias: string
  category: RedactionCategory | string
  enabled: boolean
  source: string
  note?: string | null
}

export interface RedactionRuleCreate {
  original: string
  alias: string
  category: RedactionCategory | string
  note?: string | null
}

export interface RedactionRuleUpdate {
  alias?: string
  category?: RedactionCategory | string
  enabled?: boolean
  note?: string | null
}

export interface CreateNotebookRequest {
  name: string
  description?: string
  password?: string
  creator_name?: string
}

export interface NotebookAggregateRequest {
  name: string
  description?: string
  password?: string
  creator_name?: string
  notebook_ids: string[]
  notebook_passwords: Record<string, string>
}

export interface UpdateNotebookRequest {
  name?: string
  description?: string
  archived?: boolean
  password?: string
  creator_name?: string
}

export interface NotebookPasswordUpdateRequest {
  action: 'set' | 'change' | 'remove'
  password?: string
  current_password?: string
}

export interface NotebookDeletePreview {
  notebook_id: string
  notebook_name: string
  note_count: number
  exclusive_source_count: number
  shared_source_count: number
}

export interface NotebookDeleteResponse {
  message: string
  deleted_notes: number
  deleted_sources: number
  unlinked_sources: number
}

export interface CreateNoteRequest {
  title?: string
  content: string
  note_type?: string
  notebook_id?: string
}

export interface CreateSourceRequest {
  // Backward compatibility: support old single notebook_id
  notebook_id?: string
  // New multi-notebook support
  notebooks?: string[]
  // Required fields
  type: 'link' | 'upload' | 'text'
  url?: string
  file_path?: string
  content?: string
  title?: string
  transformations?: string[]
  embed?: boolean
  delete_source?: boolean
  // New async processing support
  async_processing?: boolean
}

export interface UpdateNoteRequest {
  title?: string
  content?: string
  note_type?: string
}

export interface UpdateSourceRequest {
  title?: string
  type?: 'link' | 'upload' | 'text'
  url?: string
  content?: string
}

export interface APIError {
  detail: string
}

// Source Chat Types
// Base session interface with common fields
export interface BaseChatSession {
  id: string
  title: string
  created: string
  updated: string
  message_count?: number
  model_override?: string | null
}

export interface SourceChatSession extends BaseChatSession {
  source_id: string
  model_override?: string
}

export interface SourceChatMessage {
  id: string
  type: 'human' | 'ai'
  content: string
  timestamp?: string
}

export interface SourceChatContextIndicator {
  sources: string[]
  insights: string[]
  notes: string[]
}

export interface SourceChatSessionWithMessages extends SourceChatSession {
  messages: SourceChatMessage[]
  context_indicators?: SourceChatContextIndicator
}

export interface CreateSourceChatSessionRequest {
  source_id: string
  title?: string
  model_override?: string
}

export interface UpdateSourceChatSessionRequest {
  title?: string
  model_override?: string
}

export interface SendMessageRequest {
  message: string
  model_override?: string
  enable_web_search?: boolean
}

export interface SourceChatStreamEvent {
  type: 'user_message' | 'ai_message' | 'reasoning_status' | 'context_indicators' | 'complete' | 'error'
  content?: string
  data?: unknown
  message?: string
  timestamp?: string
}

// Notebook Chat Types
export type NotebookChatMode = 'quick' | 'research'
export type ResearchSkillMode = 'auto' | 'off' | 'selected'

export interface ResearchSkillSummary {
  id: string
  name: string
  version: string
  category: string
  description: string
  source: string
  license: string
  review_status: 'approved'
  allowed_tools: string[]
  order: number
}

export interface NotebookChatStreamEvent {
  type?: string
  content?: string
  message?: string
  questions?: unknown
  stage?: string
  status?: string
  elapsed_ms?: number
  error_code?: string
  timeout_seconds?: number
  model_id?: string
  model_name?: string
  provider?: string
  input_tokens?: number
  context_window_tokens?: number | null
  context_window_source?: 'configured' | 'builtin' | null
  estimated?: boolean
}

export interface NotebookChatSession extends BaseChatSession {
  notebook_id: string
  mode: NotebookChatMode
}

export interface NotebookChatMessage {
  id: string
  type: 'human' | 'ai'
  content: string
  timestamp?: string
  sequence?: number
}

export interface NotebookChatSessionWithMessages extends NotebookChatSession {
  messages: NotebookChatMessage[]
  has_more: boolean
  next_cursor?: number | null
}

export interface CreateNotebookChatSessionRequest {
  notebook_id: string
  title?: string
  model_override?: string
  mode?: NotebookChatMode
}

export interface UpdateNotebookChatSessionRequest {
  title?: string
  model_override?: string | null
}

export interface SendNotebookChatMessageRequest {
  session_id: string
  message: string
  context: {
    sources: Array<Record<string, unknown>>
    notes: Array<Record<string, unknown>>
  }
  model_override?: string
  enable_web_search?: boolean
}

export interface SendNotebookResearchMessageRequest {
  session_id: string
  message: string
  model_override?: string
  enable_web_search?: boolean
  allow_cross_notebook_discovery?: boolean
  enable_scientific_databases?: boolean
  research_skill_mode?: ResearchSkillMode
  research_skill_ids?: string[]
}

export interface BuildContextRequest {
  notebook_id: string
  context_config: {
    sources: Record<string, string>
    notes: Record<string, string>
  }
}

export interface BuildContextResponse {
  context: {
    sources: Array<Record<string, unknown>>
    notes: Array<Record<string, unknown>>
  }
  token_count: number
  char_count: number
}
