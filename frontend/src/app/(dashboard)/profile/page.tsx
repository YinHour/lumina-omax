'use client'

import { useState } from 'react'
import { useAuthStore } from '@/lib/stores/auth-store'
import { AppShell } from '@/components/layout/AppShell'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { UserCircle, ShieldAlert, Shield, CheckCircle, Clock, XCircle, Loader2 } from 'lucide-react'
import { Separator } from '@/components/ui/separator'
import { toast } from 'sonner'

export default function ProfilePage() {
  const { user, updateProfile, changePassword } = useAuthStore()
  const [displayName, setDisplayName] = useState(user?.display_name || '')
  const [savingProfile, setSavingProfile] = useState(false)

  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [changingPassword, setChangingPassword] = useState(false)

  if (!user) return null

  const initials = (user.display_name || user.username).charAt(0).toUpperCase()
  const statusConfig = {
    active: { icon: CheckCircle, color: 'text-green-500', label: '已激活' },
    pending: { icon: Clock, color: 'text-yellow-500', label: '等待审批' },
    rejected: { icon: XCircle, color: 'text-red-500', label: '已拒绝' },
  } as const
  const status = statusConfig[user.status as keyof typeof statusConfig] || statusConfig.pending
  const StatusIcon = status.icon

  const handleSaveProfile = async () => {
    if (!displayName.trim()) return
    setSavingProfile(true)
    const ok = await updateProfile(displayName.trim())
    setSavingProfile(false)
    if (ok) {
      toast.success('个人资料已更新')
    } else {
      toast.error('更新失败，请稍后重试')
    }
  }

  const handleChangePassword = async () => {
    if (!oldPassword || !newPassword) return
    if (newPassword.length < 6) {
      toast.error('新密码长度不能少于6位')
      return
    }
    if (newPassword !== confirmPassword) {
      toast.error('两次输入的密码不一致')
      return
    }
    setChangingPassword(true)
    const res = await changePassword(oldPassword, newPassword)
    setChangingPassword(false)
    if (res.success) {
      toast.success('密码已修改')
      setOldPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } else {
      toast.error(res.message || '密码修改失败')
    }
  }

  return (
    <AppShell>
      <div className="max-w-2xl mx-auto p-6 space-y-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <UserCircle className="h-5 w-5 text-teal-400" />
              个人资料
            </CardTitle>
            <CardDescription>管理你的个人信息和账号安全</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Avatar and Identity */}
            <div className="flex items-center gap-4">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-teal-500/20 text-teal-400 text-xl font-bold">
                {initials}
              </div>
              <div>
                <h2 className="text-lg font-semibold">{user.display_name}</h2>
                <p className="text-sm text-muted-foreground font-mono">@{user.username}</p>
                <div className="flex items-center gap-2 mt-1">
                  {user.role === 'admin' ? (
                    <Badge variant="outline" className="text-xs gap-1">
                      <ShieldAlert className="h-3 w-3 text-teal-400" /> 管理员
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="text-xs gap-1">
                      <Shield className="h-3 w-3 text-muted-foreground" /> 用户
                    </Badge>
                  )}
                  <Badge variant="outline" className={`text-xs gap-1 ${status.color}`}>
                    <StatusIcon className="h-3 w-3" /> {status.label}
                  </Badge>
                </div>
              </div>
            </div>

            <Separator />

            {/* Display Name */}
            <div className="space-y-2">
              <Label htmlFor="display-name">显示名称</Label>
              <div className="flex gap-2">
                <Input
                  id="display-name"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="你的显示名称"
                  maxLength={100}
                />
                <Button onClick={handleSaveProfile} disabled={savingProfile || !displayName.trim()}>
                  {savingProfile ? <Loader2 className="h-4 w-4 animate-spin" /> : '保存'}
                </Button>
              </div>
            </div>

            <Separator />

            {/* Change Password */}
            <div className="space-y-3">
              <h3 className="text-sm font-semibold">修改密码</h3>
              <div className="space-y-2">
                <Label htmlFor="old-password">当前密码</Label>
                <Input
                  id="old-password"
                  type="password"
                  value={oldPassword}
                  onChange={(e) => setOldPassword(e.target.value)}
                  placeholder="输入当前密码"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="new-password">新密码</Label>
                <Input
                  id="new-password"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="至少6位"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="confirm-password">确认新密码</Label>
                <Input
                  id="confirm-password"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="再次输入新密码"
                />
              </div>
              <Button onClick={handleChangePassword} disabled={changingPassword || !oldPassword || !newPassword || !confirmPassword}>
                {changingPassword ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                修改密码
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  )
}
