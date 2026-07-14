export type UsageDays = 7 | 30 | 90
export type UsageScope = 'mine' | 'all'

export interface UsageTotals {
  input_tokens: number
  output_tokens: number
  total_tokens: number
  calls: number
  failed_calls: number
}

export interface UsageSeriesPoint extends UsageTotals {
  date: string
}

export interface UsageCredentialBreakdown extends UsageTotals {
  credential_id: string | null
  credential_name: string
  provider: string
}

export interface UsageUserBreakdown extends UsageTotals {
  user_id: string | null
  username: string
}

export interface UsageRecentItem {
  id: string
  user_id: string | null
  username: string
  credential_id: string | null
  credential_name: string
  provider: string
  model_name: string
  surface: string
  input_tokens: number
  output_tokens: number
  total_tokens: number
  token_source: 'provider' | 'estimated'
  status: 'success' | 'failed'
  duration_ms: number
  created: string
}

export interface UsageUserOption {
  id: string
  username: string
  display_name: string
}

export interface UsageDashboardResponse {
  scope: UsageScope
  days: number
  selected_user_id: string | null
  totals: UsageTotals
  series: UsageSeriesPoint[]
  by_credential: UsageCredentialBreakdown[]
  by_user: UsageUserBreakdown[]
  recent: UsageRecentItem[]
  users: UsageUserOption[]
}
