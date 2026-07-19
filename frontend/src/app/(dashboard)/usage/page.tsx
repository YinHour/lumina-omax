'use client'

import { useMemo, useState, type ReactNode } from 'react'
import { AlertCircle, BarChart3, KeyRound, Loader2, Users } from 'lucide-react'

import { AppShell } from '@/components/layout/AppShell'
import { PageContainer } from '@/components/layout/PageContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useAuth } from '@/lib/hooks/use-auth'
import { useTranslation } from '@/lib/hooks/use-translation'
import { useUsage } from '@/lib/hooks/use-usage'
import type { UsageDays, UsageScope } from '@/lib/types/usage'

const periods: UsageDays[] = [7, 30, 90]

function Metric({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="min-w-0 rounded-lg border border-border/75 bg-card/60 p-4 shadow-xs">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <p className="mt-2 truncate text-2xl font-semibold tabular-nums text-foreground" title={value}>
        {value}
      </p>
      {detail && <p className="mt-1 text-xs text-muted-foreground">{detail}</p>}
    </div>
  )
}

function Section({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return (
    <section className="space-y-4 border-t border-border/70 pt-6">
      <div>
        <h2 className="text-base font-semibold text-foreground">{title}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{description}</p>
      </div>
      {children}
    </section>
  )
}

export default function UsagePage() {
  const { t, language } = useTranslation()
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'
  const [days, setDays] = useState<UsageDays>(30)
  const [scope, setScope] = useState<UsageScope>('mine')
  const [selectedUserId, setSelectedUserId] = useState<string>('all')
  const userId = scope === 'all' && selectedUserId !== 'all' ? selectedUserId : undefined
  const { data, isLoading, isError } = useUsage(days, scope, userId)

  const number = useMemo(
    () => new Intl.NumberFormat(language, { notation: 'compact', maximumFractionDigits: 1 }),
    [language]
  )
  const fullNumber = useMemo(() => new Intl.NumberFormat(language), [language])
  const dateTime = useMemo(
    () => new Intl.DateTimeFormat(language, { dateStyle: 'short', timeStyle: 'short' }),
    [language]
  )
  const usage = useMemo(
    () => t('usage', { returnObjects: true }) as Record<string, string>,
    [t]
  )
  const { surfaceLabels, unknownSurfaceLabel } = useMemo(() => {
    return {
      surfaceLabels: {
        notebook_quick: usage.surfaceNotebookQuick,
        notebook_research: usage.surfaceNotebookResearch,
        source_chat: usage.surfaceSourceChat,
        global_ask: usage.surfaceGlobalAsk,
        transformation: usage.surfaceTransformation,
        note_generation: usage.surfaceNoteGeneration,
        notebook_guide: usage.surfaceNotebookGuide,
        model_test: usage.surfaceModelTest,
        credential_management: usage.surfaceCredentialManagement,
        source_processing: usage.surfaceSourceProcessing,
        knowledge_graph: usage.surfaceKnowledgeGraph,
        embedding: usage.surfaceEmbedding,
        embedding_rebuild: usage.surfaceEmbeddingRebuild,
        api: usage.surfaceApi,
      } as Record<string, string>,
      unknownSurfaceLabel: usage.surfaceUnknown,
    }
  }, [usage])
  const maxDaily = Math.max(...(data?.series.map(point => point.total_tokens) ?? [0]), 1)
  const maxCredential = Math.max(...(data?.by_credential.map(item => item.total_tokens) ?? [0]), 1)
  const maxUser = Math.max(...(data?.by_user.map(item => item.total_tokens) ?? [0]), 1)

  const periodLabel = (period: UsageDays) => {
    if (period === 7) return usage.period7
    if (period === 90) return usage.period90
    return usage.period30
  }

  const surfaceLabel = (surface: string) => {
    return surfaceLabels[surface] ?? unknownSurfaceLabel
  }

  return (
    <AppShell>
      <PageContainer width="wide" className="space-y-6">
        <PageHeader title={usage.title} description={usage.description} />

        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div className="space-y-1.5">
            <span className="text-xs font-medium text-muted-foreground">{usage.period}</span>
            <div className="flex rounded-lg border border-border bg-muted/35 p-1" aria-label={usage.period}>
              {periods.map(period => (
                <Button
                  key={period}
                  type="button"
                  size="sm"
                  variant={days === period ? 'secondary' : 'ghost'}
                  aria-pressed={days === period}
                  onClick={() => setDays(period)}
                >
                  {periodLabel(period)}
                </Button>
              ))}
            </div>
          </div>

          {isAdmin && (
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
              <div className="space-y-1.5">
                <span className="text-xs font-medium text-muted-foreground">{usage.scope}</span>
                <div className="flex rounded-lg border border-border bg-muted/35 p-1" aria-label={usage.scope}>
                  {(['mine', 'all'] as UsageScope[]).map(value => (
                    <Button
                      key={value}
                      type="button"
                      size="sm"
                      variant={scope === value ? 'secondary' : 'ghost'}
                      aria-pressed={scope === value}
                      onClick={() => setScope(value)}
                    >
                      {value === 'mine' ? usage.mine : usage.allUsers}
                    </Button>
                  ))}
                </div>
              </div>
              {scope === 'all' && (
                <div className="space-y-1.5">
                  <label className="block text-xs font-medium text-muted-foreground" htmlFor="usage-user-filter">
                    {usage.userFilter}
                  </label>
                  <Select value={selectedUserId} onValueChange={setSelectedUserId}>
                    <SelectTrigger id="usage-user-filter" className="w-full min-w-48 sm:w-56">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">{usage.allUsersOption}</SelectItem>
                      {data?.users.map(option => (
                        <SelectItem key={option.id} value={option.id}>
                          {option.display_name || option.username}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
          )}
        </div>

        {isLoading && (
          <div className="flex min-h-64 items-center justify-center text-sm text-muted-foreground">
            <Loader2 className="mr-2 size-4 animate-spin" />
            {usage.loading}
          </div>
        )}

        {isError && (
          <div className="flex min-h-40 items-center justify-center rounded-lg border border-destructive/30 bg-destructive/5 text-sm text-destructive">
            <AlertCircle className="mr-2 size-4" />
            {usage.loadError}
          </div>
        )}

        {data && !isLoading && !isError && (
          <>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Metric label={usage.totalTokens} value={fullNumber.format(data.totals.total_tokens)} />
              <Metric label={usage.inputTokens} value={fullNumber.format(data.totals.input_tokens)} />
              <Metric label={usage.outputTokens} value={fullNumber.format(data.totals.output_tokens)} />
              <Metric
                label={usage.calls}
                value={fullNumber.format(data.totals.calls)}
                detail={usage.failedCalls.replace('{count}', fullNumber.format(data.totals.failed_calls))}
              />
            </div>

            <Section title={usage.dailyUsage} description={usage.dailyUsageDesc}>
              <div className="flex h-56 items-end gap-1 overflow-hidden border-b border-border/80 px-1 pt-4" role="img" aria-label={usage.dailyUsage}>
                {data.series.map(point => {
                  const height = point.total_tokens === 0 ? 2 : Math.max((point.total_tokens / maxDaily) * 100, 5)
                  const title = `${point.date}: ${fullNumber.format(point.total_tokens)} ${usage.tokens}`
                  return (
                    <div key={point.date} className="group flex h-full min-w-0 flex-1 items-end" title={title}>
                      <div
                        className="w-full rounded-t-sm bg-primary/70 transition-colors group-hover:bg-primary"
                        style={{ height: `${height}%` }}
                        aria-label={title}
                      />
                    </div>
                  )
                })}
              </div>
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>{data.series.at(0)?.date}</span>
                <span>{data.series.at(-1)?.date}</span>
              </div>
            </Section>

            <Section title={usage.byCredential} description={usage.byCredentialDesc}>
              {data.by_credential.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">{usage.noUsage}</p>
              ) : (
                <div className="space-y-4">
                  {data.by_credential.map(item => (
                    <div key={`${item.credential_id}-${item.provider}`} className="grid gap-2 sm:grid-cols-[minmax(10rem,16rem)_1fr_auto] sm:items-center">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium" title={item.credential_name}>{item.credential_name}</p>
                        <p className="text-xs text-muted-foreground">{item.provider}</p>
                      </div>
                      <div className="h-2 overflow-hidden rounded-full bg-muted">
                        <div className="h-full rounded-full bg-chart-2" style={{ width: `${Math.max((item.total_tokens / maxCredential) * 100, 2)}%` }} />
                      </div>
                      <div className="text-right text-sm tabular-nums">
                        <span className="font-medium">{number.format(item.total_tokens)}</span>
                        <span className="ml-2 text-xs text-muted-foreground">{usage.callsCount.replace('{count}', fullNumber.format(item.calls))}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Section>

            {isAdmin && scope === 'all' && (
              <Section title={usage.byUser} description={usage.byUserDesc}>
                <div className="space-y-4">
                  {data.by_user.map(item => (
                    <div key={item.user_id ?? item.username} className="grid gap-2 sm:grid-cols-[minmax(10rem,16rem)_1fr_auto] sm:items-center">
                      <p className="truncate text-sm font-medium" title={item.username}>{item.username}</p>
                      <div className="h-2 overflow-hidden rounded-full bg-muted">
                        <div className="h-full rounded-full bg-chart-3" style={{ width: `${Math.max((item.total_tokens / maxUser) * 100, 2)}%` }} />
                      </div>
                      <span className="text-sm font-medium tabular-nums">{number.format(item.total_tokens)}</span>
                    </div>
                  ))}
                </div>
              </Section>
            )}

            <Section title={usage.recentUsage} description={usage.recentUsageDesc}>
              <div className="overflow-x-auto rounded-lg border border-border/75">
                <table className="w-full min-w-[860px] text-left text-sm">
                  <thead className="bg-muted/55 text-xs text-muted-foreground">
                    <tr>
                      {isAdmin && scope === 'all' && <th className="px-3 py-2.5 font-medium">{usage.user}</th>}
                      <th className="px-3 py-2.5 font-medium">{usage.time}</th>
                      <th className="px-3 py-2.5 font-medium">{usage.key}</th>
                      <th className="px-3 py-2.5 font-medium">{usage.model}</th>
                      <th className="px-3 py-2.5 font-medium">{usage.surface}</th>
                      <th className="px-3 py-2.5 text-right font-medium">{usage.tokens}</th>
                      <th className="px-3 py-2.5 font-medium">{usage.source}</th>
                      <th className="px-3 py-2.5 font-medium">{usage.status}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/65">
                    {data.recent.map(item => (
                      <tr key={item.id} className="hover:bg-muted/25">
                        {isAdmin && scope === 'all' && <td className="px-3 py-3">{item.username}</td>}
                        <td className="whitespace-nowrap px-3 py-3 text-muted-foreground">{dateTime.format(new Date(item.created))}</td>
                        <td className="px-3 py-3"><span className="flex items-center gap-1.5"><KeyRound className="size-3.5 text-muted-foreground" />{item.credential_name}</span></td>
                        <td className="px-3 py-3">{item.model_name}</td>
                        <td className="px-3 py-3">{surfaceLabel(item.surface)}</td>
                        <td className="px-3 py-3 text-right font-medium tabular-nums">{fullNumber.format(item.total_tokens)}</td>
                        <td className="px-3 py-3"><Badge variant="outline">{item.token_source === 'provider' ? usage.providerReported : usage.estimated}</Badge></td>
                        <td className="px-3 py-3"><Badge variant={item.status === 'success' ? 'success' : 'destructive'}>{item.status === 'success' ? usage.success : usage.failed}</Badge></td>
                      </tr>
                    ))}
                    {data.recent.length === 0 && (
                      <tr><td colSpan={isAdmin && scope === 'all' ? 8 : 7} className="px-3 py-10 text-center text-muted-foreground">{usage.noUsage}</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
              <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
                <span className="flex items-center gap-1.5"><BarChart3 className="size-3.5" />{usage.providerReportedHint}</span>
                {isAdmin && <span className="flex items-center gap-1.5"><Users className="size-3.5" />{usage.adminHint}</span>}
              </div>
            </Section>
          </>
        )}
      </PageContainer>
    </AppShell>
  )
}
