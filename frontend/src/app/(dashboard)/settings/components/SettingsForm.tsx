'use client'

import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'
import { useSettings, useUpdateSettings } from '@/lib/hooks/use-settings'
import { useEffect, useState } from 'react'
import { ChevronDownIcon } from 'lucide-react'
import { useTranslation } from '@/lib/hooks/use-translation'

const settingsSchema = z.object({
  default_content_processing_engine_doc: z.enum(['auto', 'docling', 'mineru', 'simple']).optional(),
  default_content_processing_engine_url: z.enum(['auto', 'firecrawl', 'jina', 'simple']).optional(),
  default_embedding_option: z.enum(['ask', 'always', 'never']).optional(),
  auto_delete_files: z.enum(['yes', 'no']).optional(),
  source_batch_limit: z.number().int().min(1).max(200).optional(),
  tavily_api_key: z.string().optional().nullable(),
  tavily_include_domains: z.string().optional().nullable(),
})

type SettingsFormData = z.infer<typeof settingsSchema>

export function SettingsForm() {
  const { t } = useTranslation()
  const { data: settings, isLoading, isFetching, error } = useSettings()
  const updateSettings = useUpdateSettings()
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    doc: false,
    url: false,
    embedding: false,
    files: false,
    webSearch: false
  })
  const [hasResetForm, setHasResetForm] = useState(false)
  
  
  const {
    control,
    handleSubmit,
    reset,
    formState: { isDirty }
  } = useForm<SettingsFormData>({
    resolver: zodResolver(settingsSchema),
    defaultValues: {
      default_content_processing_engine_doc: undefined,
      default_content_processing_engine_url: undefined,
      default_embedding_option: undefined,
      auto_delete_files: undefined,
      source_batch_limit: 50,
      tavily_api_key: '',
      tavily_include_domains: '',
    }
  })


  const toggleSection = (section: string) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }))
  }

  useEffect(() => {
    // Wait until background fetch is complete so we don't populate with stale cache missing new fields
    if (settings && settings.default_content_processing_engine_doc && !hasResetForm && !isFetching) {
      const formData = {
        default_content_processing_engine_doc: settings.default_content_processing_engine_doc as 'auto' | 'docling' | 'mineru' | 'simple',
        default_content_processing_engine_url: settings.default_content_processing_engine_url as 'auto' | 'firecrawl' | 'jina' | 'simple',
        default_embedding_option: settings.default_embedding_option as 'ask' | 'always' | 'never',
        auto_delete_files: settings.auto_delete_files as 'yes' | 'no',
        source_batch_limit: settings.source_batch_limit ?? 50,
        tavily_api_key: settings.tavily_api_key || '',
        tavily_include_domains: settings.tavily_include_domains || '',
      }
      reset(formData)
      setHasResetForm(true)
    }
  }, [hasResetForm, reset, settings, isFetching])

  const onSubmit = async (data: SettingsFormData) => {
    await updateSettings.mutateAsync(data)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{t.settings.loadFailed}</AlertTitle>
        <AlertDescription>
          {error instanceof Error ? error.message : t.common.error}
        </AlertDescription>
      </Alert>
    )
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>{t.settings.contentProcessing}</CardTitle>
          <CardDescription>
            {t.settings.contentProcessingDesc}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-3">
            <Label htmlFor="doc_engine">{t.settings.docEngine}</Label>
            <Controller
              name="default_content_processing_engine_doc"
              control={control}
              render={({ field }) => (
                  <Select
                    key={field.value}
                    name={field.name}
                    value={field.value || ''}
                    onValueChange={field.onChange}
                    disabled={field.disabled || isLoading}
                  >
                      <SelectTrigger id="doc_engine" className="w-full">
                        <SelectValue placeholder={t.settings.docEnginePlaceholder} />
                      </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="auto">{t.settings.autoRecommended}</SelectItem>
                      <SelectItem value="docling">{t.settings.docling}</SelectItem>
                      <SelectItem value="mineru">{t.settings.mineru}</SelectItem>
                      <SelectItem value="simple">{t.settings.simple}</SelectItem>
                    </SelectContent>
                  </Select>
              )}
            />
            <Collapsible open={expandedSections.doc} onOpenChange={() => toggleSection('doc')}>
              <CollapsibleTrigger className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors">
                <ChevronDownIcon className={`h-4 w-4 transition-transform ${expandedSections.doc ? 'rotate-180' : ''}`} />
                {t.settings.helpMeChoose}
              </CollapsibleTrigger>
              <CollapsibleContent className="mt-2 text-sm text-muted-foreground space-y-2">
                <p>{t.settings.docHelp}</p>
              </CollapsibleContent>
            </Collapsible>
          </div>
          
          <div className="space-y-3">
            <Label htmlFor="url_engine">{t.settings.urlEngine}</Label>
            <Controller
              name="default_content_processing_engine_url"
              control={control}
              render={({ field }) => (
                <Select
                  key={field.value}
                  name={field.name}
                  value={field.value || ''}
                  onValueChange={field.onChange}
                  disabled={field.disabled || isLoading}
                >
                  <SelectTrigger id="url_engine" className="w-full">
                    <SelectValue placeholder={t.settings.urlEnginePlaceholder} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="auto">{t.settings.autoRecommended}</SelectItem>
                    <SelectItem value="firecrawl">{t.settings.firecrawl}</SelectItem>
                    <SelectItem value="jina">{t.settings.jina}</SelectItem>
                    <SelectItem value="simple">{t.settings.simple}</SelectItem>
                  </SelectContent>
                </Select>
              )}
            />
             <Collapsible open={expandedSections.url} onOpenChange={() => toggleSection('url')}>
              <CollapsibleTrigger className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors">
                <ChevronDownIcon className={`h-4 w-4 transition-transform ${expandedSections.url ? 'rotate-180' : ''}`} />
                {t.settings.helpMeChoose}
              </CollapsibleTrigger>
              <CollapsibleContent className="mt-2 text-sm text-muted-foreground space-y-2">
                <p>{t.settings.urlHelp}</p>
              </CollapsibleContent>
            </Collapsible>
          </div>

        </CardContent>
      </Card>

       <Card>
        <CardHeader>
          <CardTitle>{t.settings.embeddingAndSearch}</CardTitle>
          <CardDescription>
            {t.settings.embeddingAndSearchDesc}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
           <div className="space-y-3">
            <Label htmlFor="embedding">{t.settings.defaultEmbeddingOption}</Label>
            <Controller
              name="default_embedding_option"
              control={control}
              render={({ field }) => (
                <Select
                  key={field.value}
                  name={field.name}
                  value={field.value || ''}
                  onValueChange={field.onChange}
                  disabled={field.disabled || isLoading}
                >
                  <SelectTrigger id="embedding" className="w-full">
                    <SelectValue placeholder={t.settings.embeddingOptionPlaceholder} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="ask">{t.settings.ask}</SelectItem>
                    <SelectItem value="always">{t.settings.always}</SelectItem>
                    <SelectItem value="never">{t.settings.never}</SelectItem>
                  </SelectContent>
                </Select>
              )}
            />
             <Collapsible open={expandedSections.embedding} onOpenChange={() => toggleSection('embedding')}>
              <CollapsibleTrigger className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors">
                <ChevronDownIcon className={`h-4 w-4 transition-transform ${expandedSections.embedding ? 'rotate-180' : ''}`} />
                {t.settings.helpMeChoose}
              </CollapsibleTrigger>
              <CollapsibleContent className="mt-2 text-sm text-muted-foreground space-y-2">
                <p>{t.settings.embeddingHelp}</p>
              </CollapsibleContent>
            </Collapsible>
          </div>
        </CardContent>
      </Card>

       <Card>
        <CardHeader>
          <CardTitle>{t.settings.fileManagement}</CardTitle>
          <CardDescription>
            {t.settings.fileManagementDesc}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
           <div className="space-y-3">
            <Label htmlFor="auto_delete">{t.settings.autoDeleteFiles}</Label>
            <Controller
              name="auto_delete_files"
              control={control}
              render={({ field }) => (
                <Select
                  key={field.value}
                  name={field.name}
                  value={field.value || ''}
                  onValueChange={field.onChange}
                  disabled={field.disabled || isLoading}
                >
                  <SelectTrigger id="auto_delete" className="w-full">
                    <SelectValue placeholder={t.settings.autoDeletePlaceholder} />
                  </SelectTrigger>
                   <SelectContent>
                    <SelectItem value="yes">{t.common.yes}</SelectItem>
                    <SelectItem value="no">{t.common.no}</SelectItem>
                  </SelectContent>
                </Select>
              )}
            />
             <Collapsible open={expandedSections.files} onOpenChange={() => toggleSection('files')}>
              <CollapsibleTrigger className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors">
                <ChevronDownIcon className={`h-4 w-4 transition-transform ${expandedSections.files ? 'rotate-180' : ''}`} />
                {t.settings.helpMeChoose}
              </CollapsibleTrigger>
              <CollapsibleContent className="mt-2 text-sm text-muted-foreground space-y-2">
                <p>{t.settings.filesHelp}</p>
              </CollapsibleContent>
            </Collapsible>
          </div>

          <div className="space-y-3">
            <Label htmlFor="source_batch_limit">{t.settings.sourceBatchLimit}</Label>
            <Controller
              name="source_batch_limit"
              control={control}
              render={({ field }) => (
                <Input
                  id="source_batch_limit"
                  type="number"
                  min={1}
                  max={200}
                  value={field.value ?? 50}
                  onChange={(event) => field.onChange(event.target.value === '' ? undefined : Number(event.target.value))}
                  disabled={field.disabled || isLoading}
                />
              )}
            />
            <p className="text-sm text-muted-foreground">
              {t.settings.sourceBatchLimitHelp}
            </p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t.settings.webSearch}</CardTitle>
          <CardDescription>
            {t.settings.webSearchDesc}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
           <div className="space-y-3">
            <Label htmlFor="tavily_api_key">{t.settings.tavilyApiKey}</Label>
            <Controller
              name="tavily_api_key"
              control={control}
              render={({ field }) => (
                <Input
                  id="tavily_api_key"
                  type="password"
                  placeholder={t.settings.tavilyApiKeyPlaceholder}
                  value={field.value || ''}
                  onChange={field.onChange}
                  disabled={field.disabled || isLoading}
                />
              )}
            />
          </div>
          
          <div className="space-y-3">
            <Label htmlFor="tavily_include_domains">{t.settings.tavilyIncludeDomains}</Label>
            <Controller
              name="tavily_include_domains"
              control={control}
              render={({ field }) => (
                <Input
                  id="tavily_include_domains"
                  type="text"
                  placeholder={t.settings.tavilyIncludeDomainsPlaceholder}
                  value={field.value || ''}
                  onChange={field.onChange}
                  disabled={field.disabled || isLoading}
                />
              )}
            />
            
             <Collapsible open={expandedSections.webSearch} onOpenChange={() => toggleSection('webSearch')}>
              <CollapsibleTrigger className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors">
                <ChevronDownIcon className={`h-4 w-4 transition-transform ${expandedSections.webSearch ? 'rotate-180' : ''}`} />
                {t.settings.helpMeChoose}
              </CollapsibleTrigger>
              <CollapsibleContent className="mt-2 text-sm text-muted-foreground space-y-2">
                <p>{t.settings.tavilyHelp}</p>
              </CollapsibleContent>
            </Collapsible>
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end">
         <Button 
          type="submit" 
          disabled={!isDirty || updateSettings.isPending}
        >
          {updateSettings.isPending ? t.common.saving : t.navigation.settings}
        </Button>
      </div>
    </form>
  )
}
