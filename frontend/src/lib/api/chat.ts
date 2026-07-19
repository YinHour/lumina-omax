import apiClient from './client'
import {
  NotebookChatSession,
  NotebookChatSessionWithMessages,
  CreateNotebookChatSessionRequest,
  UpdateNotebookChatSessionRequest,
  SendNotebookChatMessageRequest,
  SendNotebookResearchMessageRequest,
  BuildContextRequest,
  BuildContextResponse,
  ResearchSkillSummary,
} from '@/lib/types/api'

export const chatApi = {
  listResearchSkills: async () => {
    const response = await apiClient.get<ResearchSkillSummary[]>(
      `/chat/research/skills`
    )
    return response.data
  },

  // Session management
  listSessions: async (notebookId: string) => {
    const response = await apiClient.get<NotebookChatSession[]>(
      `/chat/sessions`,
      { params: { notebook_id: notebookId } }
    )
    return response.data
  },

  createSession: async (data: CreateNotebookChatSessionRequest) => {
    const response = await apiClient.post<NotebookChatSession>(
      `/chat/sessions`,
      data
    )
    return response.data
  },

  getSession: async (
    sessionId: string,
    options: { limit?: number; before_sequence?: number } = {}
  ) => {
    const response = await apiClient.get<NotebookChatSessionWithMessages>(
      `/chat/sessions/${sessionId}`,
      { params: options }
    )
    return response.data
  },

  getAllSessionMessages: async (sessionId: string) => {
    let cursor: number | undefined
    let messages: NotebookChatSessionWithMessages['messages'] = []

    do {
      const page = await chatApi.getSession(sessionId, {
        limit: 200,
        ...(cursor === undefined ? {} : { before_sequence: cursor }),
      })
      messages = [...page.messages, ...messages]
      const nextCursor = page.next_cursor ?? undefined
      if (!page.has_more || nextCursor === undefined || nextCursor === cursor) {
        break
      }
      cursor = nextCursor
    } while (true)

    return messages
  },

  updateSession: async (sessionId: string, data: UpdateNotebookChatSessionRequest) => {
    const response = await apiClient.put<NotebookChatSession>(
      `/chat/sessions/${sessionId}`,
      data
    )
    return response.data
  },

  deleteSession: async (sessionId: string) => {
    await apiClient.delete(`/chat/sessions/${sessionId}`)
  },

  // Messaging with streaming
  sendMessage: async (data: SendNotebookChatMessageRequest, signal?: AbortSignal) => {
    let token = null
    if (typeof window !== 'undefined') {
      const authStorage = localStorage.getItem('auth-storage')
      if (authStorage) {
        try {
          const { state } = JSON.parse(authStorage)
          if (state?.token) {
            token = state.token
          }
        } catch (error) {
          console.error('Error parsing auth storage:', error)
        }
      }
    }

    const { getApiUrl } = await import('@/lib/config')
    const baseUrl = await getApiUrl()
    const url = `${baseUrl}/api/chat/execute`

    return fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` })
      },
      body: JSON.stringify(data),
      signal,
    }).then(response => {
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      return response.body
    })
  },

  sendResearchMessage: async (data: SendNotebookResearchMessageRequest, signal?: AbortSignal) => {
    let token = null
    if (typeof window !== 'undefined') {
      const authStorage = localStorage.getItem('auth-storage')
      if (authStorage) {
        try {
          const { state } = JSON.parse(authStorage)
          if (state?.token) token = state.token
        } catch (error) {
          console.error('Error parsing auth storage:', error)
        }
      }
    }

    const { getApiUrl } = await import('@/lib/config')
    const baseUrl = await getApiUrl()
    return fetch(`${baseUrl}/api/chat/research/execute`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` })
      },
      body: JSON.stringify(data),
      signal,
    }).then(response => {
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      return response.body
    })
  },

  buildContext: async (data: BuildContextRequest) => {
    const response = await apiClient.post<BuildContextResponse>(
      `/chat/context`,
      data
    )
    return response.data
  },
}

export default chatApi
