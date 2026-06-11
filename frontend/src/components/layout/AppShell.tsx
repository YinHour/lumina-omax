'use client'

import { useEffect, useRef, useState } from 'react'
import { Menu } from 'lucide-react'

import { AppSidebar } from './AppSidebar'
import { SetupBanner } from './SetupBanner'
import { Button } from '@/components/ui/button'
import { useTranslation } from '@/lib/hooks/use-translation'

interface AppShellProps {
  children: React.ReactNode
}

export function AppShell({ children }: AppShellProps) {
  const { t } = useTranslation()
  const [mobileOpen, setMobileOpen] = useState(false)
  const mobileTriggerRef = useRef<HTMLButtonElement | null>(null)

  useEffect(() => {
    const desktopQuery = window.matchMedia('(min-width: 768px)')
    const handleBreakpointChange = (event: MediaQueryListEvent | MediaQueryList) => {
      if (event.matches) {
        setMobileOpen(false)
      }
    }

    handleBreakpointChange(desktopQuery)
    desktopQuery.addEventListener('change', handleBreakpointChange)

    return () => {
      desktopQuery.removeEventListener('change', handleBreakpointChange)
    }
  }, [])

  return (
    <div className="flex h-screen overflow-hidden bg-stone-50/70 dark:bg-background">
      <AppSidebar
        mobileOpen={mobileOpen}
        onMobileOpenChange={setMobileOpen}
        mobileTriggerRef={mobileTriggerRef}
      />
      <main className="flex-1 flex flex-col min-h-0 overflow-hidden">
        <div className="flex h-14 shrink-0 items-center border-b border-border/70 bg-background/90 px-3 backdrop-blur md:hidden">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            ref={mobileTriggerRef}
            aria-label={t.common.openNavigation}
            onClick={() => setMobileOpen(true)}
          >
            <Menu className="h-5 w-5" />
          </Button>
        </div>
        <SetupBanner />
        {children}
      </main>
    </div>
  )
}
