import apiClient from './client'
import {
  NotebookResponse,
  CreateNotebookRequest,
  UpdateNotebookRequest,
  NotebookAggregateRequest,
  NotebookDeletePreview,
  NotebookDeleteResponse,
  NotebookGuideResponse,
  NotebookPasswordUpdateRequest,
} from '@/lib/types/api'

export const notebooksApi = {
  list: async (params?: { archived?: boolean; order_by?: string }) => {
    const response = await apiClient.get<NotebookResponse[]>('/notebooks', { params })
    return response.data
  },

  get: async (id: string) => {
    const response = await apiClient.get<NotebookResponse>(`/notebooks/${id}`)
    return response.data
  },

  getGuide: async (id: string) => {
    const response = await apiClient.get<NotebookGuideResponse>(`/notebooks/${id}/guide`)
    return response.data
  },

  regenerateGuide: async (id: string) => {
    const response = await apiClient.post<NotebookGuideResponse>(`/notebooks/${id}/guide/regenerate`)
    return response.data
  },

  create: async (data: CreateNotebookRequest) => {
    const response = await apiClient.post<NotebookResponse>('/notebooks', data)
    return response.data
  },

  aggregate: async (data: NotebookAggregateRequest) => {
    const response = await apiClient.post<NotebookResponse>('/notebooks/aggregate', data)
    return response.data
  },

  update: async (id: string, data: UpdateNotebookRequest) => {
    const response = await apiClient.put<NotebookResponse>(`/notebooks/${id}`, data)
    return response.data
  },

  deletePreview: async (id: string) => {
    const response = await apiClient.get<NotebookDeletePreview>(
      `/notebooks/${id}/delete-preview`
    )
    return response.data
  },

  delete: async (id: string, deleteExclusiveSources: boolean = false, password?: string) => {
    const config: Record<string, unknown> = {
      params: { delete_exclusive_sources: deleteExclusiveSources },
    }
    if (password) {
      config.headers = { 'X-Notebook-Password': password }
    }
    const response = await apiClient.delete<NotebookDeleteResponse>(`/notebooks/${id}`, config)
    return response.data
  },

  addSource: async (notebookId: string, sourceId: string) => {
    const response = await apiClient.post(`/notebooks/${notebookId}/sources/${sourceId}`)
    return response.data
  },

  removeSource: async (notebookId: string, sourceId: string) => {
    const response = await apiClient.delete(`/notebooks/${notebookId}/sources/${sourceId}`)
    return response.data
  },

  updatePassword: async (notebookId: string, data: NotebookPasswordUpdateRequest) => {
    const response = await apiClient.patch(`/notebooks/${notebookId}/password`, data)
    return response.data
  },
}
