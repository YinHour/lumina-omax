// Search types
export interface SearchRequest {
  query: string
  type: 'text' | 'vector'
  limit: number
  search_sources: boolean
  search_notes: boolean
  minimum_score: number
}

export interface SearchResult {
  id: string
  title: string
  parent_id: string
  final_score: number
  matches?: string[]
  relevance?: number
  similarity?: number
  score?: number
  type?: string
  source_type?: string
  created: string
  updated: string
}

export interface SearchResponse {
  results: SearchResult[]
  total_count: number
  search_type: string
}

// Ask types
export interface AskRequest {
  question: string
  strategy_model: string
  answer_model: string
  final_answer_model: string
}

export interface AskResponse {
  answer: string
  question: string
}

export interface AskCoverage {
  total_sources: number
  embedded_sources: number
  retrieved_sources: number
  retrieved_source_ids: string[]
}

// SSE Streaming types
export interface StrategyData {
  reasoning: string
  searches: Array<{
    term: string
    instructions: string
  }>
}

export interface AskStreamEvent {
  type:
    | 'strategy'
    | 'strategy_reasoning_chunk'
    | 'answer'
    | 'final_answer'
    | 'coverage'
    | 'complete'
    | 'error'
    | 'heartbeat'
  reasoning?: string
  searches?: Array<{ term: string; instructions: string }>
  content?: string
  chunk?: string
  final_answer?: string
  coverage?: AskCoverage
  total_sources?: number
  embedded_sources?: number
  retrieved_sources?: number
  retrieved_source_ids?: string[]
  message?: string
  // Heartbeat fields (silence-based keep-alive while a phase is running).
  stage?: string
  elapsed_ms?: number
  // Error fields (§31/§32: stable wire identifier + timeout details).
  error_code?: string
  timeout_seconds?: number
}
