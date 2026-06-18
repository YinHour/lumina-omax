'use client'

import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useNotebooks, useAggregateNotebooks } from '@/lib/hooks/use-notebooks'
import { useTranslation } from '@/lib/hooks/use-translation'
import { NotebookResponse } from '@/lib/types/api'

const getAggregateNotebookSchema = (nameRequiredMessage: string) => z.object({
  name: z.string().min(1, nameRequiredMessage),
  description: z.string().optional(),
  password: z.string().optional(),
  creator_name: z.string().optional(),
})

type AggregateNotebookFormData = z.infer<ReturnType<typeof getAggregateNotebookSchema>>

interface AggregateNotebookDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function AggregateNotebookDialog({ open, onOpenChange }: AggregateNotebookDialogProps) {
  const { t } = useTranslation()
  const { data: notebooks } = useNotebooks(false)
  const aggregateNotebooks = useAggregateNotebooks()
  const aggregateNotebookSchema = getAggregateNotebookSchema(t.common.nameRequired)
  
  const [selectedNotebookIds, setSelectedNotebookIds] = useState<Set<string>>(new Set())
  const [step, setStep] = useState<'selection' | 'password'>('selection')
  
  // For password verification step
  const [notebooksRequiringPassword, setNotebooksRequiringPassword] = useState<NotebookResponse[]>([])
  const [currentPasswordIndex, setCurrentPasswordIndex] = useState(0)
  const [currentPasswordInput, setCurrentPasswordInput] = useState('')
  const [passwordsDict, setPasswordsDict] = useState<Record<string, string>>({})
  const [passwordError, setPasswordError] = useState('')

  const {
    register,
    handleSubmit,
    formState: { errors, isValid },
    reset,
    getValues,
  } = useForm<AggregateNotebookFormData>({
    resolver: zodResolver(aggregateNotebookSchema),
    mode: 'onChange',
    defaultValues: {
      name: '',
    },
  })

  const closeDialog = () => {
    onOpenChange(false)
    // Reset state after closing animation
    setTimeout(() => {
      reset()
      setSelectedNotebookIds(new Set())
      setStep('selection')
      setNotebooksRequiringPassword([])
      setCurrentPasswordIndex(0)
      setCurrentPasswordInput('')
      setPasswordsDict({})
      setPasswordError('')
    }, 300)
  }

  useEffect(() => {
    if (!open) {
      reset()
      setSelectedNotebookIds(new Set())
      setStep('selection')
      setNotebooksRequiringPassword([])
      setCurrentPasswordIndex(0)
      setCurrentPasswordInput('')
      setPasswordsDict({})
      setPasswordError('')
    }
  }, [open, reset])

  const toggleNotebook = (id: string) => {
    const newSet = new Set(selectedNotebookIds)
    if (newSet.has(id)) {
      newSet.delete(id)
    } else {
      newSet.add(id)
    }
    setSelectedNotebookIds(newSet)
  }

  const handleSelectionSubmit = (data: AggregateNotebookFormData) => {
    if (selectedNotebookIds.size === 0) {
      // User must select at least one notebook
      return
    }

    // Find all selected notebooks that require a password
    const selectedNotebooks = notebooks?.filter(nb => selectedNotebookIds.has(nb.id)) || []
    const reqPasswords = selectedNotebooks.filter(nb => nb.password && nb.password.length > 0)

    if (reqPasswords.length > 0) {
      setNotebooksRequiringPassword(reqPasswords)
      setStep('password')
      setCurrentPasswordIndex(0)
      setCurrentPasswordInput('')
      setPasswordError('')
      setPasswordsDict({})
    } else {
      // No passwords required, submit directly
      submitAggregation(data, {})
    }
  }

  const handlePasswordSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    
    const currentNotebook = notebooksRequiringPassword[currentPasswordIndex]
    
    // Verify password locally
    if (currentPasswordInput !== currentNotebook.password) {
      // Incorrect password
      alert(`笔记本 "${currentNotebook.name}" 的密码错误，合并程序已退出。`)
      closeDialog()
      return
    }

    // Password correct, save to dict
    const newPasswordsDict = { ...passwordsDict, [currentNotebook.id]: currentPasswordInput }
    setPasswordsDict(newPasswordsDict)

    // Move to next or submit
    if (currentPasswordIndex + 1 < notebooksRequiringPassword.length) {
      setCurrentPasswordIndex(currentPasswordIndex + 1)
      setCurrentPasswordInput('')
      setPasswordError('')
    } else {
      // All passwords verified
      submitAggregation(getValues(), newPasswordsDict)
    }
  }

  const submitAggregation = async (formData: AggregateNotebookFormData, notebookPasswords: Record<string, string>) => {
    await aggregateNotebooks.mutateAsync({
      name: formData.name,
      description: formData.description,
      password: formData.password,
      creator_name: formData.creator_name,
      notebook_ids: Array.from(selectedNotebookIds),
      notebook_passwords: notebookPasswords
    })
    closeDialog()
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>聚合笔记本</DialogTitle>
          <DialogDescription>
            {step === 'selection' 
              ? '选择多个笔记本，它们的内容将被链接到一个新的笔记本中。' 
              : '为了完成聚合，请输入该笔记本的密码。'}
          </DialogDescription>
        </DialogHeader>

        {step === 'selection' ? (
          <form onSubmit={handleSubmit(handleSelectionSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="agg-notebook-name">{t.common.name} *</Label>
              <Input
                id="agg-notebook-name"
                {...register('name')}
                placeholder={t.notebooks.namePlaceholder}
                autoComplete="off"
              />
              {errors.name && (
                <p className="text-sm text-destructive">{errors.name.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="agg-notebook-password">密码 (可选)</Label>
              <Input
                id="agg-notebook-password"
                type="password"
                {...register('password')}
                placeholder="留空表示不设置密码"
                autoComplete="new-password"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="agg-notebook-creator">创建人 (可选)</Label>
              <Input
                id="agg-notebook-creator"
                {...register('creator_name')}
                placeholder="您的名字"
                autoComplete="off"
              />
            </div>

            <div className="space-y-2">
              <Label>选择要聚合的笔记本</Label>
              <ScrollArea className="h-[200px] w-full rounded-md border p-4">
                <div className="space-y-3">
                  {notebooks?.map((notebook) => (
                    <div key={notebook.id} className="flex items-center space-x-2">
                      <Checkbox 
                        id={`notebook-${notebook.id}`} 
                        checked={selectedNotebookIds.has(notebook.id)}
                        onCheckedChange={() => toggleNotebook(notebook.id)}
                      />
                      <label
                        htmlFor={`notebook-${notebook.id}`}
                        className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                      >
                        {notebook.name}
                      </label>
                    </div>
                  ))}
                  {(!notebooks || notebooks.length === 0) && (
                    <div className="text-sm text-muted-foreground">没有可用的笔记本</div>
                  )}
                </div>
              </ScrollArea>
              {selectedNotebookIds.size === 0 && (
                <p className="text-sm text-muted-foreground">请至少选择一个笔记本进行聚合</p>
              )}
            </div>

            <DialogFooter className="gap-2 sm:gap-0">
              <Button type="button" variant="outline" onClick={closeDialog}>
                {t.common.cancel}
              </Button>
              <Button type="submit" disabled={!isValid || selectedNotebookIds.size === 0}>
                下一步
              </Button>
            </DialogFooter>
          </form>
        ) : (
          <form onSubmit={handlePasswordSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="notebook-password">
                密码: {notebooksRequiringPassword[currentPasswordIndex]?.name}
              </Label>
              <Input
                id="notebook-password"
                type="password"
                value={currentPasswordInput}
                onChange={(e) => setCurrentPasswordInput(e.target.value)}
                placeholder="请输入密码"
                autoComplete="new-password"
                autoFocus
              />
              {passwordError && (
                <p className="text-sm text-destructive">{passwordError}</p>
              )}
            </div>

            <DialogFooter className="gap-2 sm:gap-0">
              <Button type="button" variant="outline" onClick={closeDialog}>
                取消
              </Button>
              <Button type="submit" disabled={!currentPasswordInput || aggregateNotebooks.isPending}>
                {aggregateNotebooks.isPending ? '正在聚合...' : '验证并继续'}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  )
}
