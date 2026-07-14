import apiClient from './client'
import type { UsageDashboardResponse, UsageDays, UsageScope } from '@/lib/types/usage'

export const usageApi = {
  getDashboard: async (days: UsageDays, scope: UsageScope, userId?: string) => {
    const response = await apiClient.get<UsageDashboardResponse>('/usage', {
      params: {
        days,
        scope,
        ...(userId ? { user_id: userId } : {}),
      },
    })
    return response.data
  },
}
