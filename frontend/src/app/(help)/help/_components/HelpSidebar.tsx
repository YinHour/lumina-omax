'use client'

import { useState } from 'react'
import Link from 'next/link'
import type { HelpNavItem } from '@/lib/help/docs'
import { ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'

export function HelpSidebar({ nav }: { nav: HelpNavItem[] }) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>(() => {
    const initial: Record<string, boolean> = {}
    nav.forEach(s => { initial[s.href] = true })
    return initial
  })

  const toggle = (href: string) => {
    setExpanded(prev => ({ ...prev, [href]: !prev[href] }))
  }

  return (
    <aside className="w-56 shrink-0 border-r p-4 space-y-1 overflow-y-auto">
      <Link href="/help" className="block px-3 py-1.5 rounded text-sm font-medium hover:bg-muted transition-colors">
        文档首页
      </Link>
      <div className="h-px bg-border my-2" />
      {nav.map(section => (
        <div key={section.href}>
          <button
            onClick={() => toggle(section.href)}
            className="flex items-center justify-between w-full px-3 py-1.5 rounded text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-muted transition-colors text-left"
          >
            <span>{section.label}</span>
            <ChevronDown className={cn(
              'h-3.5 w-3.5 transition-transform',
              expanded[section.href] && 'rotate-180'
            )} />
          </button>
          {expanded[section.href] && section.children && (
            <div className="ml-2 border-l border-border/50 pl-2 space-y-0.5 mt-0.5">
              {section.children.map(child => (
                <Link
                  key={child.href}
                  href={child.href}
                  className="block px-3 py-1 rounded text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                >
                  {child.label}
                </Link>
              ))}
            </div>
          )}
        </div>
      ))}
    </aside>
  )
}
