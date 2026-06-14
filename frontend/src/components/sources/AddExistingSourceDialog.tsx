'use client'

import { useState, useEffect, useMemo, useCallback } from 'react'
import { Search, Link2, LoaderIcon, FileText, Link as LinkIcon, Upload } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Checkbox } from '@/components/ui/checkbox'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { sourcesApi } from '@/lib/api/sources'
import { useSources, useAddSourcesToNotebook } from '@/lib/hooks/use-sources'
import { useSettings } from '@/lib/hooks/use-settings'
import { useNotebook } from '@/lib/hooks/use-notebooks'
import { SourceListResponse } from '@/lib/types/api'
import { useTranslation } from '@/lib/hooks/use-translation'
import { getRemainingSourceSlots, getSourceBatchLimit } from './steps/SourceTypeStep'

interface AddExistingSourceDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  notebookId: string
  onSuccess?: () => void
}

export function AddExistingSourceDialog({
  open,
  onOpenChange,
  notebookId,
  onSuccess,
}: AddExistingSourceDialogProps) {
  const { t } = useTranslation()
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([])
  const [allSources, setAllSources] = useState<SourceListResponse[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const { data: settings } = useSettings()
  const sourceLimit = getSourceBatchLimit(settings?.source_batch_limit)

  // Get sources already in this notebook
  const { data: currentNotebookSources } = useSources(notebookId)
  const { data: currentNotebook } = useNotebook(notebookId)
  const currentSourceCount = Math.max(
    currentNotebook?.source_count ?? 0,
    currentNotebookSources?.length ?? 0
  )
  const remainingSourceSlots = getRemainingSourceSlots(currentSourceCount, sourceLimit)
  const currentSourceIds = useMemo(
    () => new Set(currentNotebookSources?.map(s => s.id) || []),
    [currentNotebookSources]
  )

  const addSources = useAddSourcesToNotebook()

  const loadAllSources = useCallback(async () => {
    try {
      setIsLoading(true)
      // Use sources API directly to get all sources (max 100 per API limit)
      const sources = await sourcesApi.list({
        limit: 100,
        offset: 0,
        sort_by: 'created',
        sort_order: 'desc',
      })

      setAllSources(sources.items)
    } catch (error) {
      console.error('Error loading sources:', error)
    } finally {
      setIsLoading(false)
    }
  }, [])

  // Client-side filtering (same simple approach as the notebooks page).
  // Supports CJK/English input in real time with no debounce, no Enter key,
  // and no server round-trip.
  const embeddedSources = useMemo(
    () => allSources.filter(source => source.embedded),
    [allSources]
  )

  const filteredSources = useMemo(() => {
    const q = searchQuery.trim().toLowerCase()
    if (!q) return embeddedSources
    return embeddedSources.filter(s => (s.title || '').toLowerCase().includes(q))
  }, [embeddedSources, searchQuery])

  // Load all sources initially and reset query when opening
  useEffect(() => {
    if (open) {
      setSearchQuery('')
      loadAllSources()
    }
  }, [open, loadAllSources])

  useEffect(() => {
    const selectableSourceIds = new Set(
      embeddedSources
        .filter(source => !currentSourceIds.has(source.id))
        .map(source => source.id)
    )
    setSelectedSourceIds(prev => {
      const next = prev.filter(sourceId => selectableSourceIds.has(sourceId))
      return next.length === prev.length ? prev : next
    })
  }, [embeddedSources, currentSourceIds])

  const handleToggleSource = (sourceId: string) => {
    const source = embeddedSources.find(s => s.id === sourceId)
    if (!source || currentSourceIds.has(source.id)) {
      return
    }

    setSelectedSourceIds(prev =>
      prev.includes(sourceId)
        ? prev.filter(id => id !== sourceId)
        : prev.length < remainingSourceSlots
          ? [...prev, sourceId]
          : prev
    )
  }

  const handleAddSelected = async () => {
    if (selectedSourceIds.length === 0 || selectedSourceIds.length > remainingSourceSlots) return

    try {
      await addSources.mutateAsync({
        notebookId,
        sourceIds: selectedSourceIds,
      })

      // Reset state
      setSelectedSourceIds([])
      setSearchQuery('')
      onOpenChange(false)
      onSuccess?.()
    } catch (error) {
      // Error handled by the hook's onError
      console.error('Error adding sources:', error)
    }
  }

  const getSourceIcon = (source: SourceListResponse) => {
    // Derive type from asset
    if (source.asset?.url) {
      return <LinkIcon className="h-4 w-4" />
    }
    if (source.asset?.file_path) {
      return <Upload className="h-4 w-4" />
    }
    return <FileText className="h-4 w-4" />
  }

  const formatDate = (dateString: string) => {
    try {
      return new Date(dateString).toLocaleDateString()
    } catch {
      return ''
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl sm:max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Link2 className="h-5 w-5" />
            {t.sources.addExistingTitle}
          </DialogTitle>
          <DialogDescription>
            {t.sources.addExistingDesc}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 flex-1 overflow-hidden flex flex-col">
          {/* Search Input */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder={t.sources.searchPlaceholder}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10"
            />
            {isLoading && (
              <LoaderIcon className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 animate-spin text-muted-foreground" />
            )}
          </div>

          {/* Select All */}
          {filteredSources.length > 0 && (() => {
            const selectableSources = filteredSources.filter(s =>
              !currentSourceIds.has(s.id)
            )
            if (selectableSources.length === 0) return null
            const allSelected = selectableSources.every(s => selectedSourceIds.includes(s.id))
            const someSelected = selectableSources.some(s => selectedSourceIds.includes(s.id))
            return (
              <div
                className="flex items-center gap-2 px-1 cursor-pointer select-none"
                onClick={() => {
                  if (allSelected) {
                    setSelectedSourceIds(prev => prev.filter(id => !selectableSources.some(s => s.id === id)))
                  } else {
                    setSelectedSourceIds(prev => {
                      const slots = Math.max(remainingSourceSlots - prev.length, 0)
                      const nextIds = selectableSources
                        .map(s => s.id)
                        .filter(id => !prev.includes(id))
                        .slice(0, slots)
                      return [...prev, ...nextIds]
                    })
                  }
                }}
              >
                <Checkbox checked={allSelected ? true : someSelected ? 'indeterminate' : false} className="pointer-events-none" />
                <span className="text-sm text-muted-foreground">
                  {allSelected ? t.sources.deselectAll : t.sources.selectAll}
                </span>
              </div>
            )
          })()}

          {/* Source List */}
          <ScrollArea className="h-[400px] border rounded-md">
            {isLoading && allSources.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-[200px] text-muted-foreground">
                <LoaderIcon className="h-12 w-12 mb-2 animate-spin" />
                <p>{t.common.loading}</p>
              </div>
            ) : filteredSources.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-[200px] text-muted-foreground gap-2">
                <Search className="h-12 w-12 mb-2 opacity-50" />
                <p>{t.sources.noSourcesMatchSearch}</p>
                <p className="text-xs">{t.common.tryDifferentSearch}</p>
              </div>
            ) : (
              <div className="space-y-2 p-4">
                {filteredSources.map((source) => {
                  const isAlreadyLinked = currentSourceIds.has(source.id)
                  const isSelected = selectedSourceIds.includes(source.id)
                  const isDisabled = isAlreadyLinked || (!isSelected && selectedSourceIds.length >= remainingSourceSlots)

                  return (
                    <div
                      key={source.id}
                      className={`flex items-start gap-3 p-3 rounded-lg border transition-colors min-w-0 ${
                        isSelected ? 'bg-accent border-accent-foreground/20' : 'hover:bg-accent/50'
                      } ${
                        isDisabled ? 'opacity-70' : ''
                      }`}
                    >
                      <Checkbox
                        checked={isSelected}
                        onCheckedChange={() => handleToggleSource(source.id)}
                        disabled={isDisabled}
                        className="mt-1"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start gap-2 mb-1">
                          <div className="shrink-0 mt-0.5">
                            {getSourceIcon(source)}
                          </div>
                          <h4 className="font-medium text-sm break-words line-clamp-2 flex-1 min-w-0">
                            {source.title}
                          </h4>
                          {isAlreadyLinked && (
                            <Badge variant="secondary" className="text-xs shrink-0">
                              {t.common.linked}
                            </Badge>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground truncate">
                          {t.sources.added.replace('{date}', formatDate(source.created))}
                        </p>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </ScrollArea>

          {/* Truncation Warning */}
          {allSources.length >= 100 && !searchQuery && (
            <div className="text-xs text-muted-foreground bg-muted/50 p-2 rounded-md">
              {t.sources.showingFirst100}
            </div>
          )}

          {/* Selection Summary */}
          {selectedSourceIds.length > 0 && (
            <div className="text-sm text-muted-foreground">
              {t.sources.selectedCount.replace('{count}', selectedSourceIds.length.toString())}
            </div>
          )}
          <div className="text-xs text-muted-foreground">
            {remainingSourceSlots > 0
              ? t.sources.sourceLimitRemaining
                .replace('{remaining}', remainingSourceSlots.toString())
                .replace('{limit}', sourceLimit.toString())
              : t.sources.sourceLimitReached.replace('{count}', sourceLimit.toString())
            }
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={addSources.isPending}
          >
            {t.common.cancel}
          </Button>
          <Button
            onClick={handleAddSelected}
            disabled={selectedSourceIds.length === 0 || selectedSourceIds.length > remainingSourceSlots || addSources.isPending}
          >
            {addSources.isPending ? (
              <>
                <LoaderIcon className="mr-2 h-4 w-4 animate-spin" />
                {t.common.adding}
              </>
            ) : (
              <>{t.common.addSelected}</>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
