export type NotebookChatProgressStage =
  | 'received'
  | 'preparing_context'
  | 'context_ready'
  | 'planning'
  | 'inspecting_scope'
  | 'searching_notebook'
  | 'reading_evidence'
  | 'searching_cross_notebook'
  | 'searching_web'
  | 'inspecting_scientific_databases'
  | 'searching_scientific_databases'
  | 'reading_scientific_record'
  | 'loading_research_skills'
  | 'using_research_tool'
  | 'awaiting_model'
  | 'synthesizing'
  | 'model_streaming'

export interface NotebookChatActivityStep {
  stage: NotebookChatProgressStage
  status: 'active' | 'complete' | 'error' | 'cancelled'
}

export type NotebookChatActivityTerminal =
  | 'complete'
  | 'error'
  | 'cancelled'
  | null
