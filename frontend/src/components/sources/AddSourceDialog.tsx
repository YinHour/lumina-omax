'use client'

import { useState, useRef, useEffect, useMemo } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { LoaderIcon, CheckCircleIcon, XCircleIcon } from 'lucide-react'
import { toast } from 'sonner'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { WizardContainer, WizardStep } from '@/components/ui/wizard-container'
import { SourceTypeStep, parseAndValidateUrls } from './steps/SourceTypeStep'
import { NotebooksStep } from './steps/NotebooksStep'
import { ProcessingStep } from './steps/ProcessingStep'
import { useNotebooks } from '@/lib/hooks/use-notebooks'
import { useTransformations } from '@/lib/hooks/use-transformations'
import { useCreateSource } from '@/lib/hooks/use-sources'
import { useSettings } from '@/lib/hooks/use-settings'
import { CreateSourceRequest } from '@/lib/types/api'
import { useTranslation } from '@/lib/hooks/use-translation'
import { sourcesApi } from '@/lib/api/sources'

const MAX_BATCH_SIZE = 50

const createSourceSchema = z.object({
  type: z.enum(['link', 'upload', 'text']),
  title: z.string().optional(),
  url: z.string().optional(),
  content: z.string().optional(),
  file: z.any().optional(),
  notebooks: z.array(z.string()).optional(),
  transformations: z.array(z.string()).optional(),
  embed: z.boolean(),
  async_processing: z.boolean(),
}).refine((data) => {
  if (data.type === 'link') {
    return !!data.url && data.url.trim() !== ''
  }
  if (data.type === 'text') {
    return !!data.content && data.content.trim() !== ''
  }
  if (data.type === 'upload') {
    if (data.file instanceof FileList) {
      return data.file.length > 0
    }
    return !!data.file
  }
  return true
}, {
  message: 'Please provide the required content for the selected source type',
  path: ['type'],
}).refine((data) => {
  // Make title mandatory for text sources
  if (data.type === 'text') {
    return !!data.title && data.title.trim() !== ''
  }
  return true
}, {
  message: 'Title is required for text sources',
  path: ['title'],
})

type CreateSourceFormData = z.infer<typeof createSourceSchema>

interface AddSourceDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  defaultNotebookId?: string
}

interface ProcessingState {
  message: string
  progress?: number
}

interface BatchProgress {
  total: number
  completed: number
  failed: number
  currentItem?: string
}

export function AddSourceDialog({ 
  open, 
  onOpenChange, 
  defaultNotebookId 
}: AddSourceDialogProps) {
  const { t, language } = useTranslation()

  const WIZARD_STEPS: readonly WizardStep[] = [
    { number: 1, title: t.sources.addSource, description: t.sources.processDescription },
    { number: 2, title: t.navigation.notebooks, description: t.notebooks.searchPlaceholder },
    { number: 3, title: t.navigation.process, description: t.sources.processDescription },
  ]

  // Simplified state management
  const [currentStep, setCurrentStep] = useState(1)
  const [processing, setProcessing] = useState(false)
  const [processingStatus, setProcessingStatus] = useState<ProcessingState | null>(null)
  const [selectedNotebooks, setSelectedNotebooks] = useState<string[]>(
    defaultNotebookId ? [defaultNotebookId] : []
  )
  const [selectedTransformations, setSelectedTransformations] = useState<string[]>([])

  // Duplicate detection state
  const [showDuplicateWarning, setShowDuplicateWarning] = useState(false)
  const [duplicateFiles, setDuplicateFiles] = useState<string[]>([])
  const [pendingSubmitData, setPendingSubmitData] = useState<CreateSourceFormData | null>(null)
  
  // Batch-specific state
  const [urlValidationErrors, setUrlValidationErrors] = useState<{ url: string; line: number }[]>([])
  const [batchProgress, setBatchProgress] = useState<BatchProgress | null>(null)

  // Cleanup timeouts to prevent memory leaks
  const timeoutRef = useRef<NodeJS.Timeout | null>(null)
  const isConfirmingRef = useRef(false)

  // API hooks
  const createSource = useCreateSource()
  const { data: notebooks = [], isLoading: notebooksLoading } = useNotebooks()
  const { data: transformations = [], isLoading: transformationsLoading } = useTransformations()
  const { data: settings } = useSettings()

  // Form setup
  const {
    register,
    handleSubmit,
    control,
    watch,
    setValue,
    formState: { errors },
    reset,
  } = useForm<CreateSourceFormData>({
    resolver: zodResolver(createSourceSchema),
    defaultValues: {
      notebooks: defaultNotebookId ? [defaultNotebookId] : [],
      embed: settings?.default_embedding_option === 'always' || settings?.default_embedding_option === 'ask',
      async_processing: true,
      transformations: [],
    },
  })

  // Initialize form values when settings and transformations are loaded
  useEffect(() => {
    if (settings && transformations.length > 0) {
      const defaultTransformations = transformations
        .filter(t => t.apply_default)
        .map(t => t.id)

      setSelectedTransformations(defaultTransformations)

      // Reset form with proper embed value based on settings
      const embedValue = settings.default_embedding_option === 'always' ||
                         (settings.default_embedding_option === 'ask')

      reset({
        notebooks: defaultNotebookId ? [defaultNotebookId] : [],
        embed: embedValue,
        async_processing: true,
        transformations: [],
      })
    }
  }, [settings, transformations, defaultNotebookId, reset])

  // Cleanup effect
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
    }
  }, [])

  // Force pointer-events cleanup when processing state changes
  useEffect(() => {
    if (processing) {
      document.body.style.pointerEvents = 'auto'
      document.body.style.removeProperty('pointer-events')
    }
  }, [processing])
  
  // Also force pointer-events cleanup when duplicate warning closes
  useEffect(() => {
    if (!showDuplicateWarning) {
      document.body.style.pointerEvents = 'auto'
      document.body.style.removeProperty('pointer-events')
    }
  }, [showDuplicateWarning])

  const selectedType = watch('type')
  const watchedUrl = watch('url')
  const watchedContent = watch('content')
  const watchedFile = watch('file')
  const watchedTitle = watch('title')

  // Batch mode detection
  const { isBatchMode, itemCount, parsedUrls, parsedFiles } = useMemo(() => {
    let urlCount = 0
    let fileCount = 0
    let parsedUrls: string[] = []
    let parsedFiles: File[] = []

    if (selectedType === 'link' && watchedUrl) {
      const { valid } = parseAndValidateUrls(watchedUrl)
      parsedUrls = valid
      urlCount = valid.length
    }

    if (selectedType === 'upload' && watchedFile) {
      const fileList = watchedFile as FileList
      if (fileList?.length) {
        parsedFiles = Array.from(fileList)
        fileCount = parsedFiles.length
      }
    }

    const isBatchMode = urlCount > 1 || fileCount > 1
    const itemCount = selectedType === 'link' ? urlCount : fileCount

    return { isBatchMode, itemCount, parsedUrls, parsedFiles }
  }, [selectedType, watchedUrl, watchedFile])

  // Check for batch size limit
  const isOverLimit = itemCount > MAX_BATCH_SIZE

  // Step validation - now reactive with watched values
  const isStepValid = (step: number): boolean => {
    switch (step) {
      case 1:
        if (!selectedType) return false
        // Check batch size limit
        if (isOverLimit) return false
        // Check for URL validation errors
        if (urlValidationErrors.length > 0) return false

        if (selectedType === 'link') {
          // In batch mode, check that we have at least one valid URL
          if (isBatchMode) {
            return parsedUrls.length > 0
          }
          return !!watchedUrl && watchedUrl.trim() !== ''
        }
        if (selectedType === 'text') {
          return !!watchedContent && watchedContent.trim() !== '' &&
                 !!watchedTitle && watchedTitle.trim() !== ''
        }
        if (selectedType === 'upload') {
          if (watchedFile instanceof FileList) {
            return watchedFile.length > 0 && watchedFile.length <= MAX_BATCH_SIZE
          }
          return !!watchedFile
        }
        return true
      case 2:
      case 3:
        return true
      default:
        return false
    }
  }

  // Navigation
  const handleNextStep = (e?: React.MouseEvent) => {
    e?.preventDefault()
    e?.stopPropagation()

    // Validate URLs when leaving step 1 in link mode
    if (currentStep === 1 && selectedType === 'link' && watchedUrl) {
      const { invalid } = parseAndValidateUrls(watchedUrl)
      if (invalid.length > 0) {
        setUrlValidationErrors(invalid)
        return
      }
      setUrlValidationErrors([])
    }

    if (currentStep < 3 && isStepValid(currentStep)) {
      setCurrentStep(currentStep + 1)
    }
  }

  // Clear URL validation errors when user edits
  const handleClearUrlErrors = () => {
    setUrlValidationErrors([])
  }

  const handlePrevStep = (e?: React.MouseEvent) => {
    e?.preventDefault()
    e?.stopPropagation()
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1)
    }
  }

  const handleStepClick = (step: number) => {
    if (step <= currentStep || (step === currentStep + 1 && isStepValid(currentStep))) {
      setCurrentStep(step)
    }
  }

  // Selection handlers
  const handleNotebookToggle = (notebookId: string) => {
    const updated = selectedNotebooks.includes(notebookId)
      ? selectedNotebooks.filter(id => id !== notebookId)
      : [...selectedNotebooks, notebookId]
    setSelectedNotebooks(updated)
  }

  const handleTransformationToggle = (transformationId: string) => {
    const updated = selectedTransformations.includes(transformationId)
      ? selectedTransformations.filter(id => id !== transformationId)
      : [...selectedTransformations, transformationId]
    setSelectedTransformations(updated)
  }

  // Single source submission
  const submitSingleSource = async (data: CreateSourceFormData): Promise<void> => {
    const createRequest: CreateSourceRequest = {
      type: data.type,
      notebooks: selectedNotebooks,
      url: data.type === 'link' ? data.url : undefined,
      content: data.type === 'text' ? data.content : undefined,
      title: data.title,
      transformations: selectedTransformations,
      embed: data.embed,
      delete_source: false,
      async_processing: true,
    }

    if (data.type === 'upload') {
      let file: File | undefined;
      
      if (data.file) {
        file = data.file instanceof FileList ? data.file[0] : 
               (Array.isArray(data.file) ? data.file[0] : data.file);
      }
      
      if (file) {
        const requestWithFile = createRequest as CreateSourceRequest & { file?: File }
        requestWithFile.file = file
      }
    }

    await createSource.mutateAsync(createRequest)
  }

  // Batch submission
  const submitBatch = async (data: CreateSourceFormData, filterDuplicates = false): Promise<{ success: number; failed: number }> => {
    const results = { success: 0, failed: 0 }
    const items: { type: 'url' | 'file'; value: string | File }[] = []

    // Collect items to process
    if (data.type === 'link' && parsedUrls.length > 0) {
      parsedUrls.forEach((url: string) => items.push({ type: 'url', value: url }))
    } else if (data.type === 'upload' && parsedFiles.length > 0) {
      parsedFiles.forEach((file: File) => {
        if (filterDuplicates && duplicateFiles.includes(file.name)) {
          return // Skip duplicates
        }
        items.push({ type: 'file', value: file })
      })
    }

    if (items.length === 0) return results

    setBatchProgress({
      total: items.length,
      completed: 0,
      failed: 0,
    })

    // Process each item sequentially
    for (let i = 0; i < items.length; i++) {
      const item = items[i]
      const itemLabel = item.type === 'url'
        ? (item.value as string).substring(0, 50) + '...'
        : (item.value as File).name

      setBatchProgress(prev => prev ? {
        ...prev,
        currentItem: itemLabel,
      } : null)

      try {
        const createRequest: CreateSourceRequest = {
          type: item.type === 'url' ? 'link' : 'upload',
          notebooks: selectedNotebooks,
          url: item.type === 'url' ? item.value as string : undefined,
          transformations: selectedTransformations,
          embed: data.embed,
          delete_source: false,
          async_processing: true,
        }

        if (item.type === 'file') {
          const requestWithFile = createRequest as CreateSourceRequest & { file?: File }
          requestWithFile.file = item.value as File
        }

        await createSource.mutateAsync(createRequest)
        results.success++
      } catch (error) {
        console.error(`Error creating source for ${itemLabel}:`, error)
        results.failed++
      }

      setBatchProgress(prev => prev ? {
        ...prev,
        completed: results.success,
        failed: results.failed,
      } : null)
    }

    return results
  }

  // Form submission
  const onSubmit = async (data: CreateSourceFormData, skipDuplicateCheck = false, filterDuplicates = false) => {
    // If the event object is accidentally passed as the second argument, ignore it
    if (typeof skipDuplicateCheck !== 'boolean') {
      skipDuplicateCheck = false;
    }
    if (typeof filterDuplicates !== 'boolean') {
      filterDuplicates = false;
    }
    
    console.log('onSubmit triggered', { data, skipDuplicateCheck, filterDuplicates, processing })
    if (skipDuplicateCheck) {
      toast.info('onSubmit 被调用，跳过重复检查')
    }
    
    // Check if we are already processing and NOT skipping duplicate check
    // If we are skipping duplicate check, we might already be in processing state
    // because handleConfirmDuplicate sets it to true before calling onSubmit
    if (processing && !skipDuplicateCheck) {
      console.log('Already processing, ignoring submission')
      return
    }

    // Always force processing state to true to show loading UI
    console.log('Setting processing to true in onSubmit')
    setProcessing(true)
    
    // If we are skipping duplicate check, we don't need to wait for state to settle
    // because we already did that in handleConfirmDuplicate
    if (!skipDuplicateCheck) {
      // Wait a tiny bit for state to settle before starting heavy work
      // This is crucial for React to render the processing state before we block the thread
      // We use a small timeout to allow the UI to update
      await new Promise(resolve => setTimeout(resolve, 0))
      console.log('Finished waiting for state to settle')
    }
    
    // Duplicate check for file uploads
    if (data.type === 'upload' && !skipDuplicateCheck) {
      const duplicates: string[] = []
      
      const checkDuplicate = async (filename: string) => {
        const lastDotIndex = filename.lastIndexOf('.')
        const stem = lastDotIndex !== -1 ? filename.substring(0, lastDotIndex) : filename
        const suffix = lastDotIndex !== -1 ? filename.substring(lastDotIndex) : ''

        try {
          const results = await sourcesApi.list({ title_contains: stem, limit: 50 })
          if (!results || results.length === 0) return false

          const escapeRegExp = (string: string) => string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
          const regex = new RegExp(`^${escapeRegExp(stem)}( \\(\\d+\\))?${escapeRegExp(suffix)}$`)

          return results.some(source => source.title && regex.test(source.title))
        } catch (e) {
          console.error('Failed to check duplicate for', filename, e)
          return false
        }
      }

      if (isBatchMode && parsedFiles.length > 0) {
        // Check each file against the backend
        for (const file of parsedFiles) {
          if (await checkDuplicate(file.name)) {
            duplicates.push(file.name)
          }
        }
      } else if (data.file) {
        const file = data.file instanceof FileList ? data.file[0] : data.file
        if (file && await checkDuplicate(file.name)) {
          duplicates.push(file.name)
        }
      }

      if (duplicates.length > 0) {
        console.log('Duplicates found, showing warning. Data:', data)
        setDuplicateFiles(duplicates)
        
        // Save the raw data directly to avoid any React Hook Form proxy issues
        // But we need to make sure we don't lose the file reference
        const dataToSave = { ...data }
        if (data.file) {
          dataToSave.file = data.file
        }
        
        console.log('Setting pendingSubmitData:', dataToSave)
        setPendingSubmitData(dataToSave)
        
        // We're stopping submission, so reset processing state
        setProcessing(false)
        
        // Use setTimeout to ensure state is updated before showing dialog
        setTimeout(() => {
          setShowDuplicateWarning(true)
        }, 10)
        return // Stop submission, wait for user confirmation
      }
    }

    try {
      console.log('Starting processing, setting processing to true')
      // Ensure processing is true
      setProcessing(true)
      
      // Make sure the warning dialog is closed
      setShowDuplicateWarning(false)
      
      // Wait a tiny bit for state to settle before starting heavy work
      // This is crucial for React to render the processing state before we block the thread
      await new Promise(resolve => setTimeout(resolve, 0))
      
      console.log('Starting actual submission...', { isBatchMode, data })
      
      if (isBatchMode) {
        // Batch submission
        setProcessingStatus({ message: t.sources.processingFiles })
        const results = await submitBatch(data, filterDuplicates)

        if (results.success === 0 && results.failed === 0) {
          toast.info(language.startsWith('zh') ? '没有上传新文件，全部为重复项' : 'No new files uploaded, all were duplicates')
          handleClose()
          return
        }

        // Show summary toast
        if (results.failed === 0) {
          toast.success(t.sources.batchSuccess.replace('{count}', results.success.toString()))
        } else if (results.success === 0) {
          toast.error(t.sources.batchFailed.replace('{count}', results.failed.toString()))
        } else {
          toast.warning(t.sources.batchPartial.replace('{success}', results.success.toString()).replace('{failed}', results.failed.toString()))
        }

        handleClose()
      } else {
        if (filterDuplicates) {
          toast.info(language.startsWith('zh') ? '该文件为重复项，已跳过' : 'File was a duplicate and skipped')
          handleClose()
          return
        }
        
        // Single source submission
        setProcessingStatus({ message: t.sources.submittingSource })
        await submitSingleSource(data)
        handleClose()
      }
    } catch (error) {
      console.error('Error creating source:', error)
      toast.error(t.common.errorSubmitting + ': ' + (error instanceof Error ? error.message : String(error)))
      setProcessingStatus({
        message: t.common.error,
      })
      timeoutRef.current = setTimeout(() => {
        setProcessing(false)
        setProcessingStatus(null)
        setBatchProgress(null)
      }, 3000)
    }
  }

  // Dialog management
  const handleClose = () => {
    console.log('handleClose triggered')
    // Clear any pending timeouts
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = null
    }
    isConfirmingRef.current = false

    reset()
    setCurrentStep(1)
    setProcessing(false)
    setProcessingStatus(null)
    setSelectedNotebooks(defaultNotebookId ? [defaultNotebookId] : [])
    setUrlValidationErrors([])
    setBatchProgress(null)
    setShowDuplicateWarning(false)
    setPendingSubmitData(null)
    
    // Clear files after a delay to let the dialog animate out
    setTimeout(() => {
      setDuplicateFiles([])
    }, 300)
    
    // Reset to default transformations
    if (transformations.length > 0) {
      const defaultTransformations = transformations
        .filter(t => t.apply_default)
        .map(t => t.id)
      setSelectedTransformations(defaultTransformations)
    } else {
      setSelectedTransformations([])
    }

    onOpenChange(false)
  }

  const handleConfirmDuplicate = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    
    console.log('handleConfirmDuplicate triggered', { pendingSubmitData })

    if (pendingSubmitData) {
      isConfirmingRef.current = true
      
      // We must extract the data immediately before any state changes
      // React Hook Form data can be lost if the component re-renders
      const dataToSubmit = { ...pendingSubmitData }
      if (pendingSubmitData.file) {
        dataToSubmit.file = pendingSubmitData.file
      }
      
      console.log('Calling onSubmit with dataToSubmit:', dataToSubmit)
      toast.info('确认继续上传，准备提交...')
      
      // Now close the warning dialog immediately to avoid any interaction issues
      setShowDuplicateWarning(false)
      
      // Force processing true immediately so the UI switches to loading state
      setProcessing(true)
      
      // Call onSubmit directly without setTimeout so it runs in the same event loop
      // This ensures the form data is still valid
      try {
        // We MUST pass true for skipDuplicateCheck here
        // Call it immediately without setTimeout to avoid losing form context
        onSubmit(dataToSubmit, true).catch(err => {
          console.error('Error in onSubmit called from handleConfirmDuplicate:', err)
          setProcessing(false) // Reset on error
        }).finally(() => {
          isConfirmingRef.current = false
          // Clear pending data only after submission is complete or failed
          setPendingSubmitData(null)
        })
      } catch (err) {
        console.error('Synchronous error in onSubmit:', err)
        isConfirmingRef.current = false
        setPendingSubmitData(null)
        setProcessing(false) // Reset on error
      }
      
    } else {
      console.log('No pendingSubmitData found, just closing dialog')
      setShowDuplicateWarning(false)
    }
  }

  const handleCancelDuplicate = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    console.log('handleCancelDuplicate triggered')
    isConfirmingRef.current = false
    setShowDuplicateWarning(false)
    setPendingSubmitData(null)
    
    // Clear files after a delay to let the dialog animate out
    setTimeout(() => {
      setDuplicateFiles([])
    }, 300)
  }

  const handleUploadNonDuplicates = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    
    console.log('handleUploadNonDuplicates triggered', { pendingSubmitData })

    if (pendingSubmitData) {
      isConfirmingRef.current = true
      
      const dataToSubmit = { ...pendingSubmitData }
      if (pendingSubmitData.file) {
        dataToSubmit.file = pendingSubmitData.file
      }
      
      console.log('Calling onSubmit with dataToSubmit (filtering duplicates):', dataToSubmit)
      toast.info(language.startsWith('zh') ? '确认继续上传，过滤重复项...' : 'Continuing upload, filtering duplicates...')
      
      setShowDuplicateWarning(false)
      setProcessing(true)
      
      try {
        // Pass true for skipDuplicateCheck and true for filterDuplicates
        onSubmit(dataToSubmit, true, true).catch(err => {
          console.error('Error in onSubmit called from handleUploadNonDuplicates:', err)
          setProcessing(false) // Reset on error
        }).finally(() => {
          isConfirmingRef.current = false
          setPendingSubmitData(null)
        })
      } catch (err) {
        console.error('Synchronous error in onSubmit:', err)
        isConfirmingRef.current = false
        setPendingSubmitData(null)
        setProcessing(false) // Reset on error
      }
      
    } else {
      setShowDuplicateWarning(false)
    }
  }

  // Processing view
  if (processing) {
    const progressPercent = batchProgress
      ? Math.round(((batchProgress.completed + batchProgress.failed) / batchProgress.total) * 100)
      : undefined

    return (
      <Dialog open={open} onOpenChange={handleClose}>
        <DialogContent className="sm:max-w-[500px]" showCloseButton={true}>
          <DialogHeader>
            <DialogTitle>
              {batchProgress ? t.sources.processingFiles : t.sources.statusProcessing}
            </DialogTitle>
            <DialogDescription>
              {batchProgress
                ? t.sources.processingBatchSources.replace('{count}', batchProgress.total.toString())
                : t.sources.processingSource
              }
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="flex items-center gap-3">
              <LoaderIcon className="h-5 w-5 animate-spin text-primary" />
              <span className="text-sm text-muted-foreground">
                {processingStatus?.message || t.common.processing}
              </span>
            </div>

            {/* Batch progress */}
            {batchProgress && (
              <>
                <div className="w-full bg-muted rounded-full h-2">
                  <div
                    className="bg-primary h-2 rounded-full transition-all duration-300"
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>

                <div className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-4">
                    <span className="flex items-center gap-1.5 text-green-600">
                      <CheckCircleIcon className="h-4 w-4" />
                      {batchProgress.completed} {t.common.completed}
                    </span>
                    {batchProgress.failed > 0 && (
                      <span className="flex items-center gap-1.5 text-destructive">
                        <XCircleIcon className="h-4 w-4" />
                        {batchProgress.failed} {t.common.failed}
                      </span>
                    )}
                  </div>
                   <span className="text-muted-foreground">
                    {batchProgress.completed + batchProgress.failed} / {batchProgress.total}
                  </span>
                </div>

                {batchProgress.currentItem && (
                  <p className="text-xs text-muted-foreground truncate">
                    {t.common.current}: {batchProgress.currentItem}
                  </p>
                )}
              </>
            )}

            {/* Single source progress */}
            {!batchProgress && processingStatus?.progress && (
              <div className="w-full bg-muted rounded-full h-2">
                <div
                  className="bg-primary h-2 rounded-full transition-all duration-300"
                  style={{ width: `${processingStatus.progress}%` }}
                />
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    )
  }

  const currentStepValid = isStepValid(currentStep)

  return (
    <>
      <Dialog open={open} onOpenChange={handleClose}>
        <DialogContent 
          className="sm:max-w-[700px] p-0"
          onInteractOutside={(e) => {
            if (showDuplicateWarning) {
              e.preventDefault()
            }
          }}
          onEscapeKeyDown={(e) => {
            if (showDuplicateWarning) {
              e.preventDefault()
            }
          }}
        >
          <DialogHeader className="px-6 pt-6 pb-0">
            <DialogTitle>{t.sources.addNew}</DialogTitle>
            <DialogDescription>
              {t.sources.processDescription}
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleSubmit((data) => {
            console.log('Form submitted via handleSubmit', data)
            onSubmit(data)
          })} className="min-w-0" id="add-source-form">
          <WizardContainer
            currentStep={currentStep}
            steps={WIZARD_STEPS}
            onStepClick={handleStepClick}
            className="border-0"
          >
            {currentStep === 1 && (
              <SourceTypeStep
                // @ts-expect-error - Type inference issue with zod schema
                control={control}
                register={register}
                setValue={setValue}
                // @ts-expect-error - Type inference issue with zod schema
                errors={errors}
                urlValidationErrors={urlValidationErrors}
                onClearUrlErrors={handleClearUrlErrors}
              />
            )}
            
            {currentStep === 2 && (
              <NotebooksStep
                notebooks={notebooks}
                selectedNotebooks={selectedNotebooks}
                onToggleNotebook={handleNotebookToggle}
                loading={notebooksLoading}
              />
            )}
            
            {currentStep === 3 && (
              <ProcessingStep
                // @ts-expect-error - Type inference issue with zod schema
                control={control}
                transformations={transformations}
                selectedTransformations={selectedTransformations}
                onToggleTransformation={handleTransformationToggle}
                loading={transformationsLoading}
                settings={settings}
              />
            )}
          </WizardContainer>

          {/* Navigation */}
          <div className="flex justify-between items-center px-6 py-4 border-t border-border bg-muted">
            <Button 
              type="button" 
              variant="outline" 
              onClick={handleClose}
            >
              {t.common.cancel}
            </Button>

            <div className="flex gap-2">
              {currentStep > 1 && (
                <Button
                  type="button"
                  variant="outline"
                  onClick={handlePrevStep}
                >
                  {t.common.back}
                </Button>
              )}

              {/* Show Next button on steps 1 and 2, styled as outline/secondary */}
              {currentStep < 3 && (
                <Button
                  type="button"
                  variant="outline"
                  onClick={(e) => handleNextStep(e)}
                  disabled={!currentStepValid}
                >
                  {t.common.next}
                </Button>
              )}

              {/* Show Done button on all steps, styled as primary */}
              <Button
                type="submit"
                disabled={!currentStepValid || createSource.isPending}
                className="min-w-[120px]"
              >
                {createSource.isPending ? t.common.adding : t.common.done}
              </Button>
            </div>
          </div>
        </form>
      </DialogContent>
    </Dialog>

    <AlertDialog open={showDuplicateWarning} onOpenChange={(open) => {
      console.log('AlertDialog onOpenChange', open)
      
      // If the dialog is being opened, just set the state
      if (open) {
        setShowDuplicateWarning(true)
        return
      }
      
      // Dialog is being closed
      
      // If we are currently confirming (user clicked "Yes"), do nothing here
      // The handleConfirmDuplicate function will manage the state
      if (isConfirmingRef.current) {
        console.log('AlertDialog closed while confirming, ignoring')
        return
      }
      
      // If we have pending data but aren't confirming, it's a cancel
      // (e.g. user clicked outside the dialog or pressed Escape)
      if (pendingSubmitData) {
        console.log('AlertDialog closed by clicking outside, canceling')
        // We only cancel if processing hasn't started yet
        if (!processing) {
          setShowDuplicateWarning(false)
          // We must clear pendingSubmitData here if it's a true cancel
          // otherwise it might interfere with future submissions
          setPendingSubmitData(null) 
          
          setTimeout(() => {
            setDuplicateFiles([])
          }, 300)
        }
        return
      }
      
      // Normal close (no pending data)
      setShowDuplicateWarning(false)
      
      setTimeout(() => {
        setDuplicateFiles([])
      }, 300)
    }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>
            {language.startsWith('zh') ? '发现同名文件' : 'Duplicate Files Detected'}
          </AlertDialogTitle>
          <div className="text-muted-foreground text-sm">
            {language.startsWith('zh') 
              ? '系统检测到以下文件可能已经上传过：' 
              : 'The system detected that the following files may have already been uploaded:'}
            <ul className="list-disc pl-5 mt-2 mb-2 max-h-[150px] overflow-y-auto">
              {duplicateFiles.map((file, i) => (
                <li key={i} className="text-sm font-medium text-foreground">{file}</li>
              ))}
            </ul>
            {language.startsWith('zh') ? '是否继续上传？' : 'Do you want to continue uploading?'}
          </div>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <Button type="button" variant="outline" onClick={(e) => {
            console.log('Cancel button clicked')
            handleCancelDuplicate(e)
          }}>
            {language.startsWith('zh') ? '否 (取消)' : 'No (Cancel)'}
          </Button>
          <Button type="button" variant="secondary" onClick={(e) => {
            console.log('Upload non-duplicates button clicked')
            handleUploadNonDuplicates(e)
          }}>
            {language.startsWith('zh') ? '仅上传非重复文件' : 'Only Non-duplicates'}
          </Button>
          <Button type="button" onClick={(e) => {
            console.log('Confirm button clicked')
            handleConfirmDuplicate(e)
          }}>
            {language.startsWith('zh') ? '是 (全部上传)' : 'Yes (Upload All)'}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </>
  )
}
