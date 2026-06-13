'use client'

import { useState, useMemo, useRef, useCallback, useEffect } from 'react'
import { SourceListResponse } from '@/lib/types/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Plus, FileText, Link2, ChevronDown, Loader2, MoreVertical, CheckSquare, List, Ban, Search } from 'lucide-react'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { EmptyState } from '@/components/common/EmptyState'
import { AddSourceDialog } from '@/components/sources/AddSourceDialog'
import { AddExistingSourceDialog } from '@/components/sources/AddExistingSourceDialog'
import { SourceCard } from '@/components/sources/SourceCard'
import { useDeleteSource, useRetrySource, useRemoveSourceFromNotebook } from '@/lib/hooks/use-sources'
import { ConfirmDialog } from '@/components/common/ConfirmDialog'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { useModalManager } from '@/lib/hooks/use-modal-manager'
import { ContextMode } from '../[id]/page'
import { CollapsibleColumn, createCollapseButton } from '@/components/notebooks/CollapsibleColumn'
import { useNotebookColumnsStore } from '@/lib/stores/notebook-columns-store'
import { useTranslation } from '@/lib/hooks/use-translation'
import { useToast } from '@/lib/hooks/use-toast'
import { useAuthStore } from '@/lib/stores/auth-store'

interface SourcesColumnProps {
  sources?: SourceListResponse[]
  isLoading: boolean
  notebookId: string
  notebookName?: string
  onRefresh?: () => void
  contextSelections?: Record<string, ContextMode>
  onContextModeChange?: (sourceId: string, mode: ContextMode) => void
  onBulkContextModeChange?: (mode: ContextMode) => void
  // Pagination props
  hasNextPage?: boolean
  isFetchingNextPage?: boolean
  fetchNextPage?: () => void
}

export function SourcesColumn({
  sources,
  isLoading,
  notebookId,
  onRefresh,
  contextSelections,
  onContextModeChange,
  onBulkContextModeChange,
  hasNextPage,
  isFetchingNextPage,
  fetchNextPage,
}: SourcesColumnProps) {
  const { t, language } = useTranslation()
  const { toast } = useToast()
  const user = useAuthStore((s) => s.user)
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [addDialogOpen, setAddDialogOpen] = useState(false)
  const [addExistingDialogOpen, setAddExistingDialogOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [sourceToDelete, setSourceToDelete] = useState<string | null>(null)
  const [removeDialogOpen, setRemoveDialogOpen] = useState(false)
  const [sourceToRemove, setSourceToRemove] = useState<string | null>(null)
  const [sourceQuery, setSourceQuery] = useState('')

  // Group and sort sources for aggregated notebooks
  const displaySources = useMemo(() => {
    if (!sources || sources.length === 0) return sources;
    
    // Check if any source belongs to a different notebook to infer it's an aggregated view
    const isAggregated = sources.some(s => s.origin_notebook_id && s.origin_notebook_id !== notebookId);
    
    if (!isAggregated) {
      return sources;
    }

    // Sort by origin notebook name, then by updated
    return [...sources].sort((a, b) => {
      const nameA = a.origin_notebook_name || t.navigation.notebooks;
      const nameB = b.origin_notebook_name || t.navigation.notebooks;
      
      if (nameA !== nameB) {
        return nameA.localeCompare(nameB);
      }
      
      // Fallback to updated desc
      const dateA = new Date(a.updated).getTime();
      const dateB = new Date(b.updated).getTime();
      return dateB - dateA;
    });
  }, [sources, notebookId, t.navigation.notebooks]);

  const selectedSourceCount = useMemo(() => {
    if (!sources || !contextSelections) return 0
    return sources.filter(source => contextSelections[source.id] !== 'off').length
  }, [sources, contextSelections])

  const filteredSources = useMemo(() => {
    if (!displaySources || displaySources.length === 0) return displaySources
    const query = sourceQuery.trim().toLowerCase()
    if (!query) return displaySources

    return displaySources.filter(source => {
      const searchableText = [
        source.title,
        source.asset?.file_path,
        source.asset?.url,
        source.origin_notebook_name,
        source.uploader_name,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
      return searchableText.includes(query)
    })
  }, [displaySources, sourceQuery])

  const { openModal } = useModalManager()
  const deleteSource = useDeleteSource()
  const retrySource = useRetrySource()
  const removeFromNotebook = useRemoveSourceFromNotebook()

  // Collapsible column state
  const { sourcesCollapsed, toggleSources } = useNotebookColumnsStore()
  const collapseButton = useMemo(
    () => createCollapseButton(toggleSources, t.navigation.sources),
    [toggleSources, t.navigation.sources]
  )

  // Scroll container ref for infinite scroll
  const scrollContainerRef = useRef<HTMLDivElement>(null)

  // Handle scroll for infinite loading
  const handleScroll = useCallback(() => {
    const container = scrollContainerRef.current
    if (!container || !hasNextPage || isFetchingNextPage || !fetchNextPage) return

    const { scrollTop, scrollHeight, clientHeight } = container
    // Load more when user scrolls within 200px of the bottom
    if (scrollHeight - scrollTop - clientHeight < 200) {
      fetchNextPage()
    }
  }, [hasNextPage, isFetchingNextPage, fetchNextPage])

  // Attach scroll listener
  useEffect(() => {
    const container = scrollContainerRef.current
    if (!container) return

    container.addEventListener('scroll', handleScroll)
    return () => container.removeEventListener('scroll', handleScroll)
  }, [handleScroll])

  useEffect(() => {
    if (!deleteDialogOpen && typeof document !== 'undefined') {
      document.body.style.removeProperty('pointer-events')
    }
  }, [deleteDialogOpen])
  
  const [deletePassword, setDeletePassword] = useState('')
  const [deletePasswordError, setDeletePasswordError] = useState('')
  const [deleteNeedsPassword, setDeleteNeedsPassword] = useState(false)

  const handleDeleteClick = (sourceId: string) => {
    const src = sources?.find(s => s.id === sourceId)
    const needsPassword = src ? (src.notebook_count || 0) > 1 : false
    setSourceToDelete(sourceId)
    setDeleteNeedsPassword(needsPassword)
    setDeletePassword('')
    setDeletePasswordError('')
    setDeleteDialogOpen(true)
  }

  const handleDeleteConfirm = async () => {
    if (!sourceToDelete) return

    try {
      await deleteSource.mutateAsync({ id: sourceToDelete, password: deletePassword || undefined })
      setDeleteDialogOpen(false)
      setSourceToDelete(null)
      onRefresh?.()
    } catch (error) {
      console.error('Failed to delete source:', error)
      toast({
        title: t.common.error,
        description: t.sources.failedToDeleteSource,
        variant: 'destructive',
      })
    }
  }

  const handleRemoveFromNotebook = (sourceId: string) => {
    setSourceToRemove(sourceId)
    setRemoveDialogOpen(true)
  }

  const handleRemoveConfirm = async () => {
    if (!sourceToRemove) return

    try {
      await removeFromNotebook.mutateAsync({
        notebookId,
        sourceId: sourceToRemove
      })
      setRemoveDialogOpen(false)
      setSourceToRemove(null)
    } catch (error) {
      console.error('Failed to remove source from notebook:', error)
      // Error toast is handled by the hook
    }
  }

  const handleRetry = async (sourceId: string) => {
    try {
      await retrySource.mutateAsync(sourceId)
    } catch (error) {
      console.error('Failed to retry source:', error)
    }
  }

  const handleSourceClick = (sourceId: string) => {
    openModal('source', sourceId)
  }

  return (
    <>
      <CollapsibleColumn
        isCollapsed={sourcesCollapsed}
        onToggle={toggleSources}
        collapsedIcon={FileText}
        collapsedLabel={t.navigation.sources}
      >
        <Card className="h-full flex flex-col flex-1 overflow-hidden">
          <CardHeader className="pb-3 flex-shrink-0">
            <div className="space-y-3">
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <CardTitle className="text-lg">{t.navigation.sources}</CardTitle>
                  {sources && sources.length > 0 && (
                    <div className="mt-1 text-xs text-muted-foreground">
                      {t.sources.selectedCount.replace('{count}', selectedSourceCount.toString())}
                      <span className="mx-1">/</span>
                      {t.sources.totalItems.replace('{count}', sources.length.toString())}
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2">
                <DropdownMenu open={dropdownOpen} onOpenChange={setDropdownOpen}>
                  <DropdownMenuTrigger asChild>
                    <Button size="sm">
                      <Plus className="h-4 w-4 mr-2" />
                      {t.sources.addSource}
                      <ChevronDown className="h-4 w-4 ml-2" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onClick={() => { setDropdownOpen(false); setAddDialogOpen(true); }}>
                      <Plus className="h-4 w-4 mr-2" />
                      {t.sources.addSource}
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => { setDropdownOpen(false); setAddExistingDialogOpen(true); }}>
                      <Link2 className="h-4 w-4 mr-2" />
                      {t.sources.addExistingTitle}
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
                
                {onBulkContextModeChange && sources && sources.length > 0 && (
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-8 w-8">
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => onBulkContextModeChange('full')}>
                        <List className="h-4 w-4 mr-2" />
                        {t.sources.setAllFullText}
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => onBulkContextModeChange('insights')}>
                        <CheckSquare className="h-4 w-4 mr-2" />
                        {t.sources.setAllInsights}
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => onBulkContextModeChange('off')}>
                        <Ban className="h-4 w-4 mr-2" />
                        {t.sources.setAllToOff}
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                )}
                
                {collapseButton}
                </div>
              </div>
              {sources && sources.length > 0 && (
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    value={sourceQuery}
                    onChange={(event) => setSourceQuery(event.target.value)}
                    placeholder={t.sources.filterSources || t.sources.searchPlaceholder}
                    className="h-9 pl-9"
                  />
                </div>
              )}
            </div>
          </CardHeader>

          <CardContent ref={scrollContainerRef} className="flex-1 overflow-y-auto min-h-0">
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <LoadingSpinner />
              </div>
            ) : !displaySources || displaySources.length === 0 ? (
              <EmptyState
                icon={FileText}
                title={t.sources.noSourcesYet}
                description={t.sources.createFirstSource}
              />
            ) : !filteredSources || filteredSources.length === 0 ? (
              <EmptyState
                icon={Search}
                title={t.sources.noSourcesMatchSearch}
                description={t.sources.searchPlaceholder}
              />
            ) : (
              <div className="space-y-3">
                {filteredSources.map((source) => (
                  <SourceCard
                    key={source.id}
                    source={source}
                    onClick={handleSourceClick}
                    onDelete={handleDeleteClick}
                    onRetry={handleRetry}
                    onRemoveFromNotebook={handleRemoveFromNotebook}
                    onRefresh={onRefresh}
                    showRemoveFromNotebook={true}
                    currentNotebookId={notebookId}
                    currentUserId={user?.id}
                    contextMode={contextSelections?.[source.id]}
                    onContextModeChange={onContextModeChange
                      ? (mode) => onContextModeChange(source.id, mode)
                      : undefined
                    }
                  />
                ))}
                {/* Loading indicator for infinite scroll */}
                {isFetchingNextPage && (
                  <div className="flex items-center justify-center py-4">
                    <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </CollapsibleColumn>

      <AddSourceDialog
        open={addDialogOpen}
        onOpenChange={setAddDialogOpen}
        defaultNotebookId={notebookId}
      />

      <AddExistingSourceDialog
        open={addExistingDialogOpen}
        onOpenChange={setAddExistingDialogOpen}
        notebookId={notebookId}
        onSuccess={onRefresh}
      />

      <Dialog open={deleteDialogOpen} onOpenChange={(open) => {
        if (!open) {
          setDeletePassword('')
          setDeletePasswordError('')
          setSourceToDelete(null)
        }
        setDeleteDialogOpen(open)
      }}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>{t.sources.delete}</DialogTitle>
            <DialogDescription>
              {t.sources.deleteConfirm}
            </DialogDescription>
          </DialogHeader>
          
          {deleteNeedsPassword && (
            <div className="space-y-2 py-4">
              <p className="text-sm font-medium">
                {t.common.adminPasswordRequired}
              </p>
              <Input
                type="password"
                value={deletePassword}
                onChange={e => {
                  setDeletePassword(e.target.value)
                  setDeletePasswordError('')
                }}
                onKeyDown={e => {
                  e.stopPropagation()
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    handleDeleteConfirm()
                  }
                }}
                placeholder={t.notebooks.enterPassword}
                autoFocus
              />
              {deletePasswordError && (
                <p className="text-sm text-destructive">{deletePasswordError}</p>
              )}
            </div>
          )}
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              {t.common.cancel}
            </Button>
            <Button variant="destructive" onClick={handleDeleteConfirm} disabled={deleteSource.isPending}>
              {deleteSource.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {t.common.delete}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={removeDialogOpen}
        onOpenChange={setRemoveDialogOpen}
        title={t.sources.removeFromNotebook}
        description={t.sources.removeConfirm}
        confirmText={t.common.remove}
        onConfirm={handleRemoveConfirm}
        isLoading={removeFromNotebook.isPending}
        confirmVariant="default"
      />
    </>
  )
}
