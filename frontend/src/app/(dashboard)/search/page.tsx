'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { useTranslation } from '@/lib/hooks/use-translation'
import { AppShell } from '@/components/layout/AppShell'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Search, ChevronDown, AlertCircle, Settings, MessageCircleQuestion } from 'lucide-react'
import { useSearch } from '@/lib/hooks/use-search'
import { useAsk } from '@/lib/hooks/use-ask'
import { useModelDefaults, useModels } from '@/lib/hooks/use-models'
import { useModalManager } from '@/lib/hooks/use-modal-manager'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { StreamingResponse } from '@/components/search/StreamingResponse'
import { AdvancedModelsDialog } from '@/components/search/AdvancedModelsDialog'
import { SaveToNotebooksDialog } from '@/components/search/SaveToNotebooksDialog'

export default function SearchPage() {
  const { t, language } = useTranslation()
  // URL params
  const searchParams = useSearchParams()
  const urlQuery = searchParams?.get('q') || ''
  const rawMode = searchParams?.get('mode')
  const urlMode = rawMode === 'search' ? 'search' : 'ask'

  // Tab state (controlled)
  const [activeTab, setActiveTab] = useState<'ask' | 'search'>(() => {
    if (urlMode) return urlMode === 'search' ? 'search' : 'ask'
    if (typeof window !== 'undefined') {
      return (localStorage.getItem('search-active-tab') as 'ask' | 'search') || 'ask'
    }
    return 'ask'
  })

  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('search-active-tab', activeTab)
    }
  }, [activeTab])

  // Search state
  const [searchQuery, setSearchQuery] = useState(() => {
    if (urlMode === 'search' && urlQuery) return urlQuery
    if (typeof window !== 'undefined') {
      return localStorage.getItem('search-query') || ''
    }
    return ''
  })
  const [searchType, setSearchType] = useState<'text' | 'vector'>(() => {
    if (typeof window !== 'undefined') {
      return (localStorage.getItem('search-type') as 'text' | 'vector') || 'text'
    }
    return 'text'
  })
  const [searchSources, setSearchSources] = useState(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('search-sources')
      return saved ? saved === 'true' : true
    }
    return true
  })
  const [searchNotes, setSearchNotes] = useState(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('search-notes')
      return saved ? saved === 'true' : true
    }
    return true
  })
  
  // Persisted search results
  const [persistedSearchResults, setPersistedSearchResults] = useState<any>(null)

  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('search-query', searchQuery)
      localStorage.setItem('search-type', searchType)
      localStorage.setItem('search-sources', searchSources.toString())
      localStorage.setItem('search-notes', searchNotes.toString())
    }
  }, [searchQuery, searchType, searchSources, searchNotes])

  // Ask state
  const [askQuestion, setAskQuestion] = useState(() => {
    if (urlMode === 'ask' && urlQuery) return urlQuery
    if (typeof window !== 'undefined') {
      return localStorage.getItem('ask-question') || ''
    }
    return ''
  })

  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('ask-question', askQuestion)
    }
  }, [askQuestion])

  // Advanced models dialog
  const [showAdvancedModels, setShowAdvancedModels] = useState(false)
  const [customModels, setCustomModels] = useState<{
    strategy: string
    answer: string
    finalAnswer: string
  } | null>(() => {
    if (typeof window !== 'undefined') {
      try {
        const saved = localStorage.getItem('ask-custom-models')
        return saved ? JSON.parse(saved) : null
      } catch (e) {
        return null
      }
    }
    return null
  })

  useEffect(() => {
    if (typeof window !== 'undefined') {
      if (customModels) {
        localStorage.setItem('ask-custom-models', JSON.stringify(customModels))
      } else {
        localStorage.removeItem('ask-custom-models')
      }
    }
  }, [customModels])

  // Save to notebooks dialog
  const [showSaveDialog, setShowSaveDialog] = useState(false)

  // Hooks
  const searchMutation = useSearch()
  
  // Get active search data (either from current mutation or persisted)
  const activeSearchData = searchMutation.data || persistedSearchResults
  
  // Load persisted search results on mount
  useEffect(() => {
    if (typeof window !== 'undefined' && !searchMutation.data && !searchMutation.isPending) {
      try {
        const savedResults = localStorage.getItem('search-results')
        if (savedResults) {
          setPersistedSearchResults(JSON.parse(savedResults))
        }
      } catch (e) {
        console.error('Failed to parse saved search results', e)
      }
    }
  }, [])

  // Clear persisted results when a new search starts
  useEffect(() => {
    if (searchMutation.isPending) {
      setPersistedSearchResults(null)
    }
  }, [searchMutation.isPending])
  const ask = useAsk()
  const { data: modelDefaults, isLoading: modelsLoading } = useModelDefaults()
  const { data: availableModels } = useModels()
  const { openModal } = useModalManager()

  const modelNameById = useMemo(() => {
    if (!availableModels) {
      return new Map<string, string>()
    }
    return new Map(availableModels.map((model) => [model.id, model.name]))
  }, [availableModels])

  const resolveModelName = (id?: string | null) => {
    if (!id) return t.searchPage.notSet
    return modelNameById.get(id) ?? id
  }

  const hasEmbeddingModel = !!modelDefaults?.default_embedding_model

  // Track if we've already auto-triggered from URL params
  const hasAutoTriggeredRef = useRef(false)
  const lastUrlParamsRef = useRef({ q: '', mode: '' })

  const handleSearch = useCallback(() => {
    if (!searchQuery.trim()) return

    searchMutation.mutate({
      query: searchQuery,
      type: searchType,
      limit: 100,
      search_sources: searchSources,
      search_notes: searchNotes,
      minimum_score: 0.2
    })
  }, [searchQuery, searchType, searchSources, searchNotes, searchMutation])

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch()
    }
  }

  const handleAsk = useCallback(() => {
    if (!askQuestion.trim() || !modelDefaults?.default_chat_model) return

    const models = customModels || {
      strategy: modelDefaults.default_chat_model,
      answer: modelDefaults.default_chat_model,
      finalAnswer: modelDefaults.default_chat_model
    }

    ask.sendAsk(askQuestion, models)
  }, [askQuestion, modelDefaults, customModels, ask])

  const handleClearAsk = useCallback(() => {
    setAskQuestion('')
    ask.clearState()
    setCustomModels(null)
    if (typeof window !== 'undefined') {
      localStorage.removeItem('ask-question')
      localStorage.removeItem('ask-custom-models')
      localStorage.removeItem('ask-store-state')
    }
  }, [ask])

  const handleClearSearch = useCallback(() => {
    setSearchQuery('')
    searchMutation.reset()
    setPersistedSearchResults(null)
    if (typeof window !== 'undefined') {
      localStorage.removeItem('search-results')
      localStorage.removeItem('search-query')
      // We don't remove search-type, search-sources, and search-notes 
      // so the user's preferred settings are kept
    }
  }, [searchMutation])

  // Auto-trigger search/ask when arriving with URL params
  useEffect(() => {
    // Skip if already triggered or no query
    if (hasAutoTriggeredRef.current || !urlQuery) return

    // Wait for models to load before triggering ask
    if (urlMode === 'ask' && modelsLoading) return

    if (urlMode === 'search') {
      handleSearch()
      hasAutoTriggeredRef.current = true
    } else if (urlMode === 'ask' && modelDefaults?.default_chat_model) {
      handleAsk()
      hasAutoTriggeredRef.current = true
    }
  }, [urlQuery, urlMode, modelsLoading, modelDefaults, handleSearch, handleAsk])

  // Handle URL param changes while on page (e.g., from command palette again)
  useEffect(() => {
    const currentQ = searchParams?.get('q') || ''
    const rawCurrentMode = searchParams?.get('mode')
    const currentMode = rawCurrentMode === 'search' ? 'search' : 'ask'

    // Check if URL params have changed
    if (currentQ !== lastUrlParamsRef.current.q || currentMode !== lastUrlParamsRef.current.mode) {
      lastUrlParamsRef.current = { q: currentQ, mode: currentMode }

      if (currentQ) {
        // Update state based on mode
        if (currentMode === 'search') {
          setSearchQuery(currentQ)
          setActiveTab('search')
          // Reset trigger flag so we auto-trigger with new params
          hasAutoTriggeredRef.current = false
        } else {
          setAskQuestion(currentQ)
          setActiveTab('ask')
          hasAutoTriggeredRef.current = false
        }
      }
    }
  }, [searchParams])

  return (
    <AppShell>
      <div className="flex h-full min-h-0 flex-col overflow-hidden p-4 md:p-6">
        <h1 className="shrink-0 text-xl md:text-2xl font-bold mb-4 md:mb-6">{t.searchPage.askAndSearch}</h1>

        <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'ask' | 'search')} className="w-full flex-1 min-h-0 space-y-6 overflow-hidden">
          <div className="shrink-0 space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{t.searchPage.chooseAMode}</p>
            <TabsList aria-label={t.common.accessibility.searchKB} className="w-full max-w-xl">
              <TabsTrigger value="ask">
                <MessageCircleQuestion className="h-4 w-4" />
                {t.searchPage.askBeta}
              </TabsTrigger>
              <TabsTrigger value="search">
                <Search className="h-4 w-4" />
                {t('searchPage.search')}
              </TabsTrigger>
            </TabsList>
          </div>

          <TabsContent value="ask" className="mt-0 min-h-0 overflow-hidden data-[state=inactive]:hidden">
            <Card className="h-full min-h-0 overflow-hidden">
              <CardHeader className="shrink-0">
                <CardTitle className="text-lg">{t.searchPage.askYourKb}</CardTitle>
                <p className="text-sm text-muted-foreground">
                  {t.searchPage.askYourKbDesc}
                </p>
              </CardHeader>
              <CardContent className="min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain pb-6 pr-3 [scrollbar-gutter:stable]">
                {/* Question Input */}
                <div className="space-y-2">
                  <Label htmlFor="ask-question">{t.searchPage.question}</Label>
                  <Textarea
                    id="ask-question"
                    name="ask-question"
                    placeholder={t.searchPage.enterQuestionPlaceholder}
                    value={askQuestion}
                    onChange={(e) => setAskQuestion(e.target.value)}
                    onKeyDown={(e) => {
                      // Submit on Cmd/Ctrl+Enter
                      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && !ask.isStreaming && askQuestion.trim()) {
                        e.preventDefault()
                        handleAsk()
                      }
                    }}
                    disabled={ask.isStreaming}
                    rows={3}
                    aria-label={t.common.accessibility.enterQuestion}
                  />
                  <p className="text-xs text-muted-foreground">{t.searchPage.pressToSubmit}</p>
                </div>

                {/* Models Display */}
                {!hasEmbeddingModel ? (
                  <div className="flex items-center gap-2 p-3 text-sm text-amber-600 dark:text-amber-500 bg-amber-50 dark:bg-amber-950/20 rounded-md">
                    <AlertCircle className="h-4 w-4" />
                    <span>{t.searchPage.noEmbeddingModel}</span>
                  </div>
                ) : (
                  <>
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <Label className="text-xs text-muted-foreground">
                          {customModels ? t.searchPage.usingCustomModels : t.searchPage.usingDefaultModels}
                        </Label>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setShowAdvancedModels(true)}
                          disabled={ask.isStreaming}
                          className="h-auto py-1 px-2"
                        >
                          <Settings className="h-3 w-3 mr-1" />
                          {t.searchPage.advanced}
                        </Button>
                      </div>
                      <div className="flex gap-2 text-xs flex-wrap">
                        <Badge variant="secondary">
                          {t.searchPage.strategy}: {resolveModelName(customModels?.strategy || modelDefaults?.default_chat_model)}
                        </Badge>
                        <Badge variant="secondary">
                          {t.searchPage.answer}: {resolveModelName(customModels?.answer || modelDefaults?.default_chat_model)}
                        </Badge>
                        <Badge variant="secondary">
                          {t.searchPage.final}: {resolveModelName(customModels?.finalAnswer || modelDefaults?.default_chat_model)}
                        </Badge>
                      </div>
                    </div>

                    <div className="flex flex-col sm:flex-row flex-wrap gap-2">
                      <Button
                        onClick={handleAsk}
                        disabled={ask.isStreaming || !askQuestion.trim()}
                        className="w-full sm:flex-1"
                      >
                        {ask.isStreaming ? (
                          <>
                            <LoadingSpinner size="sm" className="mr-2" />
                            {t.searchPage.processing}
                          </>
                        ) : (
                          t.searchPage.ask
                        )}
                      </Button>
                      
                      {(ask.finalAnswer || ask.answers.length > 0 || ask.strategy || askQuestion.length > 0) && (
                        <Button
                          variant="outline"
                          onClick={handleClearAsk}
                          disabled={ask.isStreaming}
                          className="w-full sm:flex-1"
                        >
                          {language.startsWith('zh') ? '清空内容' : 'Clear'}
                        </Button>
                      )}
                    </div>
                  </>
                )}

                {/* Streaming Response */}
                <StreamingResponse
                  isStreaming={ask.isStreaming}
                  strategy={ask.strategy}
                  answers={ask.answers}
                  finalAnswer={ask.finalAnswer}
                  onSaveRequest={() => setShowSaveDialog(true)}
                />

                {/* Advanced Models Dialog */}
                <AdvancedModelsDialog
                  open={showAdvancedModels}
                  onOpenChange={setShowAdvancedModels}
                  defaultModels={{
                    strategy: customModels?.strategy || modelDefaults?.default_chat_model || '',
                    answer: customModels?.answer || modelDefaults?.default_chat_model || '',
                    finalAnswer: customModels?.finalAnswer || modelDefaults?.default_chat_model || ''
                  }}
                  onSave={setCustomModels}
                />

                {/* Save to Notebooks Dialog */}
                {ask.finalAnswer && (
                  <SaveToNotebooksDialog
                    open={showSaveDialog}
                    onOpenChange={setShowSaveDialog}
                    question={askQuestion}
                    answer={ask.finalAnswer}
                  />
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="search" className="mt-0 min-h-0 overflow-y-auto data-[state=inactive]:hidden">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">{t('searchPage.search')}</CardTitle>
                <p className="text-sm text-muted-foreground">
                  {t.searchPage.searchDesc}
                </p>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Search Input */}
                <div className="space-y-2">
                  <Label htmlFor="search-query" className="sr-only">
                    {t('searchPage.search')}
                  </Label>
                  <div className="flex flex-col sm:flex-row flex-wrap gap-2">
                    <Input
                      id="search-query"
                      name="search-query"
                      placeholder={t.searchPage.enterSearchPlaceholder}
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      onKeyPress={handleKeyPress}
                      disabled={searchMutation.isPending}
                      className="flex-1"
                      aria-label={t.common.accessibility.enterSearch}
                      autoComplete="off"
                    />
                    <Button
                      onClick={handleSearch}
                      disabled={searchMutation.isPending || !searchQuery.trim()}
                      aria-label={t.common.accessibility.searchKBBtn}
                      className="w-full sm:w-auto"
                    >
                      {searchMutation.isPending ? (
                        <LoadingSpinner size="sm" />
                      ) : (
                        <Search className="h-4 w-4 mr-2" />
                      )}
                      {t('searchPage.search')}
                    </Button>
                    
                    {(activeSearchData || searchMutation.isError || searchQuery.length > 0) && (
                      <Button
                        variant="outline"
                        onClick={handleClearSearch}
                        disabled={searchMutation.isPending}
                        className="w-full sm:w-auto"
                      >
                        {language.startsWith('zh') ? '清空内容' : 'Clear'}
                      </Button>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground">{t.searchPage.pressToSearch}</p>
                </div>

                {/* Search Options */}
                <div className="space-y-4">
                  {/* Search Type */}
                  <div className="space-y-2" role="group" aria-labelledby="search-type-label">
                    <span id="search-type-label" className="text-sm font-medium leading-none">{t.searchPage.searchType}</span>
                    {!hasEmbeddingModel && (
                      <div className="flex items-center gap-2 text-sm text-amber-600 dark:text-amber-500">
                        <AlertCircle className="h-4 w-4" />
                        <span>{t.searchPage.vectorSearchWarning}</span>
                      </div>
                    )}
                    <RadioGroup
                      name="search-type"
                      value={searchType}
                      onValueChange={(value: 'text' | 'vector') => setSearchType(value)}
                      disabled={modelsLoading || searchMutation.isPending}
                    >
                      <div className="flex items-center space-x-2">
                        <RadioGroupItem value="text" id="text" />
                        <Label htmlFor="text" className="font-normal cursor-pointer">
                          {t.searchPage.textSearch}
                        </Label>
                      </div>
                      <div className="flex items-center space-x-2">
                        <RadioGroupItem
                          value="vector"
                          id="vector"
                          disabled={!hasEmbeddingModel || searchMutation.isPending}
                        />
                        <Label
                          htmlFor="vector"
                          className={`font-normal ${!hasEmbeddingModel ? 'text-muted-foreground cursor-not-allowed' : 'cursor-pointer'}`}
                        >
                          {t.searchPage.vectorSearch}
                        </Label>
                      </div>
                    </RadioGroup>
                  </div>

                  {/* Search Locations */}
                  <div className="space-y-2" role="group" aria-labelledby="search-in-label">
                    <span id="search-in-label" className="text-sm font-medium leading-none">{t.searchPage.searchIn}</span>
                    <div className="space-y-2">
                      <div className="flex items-center space-x-2">
                        <Checkbox
                          id="sources"
                          name="sources"
                          checked={searchSources}
                          onCheckedChange={(checked) => setSearchSources(checked as boolean)}
                          disabled={searchMutation.isPending}
                        />
                        <Label htmlFor="sources" className="font-normal cursor-pointer">
                          {t.searchPage.searchSources}
                        </Label>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Checkbox
                          id="notes"
                          name="notes"
                          checked={searchNotes}
                          onCheckedChange={(checked) => setSearchNotes(checked as boolean)}
                          disabled={searchMutation.isPending}
                        />
                        <Label htmlFor="notes" className="font-normal cursor-pointer">
                          {t.searchPage.searchNotes}
                        </Label>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Search Results */}
                {activeSearchData && (
                  <div className="mt-6 space-y-3">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-medium">
                        {t.searchPage.resultsFound?.replace('{count}', activeSearchData.total_count.toString()) || `${activeSearchData.total_count} results found`}
                      </h3>
                      <Badge variant="outline">{activeSearchData.search_type === 'text' ? t.searchPage.textSearch : t.searchPage.vectorSearch}</Badge>
                    </div>

                    {activeSearchData.results.length === 0 ? (
                      <Card>
                        <CardContent className="pt-6 text-center text-muted-foreground">
                          {t.searchPage.noResultsFor.replace('{query}', searchQuery)}
                        </CardContent>
                      </Card>
                    ) : (
                      <div className="space-y-2 max-h-[60vh] overflow-y-auto pr-2">
                        {activeSearchData.results.map((result: any, index: number) => {
                          // Parse type from parent_id (format: "source:id" or "note:id" or "source_insight:id")
                          // Handle null parent_id gracefully (orphaned records)
                          if (!result.parent_id) {
                            console.warn('Search result with null parent_id:', result)
                            return null
                          }
                          const [type, id] = result.parent_id.split(':')
                          const modalType = type === 'source_insight' ? 'insight' : type as 'source' | 'note' | 'insight'

                          return (
                          <Card key={index}>
                            <CardContent className="pt-4">
                              <div className="flex items-start justify-between gap-4">
                                <div className="flex-1">
                                  <button
                                    onClick={() => openModal(modalType, id)}
                                    className="text-primary hover:underline font-medium"
                                  >
                                    {result.title}
                                  </button>
                                  <Badge variant="secondary" className="ml-2">
                                    {result.final_score.toFixed(2)}
                                  </Badge>
                                </div>
                              </div>

                              {result.matches && result.matches.length > 0 && (
                                <Collapsible className="mt-3">
                                  <CollapsibleTrigger className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
                                    <ChevronDown className="h-4 w-4" />
                                    {t.searchPage.matches.replace('{count}', result.matches.length.toString())}
                                  </CollapsibleTrigger>
                                  <CollapsibleContent className="mt-2 space-y-1">
                                    {result.matches.map((match: any, i: number) => (
                                      <div key={i} className="text-sm pl-6 py-1 border-l-2 border-muted">
                                        {match}
                                      </div>
                                    ))}
                                  </CollapsibleContent>
                                </Collapsible>
                              )}
                            </CardContent>
                          </Card>
                        )})}
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </AppShell>
  )
}
