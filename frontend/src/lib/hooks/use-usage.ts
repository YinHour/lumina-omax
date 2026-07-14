import { useQuery } from '@tanstack/react-query'

import { usageApi } from '@/lib/api/usage'
import type { UsageDays, UsageScope } from '@/lib/types/usage'

export const usageQueryKey = (days: UsageDays, scope: UsageScope, userId?: string) => (
  ['usage', days, scope, userId ?? 'all'] as const
)

export function useUsage(days: UsageDays, scope: UsageScope, userId?: string) {
  return useQuery({
    queryKey: usageQueryKey(days, scope, userId),
    queryFn: () => usageApi.getDashboard(days, scope, userId),
  })
}
