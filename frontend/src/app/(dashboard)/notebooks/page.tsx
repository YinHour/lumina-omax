'use client'

import { useMemo, useState } from 'react'

import { AppShell } from '@/components/layout/AppShell'
import { PageContainer } from '@/components/layout/PageContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import { NotebookList } from './components/NotebookList'
import { Button } from '@/components/ui/button'
import { Layers, Plus, RefreshCw } from 'lucide-react'
import { useNotebooks } from '@/lib/hooks/use-notebooks'
import { CreateNotebookDialog } from '@/components/notebooks/CreateNotebookDialog'
import { Input } from '@/components/ui/input'
import { useTranslation } from '@/lib/hooks/use-translation'
import { AggregateNotebookDialog } from '@/components/notebooks/AggregateNotebookDialog'

export default function NotebooksPage() {
  const { t } = useTranslation()
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [aggregateDialogOpen, setAggregateDialogOpen] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const { data: notebooks, isLoading, refetch } = useNotebooks(false)
  const { data: archivedNotebooks } = useNotebooks(true)

  const normalizedQuery = searchTerm.trim().toLowerCase()

  const filteredActive = useMemo(() => {
    if (!notebooks) {
      return undefined
    }
    const regularNotebooks = notebooks.filter(nb => !nb.is_aggregated)
    if (!normalizedQuery) {
      return regularNotebooks
    }
    return regularNotebooks.filter((notebook) =>
      notebook.name.toLowerCase().includes(normalizedQuery)
    )
  }, [notebooks, normalizedQuery])

  const filteredAggregated = useMemo(() => {
    if (!notebooks) {
      return undefined
    }
    const aggregatedNotebooks = notebooks.filter(nb => nb.is_aggregated)
    if (!normalizedQuery) {
      return aggregatedNotebooks
    }
    return aggregatedNotebooks.filter((notebook) =>
      notebook.name.toLowerCase().includes(normalizedQuery)
    )
  }, [notebooks, normalizedQuery])

  const filteredArchived = useMemo(() => {
    if (!archivedNotebooks) {
      return undefined
    }
    if (!normalizedQuery) {
      return archivedNotebooks
    }
    return archivedNotebooks.filter((notebook) =>
      notebook.name.toLowerCase().includes(normalizedQuery)
    )
  }, [archivedNotebooks, normalizedQuery])

  const hasArchived = (archivedNotebooks?.length ?? 0) > 0
  const isSearching = normalizedQuery.length > 0
  const activeNotebookSection = (
    <NotebookList
      notebooks={filteredActive}
      isLoading={isLoading}
      title={t.notebooks.activeNotebooks}
      emptyTitle={isSearching ? t.common.noMatches : undefined}
      emptyDescription={isSearching ? t.common.tryDifferentSearch : undefined}
      onAction={!isSearching ? () => setCreateDialogOpen(true) : undefined}
      actionLabel={!isSearching ? t.notebooks.newNotebook : undefined}
    />
  )
  const aggregatedNotebookSection =
    filteredAggregated && filteredAggregated.length > 0 ? (
      <NotebookList
        notebooks={filteredAggregated}
        isLoading={isLoading}
        title="聚合的笔记本"
        collapsible
        defaultExpanded
        emptyTitle={isSearching ? t.common.noMatches : undefined}
        emptyDescription={isSearching ? t.common.tryDifferentSearch : undefined}
      />
    ) : null
  const archivedNotebookSection = hasArchived ? (
    <NotebookList
      notebooks={filteredArchived}
      isLoading={false}
      title={t.notebooks.archivedNotebooks}
      collapsible
      emptyTitle={isSearching ? t.common.noMatches : undefined}
      emptyDescription={isSearching ? t.common.tryDifferentSearch : undefined}
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
                variant="outline"
                onClick={() => setAggregateDialogOpen(true)}
              >
                <Layers className="size-4" />
                聚合笔记本
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
