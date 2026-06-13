'use client'

import { use, useState, useEffect } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { NotebookHeader } from '../components/NotebookHeader'
import { SourcesColumn } from '../components/SourcesColumn'
import { NotesColumn } from '../components/NotesColumn'
import { ChatColumn } from '../components/ChatColumn'
import { useNotebook } from '@/lib/hooks/use-notebooks'
import { useNotebookSources } from '@/lib/hooks/use-sources'
import { useNotes } from '@/lib/hooks/use-notes'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { useNotebookColumnsStore } from '@/lib/stores/notebook-columns-store'
import { useRecentNotebooksStore } from '@/lib/stores/recent-notebooks-store'
import { useIsDesktop } from '@/lib/hooks/use-media-query'
import { useTranslation } from '@/lib/hooks/use-translation'
import { cn } from '@/lib/utils'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { FileText, StickyNote, MessageSquare, Lock } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'

export type ContextMode = 'off' | 'insights' | 'full'

export interface ContextSelections {
  sources: Record<string, ContextMode>
  notes: Record<string, ContextMode>
}

export default function NotebookPage({ params }: { params: Promise<{ id: string }> }) {
  const { t } = useTranslation()
  const resolvedParams = use(params)

  // Ensure the notebook ID is properly decoded from URL
  const notebookId = resolvedParams?.id ? decodeURIComponent(resolvedParams.id) : ''

  const { data: notebook, isLoading: notebookLoading } = useNotebook(notebookId)
  const {
    sources,
    isLoading: sourcesLoading,
    refetch: refetchSources,
    hasNextPage,
    isFetchingNextPage,
    fetchNextPage,
  } = useNotebookSources(notebookId)
  const { data: notes, isLoading: notesLoading } = useNotes(notebookId)

  // Get collapse states for dynamic layout
  const { sourcesCollapsed, notesCollapsed, setNotes } = useNotebookColumnsStore()
  const recordNotebook = useRecentNotebooksStore((state) => state.recordNotebook)

  // Detect desktop to avoid double-mounting ChatColumn
  const isDesktop = useIsDesktop()

  // Mobile tab state (Sources, Notes, or Chat)
  const [mobileActiveTab, setMobileActiveTab] = useState<'sources' | 'notes' | 'chat'>('chat')

  // Context selection state
  const [contextSelections, setContextSelections] = useState<ContextSelections>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem(`notebook-context-${notebookId}`)
      if (saved) {
        try {
          return JSON.parse(saved)
        } catch (e) {
          console.error('Failed to parse saved context selections', e)
        }
      }
    }
    return {
      sources: {},
      notes: {}
    }
  })

  // Save to localStorage whenever it changes
  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(`notebook-context-${notebookId}`, JSON.stringify(contextSelections))
    }
  }, [contextSelections, notebookId])

  // Password state
  const [isUnlocked, setIsUnlocked] = useState(false)
  const [passwordInput, setPasswordInput] = useState('')
  const [passwordError, setPasswordError] = useState('')

  useEffect(() => {
    if (!notebook?.password) {
      setIsUnlocked(true)
    } else {
      setIsUnlocked(false)
    }
  }, [notebook])

  useEffect(() => {
    if (notebook?.id && notebook.name) {
      recordNotebook({ id: notebook.id, name: notebook.name })
    }
  }, [notebook?.id, notebook?.name, recordNotebook])

  const handleUnlock = (e: React.FormEvent) => {
    e.preventDefault()
    if (notebook?.password) {
      if (
        passwordInput === notebook.password ||
        passwordInput === process.env.NEXT_PUBLIC_MASTER_NOTEBOOK_PASSWORD
      ) {
        setIsUnlocked(true)
        setPasswordError('')
      } else {
        setPasswordError(t.notebooks.incorrectPassword)
      }
    }
  }

  // Initialize and update selections when sources load or change
  useEffect(() => {
    if (sources && sources.length > 0) {
      setContextSelections(prev => {
        const newSourceSelections = { ...prev.sources }
        let changed = false
        sources.forEach(source => {
          if (newSourceSelections[source.id] === undefined) {
            newSourceSelections[source.id] = 'full'
            changed = true
          }
        })
        return changed ? { ...prev, sources: newSourceSelections } : prev
      })
    }
  }, [sources])

  useEffect(() => {
    if (notes && notes.length > 0) {
      setContextSelections(prev => {
        const newNoteSelections = { ...prev.notes }
        let changed = false
        notes.forEach(note => {
          // Only set default if not already set
          if (!(note.id in newNoteSelections)) {
            // Notes default to 'full'
            newNoteSelections[note.id] = 'full'
            changed = true
          }
        })
        return changed ? { ...prev, notes: newNoteSelections } : prev
      })
    }
  }, [notes])

  useEffect(() => {
    if (!notesLoading && notes && notes.length === 0) {
      setNotes(true)
    }
  }, [notes, notesLoading, setNotes])

  // Handler to update context selection
  const handleContextModeChange = (itemId: string, mode: ContextMode, type: 'source' | 'note') => {
    setContextSelections(prev => ({
      ...prev,
      [type === 'source' ? 'sources' : 'notes']: {
        ...(type === 'source' ? prev.sources : prev.notes),
        [itemId]: mode
      }
    }))
  }

  const handleBulkContextModeChange = (mode: ContextMode, type: 'source' | 'note', itemIds?: string[]) => {
    setContextSelections(prev => {
      const allItems = type === 'source' ? sources : notes
      if (!allItems) return prev
      const scopedIds = itemIds ? new Set(itemIds) : null
      const items = scopedIds
        ? allItems.filter(item => scopedIds.has(item.id))
        : allItems
      if (items.length === 0) return prev
      
      const newSelections = { ...(type === 'source' ? prev.sources : prev.notes) }
      let changed = false
      
      items.forEach(item => {
        if (newSelections[item.id] !== mode) {
          newSelections[item.id] = mode
          changed = true
        }
      })
      
      if (!changed) return prev
      
      return {
        ...prev,
        [type === 'source' ? 'sources' : 'notes']: newSelections
      }
    })
  }

  if (notebookLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (!notebook) {
    return (
      <AppShell>
        <div className="p-6">
          <h1 className="text-2xl font-bold mb-4">{t.notebooks.notFound}</h1>
          <p className="text-muted-foreground">{t.notebooks.notFoundDesc}</p>
        </div>
      </AppShell>
    )
  }

  if (notebook.password && !isUnlocked) {
    return (
      <AppShell>
        <div className="flex-1 flex flex-col items-center justify-center p-6 h-[calc(100vh-4rem)]">
          <div className="max-w-md w-full space-y-6 bg-card p-8 rounded-xl border shadow-sm">
            <div className="space-y-2 text-center">
              <div className="mx-auto w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center mb-4">
                <Lock className="h-6 w-6 text-primary" />
              </div>
              <h2 className="text-2xl font-bold tracking-tight">{t.notebooks.protectedNotebook}</h2>
              <p className="text-muted-foreground text-sm">
                {t.notebooks.passwordRequiredDesc}
              </p>
            </div>
            <form onSubmit={handleUnlock} className="space-y-4">
              <div className="space-y-2">
                <Input
                  type="password"
                  placeholder={t.notebooks.enterPassword}
                  value={passwordInput}
                  onChange={(e) => setPasswordInput(e.target.value)}
                  autoFocus
                />
                {passwordError && (
                  <p className="text-sm text-destructive">{passwordError}</p>
                )}
              </div>
              <Button type="submit" className="w-full">
                {t.notebooks.unlock}
              </Button>
            </form>
          </div>
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell>
      <div className="flex flex-col flex-1 min-h-0">
        <div className="flex-shrink-0 p-6 pb-0">
          <NotebookHeader notebook={notebook} />
        </div>

        <div className="flex-1 p-6 pt-6 overflow-x-auto flex flex-col">
          {/* Mobile: Tabbed interface - only render on mobile to avoid double-mounting */}
          {!isDesktop && (
            <>
              <div className="lg:hidden mb-4">
                <Tabs value={mobileActiveTab} onValueChange={(value) => setMobileActiveTab(value as 'sources' | 'notes' | 'chat')}>
                  <TabsList className="grid w-full grid-cols-3">
                    <TabsTrigger value="sources" className="gap-2">
                      <FileText className="h-4 w-4" />
                      {t.navigation.sources}
                    </TabsTrigger>
                    <TabsTrigger value="notes" className="gap-2">
                      <StickyNote className="h-4 w-4" />
                      {t.common.notes}
                    </TabsTrigger>
                    <TabsTrigger value="chat" className="gap-2">
                      <MessageSquare className="h-4 w-4" />
                      {t.common.chat}
                    </TabsTrigger>
                  </TabsList>
                </Tabs>
              </div>

              {/* Mobile: Show only active tab (all stay mounted for chat streaming persistence) */}
              <div className="flex-1 overflow-hidden lg:hidden">
                <div className={cn(mobileActiveTab !== 'sources' && 'hidden')}>
                  <SourcesColumn
                    sources={sources}
                    isLoading={sourcesLoading}
                    notebookId={notebookId}
                    notebookName={notebook?.name}
                    onRefresh={refetchSources}
                    contextSelections={contextSelections.sources}
                    onContextModeChange={(sourceId, mode) => handleContextModeChange(sourceId, mode, 'source')}
                    onBulkContextModeChange={(mode, sourceIds) => handleBulkContextModeChange(mode, 'source', sourceIds)}
                    hasNextPage={hasNextPage}
                    isFetchingNextPage={isFetchingNextPage}
                    fetchNextPage={fetchNextPage}
                  />
                </div>
                <div className={cn(mobileActiveTab !== 'notes' && 'hidden')}>
                  <NotesColumn
                    notes={notes}
                    isLoading={notesLoading}
                    notebookId={notebookId}
                    contextSelections={contextSelections.notes}
                    onContextModeChange={(noteId, mode) => handleContextModeChange(noteId, mode, 'note')}
                    onBulkContextModeChange={(mode) => handleBulkContextModeChange(mode, 'note')}
                  />
                </div>
                <div className={cn(mobileActiveTab !== 'chat' && 'hidden')}>
                  <ChatColumn
                    notebookId={notebookId}
                    contextSelections={contextSelections}
                    sources={sources}
                    sourcesLoading={sourcesLoading}
                  />
                </div>
              </div>
            </>
          )}

          {/* Desktop: Collapsible columns layout */}
          <div className={cn(
            'hidden lg:flex h-full min-h-0 gap-6 transition-all duration-150',
            'flex-row'
          )}>
            {/* Sources Column */}
            <div className={cn(
              'transition-all duration-150',
              sourcesCollapsed ? 'w-12 flex-shrink-0' : 'flex-none basis-1/3'
            )}>
              <SourcesColumn
                sources={sources}
                isLoading={sourcesLoading}
                notebookId={notebookId}
                notebookName={notebook?.name}
                onRefresh={refetchSources}
                contextSelections={contextSelections.sources}
                onContextModeChange={(sourceId, mode) => handleContextModeChange(sourceId, mode, 'source')}
                onBulkContextModeChange={(mode, sourceIds) => handleBulkContextModeChange(mode, 'source', sourceIds)}
                hasNextPage={hasNextPage}
                isFetchingNextPage={isFetchingNextPage}
                fetchNextPage={fetchNextPage}
              />
            </div>

            {/* Chat Column - always expanded, placed next to sources for faster reference */}
            <div className="transition-all duration-150 flex-1 min-w-0 lg:pr-6 lg:-mr-6">
              <ChatColumn
                notebookId={notebookId}
                contextSelections={contextSelections}
                sources={sources}
                sourcesLoading={sourcesLoading}
              />
            </div>

            {/* Notes Column */}
            <div className={cn(
              'transition-all duration-150',
              notesCollapsed ? 'w-12 flex-shrink-0' : 'flex-none basis-1/3'
            )}>
              <NotesColumn
                notes={notes}
                isLoading={notesLoading}
                notebookId={notebookId}
                contextSelections={contextSelections.notes}
                onContextModeChange={(noteId, mode) => handleContextModeChange(noteId, mode, 'note')}
                onBulkContextModeChange={(mode) => handleBulkContextModeChange(mode, 'note')}
              />
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  )
}
