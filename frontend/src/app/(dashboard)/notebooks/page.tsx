'use client'

import { useCallback, useMemo, useState } from 'react'

import { AppShell } from '@/components/layout/AppShell'
import { PageContainer } from '@/components/layout/PageContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import { NotebookList } from './components/NotebookList'
import { Button } from '@/components/ui/button'
import { Layers, Plus, RefreshCw, UserCheck } from 'lucide-react'
import { useNotebooks } from '@/lib/hooks/use-notebooks'
import { CreateNotebookDialog } from '@/components/notebooks/CreateNotebookDialog'
import { Input } from '@/components/ui/input'
import { useTranslation } from '@/lib/hooks/use-translation'
import { AggregateNotebookDialog } from '@/components/notebooks/AggregateNotebookDialog'
import { useAuthStore } from '@/lib/stores/auth-store'
import { sameRecordId } from '@/lib/utils/record-id'
import type { NotebookResponse } from '@/lib/types/api'

export default function NotebooksPage() {
  const { t } = useTranslation()
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [aggregateDialogOpen, setAggregateDialogOpen] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [showMineOnly, setShowMineOnly] = useState(false)
  const { data: notebooks, isLoading, refetch } = useNotebooks(false)
  const { data: archivedNotebooks } = useNotebooks(true)
  const user = useAuthStore((state) => state.user)

  const normalizedQuery = searchTerm.trim().toLowerCase()
  const isOwnerFiltered = showMineOnly

  const matchesNotebookFilters = useCallback((notebook: NotebookResponse) => {
    const matchesOwner = !isOwnerFiltered || sameRecordId(notebook.created_by, user?.id)
    const matchesQuery =
      !normalizedQuery || notebook.name.toLowerCase().includes(normalizedQuery)

    return matchesOwner && matchesQuery
  }, [isOwnerFiltered, normalizedQuery, user?.id])

  const filteredActive = useMemo(() => {
    if (!notebooks) {
      return undefined
    }
    return notebooks.filter(nb => !nb.is_aggregated && matchesNotebookFilters(nb))
  }, [matchesNotebookFilters, notebooks])

  const filteredAggregated = useMemo(() => {
    if (!notebooks) {
      return undefined
    }
    return notebooks.filter(nb => nb.is_aggregated && matchesNotebookFilters(nb))
  }, [matchesNotebookFilters, notebooks])

  const filteredArchived = useMemo(() => {
    if (!archivedNotebooks) {
      return undefined
    }
    return archivedNotebooks.filter(matchesNotebookFilters)
  }, [archivedNotebooks, matchesNotebookFilters])

  const hasArchived = (filteredArchived?.length ?? 0) > 0 || (archivedNotebooks?.length ?? 0) > 0
  const isSearching = normalizedQuery.length > 0
  const isFiltering = isSearching || isOwnerFiltered
  const emptyTitle =
    isSearching ? t.common.noMatches : isOwnerFiltered ? t.notebooks.noOwnedNotebooks : undefined
  const emptyDescription = isSearching ? t.common.tryDifferentSearch : undefined
  const activeNotebookSection = (
    <NotebookList
      notebooks={filteredActive}
      isLoading={isLoading}
      title={t.notebooks.activeNotebooks}
      emptyTitle={emptyTitle}
      emptyDescription={emptyDescription}
      onAction={!isSearching && !isOwnerFiltered ? () => setCreateDialogOpen(true) : undefined}
      actionLabel={!isSearching && !isOwnerFiltered ? t.notebooks.newNotebook : undefined}
    />
  )
  const aggregatedNotebookSection =
    filteredAggregated && (filteredAggregated.length > 0 || isFiltering) ? (
      <NotebookList
        notebooks={filteredAggregated}
        isLoading={isLoading}
        title={t.notebooks.aggregatedNotebooks}
        collapsible
        defaultExpanded
        emptyTitle={emptyTitle}
        emptyDescription={emptyDescription}
      />
    ) : null
  const archivedNotebookSection = hasArchived ? (
    <NotebookList
      notebooks={filteredArchived}
      isLoading={false}
      title={t.notebooks.archivedNotebooks}
      collapsible
      emptyTitle={emptyTitle}
      emptyDescription={emptyDescription}
    />
  ) : null

  return (
    <AppShell>
      <PageContainer className="space-y-6">
        <PageHeader
          title={t.notebooks.title}
          actions={
            <>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => refetch()}
                aria-label={t.common.refresh}
              >
                <RefreshCw className="size-4" />
              </Button>
              <Input
                id="notebook-search"
                name="notebook-search"
                value={searchTerm}
                onChange={(event) => setSearchTerm(event.target.value)}
                placeholder={t.notebooks.searchPlaceholder}
                autoComplete="off"
                aria-label={
                  t.common.accessibility?.searchNotebooks || 'Search notebooks'
                }
                className="w-full sm:w-64"
              />
              <Button
                type="button"
                variant={showMineOnly ? 'secondary' : 'outline'}
                aria-pressed={showMineOnly}
                onClick={() => setShowMineOnly((value) => !value)}
              >
                <UserCheck className="size-4" />
                {t.notebooks.showMineOnly}
              </Button>
              <Button
                variant="outline"
                onClick={() => setAggregateDialogOpen(true)}
              >
                <Layers className="size-4" />
                {t.notebooks.aggregateNotebook}
              </Button>
              <Button onClick={() => setCreateDialogOpen(true)}>
                <Plus className="size-4" />
                {t.notebooks.newNotebook}
              </Button>
            </>
          }
        />
        <div className="space-y-8">
          {activeNotebookSection}
          {aggregatedNotebookSection}
          {archivedNotebookSection}
        </div>
      </PageContainer>

      <CreateNotebookDialog
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
      />
      <AggregateNotebookDialog
        open={aggregateDialogOpen}
        onOpenChange={setAggregateDialogOpen}
      />
    </AppShell>
  )
}
