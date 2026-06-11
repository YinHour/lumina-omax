'use client'

import { AppShell } from '@/components/layout/AppShell'
import { PageContainer } from '@/components/layout/PageContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import { RebuildEmbeddings } from './components/RebuildEmbeddings'
import { SystemInfo } from './components/SystemInfo'
import { useTranslation } from '@/lib/hooks/use-translation'

export default function AdvancedPage() {
  const { t } = useTranslation()
  return (
    <AppShell>
      <PageContainer width="readable" className="space-y-6">
        <PageHeader
          title={t.advanced.title}
          description={t.advanced.desc}
        />
        <SystemInfo />
        <RebuildEmbeddings />
      </PageContainer>
    </AppShell>
  )
}
