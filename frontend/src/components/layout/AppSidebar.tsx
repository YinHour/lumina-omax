'use client'

import { useState, useEffect, type RefObject } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { usePathname } from 'next/navigation'
import * as DialogPrimitive from '@radix-ui/react-dialog'

import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/lib/hooks/use-auth'
import { useSidebarStore } from '@/lib/stores/sidebar-store'
import { useCreateDialogs } from '@/lib/hooks/use-create-dialogs'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { ThemeToggle } from '@/components/common/ThemeToggle'
import { LanguageToggle } from '@/components/common/LanguageToggle'
import { TranslationKeys } from '@/lib/locales'
import { useTranslation } from '@/lib/hooks/use-translation'
import { Separator } from '@/components/ui/separator'
import {
  Book,
  Search,
  Bot,
  Shuffle,
  Settings,
  LogOut,
  ChevronLeft,
  Menu,
  FileText,
  Plus,
  Wrench,
  Command,
  HelpCircle,
} from 'lucide-react'

interface NavItem { name: string; href: string; icon: typeof Book; adminOnly?: boolean }

interface AppSidebarProps {
  mobileOpen: boolean
  onMobileOpenChange: (open: boolean) => void
  mobileTriggerRef?: RefObject<HTMLButtonElement | null>
}

const getNavigation = (t: TranslationKeys, isAdmin: boolean): { title: string; items: NavItem[] }[] => {
  const manageItems: NavItem[] = [
    { name: t.navigation.models, href: '/settings/api-keys', icon: Bot, adminOnly: true },
    { name: t.navigation.transformations, href: '/transformations', icon: Shuffle },
    { name: t.navigation.settings, href: '/settings', icon: Settings, adminOnly: true },
    { name: t.navigation.help, href: '/help', icon: HelpCircle },
    { name: t.navigation.advanced, href: '/advanced', icon: Wrench, adminOnly: true },
  ]

  return [
    {
      title: t.navigation.collect,
      items: [
        { name: t.navigation.sources, href: '/sources', icon: FileText },
      ],
    },
    {
      title: t.navigation.process,
      items: [
        { name: t.navigation.notebooks, href: '/notebooks', icon: Book },
        { name: t.navigation.askAndSearch, href: '/search', icon: Search },
      ],
    },
    {
      title: t.navigation.manage,
      items: manageItems.filter(item => !item.adminOnly || isAdmin),
    },
  ]
}

type CreateTarget = 'source' | 'notebook'

export function AppSidebar({
  mobileOpen,
  onMobileOpenChange,
  mobileTriggerRef,
}: AppSidebarProps) {
  const { t } = useTranslation()
  const pathname = usePathname()
  const { logout, user } = useAuth()
  const navigation = getNavigation(t, user?.role === 'admin')
  const activeHref = navigation
    .flatMap(section => section.items)
    .filter(item => pathname === item.href || pathname?.startsWith(`${item.href}/`))
    .sort((left, right) => right.href.length - left.href.length)[0]?.href
  const { isCollapsed, toggleCollapse } = useSidebarStore()
  const { openSourceDialog, openNotebookDialog } = useCreateDialogs()

  const [desktopCreateMenuOpen, setDesktopCreateMenuOpen] = useState(false)
  const [mobileCreateMenuOpen, setMobileCreateMenuOpen] = useState(false)
  const [isMac, setIsMac] = useState(true) // Default to Mac for SSR

  // Detect platform for keyboard shortcut display
  useEffect(() => {
    setIsMac(navigator.platform.toLowerCase().includes('mac'))
  }, [])

  const handleCreateSelection = (
    target: CreateTarget,
    setCreateMenuOpen: (open: boolean) => void
  ) => {
    setCreateMenuOpen(false)

    if (target === 'source') {
      openSourceDialog()
    } else if (target === 'notebook') {
      openNotebookDialog()
    }
  }

  const renderSidebarContent = (mobile: boolean) => {
    const collapsed = !mobile && isCollapsed
    const createMenuOpen = mobile ? mobileCreateMenuOpen : desktopCreateMenuOpen
    const setCreateMenuOpen = mobile ? setMobileCreateMenuOpen : setDesktopCreateMenuOpen

    return (
      <>
        <div
          className={cn(
            'flex h-16 items-center group',
            collapsed ? 'justify-center px-2' : 'justify-between px-4'
          )}
        >
          {collapsed ? (
            <div className="relative flex w-full items-center justify-center">
              <Image
                src="/logo.png"
                alt="Lumiton Omax Logo"
                width={32}
                height={32}
                className="transition-opacity group-hover:opacity-0"
              />
              <Button
                variant="ghost"
                size="sm"
                onClick={toggleCollapse}
                className="absolute text-sidebar-foreground hover:bg-sidebar-accent opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <Menu className="h-4 w-4" />
              </Button>
            </div>
          ) : (
            <>
              <Image src="/logo.png" alt="Lumiton Omax Logo" width={28} height={28} className="shrink-0" />
              <span className="flex-1 text-center text-base font-bold whitespace-nowrap text-sidebar-foreground mx-2" data-testid="sidebar-brand">
                Lumiton·Omax|知涌
              </span>
              {!mobile && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={toggleCollapse}
                  className="text-sidebar-foreground hover:bg-sidebar-accent shrink-0"
                  data-testid="sidebar-toggle"
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
              )}
            </>
          )}
        </div>

        <nav
          className={cn(
            'flex-1 space-y-1 py-4 overflow-y-auto min-h-0',
            collapsed ? 'px-2' : 'px-3'
          )}
        >
          <div
            className={cn(
              'mb-4',
              collapsed ? 'px-0' : 'px-3'
            )}
          >
            <DropdownMenu open={createMenuOpen} onOpenChange={setCreateMenuOpen}>
              {collapsed ? (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <DropdownMenuTrigger asChild>
                      <Button
                        onClick={() => setCreateMenuOpen(true)}
                        variant="default"
                        size="sm"
                        className="w-full justify-center px-2"
                        aria-label={t.common.create}
                      >
                        <Plus className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                  </TooltipTrigger>
                   <TooltipContent side="right">{t.common.create}</TooltipContent>
                </Tooltip>
              ) : (
                <DropdownMenuTrigger asChild>
                  <Button
                    onClick={() => setCreateMenuOpen(true)}
                    variant="default"
                    size="sm"
                    className="w-full justify-start"
                   >
                    <Plus className="h-4 w-4 mr-2" />
                    {t.common.create}
                  </Button>
                </DropdownMenuTrigger>
              )}

              <DropdownMenuContent
                align={collapsed ? 'end' : 'start'}
                side={collapsed ? 'right' : 'bottom'}
                className="w-48"
              >
                <DropdownMenuItem
                  onSelect={(event) => {
                    event.preventDefault()
                    handleCreateSelection('source', setCreateMenuOpen)
                  }}
                  className="gap-2"
                >
                   <FileText className="h-4 w-4" />
                  {t.common.source}
                </DropdownMenuItem>
                <DropdownMenuItem
                  onSelect={(event) => {
                    event.preventDefault()
                    handleCreateSelection('notebook', setCreateMenuOpen)
                  }}
                  className="gap-2"
                >
                   <Book className="h-4 w-4" />
                  {t.common.notebook}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>

          {navigation.map((section, index) => (
            <div key={section.title}>
              {index > 0 && (
                <Separator className="my-3" />
              )}
              <div className="space-y-1">
                <h3
                  className={cn(
                    'mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-sidebar-foreground/60',
                    collapsed && 'hidden'
                  )}
                >
                  {section.title}
                </h3>

                {section.items.map((item) => {
                  const isActive = item.href === activeHref
                  const button = (
                    <Button
                      variant="ghost"
                      data-active={isActive}
                      className={cn(
                        'relative w-full justify-start gap-3 overflow-hidden text-sidebar-foreground before:absolute before:inset-y-2 before:left-0 before:w-0.5 before:rounded-full before:bg-transparent',
                        'data-[active=true]:bg-sidebar-accent data-[active=true]:text-sidebar-accent-foreground data-[active=true]:before:bg-sidebar-primary',
                        collapsed && 'justify-center px-2'
                      )}
                    >
                      <item.icon className="h-4 w-4" />
                      {!collapsed && <span>{item.name}</span>}
                    </Button>
                  )

                  if (collapsed) {
                    return (
                      <Tooltip key={item.name}>
                        <TooltipTrigger asChild>
                          <Link
                            href={item.href}
                            aria-current={isActive ? 'page' : undefined}
                            onClick={() => onMobileOpenChange(false)}
                          >
                            {button}
                          </Link>
                        </TooltipTrigger>
                        <TooltipContent side="right">{item.name}</TooltipContent>
                      </Tooltip>
                    )
                  }

                  return (
                    <Link
                      key={item.name}
                      href={item.href}
                      aria-current={isActive ? 'page' : undefined}
                      onClick={() => onMobileOpenChange(false)}
                    >
                      {button}
                    </Link>
                  )
                })}
              </div>
            </div>
          ))}
        </nav>

        <div
          className={cn(
            'border-t border-sidebar-border p-3 space-y-2',
            collapsed && 'px-2'
          )}
        >
          {/* Command Palette hint */}
          <div
            className={cn(
              'px-3 py-1.5 text-xs text-sidebar-foreground/60',
              collapsed && 'hidden'
            )}
          >
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                  <Command className="h-3 w-3" />
                  {t.common.quickActions}
              </span>
              <kbd className="pointer-events-none inline-flex h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground">
                {isMac ? <span className="text-xs">⌘</span> : <span>Ctrl+</span>}K
              </kbd>
            </div>
            <p className="mt-1 text-[10px] text-sidebar-foreground/40">
              {t.common.quickActionsDesc}
            </p>
          </div>

          {/* User Profile */}
          {user && (
            <Link
              href="/profile"
              className={cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 transition-colors hover:bg-muted',
                collapsed && 'hidden'
              )}
              onClick={() => onMobileOpenChange(false)}
            >
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary text-xs font-bold">
                {user.display_name?.charAt(0) || user.username?.charAt(0) || '?'}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate text-sidebar-foreground">{user.display_name || user.username}</p>
                <p className="text-xs text-muted-foreground truncate">@{user.username}</p>
              </div>
            </Link>
          )}

          <div
            className={cn(
              'flex flex-row gap-2',
              collapsed ? 'items-center' : 'items-stretch'
            )}
          >
            {collapsed ? (
              <>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div>
                      <ThemeToggle iconOnly />
                    </div>
                  </TooltipTrigger>
                  <TooltipContent side="right">{t.common.theme}</TooltipContent>
                </Tooltip>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div>
                      <LanguageToggle iconOnly />
                    </div>
                  </TooltipTrigger>
                  <TooltipContent side="right">{t.common.language}</TooltipContent>
                </Tooltip>
              </>
            ) : (
              <>
                <div className="flex-1"><ThemeToggle /></div>
                <div className="flex-1"><LanguageToggle /></div>
              </>
            )}
          </div>

          {collapsed ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="outline"
                  className="w-full justify-center"
                  onClick={logout}
                  aria-label={t.common.signOut}
                >
                  <LogOut className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
               <TooltipContent side="right">{t.common.signOut}</TooltipContent>
            </Tooltip>
          ) : (
            <Button
              variant="outline"
              className="w-full justify-start gap-3"
              onClick={logout}
              aria-label={t.common.signOut}
             >
              <LogOut className="h-4 w-4" />
              {t.common.signOut}
            </Button>
          )}
        </div>
      </>
    )
  }

  return (
    <TooltipProvider delayDuration={0}>
      <DialogPrimitive.Root
        open={mobileOpen}
        onOpenChange={onMobileOpenChange}
      >
        <DialogPrimitive.Portal>
          <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-slate-950/35 backdrop-blur-[1px] md:hidden" />
          <DialogPrimitive.Content
            aria-describedby={undefined}
            onCloseAutoFocus={(event) => {
              if (mobileTriggerRef?.current) {
                event.preventDefault()
                mobileTriggerRef.current.focus()
              }
            }}
            className="app-sidebar fixed inset-y-0 left-0 z-50 flex h-full w-64 flex-col border-r border-sidebar-border bg-sidebar shadow-xl outline-none md:hidden"
          >
            <DialogPrimitive.Title className="sr-only">
              {t.common.navigationLabel}
            </DialogPrimitive.Title>
            {renderSidebarContent(true)}
          </DialogPrimitive.Content>
        </DialogPrimitive.Portal>
      </DialogPrimitive.Root>

      <aside
        aria-label={t.common.navigationLabel}
        className={cn(
          'app-sidebar hidden h-full flex-col border-r border-sidebar-border bg-sidebar transition-[width] duration-300 md:flex',
          isCollapsed ? 'md:w-16' : 'md:w-64'
        )}
      >
        {renderSidebarContent(false)}
      </aside>
    </TooltipProvider>
  )
}
