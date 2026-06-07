'use client'

import { useState, useEffect } from 'react'
import { Lock, KeyRound, Trash2 } from 'lucide-react'
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
import { Label } from '@/components/ui/label'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { useUpdateNotebookPassword } from '@/lib/hooks/use-notebooks'
import { useTranslation } from '@/lib/hooks/use-translation'

interface ManageNotebookPasswordDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  notebookId: string
  hasPassword: boolean
}

type TabValue = 'set' | 'change' | 'remove'

export function ManageNotebookPasswordDialog({
  open,
  onOpenChange,
  notebookId,
  hasPassword,
}: ManageNotebookPasswordDialogProps) {
  const { t } = useTranslation()
  const updatePassword = useUpdateNotebookPassword()

  const defaultTab: TabValue = hasPassword ? 'change' : 'set'
  const [activeTab, setActiveTab] = useState<TabValue>(defaultTab)
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open && typeof document !== 'undefined') {
      document.body.style.removeProperty('pointer-events')
    }
  }, [open])

  useEffect(() => {
    if (open) {
      setActiveTab(hasPassword ? 'change' : 'set')
      setPassword('')
      setConfirmPassword('')
      setError('')
    }
  }, [open, hasPassword])

  const handleSubmit = async () => {
    setError('')

    if (activeTab === 'set' || activeTab === 'change') {
      if (!password) {
        setError(t.notebooks.passwordRequired || 'Password is required')
        return
      }
      if (password.length < 6) {
        setError(t.notebooks.passwordTooShort || 'Password must be at least 6 characters')
        return
      }
      if (password !== confirmPassword) {
        setError(t.notebooks.passwordMismatch || 'Passwords do not match')
        return
      }
    }

    try {
      await updatePassword.mutateAsync({
        id: notebookId,
        data: {
          action: activeTab as 'set' | 'change' | 'remove',
          password: activeTab === 'remove' ? undefined : password,
        },
      })
      onOpenChange(false)
    } catch {
      // error toast handled by hook
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[450px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Lock className="h-5 w-5" />
            {t.notebooks.passwordManagement || 'Password Management'}
          </DialogTitle>
          <DialogDescription>
            {t.notebooks.passwordManagementDesc || 'Set, change, or remove the notebook password'}
          </DialogDescription>
        </DialogHeader>

        <Tabs value={activeTab} onValueChange={(v) => { setActiveTab(v as TabValue); setError('') }}>
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="set" disabled={hasPassword}>
              <KeyRound className="h-4 w-4 mr-2" />
              {t.notebooks.setPassword || 'Set'}
            </TabsTrigger>
            <TabsTrigger value="change" disabled={!hasPassword}>
              <KeyRound className="h-4 w-4 mr-2" />
              {t.notebooks.changePassword || 'Change'}
            </TabsTrigger>
            <TabsTrigger value="remove" disabled={!hasPassword}>
              <Trash2 className="h-4 w-4 mr-2" />
              {t.notebooks.removePassword || 'Remove'}
            </TabsTrigger>
          </TabsList>

          <div className="space-y-4 mt-4">
            {activeTab !== 'remove' && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="new-password">
                    {t.notebooks.newPassword || 'New Password'}
                  </Label>
                  <Input
                    id="new-password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder={
                      activeTab === 'set'
                        ? (t.notebooks.setPasswordPlaceholder || 'Enter password (at least 6 characters)')
                        : (t.notebooks.newPasswordPlaceholder || 'Enter new password')
                    }
                    onKeyDown={(e) => { e.stopPropagation() }}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="confirm-password">
                    {t.notebooks.confirmPassword || 'Confirm Password'}
                  </Label>
                  <Input
                    id="confirm-password"
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder={t.notebooks.confirmPasswordPlaceholder || 'Re-enter password'}
                    onKeyDown={(e) => { e.stopPropagation() }}
                  />
                </div>
              </>
            )}
          </div>
        </Tabs>

        {error && (
          <p className="text-sm text-destructive">{error}</p>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={updatePassword.isPending}>
            {t.common.cancel}
          </Button>
          <Button onClick={handleSubmit} disabled={updatePassword.isPending}>
            {updatePassword.isPending ? t.common.saving : (activeTab === 'remove' ? t.notebooks.removePasswordBtn || 'Remove Password' : activeTab === 'set' ? t.notebooks.setPasswordBtn || 'Set Password' : t.notebooks.changePasswordBtn || 'Change Password')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
