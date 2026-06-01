import Link from 'next/link'
import { getHelpNav } from '@/lib/help/docs'

export default function HelpLayout({ children }: { children: React.ReactNode }) {
  const nav = getHelpNav()

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b sticky top-0 bg-background/95 backdrop-blur z-50">
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center gap-4">
          <Link href="/help" className="font-bold text-lg text-teal-400 hover:text-teal-300 transition-colors">
            Lumina·Omax 帮助中心
          </Link>
          <span className="text-xs text-muted-foreground">|</span>
          <Link href="/notebooks" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
            返回应用
          </Link>
        </div>
      </header>
      <div className="max-w-7xl mx-auto flex">
        <aside className="w-56 shrink-0 border-r min-h-[calc(100vh-3.5rem)] p-4 space-y-1 overflow-y-auto sticky top-14">
          <Link
            href="/help"
            className="block px-3 py-1.5 rounded text-sm font-medium hover:bg-muted transition-colors"
          >
            文档首页
          </Link>
          <div className="h-px bg-border my-2" />
          {nav.map(section => (
            <div key={section.href}>
              <Link
                href={section.href}
                className="block px-3 py-1.5 rounded text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
              >
                {section.label}
              </Link>
              {section.children && (
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
        <main className="flex-1 min-w-0 p-8">
          {children}
        </main>
      </div>
    </div>
  )
}
