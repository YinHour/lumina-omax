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
import { useTranslation } from '@/lib/hooks/use-translation'

export default function ProfilePage() {
  const { t } = useTranslation()
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
    active: { icon: CheckCircle, color: 'text-green-500', label: t.profile.active },
    pending: { icon: Clock, color: 'text-yellow-500', label: t.profile.pending },
    rejected: { icon: XCircle, color: 'text-red-500', label: t.profile.rejected },
  } as const
  const status = statusConfig[user.status as keyof typeof statusConfig] || statusConfig.pending
  const StatusIcon = status.icon

  const handleSaveProfile = async () => {
    if (!displayName.trim()) return
    setSavingProfile(true)
    const ok = await updateProfile(displayName.trim())
    setSavingProfile(false)
    if (ok) {
      toast.success(t.profile.profileUpdated)
    } else {
      toast.error(t.profile.updateFailed)
    }
  }

  const handleChangePassword = async () => {
    if (!oldPassword || !newPassword) return
    if (newPassword.length < 6) {
      toast.error(t.profile.passwordTooShort)
      return
    }
    if (newPassword !== confirmPassword) {
      toast.error(t.profile.passwordMismatch)
      return
    }
    setChangingPassword(true)
    const res = await changePassword(oldPassword, newPassword)
    setChangingPassword(false)
    if (res.success) {
      toast.success(t.profile.passwordChanged)
      setOldPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } else {
      toast.error(res.message || t.profile.passwordFailed)
    }
  }

  return (
    <AppShell>
      <div className="max-w-2xl mx-auto p-6 space-y-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <UserCircle className="h-5 w-5 text-teal-400" />
              {t.profile.title}
            </CardTitle>
            <CardDescription>{t.profile.desc}</CardDescription>
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
                      <ShieldAlert className="h-3 w-3 text-teal-400" /> {t.profile.admin}
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="text-xs gap-1">
                      <Shield className="h-3 w-3 text-muted-foreground" /> {t.profile.user}
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
              <Label htmlFor="display-name">{t.profile.displayName}</Label>
              <div className="flex gap-2">
                <Input
                  id="display-name"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder={t.profile.displayNamePlaceholder}
                  maxLength={100}
                />
                <Button onClick={handleSaveProfile} disabled={savingProfile || !displayName.trim()}>
                  {savingProfile ? <Loader2 className="h-4 w-4 animate-spin" /> : t.profile.save}
                </Button>
              </div>
            </div>

            <Separator />

            {/* Change Password */}
            <div className="space-y-3">
              <h3 className="text-sm font-semibold">{t.profile.changePassword}</h3>
              <div className="space-y-2">
                <Label htmlFor="old-password">{t.profile.currentPassword}</Label>
                <Input
                  id="old-password"
                  type="password"
                  value={oldPassword}
                  onChange={(e) => setOldPassword(e.target.value)}
                  placeholder={t.profile.currentPasswordPlaceholder}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="new-password">{t.profile.newPassword}</Label>
                <Input
                  id="new-password"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder={t.profile.newPasswordPlaceholder}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="confirm-password">{t.profile.confirmPassword}</Label>
                <Input
                  id="confirm-password"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder={t.profile.confirmPasswordPlaceholder}
                />
              </div>
              <Button onClick={handleChangePassword} disabled={changingPassword || !oldPassword || !newPassword || !confirmPassword}>
                {changingPassword ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                {t.profile.changePassword}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  )
}
