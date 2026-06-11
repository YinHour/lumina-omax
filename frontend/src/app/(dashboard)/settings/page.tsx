'use client'

import { AppShell } from '@/components/layout/AppShell'
import { PageContainer } from '@/components/layout/PageContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import { SettingsForm } from './components/SettingsForm'
import { UserApprovalDashboard } from './components/UserApprovalDashboard'
import { useSettings } from '@/lib/hooks/use-settings'
import { Button } from '@/components/ui/button'
import { RefreshCw } from 'lucide-react'
import { useTranslation } from '@/lib/hooks/use-translation'

export default function SettingsPage() {
  const { t } = useTranslation()
  const { refetch } = useSettings()

  return (
    <AppShell>
      <PageContainer width="readable" className="space-y-6">
        <PageHeader
          title={t.navigation.settings}
          actions={
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetch()}
              aria-label={t.common.refresh}
            >
              <RefreshCw className="h-4 w-4" />
            </Button>
          }
        />
        <SettingsForm />
        <UserApprovalDashboard />
      </PageContainer>
    </AppShell>
  )
}
