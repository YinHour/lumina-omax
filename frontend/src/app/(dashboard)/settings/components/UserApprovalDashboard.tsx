'use client'

import { useEffect, useState, useCallback } from 'react'
import { useAuthStore } from '@/lib/stores/auth-store'
import { apiClient } from '@/lib/api/client'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { 
  Users, 
  RefreshCw, 
  Clock, 
  UserCheck, 
  UserX,
  AlertCircle,
  ShieldAlert,
  Shield,
  Key,
} from 'lucide-react'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { ConfirmDialog } from '@/components/common/ConfirmDialog'
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
} from '@/components/ui/alert-dialog'
import { useTranslation } from '@/lib/hooks/use-translation'

interface UserItem {
  id: string
  username: string
  display_name: string
  status: 'pending' | 'active' | 'rejected'
  role: string
  created?: string
}

export function UserApprovalDashboard() {
  const { t } = useTranslation()
  const { token, user } = useAuthStore()
  const approvalText = t.settings.userApproval
  const [usersList, setUsersList] = useState<UserItem[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<'all' | 'pending' | 'active' | 'rejected'>('all')
  const [confirmAction, setConfirmAction] = useState<{ userId: string; status: 'active' | 'rejected' } | null>(null)
  const [resetPwdOpen, setResetPwdOpen] = useState(false)
  const [resetPwdUserId, setResetPwdUserId] = useState<string | null>(null)
  const [resetPwd, setResetPwd] = useState('')
  const [resetPwdConfirm, setResetPwdConfirm] = useState('')
  const [resetPwdError, setResetPwdError] = useState<string | null>(null)
  const [resetPwdSubmitting, setResetPwdSubmitting] = useState(false)

  const fetchUsers = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const response = await apiClient.get('/auth/users')
      setUsersList(response.data)
    } catch (err: unknown) {
      console.error('Error fetching users:', err)
      setError(err instanceof Error ? err.message : approvalText.fetchFailed)
    } finally {
      setIsLoading(false)
    }
  }, [approvalText.fetchFailed])

  const handleUpdateStatus = async (userId: string, targetStatus: 'active' | 'rejected') => {
    setConfirmAction({ userId, status: targetStatus })
  }

  const executeStatusUpdate = async () => {
    if (!confirmAction) return
    const { userId, status: targetStatus } = confirmAction
    setConfirmAction(null)
    try {
      const response = await apiClient.put(`/auth/users/${userId}/status`, { status: targetStatus })
      const updatedUser = response.data
      
      // Update local state
      setUsersList(prev => prev.map(u => u.id === userId ? { ...u, status: updatedUser.status } : u))
      
      toast.success(targetStatus === 'active' ? approvalText.statusApproved : approvalText.statusRejected)
    } catch (err: unknown) {
      console.error('Error updating status:', err)
      toast.error(err instanceof Error ? err.message : t.common.error)
    }
  }

  const handleUpdateRole = async (userId: string, targetRole: 'admin' | 'user') => {
    try {
      const response = await apiClient.put(`/auth/users/${userId}/role`, { role: targetRole })
      const updatedUser = response.data
      setUsersList(prev => prev.map(u => u.id === userId ? { ...u, role: updatedUser.role } : u))
      toast.success(targetRole === 'admin' ? approvalText.rolePromoted : approvalText.roleRevoked)
    } catch (err: unknown) {
      console.error('Error updating role:', err)
      toast.error(err instanceof Error ? err.message : t.common.error)
    }
  }

  const handleResetPassword = async (userId: string, newPassword: string) => {
    if (!newPassword || newPassword.length < 6) {
      setResetPwdError(approvalText.passwordMinLength)
      return
    }
    try {
      await apiClient.put(`/auth/users/${userId}/password`, { password: newPassword })
      return true
    } catch (err: unknown) {
      console.error('Error resetting password:', err)
      toast.error(err instanceof Error ? err.message : t.common.error)
      return false
    }
  }

  const executeResetPassword = async () => {
    if (!resetPwdUserId) return
    setResetPwdSubmitting(true)
    setResetPwdError(null)

    if (resetPwd.length < 6) {
      setResetPwdError(approvalText.passwordMinLength)
      setResetPwdSubmitting(false)
      return
    }
    if (resetPwd !== resetPwdConfirm) {
      setResetPwdError(approvalText.passwordMismatch)
      setResetPwdSubmitting(false)
      return
    }

    const success = await handleResetPassword(resetPwdUserId, resetPwd)
    setResetPwdSubmitting(false)
    if (success) {
      toast.success(approvalText.passwordResetSuccess)
      setResetPwdOpen(false)
      setResetPwdUserId(null)
      setResetPwd('')
      setResetPwdConfirm('')
    }
  }

  useEffect(() => {
    if (user?.role === 'admin' && token) {
      void fetchUsers()
    }
  }, [user, token, fetchUsers])

  // Only render for administrators
  if (user?.role !== 'admin') {
    return null
  }

  const filteredUsers = usersList.filter(u => {
    if (filter === 'all') return true
    return u.status === filter
  })

  return (
    <>
    <Card className="w-full mt-6 border-border shadow-md">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4 border-b">
        <div className="space-y-1">
          <CardTitle className="text-xl font-bold flex items-center gap-2">
            <Users className="h-5 w-5 text-teal-400" />
            {approvalText.title}
          </CardTitle>
          <CardDescription className="text-xs text-muted-foreground">
            {approvalText.description}
          </CardDescription>
        </div>
        <Button 
          variant="outline" 
          size="sm" 
          onClick={fetchUsers} 
          disabled={isLoading}
          className="h-8 w-8 p-0"
        >
          <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
        </Button>
      </CardHeader>

      <CardContent className="pt-4">
        {/* Filters */}
        <div className="flex gap-2 mb-4">
          {(['all', 'pending', 'active', 'rejected'] as const).map((status) => {
            const counts = usersList.filter(u => status === 'all' ? true : u.status === status).length
            const labels = {
              all: approvalText.filters.all,
              pending: approvalText.filters.pending,
              active: approvalText.filters.active,
              rejected: approvalText.filters.rejected,
            }
            const activeColors = {
              all: 'bg-primary text-primary-foreground',
              pending: 'bg-yellow-500 text-white',
              active: 'bg-green-600 text-white',
              rejected: 'bg-red-600 text-white'
            }
            
            return (
              <Button
                key={status}
                variant={filter === status ? 'default' : 'outline'}
                size="sm"
                onClick={() => setFilter(status)}
                className={`h-8 px-3 text-xs font-semibold rounded-lg ${filter === status ? activeColors[status] : ''}`}
              >
                {labels[status]} <span className="ml-1 opacity-70 font-mono">({counts})</span>
              </Button>
            )
          })}
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-10">
            <LoadingSpinner size="md" />
          </div>
        ) : error ? (
          <div className="flex items-center gap-2 text-red-500 text-sm bg-red-500/10 p-4 rounded-lg border border-red-500/20 my-4">
            <AlertCircle className="h-5 w-5" />
            <span>{error}</span>
          </div>
        ) : filteredUsers.length === 0 ? (
          <div className="text-center py-12 text-sm text-muted-foreground border border-dashed rounded-xl bg-muted/10">
            <Users className="h-8 w-8 mx-auto mb-2 text-muted-foreground/50" />
            {approvalText.noMembers}
          </div>
        ) : (
          <div className="divide-y border rounded-xl overflow-hidden bg-background">
            {filteredUsers.map((item) => (
              <div 
                key={item.id} 
                className="flex flex-col sm:flex-row sm:items-center justify-between p-4 gap-4 hover:bg-muted/10 transition-colors"
              >
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-sm text-foreground">{item.display_name}</span>
                    <span className="text-xs text-muted-foreground font-mono">@{item.username}</span>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleUpdateRole(item.id, item.role === 'admin' ? 'user' : 'admin')}
                      className="h-6 px-1.5 text-[10px] gap-1 font-semibold"
                      title={item.role === 'admin' ? approvalText.roleRevokeTitle : approvalText.rolePromoteTitle}
                      disabled={item.username === 'admin'}
                    >
                      {item.role === 'admin' ? (
                        <><ShieldAlert className="h-3 w-3 text-teal-400" /> {approvalText.adminRole}</>
                      ) : (
                        <><Shield className="h-3 w-3 text-muted-foreground" /> {approvalText.userRole}</>
                      )}
                    </Button>
                  </div>
                  
                  {item.created && (
                    <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
                      <Clock className="h-3 w-3" />
                      <span>{approvalText.registeredAt}: {item.created}</span>
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-3.5 ml-auto sm:ml-0">
                  {/* Status badge */}
                  <div>
                    {item.status === 'pending' && (
                      <Badge variant="outline" className="bg-yellow-500/10 text-yellow-600 border-yellow-500/20 text-xs font-semibold">
                        {approvalText.status.pending}
                      </Badge>
                    )}
                    {item.status === 'active' && (
                      <Badge variant="outline" className="bg-green-500/10 text-green-600 border-green-500/20 text-xs font-semibold">
                        {approvalText.status.active}
                      </Badge>
                    )}
                    {item.status === 'rejected' && (
                      <Badge variant="outline" className="bg-red-500/10 text-red-600 border-red-500/20 text-xs font-semibold">
                        {approvalText.status.rejected}
                      </Badge>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex gap-1.5">
                    {item.status !== 'active' && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleUpdateStatus(item.id, 'active')}
                        className="h-8 px-2 text-xs font-semibold text-green-600 hover:text-green-700 hover:bg-green-500/5 flex items-center gap-1"
                      >
                        <UserCheck className="h-3.5 w-3.5" /> {approvalText.approveActivate}
                      </Button>
                    )}
                    {item.status === 'pending' && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleUpdateStatus(item.id, 'rejected')}
                        className="h-8 px-2 text-xs font-semibold text-red-600 hover:text-red-700 hover:bg-red-500/5 flex items-center gap-1"
                      >
                        <UserX className="h-3.5 w-3.5" /> {approvalText.rejectApplication}
                      </Button>
                    )}
                    {item.status === 'active' && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleUpdateStatus(item.id, 'rejected')}
                        className="h-8 px-2 text-xs font-semibold text-red-600 hover:text-red-700 hover:bg-red-500/5 flex items-center gap-1"
                      >
                        <UserX className="h-3.5 w-3.5" /> {approvalText.disableAccount}
                      </Button>
                    )}
                    {item.status === 'active' && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          setResetPwdUserId(item.id)
                          setResetPwd('')
                          setResetPwdConfirm('')
                          setResetPwdError(null)
                          setResetPwdOpen(true)
                        }}
                        className="h-8 px-2 text-xs font-semibold text-muted-foreground hover:text-foreground flex items-center gap-1"
                        title={approvalText.resetPassword}
                      >
                        <Key className="h-3.5 w-3.5" /> {approvalText.resetPassword}
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
    
    <ConfirmDialog
      open={confirmAction !== null}
      onOpenChange={(open) => { if (!open) setConfirmAction(null) }}
      title={confirmAction?.status === 'active' ? approvalText.confirmApproveTitle : confirmAction?.status === 'rejected' ? approvalText.confirmRejectTitle : ''}
      description={confirmAction?.status === 'active'
        ? approvalText.confirmApproveDesc
        : approvalText.confirmRejectDesc
      }
      confirmText={confirmAction?.status === 'active' ? approvalText.approveActivate : t.common.confirm}
      confirmVariant={confirmAction?.status === 'active' ? 'default' : 'destructive'}
      onConfirm={executeStatusUpdate}
    />

    <AlertDialog open={resetPwdOpen} onOpenChange={(open) => {
      if (!open) { setResetPwdOpen(false); setResetPwdUserId(null); setResetPwd(''); setResetPwdConfirm(''); setResetPwdError(null) }
    }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{approvalText.resetPassword}</AlertDialogTitle>
          <AlertDialogDescription>{approvalText.resetPasswordDesc}</AlertDialogDescription>
        </AlertDialogHeader>
        <div className="space-y-3 py-2">
          <div>
            <Label htmlFor="reset-new-password" className="text-sm font-medium">{approvalText.newPassword}</Label>
            <Input
              id="reset-new-password"
              type="password"
              value={resetPwd}
              onChange={(e) => { setResetPwd(e.target.value); setResetPwdError(null) }}
              placeholder={approvalText.newPasswordPlaceholder}
              disabled={resetPwdSubmitting}
              className="mt-1"
            />
          </div>
          <div>
            <Label htmlFor="reset-confirm-password" className="text-sm font-medium">{approvalText.confirmNewPassword}</Label>
            <Input
              id="reset-confirm-password"
              type="password"
              value={resetPwdConfirm}
              onChange={(e) => { setResetPwdConfirm(e.target.value); setResetPwdError(null) }}
              placeholder={approvalText.confirmNewPasswordPlaceholder}
              disabled={resetPwdSubmitting}
              className="mt-1"
            />
          </div>
          {resetPwdError && (
            <p className="text-xs text-red-500">{resetPwdError}</p>
          )}
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={resetPwdSubmitting}>{t.common.cancel}</AlertDialogCancel>
          <AlertDialogAction onClick={executeResetPassword} disabled={resetPwdSubmitting}>
            {resetPwdSubmitting ? approvalText.resetting : approvalText.confirmReset}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
    </>
  )
}
