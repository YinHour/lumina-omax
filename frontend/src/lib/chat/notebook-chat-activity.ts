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
