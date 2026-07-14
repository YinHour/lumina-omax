import { fireEvent, render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import UsagePage from './page'

const state = vi.hoisted(() => ({
  role: 'user',
  useUsage: vi.fn(),
}))

const dashboard = {
  scope: 'mine' as const,
  days: 30,
  selected_user_id: 'user:1',
  totals: { input_tokens: 1200, output_tokens: 300, total_tokens: 1500, calls: 3, failed_calls: 1 },
  series: [
    { date: '2026-07-13', input_tokens: 400, output_tokens: 100, total_tokens: 500, calls: 1, failed_calls: 0 },
    { date: '2026-07-14', input_tokens: 800, output_tokens: 200, total_tokens: 1000, calls: 2, failed_calls: 1 },
  ],
  by_credential: [
    { credential_id: 'credential:1', credential_name: 'DeepSeek production', provider: 'deepseek', input_tokens: 1200, output_tokens: 300, total_tokens: 1500, calls: 3, failed_calls: 1 },
  ],
  by_user: [
    { user_id: 'user:1', username: 'researcher', input_tokens: 1200, output_tokens: 300, total_tokens: 1500, calls: 3, failed_calls: 1 },
  ],
  recent: [
    { id: 'ai_token_usage:1', user_id: 'user:1', username: 'researcher', credential_id: 'credential:1', credential_name: 'DeepSeek production', provider: 'deepseek', model_name: 'DeepSeek V4 Pro', surface: 'global_ask', input_tokens: 400, output_tokens: 100, total_tokens: 500, token_source: 'provider' as const, status: 'success' as const, duration_ms: 900, created: '2026-07-14T08:00:00Z' },
  ],
  users: [{ id: 'user:1', username: 'researcher', display_name: 'Researcher' }],
}

vi.mock('@/components/layout/AppShell', () => ({ AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div> }))
vi.mock('@/components/layout/PageContainer', () => ({ PageContainer: ({ children }: { children: ReactNode }) => <main>{children}</main> }))
vi.mock('@/components/layout/PageHeader', () => ({ PageHeader: ({ title }: { title: string }) => <h1>{title}</h1> }))
vi.mock('@/components/ui/select', () => ({
  Select: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  SelectContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  SelectItem: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  SelectTrigger: ({ children }: { children: ReactNode }) => <button type="button">{children}</button>,
  SelectValue: () => null,
}))

vi.mock('@/lib/hooks/use-auth', () => ({
  useAuth: () => ({ user: { id: 'user:1', role: state.role } }),
}))

vi.mock('@/lib/hooks/use-usage', () => ({
  useUsage: (...args: unknown[]) => state.useUsage(...args),
}))

vi.mock('@/lib/hooks/use-translation', () => ({
  useTranslation: () => ({
    language: 'en-US',
    t: {
      usage: {
        title: 'AI token usage', description: 'Description', period: 'Period', period7: '7 days', period30: '30 days', period90: '90 days', scope: 'Scope', mine: 'My usage', allUsers: 'All users', userFilter: 'User', allUsersOption: 'All users', totalTokens: 'Total tokens', inputTokens: 'Input tokens', outputTokens: 'Output tokens', calls: 'Calls', failedCalls: '{count} failed', tokens: 'tokens', dailyUsage: 'Daily usage', dailyUsageDesc: 'Daily description', byCredential: 'Usage by key', byCredentialDesc: 'Key description', byUser: 'Usage by user', byUserDesc: 'User description', recentUsage: 'Recent activity', recentUsageDesc: 'Recent description', noUsage: 'No usage', loading: 'Loading', loadError: 'Error', model: 'Model', key: 'Key', user: 'User', surface: 'Workflow', time: 'Time', status: 'Status', source: 'Count source', providerReported: 'Provider', estimated: 'Estimated', success: 'Success', failed: 'Failed', callsCount: '{count} calls', providerReportedHint: 'Provider hint', adminHint: 'Admin hint', surfaceNotebookQuick: 'Quick chat', surfaceNotebookResearch: 'Research chat', surfaceSourceChat: 'Source chat', surfaceGlobalAsk: 'Global Ask', surfaceTransformation: 'Transformation', surfaceNoteGeneration: 'Note generation', surfaceNotebookGuide: 'Guide', surfaceModelTest: 'Model test', surfaceCredentialManagement: 'Credential', surfaceSourceProcessing: 'Source processing', surfaceKnowledgeGraph: 'Knowledge graph', surfaceEmbedding: 'Embedding', surfaceEmbeddingRebuild: 'Embedding rebuild', surfaceApi: 'API', surfaceUnknown: 'Other',
      },
    },
  }),
}))

describe('UsagePage', () => {
  beforeEach(() => {
    state.role = 'user'
    state.useUsage.mockReset()
    state.useUsage.mockReturnValue({ data: dashboard, isLoading: false, isError: false })
  })

  it('shows the current user token totals and credential audit', () => {
    render(<UsagePage />)

    expect(state.useUsage).toHaveBeenCalledWith(30, 'mine', undefined)
    expect(screen.getByRole('heading', { name: 'AI token usage' })).toBeInTheDocument()
    expect(screen.getByText('1,500')).toBeInTheDocument()
    expect(screen.getAllByText('DeepSeek production').length).toBeGreaterThan(0)
    expect(screen.getByText('Global Ask')).toBeInTheDocument()
    expect(screen.queryByText('Usage by user')).not.toBeInTheDocument()
  })

  it('lets an administrator switch to the all-user audit', () => {
    state.role = 'admin'
    render(<UsagePage />)

    fireEvent.click(screen.getByRole('button', { name: 'All users' }))

    expect(state.useUsage).toHaveBeenLastCalledWith(30, 'all', undefined)
    expect(screen.getByText('Usage by user')).toBeInTheDocument()
    expect(screen.getAllByText('researcher').length).toBeGreaterThan(0)
  })
})
