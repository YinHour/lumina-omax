import Link from 'next/link'
import { getHelpNav } from '@/lib/help/docs'
import { HelpSidebar } from './_components/HelpSidebar'

export default function HelpLayout({ children }: { children: React.ReactNode }) {
  const nav = getHelpNav()

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b sticky top-0 bg-background/95 backdrop-blur z-50">
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center gap-4">
          <Link href="/help" className="font-bold text-lg text-teal-400 hover:text-teal-300 transition-colors">
            Lumiton·Omax | 知涌
          </Link>
          <span className="text-xs text-muted-foreground">|</span>
          <Link href="/notebooks" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
            返回应用
          </Link>
        </div>
      </header>
      <div className="max-w-7xl mx-auto flex h-[calc(100vh-3.5rem)]">
        <HelpSidebar nav={nav} />
        <main className="flex-1 min-w-0 p-8 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  )
}
