'use client'

import { useMemo } from 'react'
import Link from 'next/link'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { ShieldAlert, AlertTriangle, ArrowRight } from 'lucide-react'
import { useTranslation } from '@/lib/hooks/use-translation'
import { useCredentialStatus, useEnvStatus } from '@/lib/hooks/use-credentials'

export function SetupBanner() {
  const { t } = useTranslation()
  const { data: credentialStatus } = useCredentialStatus()
  const { data: envStatus } = useEnvStatus()

  const encryptionReady = credentialStatus?.encryption_configured ?? true

  const providersToMigrate = useMemo(() => {
    if (!envStatus || !credentialStatus) return []
    const providers: string[] = []
    for (const provider in envStatus) {
      if (envStatus[provider] && credentialStatus.source[provider] === 'environment') {
        providers.push(provider)
      }
    }
    return providers
  }, [envStatus, credentialStatus])

  if (encryptionReady && providersToMigrate.length === 0) {
    return null
  }

  if (!encryptionReady) {
    return (
      <div className="px-4 pt-3">
        <Alert variant="destructive">
          <ShieldAlert className="size-4" />
          <AlertTitle>{t.setupBanner.encryptionRequired}</AlertTitle>
          <AlertDescription className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <span>{t.setupBanner.encryptionRequiredDescription}</span>
          </AlertDescription>
        </Alert>
      </div>
    )
  }

  return (
    <div className="px-4 pt-3">
      <Alert variant="warning">
        <AlertTriangle className="size-4" />
        <AlertTitle>{t.setupBanner.migrationAvailable}</AlertTitle>
        <AlertDescription className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <span>
            {t.setupBanner.migrationDescription.replace('{count}', providersToMigrate.length.toString())}
          </span>
          <Button variant="outline" size="sm" asChild>
            <Link href="/settings/api-keys">
              {t.setupBanner.goToSettings}
              <ArrowRight className="size-4" />
            </Link>
          </Button>
        </AlertDescription>
      </Alert>
    </div>
  )
}
