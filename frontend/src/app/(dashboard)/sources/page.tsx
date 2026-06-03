'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { sourcesApi } from '@/lib/api/sources'
import { SourceListResponse } from '@/lib/types/api'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { EmptyState } from '@/components/common/EmptyState'
import { AppShell } from '@/components/layout/AppShell'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Checkbox } from '@/components/ui/checkbox'
import { FileText, Link as LinkIcon, Upload, AlignLeft, Trash2, ArrowUpDown, Loader2 } from 'lucide-react'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { format } from 'date-fns'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useTranslation } from '@/lib/hooks/use-translation'
import { cn } from '@/lib/utils'
import { toast } from '@/lib/hooks/use-toast'
import { getApiErrorKey } from '@/lib/utils/error-handler'

export default function SourcesPage() {
  const { t, language } = useTranslation()
  const [sources, setSources] = useState<SourceListResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [sortBy, setSortBy] = useState<'created' | 'updated'>('updated')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')
  const [deleteDialog, setDeleteDialog] = useState<{ open: boolean; source: SourceListResponse | null }>({
    open: false,
    source: null
  })
  const router = useRouter()
  const tableRef = useRef<HTMLTableElement>(null)
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  
  // Pagination state
  const [page, setPage] = useState(1)
  const [hasMore, setHasMore] = useState(true)
  const PAGE_SIZE = 30

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [batchDeleteDialog, setBatchDeleteDialog] = useState(false)
  const [batchDeletePassword, setBatchDeletePassword] = useState('')
  const [batchDeletePasswordError, setBatchDeletePasswordError] = useState('')
  const [isBatchDeleting, setIsBatchDeleting] = useState(false)
  const [lastSelectedIndex, setLastSelectedIndex] = useState<number | null>(null)

  const fetchSources = useCallback(async () => {
    try {
      setLoading(true)
      const data = await sourcesApi.list({
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
        sort_by: sortBy,
        sort_order: sortOrder,
      })

      setSources(data)
      setHasMore(data.length === PAGE_SIZE)
    } catch (err) {
      console.error('Failed to fetch sources:', err)
      setError(t.sources.failedToLoad)
      toast.error(t.sources.failedToLoad)
    } finally {
      setLoading(false)
    }
  }, [page, sortBy, sortOrder, t.sources.failedToLoad])

  // Initial load and when sort changes
  useEffect(() => {
    fetchSources()
  }, [fetchSources])

  // Listen for sourcesUpdated event to refresh instantly
  useEffect(() => {
    const handleSourcesUpdated = () => {
      fetchSources()
    }
    window.addEventListener('sourcesUpdated', handleSourcesUpdated)
    return () => window.removeEventListener('sourcesUpdated', handleSourcesUpdated)
  }, [fetchSources])

  // Polling for status updates
  useEffect(() => {
    const pollSources = async () => {
      // Avoid polling if already loading
      if (loading) return

      try {
        const data = await sourcesApi.list({
          limit: PAGE_SIZE,
          offset: (page - 1) * PAGE_SIZE,
          sort_by: sortBy,
          sort_order: sortOrder,
        })
        
        setSources(data)
        setHasMore(data.length === PAGE_SIZE)
      } catch (err) {
        console.error('Failed to poll sources:', err)
      }
    }

    const interval = setInterval(pollSources, 5000)
    return () => clearInterval(interval)
  }, [page, sortBy, sortOrder, loading])

  useEffect(() => {
    // Focus the table when component mounts or sources change
    if (sources.length > 0 && tableRef.current && !deleteDialog.open) {
      // Only focus if no other specific element is focused (like an input)
      if (document.activeElement === document.body || document.activeElement === tableRef.current) {
        tableRef.current.focus()
      }
    }
  }, [sources, deleteDialog.open])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (sources.length === 0) return
      
      // Do not handle keyboard navigation if a dialog is open
      // Use document.querySelector to check for any open dialogs globally
      if (deleteDialog.open || document.querySelector('[role="dialog"]')) return

      // Do not handle keyboard navigation if an input element is focused
      if (document.activeElement?.tagName === 'INPUT' || document.activeElement?.tagName === 'TEXTAREA') return

      // Do not handle keyboard navigation if any modifier keys are pressed
      if (e.ctrlKey || e.altKey || e.metaKey || e.shiftKey) return

      // Only handle specific keys
      if (!['ArrowDown', 'ArrowUp', 'Enter', 'Home', 'End'].includes(e.key)) return

      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault()
          setSelectedIndex((prev) => {
            const newIndex = Math.min(prev + 1, sources.length - 1)
            // Scroll to keep selected row visible
            setTimeout(() => scrollToSelectedRow(newIndex), 0)
            return newIndex
          })
          break
        case 'ArrowUp':
          e.preventDefault()
          setSelectedIndex((prev) => {
            const newIndex = Math.max(prev - 1, 0)
            // Scroll to keep selected row visible
            setTimeout(() => scrollToSelectedRow(newIndex), 0)
            return newIndex
          })
          break
        case 'Enter':
          e.preventDefault()
          if (sources[selectedIndex]) {
            router.push(`/sources/${sources[selectedIndex].id}`)
          }
          break
        case 'Home':
          e.preventDefault()
          setSelectedIndex(0)
          setTimeout(() => scrollToSelectedRow(0), 0)
          break
        case 'End':
          e.preventDefault()
          const lastIndex = sources.length - 1
          setSelectedIndex(lastIndex)
          setTimeout(() => scrollToSelectedRow(lastIndex), 0)
          break
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [sources, selectedIndex, router, deleteDialog.open])

  const scrollToSelectedRow = (index: number) => {
    const scrollContainer = scrollContainerRef.current
    if (!scrollContainer) return

    // Find the selected row element
    const rows = scrollContainer.querySelectorAll('tbody tr')
    const selectedRow = rows[index] as HTMLElement
    if (!selectedRow) return

    const containerRect = scrollContainer.getBoundingClientRect()
    const rowRect = selectedRow.getBoundingClientRect()

    // Check if row is above visible area
    if (rowRect.top < containerRect.top) {
      selectedRow.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
    // Check if row is below visible area
    else if (rowRect.bottom > containerRect.bottom) {
      selectedRow.scrollIntoView({ behavior: 'smooth', block: 'end' })
    }
  }

  const toggleSort = (field: 'created' | 'updated') => {
    if (sortBy === field) {
      // Toggle order if clicking the same field
      setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc')
    } else {
      // Switch to new field with default desc order
      setSortBy(field)
      setSortOrder('desc')
    }
  }

  // Cache translations outside the loop to prevent proxy infinite loop detection
  const tSourcesTypeLink = t.sources?.type?.link ?? 'Link'
  const tSourcesTypeFile = t.sources?.type?.file ?? 'File'
  const tSourcesTypeText = t.sources?.type?.text ?? 'Text'
  const tUntitledSource = t.sources?.untitledSource ?? 'Untitled Source'
  const tYes = t.sources?.yes ?? 'Yes'
  const tNo = t.sources?.no ?? 'No'

  const getSourceIcon = (source: SourceListResponse) => {
    if (source.asset?.url) return <LinkIcon className="h-4 w-4" />
    if (source.asset?.file_path) return <Upload className="h-4 w-4" />
    return <AlignLeft className="h-4 w-4" />
  }

  const getSourceType = (source: SourceListResponse) => {
    if (source.asset?.url) return tSourcesTypeLink
    if (source.asset?.file_path) return tSourcesTypeFile
    return tSourcesTypeText
  }

  const handleRowClick = useCallback((index: number, sourceId: string) => {
    setSelectedIndex(index)
    router.push(`/sources/${sourceId}`)
  }, [router])

  const [deletePassword, setDeletePassword] = useState('')
  const [deletePasswordError, setDeletePasswordError] = useState('')

  const handleDeleteClick = useCallback((e: React.MouseEvent, source: SourceListResponse) => {
    e.preventDefault()
    e.stopPropagation() // Prevent row click
    setDeletePassword('')
    setDeletePasswordError('')
    setDeleteDialog({ open: true, source })
  }, [])

  const handleDeleteConfirm = async () => {
    if (!deleteDialog.source) return

    const masterPassword = process.env.NEXT_PUBLIC_MASTER_NOTEBOOK_PASSWORD
    if (masterPassword && deletePassword !== masterPassword) {
      setDeletePasswordError(t.sources.incorrectPassword)
      return
    }

    try {
      await sourcesApi.delete(deleteDialog.source.id)
      toast.success(t.sources.deleteSuccess)
      // Remove the deleted source from the list
      setSources(prev => prev.filter(s => s.id !== deleteDialog.source?.id))
      setDeleteDialog({ open: false, source: null })
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } }, message?: string };
      console.error('Failed to delete source:', error)
      toast.error(t(getApiErrorKey(error.response?.data?.detail || error.message)))
    }
  }

  const handleBatchDeleteConfirm = async () => {
    const masterPassword = process.env.NEXT_PUBLIC_MASTER_NOTEBOOK_PASSWORD
    if (masterPassword && batchDeletePassword !== masterPassword) {
      setBatchDeletePasswordError(t.sources.incorrectPassword)
      return
    }

    setIsBatchDeleting(true)
    let successCount = 0
    let failCount = 0

    const promises = Array.from(selectedIds).map(id => sourcesApi.delete(id))
    const results = await Promise.allSettled(promises)
    
    results.forEach(result => {
      if (result.status === 'fulfilled') successCount++
      else failCount++
    })

    if (failCount === 0) {
      toast.success(t.sources.batchDeleteSuccess?.replace('{count}', successCount.toString()) ?? (language.startsWith('zh') ? `成功删除 ${successCount} 个来源` : `Successfully deleted ${successCount} sources`))
    } else {
      toast.error(t.sources.batchPartialSuccess?.replace('{success}', successCount.toString()).replace('{failed}', failCount.toString()) ?? (language.startsWith('zh') ? `成功删除 ${successCount} 个，失败 ${failCount} 个` : `Deleted ${successCount} sources, ${failCount} failed`))
    }

    setIsBatchDeleting(false)
    setBatchDeleteDialog(false)
    setSelectedIds(new Set())
    setBatchDeletePassword('')
    fetchSources()
  }

  if (loading) {
    return (
      <AppShell>
        <div className="flex h-full items-center justify-center">
          <LoadingSpinner />
        </div>
      </AppShell>
    )
  }

  if (error) {
    return (
      <AppShell>
        <div className="flex h-full items-center justify-center">
          <p className="text-red-500">{error}</p>
        </div>
      </AppShell>
    )
  }

  if (sources.length === 0 && page === 1) {
    return (
      <AppShell>
        <EmptyState
          icon={FileText}
          title={t.sources.noSourcesYet}
          description={t.sources.allSourcesDescShort}
        />
      </AppShell>
    )
  }

  return (
    <AppShell>
      <div className="flex flex-col h-full w-full max-w-none px-6 py-6">
        <div className="mb-6 flex-shrink-0">
          <h1 className="text-3xl font-bold">{t.sources.allSources}</h1>
          <p className="mt-2 text-muted-foreground">
            {t.sources.allSourcesDesc}
          </p>
        </div>

        <div ref={scrollContainerRef} className="flex-1 rounded-md border overflow-auto">
          <table
            ref={tableRef}
            tabIndex={0}
            className="w-full min-w-[800px] outline-none table-fixed"
          >
            <colgroup>
              <col className="w-[50px]" />
              <col className="w-[120px]" />
              <col className="w-auto" />
              <col className="w-[120px]" />
              <col className="w-[150px]" />
              <col className="w-[80px]" />
              <col className="w-[100px]" />
              <col className="w-[100px]" />
              <col className="w-[100px]" />
              <col className="w-[100px]" />
            </colgroup>
            <thead className="sticky top-0 bg-background z-10">
              <tr className="border-b bg-muted/50">
                <th className="h-12 w-[50px] px-4 text-left align-middle"></th>
                <th className="h-12 px-4 text-left align-middle font-medium text-muted-foreground">
                  {t.common.type}
                </th>
                 <th className="h-12 px-4 text-left align-middle font-medium text-muted-foreground">
                  {t.common.title}
                </th>
                <th className="h-12 px-4 text-left align-middle font-medium text-muted-foreground">
                  {t.sources.uploader}
                </th>
                <th className="h-12 px-4 text-left align-middle font-medium text-muted-foreground hidden sm:table-cell">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => toggleSort('created')}
                    className="h-8 px-2 hover:bg-muted"
                  >
                    {t.common.created_label}
                    <ArrowUpDown className={cn(
                      "ml-2 h-3 w-3",
                      sortBy === 'created' ? 'opacity-100' : 'opacity-30'
                    )} />
                    {sortBy === 'created' && (
                      <span className="ml-1 text-xs">
                        {sortOrder === 'asc' ? '↑' : '↓'}
                      </span>
                    )}
                  </Button>
                </th>
                <th className="h-12 px-4 text-center align-middle font-medium text-muted-foreground hidden md:table-cell">
                  {t.sources.insights}
                </th>
                <th className="h-12 px-4 text-center align-middle font-medium text-muted-foreground hidden lg:table-cell">
                  {t.sources.embedded}
                </th>
                  <th className="h-12 px-4 text-center align-middle font-medium text-muted-foreground hidden lg:table-cell">
                    {t.sources.kgExtracted || "已抽取图谱"}
                  </th>
                  <th className="h-12 px-4 text-center align-middle font-medium text-muted-foreground hidden lg:table-cell">
                    {t.sources.references}
                  </th>
                  <th className="h-12 px-4 text-right align-middle font-medium text-muted-foreground">
                    {t.common.actions}
                  </th>
                </tr>
              </thead>
            <tbody>
              {sources.map((source, index) => (
                <tr
                  key={source.id}
                  onClick={() => handleRowClick(index, source.id)}
                  onMouseEnter={() => setSelectedIndex(index)}
                  className={cn(
                    "border-b transition-colors cursor-pointer",
                    selectedIndex === index
                      ? "bg-accent"
                      : "hover:bg-muted/50"
                  )}
                >
                  <td 
                    className="h-12 w-[50px] px-4 select-none" 
                    onMouseDown={(e) => {
                      // Prevent text selection when shift-clicking
                      if (e.shiftKey) {
                        e.preventDefault()
                      }
                    }}
                    onClick={(e) => {
                    e.stopPropagation()
                    if (e.shiftKey) {
                      window.getSelection()?.removeAllRanges()
                    }
                    const isChecked = !selectedIds.has(source.id)
                    setSelectedIds(prev => {
                      const next = new Set(prev)
                      if (e.shiftKey && lastSelectedIndex !== null) {
                        const start = Math.min(lastSelectedIndex, index)
                        const end = Math.max(lastSelectedIndex, index)
                        for (let i = start; i <= end; i++) {
                          if (isChecked) next.add(sources[i].id)
                          else next.delete(sources[i].id)
                        }
                      } else {
                        if (isChecked) next.add(source.id)
                        else next.delete(source.id)
                      }
                      return next
                    })
                    setLastSelectedIndex(index)
                  }}>
                    <Checkbox
                      checked={selectedIds.has(source.id)}
                      className="pointer-events-none"
                    />
                  </td>
                  <td className="h-12 px-4">
                    <div className="flex items-center gap-2">
                      {getSourceIcon(source)}
                      <Badge variant="secondary" className="text-xs">
                        {getSourceType(source)}
                      </Badge>
                    </div>
                  </td>
                  <td className="h-12 px-4">
                    <div className="flex flex-col overflow-hidden">
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className="font-medium truncate">
                            {source.title || tUntitledSource}
                          </span>
                        </TooltipTrigger>
                        <TooltipContent side="top" align="start" className="max-w-md break-all">
                          {source.title || tUntitledSource}
                        </TooltipContent>
                      </Tooltip>
                      {source.asset?.url && (
                        <span className="text-xs text-muted-foreground truncate">
                          {source.asset.url}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="h-12 px-4 text-muted-foreground text-sm">
                    {source.uploader_name || "System Admin"}
                  </td>
                  <td className="h-12 px-4 text-muted-foreground text-sm hidden sm:table-cell">
                    {format(new Date(source.created), 'yyyy-MM-dd HH:mm:ss')}
                  </td>
                  <td className="h-12 px-4 text-center hidden md:table-cell">
                    <span className="text-sm font-medium">{source.insights_count || 0}</span>
                  </td>
                  <td className="h-12 px-4 text-center hidden lg:table-cell">
                    <Badge variant={source.embedded ? "default" : "secondary"} className="text-xs">
                      {source.embedded ? tYes : tNo}
                    </Badge>
                  </td>
                  <td className="h-12 px-4 text-center hidden lg:table-cell">
                    <Badge variant={source.kg_extracted ? "default" : "secondary"} className="text-xs">
                      {source.kg_extracted ? tYes : tNo}
                    </Badge>
                  </td>
                  <td className="h-12 px-4 text-center hidden lg:table-cell">
                    <span className="text-sm font-medium">{source.notebook_count || 0}</span>
                  </td>
                  <td className="h-12 px-4 text-right">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={(e) => handleDeleteClick(e, source)}
                      className="text-destructive hover:text-destructive"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination Controls */}
        <div className="flex items-center justify-between mt-4 pt-4 border-t">
          <Button 
            variant="outline" 
            onClick={() => { setPage(p => Math.max(1, p - 1)); setSelectedIds(new Set()); }}
            disabled={page === 1}
          >
            {t.sources.prevPage}
          </Button>
          <span className="text-sm text-muted-foreground">
            {t.sources.pageOf.replace('{page}', page.toString())}
          </span>
          <Button 
            variant="outline" 
            onClick={() => { setPage(p => p + 1); setSelectedIds(new Set()); }}
            disabled={!hasMore}
          >
            {t.sources.nextPage}
          </Button>
        </div>
      </div>

      <Dialog open={deleteDialog.open} onOpenChange={(open) => {
        if (!open) {
          setDeletePassword('')
          setDeletePasswordError('')
        }
        setDeleteDialog({ open, source: open ? deleteDialog.source : null })
      }}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>{t.sources?.delete ?? 'Delete'}</DialogTitle>
            <DialogDescription>
              {(t.sources?.deleteConfirmWithTitle ?? 'Are you sure you want to delete {title}?').replace('{title}', deleteDialog.source?.title || tUntitledSource)}
            </DialogDescription>
          </DialogHeader>
          
          {process.env.NEXT_PUBLIC_MASTER_NOTEBOOK_PASSWORD && (
            <div className="space-y-2 py-4">
              <p className="text-sm font-medium">
                {t.sources.enterPassword}
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
                placeholder={t.sources.enterPassword}
                autoFocus
              />
              {deletePasswordError && (
                <p className="text-sm text-destructive">{deletePasswordError}</p>
              )}
            </div>
          )}
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialog({ open: false, source: null })}>
              {t.common?.cancel ?? 'Cancel'}
            </Button>
            <Button variant="destructive" onClick={handleDeleteConfirm}>
              {t.common?.delete ?? 'Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={batchDeleteDialog} onOpenChange={(open) => {
        if (!open) {
          setBatchDeletePassword('')
          setBatchDeletePasswordError('')
        }
        if (!isBatchDeleting) {
          setBatchDeleteDialog(open)
        }
      }}>
        <DialogContent className="sm:max-w-[425px]" onPointerDownOutside={(e) => { if (isBatchDeleting) e.preventDefault() }} onEscapeKeyDown={(e) => { if (isBatchDeleting) e.preventDefault() }}>
          <DialogHeader>
            <DialogTitle>{t.sources?.batchDelete ?? (language.startsWith('zh') ? '批量删除' : 'Batch Delete')}</DialogTitle>
            <DialogDescription>
              {t.sources?.batchDeleteConfirm?.replace('{count}', selectedIds.size.toString()) ?? (language.startsWith('zh') ? `确定要永久删除选定的 ${selectedIds.size} 个来源吗？` : `Are you sure you want to permanently delete the selected ${selectedIds.size} sources?`)}
            </DialogDescription>
          </DialogHeader>
          
          {process.env.NEXT_PUBLIC_MASTER_NOTEBOOK_PASSWORD && (
            <div className="space-y-2 py-4">
              <p className="text-sm font-medium">
                {t.sources.enterPassword}
              </p>
              <Input
                type="password"
                value={batchDeletePassword}
                onChange={e => {
                  setBatchDeletePassword(e.target.value)
                  setBatchDeletePasswordError('')
                }}
                onKeyDown={e => {
                  e.stopPropagation()
                  if (e.key === 'Enter' && !isBatchDeleting) {
                    e.preventDefault()
                    handleBatchDeleteConfirm()
                  }
                }}
                placeholder={t.sources.enterPassword}
                autoFocus
                disabled={isBatchDeleting}
              />
              {batchDeletePasswordError && (
                <p className="text-sm text-destructive">{batchDeletePasswordError}</p>
              )}
            </div>
          )}
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setBatchDeleteDialog(false)} disabled={isBatchDeleting}>
              {t.common?.cancel ?? 'Cancel'}
            </Button>
            <Button variant="destructive" onClick={handleBatchDeleteConfirm} disabled={isBatchDeleting}>
              {isBatchDeleting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {t.common?.delete ?? 'Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {selectedIds.size > 0 && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 bg-popover border shadow-lg rounded-full px-4 py-3 flex items-center gap-4 animate-in slide-in-from-bottom-5">
          <span className="text-sm font-medium whitespace-nowrap">
            {t.sources?.itemsSelected?.replace('{count}', selectedIds.size.toString()) ?? (language.startsWith('zh') ? `已选择 ${selectedIds.size} 项` : `${selectedIds.size} items selected`)}
          </span>
          <div className="h-4 w-px bg-border"></div>
          <Button variant="ghost" size="sm" onClick={() => setSelectedIds(new Set())}>
            {t.sources?.clearSelection ?? (language.startsWith('zh') ? '取消选择' : 'Clear Selection')}
          </Button>
          <Button variant="destructive" size="sm" onClick={() => setBatchDeleteDialog(true)}>
            <Trash2 className="h-4 w-4 mr-2" />
            {t.sources?.batchDelete ?? (language.startsWith('zh') ? '批量删除' : 'Batch Delete')}
          </Button>
        </div>
      )}
    </AppShell>
  )
}