'use client'

import { useEffect, useState, useCallback } from 'react'
import { useAuthStore } from '@/lib/stores/auth-store'
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

interface UserItem {
  id: string
  username: string
  display_name: string
  status: 'pending' | 'active' | 'rejected'
  role: string
  created?: string
}

export function UserApprovalDashboard() {
  const { token, user } = useAuthStore()
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
      console.log('[UserApprovalDashboard] Fetching users, token present:', !!token)
      const response = await fetch(`/api/auth/users`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      if (!response.ok) {
        const body = await response.text().catch(() => '(empty)')
        console.error(`[UserApprovalDashboard] fetchUsers failed: ${response.status}`, body)
        throw new Error(`获取成员列表失败: ${response.status} — ${body}`)
      }

      const data = await response.json()
      setUsersList(data)
    } catch (err: unknown) {
      console.error('Error fetching users:', err)
      setError(err instanceof Error ? err.message : '获取成员列表失败')
    } finally {
      setIsLoading(false)
    }
  }, [token])

  const handleUpdateStatus = async (userId: string, targetStatus: 'active' | 'rejected') => {
    setConfirmAction({ userId, status: targetStatus })
  }

  const executeStatusUpdate = async () => {
    if (!confirmAction) return
    const { userId, status: targetStatus } = confirmAction
    setConfirmAction(null)
    try {
      const response = await fetch(`/api/auth/users/${userId}/status`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ status: targetStatus })
      })

      if (!response.ok) {
        throw new Error(`更新成员状态失败: ${response.status}`)
      }

      const updatedUser = await response.json()
      
      // Update local state
      setUsersList(prev => prev.map(u => u.id === userId ? { ...u, status: updatedUser.status } : u))
      
      toast.success(targetStatus === 'active' ? '已成功批准该成员账号并激活' : '已拒绝该成员账号申请')
    } catch (err: unknown) {
      console.error('Error updating status:', err)
      toast.error(err instanceof Error ? err.message : '操作失败')
    }
  }

  const handleUpdateRole = async (userId: string, targetRole: 'admin' | 'user') => {
    try {
      const response = await fetch(`/api/auth/users/${userId}/role`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ role: targetRole })
      })

      if (!response.ok) {
        throw new Error(`更新角色失败: ${response.status}`)
      }

      const updatedUser = await response.json()
      setUsersList(prev => prev.map(u => u.id === userId ? { ...u, role: updatedUser.role } : u))
      toast.success(targetRole === 'admin' ? '已将该成员提升为管理员' : '已取消该成员的管理员权限')
    } catch (err: unknown) {
      console.error('Error updating role:', err)
      toast.error(err instanceof Error ? err.message : '操作失败')
    }
  }

  const handleResetPassword = async (userId: string, newPassword: string) => {
    if (!newPassword || newPassword.length < 6) {
      setResetPwdError('密码长度不能少于6位')
      return
    }
    try {
      const response = await fetch(`/api/auth/users/${userId}/password`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ password: newPassword })
      })

      if (!response.ok) {
        throw new Error(`重置密码失败: ${response.status}`)
      }

      return true
    } catch (err: unknown) {
      console.error('Error resetting password:', err)
      toast.error(err instanceof Error ? err.message : '操作失败')
      return false
    }
  }

  const executeResetPassword = async () => {
    if (!resetPwdUserId) return
    setResetPwdSubmitting(true)
    setResetPwdError(null)

    if (resetPwd.length < 6) {
      setResetPwdError('密码长度不能少于6位')
      setResetPwdSubmitting(false)
      return
    }
    if (resetPwd !== resetPwdConfirm) {
      setResetPwdError('两次输入的密码不一致')
      setResetPwdSubmitting(false)
      return
    }

    const success = await handleResetPassword(resetPwdUserId, resetPwd)
    setResetPwdSubmitting(false)
    if (success) {
      toast.success('密码已成功重置')
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
            成员注册审批与账号管理
          </CardTitle>
          <CardDescription className="text-xs text-muted-foreground">
            批准、拒绝或停用系统成员，保障科研数据资产安全隔离
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
              all: '全部',
              pending: '待审批',
              active: '已激活',
              rejected: '已拒绝'
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
            没有找到符合筛选条件的成员
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
                      title={item.role === 'admin' ? '点击取消管理员权限' : '点击提升为管理员'}
                      disabled={item.username === 'admin'}
                    >
                      {item.role === 'admin' ? (
                        <><ShieldAlert className="h-3 w-3 text-teal-400" /> 管理员</>
                      ) : (
                        <><Shield className="h-3 w-3 text-muted-foreground" /> 用户</>
                      )}
                    </Button>
                  </div>
                  
                  {item.created && (
                    <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
                      <Clock className="h-3 w-3" />
                      <span>注册时间：{item.created}</span>
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-3.5 ml-auto sm:ml-0">
                  {/* Status badge */}
                  <div>
                    {item.status === 'pending' && (
                      <Badge variant="outline" className="bg-yellow-500/10 text-yellow-600 border-yellow-500/20 text-xs font-semibold">
                        待审批 (pending)
                      </Badge>
                    )}
                    {item.status === 'active' && (
                      <Badge variant="outline" className="bg-green-500/10 text-green-600 border-green-500/20 text-xs font-semibold">
                        已激活 (active)
                      </Badge>
                    )}
                    {item.status === 'rejected' && (
                      <Badge variant="outline" className="bg-red-500/10 text-red-600 border-red-500/20 text-xs font-semibold">
                        已拒绝 (rejected)
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
                        <UserCheck className="h-3.5 w-3.5" /> 批准并激活
                      </Button>
                    )}
                    {item.status === 'pending' && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleUpdateStatus(item.id, 'rejected')}
                        className="h-8 px-2 text-xs font-semibold text-red-600 hover:text-red-700 hover:bg-red-500/5 flex items-center gap-1"
                      >
                        <UserX className="h-3.5 w-3.5" /> 拒绝申请
                      </Button>
                    )}
                    {item.status === 'active' && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleUpdateStatus(item.id, 'rejected')}
                        className="h-8 px-2 text-xs font-semibold text-red-600 hover:text-red-700 hover:bg-red-500/5 flex items-center gap-1"
                      >
                        <UserX className="h-3.5 w-3.5" /> 禁用账号
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
                        title="重置密码"
                      >
                        <Key className="h-3.5 w-3.5" /> 重置密码
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
      title={confirmAction?.status === 'active' ? '批准成员账号' : confirmAction?.status === 'rejected' ? '拒绝 / 禁用成员账号' : ''}
      description={confirmAction?.status === 'active'
        ? '此操作将激活该成员的账号，该成员将以普通用户身份登录系统。'
        : '此操作将拒绝该成员的注册申请或禁用其账号，该成员将无法登录系统。'
      }
      confirmText={confirmAction?.status === 'active' ? '批准并激活' : '确认操作'}
      confirmVariant={confirmAction?.status === 'active' ? 'default' : 'destructive'}
      onConfirm={executeStatusUpdate}
    />

    <AlertDialog open={resetPwdOpen} onOpenChange={(open) => {
      if (!open) { setResetPwdOpen(false); setResetPwdUserId(null); setResetPwd(''); setResetPwdConfirm(''); setResetPwdError(null) }
    }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>重置密码</AlertDialogTitle>
          <AlertDialogDescription>请为该成员设置一个新密码，并确认输入无误。</AlertDialogDescription>
        </AlertDialogHeader>
        <div className="space-y-3 py-2">
          <div>
            <Label htmlFor="reset-new-password" className="text-sm font-medium">新密码</Label>
            <Input
              id="reset-new-password"
              type="password"
              value={resetPwd}
              onChange={(e) => { setResetPwd(e.target.value); setResetPwdError(null) }}
              placeholder="请输入至少 6 位的新密码"
              disabled={resetPwdSubmitting}
              className="mt-1"
            />
          </div>
          <div>
            <Label htmlFor="reset-confirm-password" className="text-sm font-medium">确认新密码</Label>
            <Input
              id="reset-confirm-password"
              type="password"
              value={resetPwdConfirm}
              onChange={(e) => { setResetPwdConfirm(e.target.value); setResetPwdError(null) }}
              placeholder="请再次输入新密码"
              disabled={resetPwdSubmitting}
              className="mt-1"
            />
          </div>
          {resetPwdError && (
            <p className="text-xs text-red-500">{resetPwdError}</p>
          )}
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={resetPwdSubmitting}>取消</AlertDialogCancel>
          <AlertDialogAction onClick={executeResetPassword} disabled={resetPwdSubmitting}>
            {resetPwdSubmitting ? '重置中...' : '确认重置'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
    </>
  )
}
