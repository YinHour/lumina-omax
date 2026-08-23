import apiClient from './client'
import {
  RedactionRule,
  RedactionRuleCreate,
  RedactionRuleUpdate,
} from '@/lib/types/api'

export const redactionApi = {
  list: async () => {
    const response = await apiClient.get<RedactionRule[]>('/redaction/rules')
    return response.data
  },

  create: async (data: RedactionRuleCreate) => {
    const response = await apiClient.post<RedactionRule>('/redaction/rules', data)
    return response.data
  },

  update: async (id: string, data: RedactionRuleUpdate) => {
    const response = await apiClient.put<RedactionRule>(
      `/redaction/rules/${id}`,
      data
    )
    return response.data
  },

  delete: async (id: string) => {
    await apiClient.delete(`/redaction/rules/${id}`)
  },
}
