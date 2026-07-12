'use client'

import { use, useCallback, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { ArrowLeft, FileText, PanelLeftOpen, X } from 'lucide-react'
import { useSourceChat } from '@/lib/hooks/useSourceChat'
import { ChatPanel } from '@/components/source/ChatPanel'
import { useNavigation } from '@/lib/hooks/use-navigation'
import { SourceDetailContent } from '@/components/source/SourceDetailContent'
import { useTranslation } from '@/lib/hooks/use-translation'
import { cn } from '@/lib/utils'

export default function SourceDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const router = useRouter()
  const resolvedParams = use(params)
  const sourceId = resolvedParams?.id ? decodeURIComponent(resolvedParams.id) : ''
  const navigation = useNavigation()
  const { t } = useTranslation()
  const [sourceCollapsed, setSourceCollapsed] = useState(false)

  // Initialize source chat
  const chat = useSourceChat(sourceId)

  const handleBack = useCallback(() => {
    const returnPath = navigation.getReturnPath()
    router.push(returnPath)
    navigation.clearReturnTo()
  }, [navigation, router])

  return (
    <div className="flex flex-col h-screen">
      {/* Page-level navigation stays available when the source column is collapsed. */}
      <div className="flex items-center justify-between pb-4 pl-6 pr-20 pt-6">
        <Button
          variant="ghost"
          size="sm"
          onClick={handleBack}
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          {navigation.getReturnLabel() || t.sources.backToSources}
        </Button>
        <Button
          variant="ghost"
          size="icon"
          aria-label={t.common.close}
          onClick={handleBack}
        >
          <X className="h-4 w-4" />
        </Button>
      </div>

      {/* Main content: Source detail + Chat */}
      <div className="grid min-h-0 flex-1 gap-6 overflow-hidden px-6 lg:flex">
        {sourceCollapsed && (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  className="group hidden h-full w-12 shrink-0 flex-col items-center justify-center gap-3 rounded-xl border bg-card py-6 text-muted-foreground transition-colors duration-200 hover:bg-accent/50 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 lg:flex"
                  aria-label={t.sources.expandSourceContent}
                  onClick={() => setSourceCollapsed(false)}
                >
                  <PanelLeftOpen className="h-5 w-5 shrink-0" />
                  <span
                    className="whitespace-nowrap text-xs font-medium"
                    style={{ writingMode: 'vertical-rl', textOrientation: 'mixed' }}
                  >
                    {t.sources.sourceContent}
                  </span>
                  <FileText className="h-4 w-4 shrink-0 opacity-70" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="right">
                <p>{t.sources.expandSourceContent}</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}

        {/* Left column - Source detail */}
        <div
          data-testid="source-detail-column"
          className={cn(
            'min-h-0 overflow-y-auto px-4 pb-6 lg:min-w-0 lg:flex-[2_1_0%]',
            sourceCollapsed && 'lg:hidden'
          )}
        >
          <SourceDetailContent
            sourceId={sourceId}
            showChatButton={false}
            onClose={handleBack}
            showCloseButton={false}
            onCollapse={() => setSourceCollapsed(true)}
          />
        </div>

        {/* Right column - Chat */}
        <div className="min-h-0 overflow-y-auto px-4 pb-6 lg:min-w-0 lg:flex-[1_1_0%]">
          <ChatPanel
            messages={chat.messages}
            isStreaming={chat.isStreaming}
            activityStatus={chat.activityStatus}
            activityElapsedSeconds={chat.activityElapsedSeconds}
            contextIndicators={chat.contextIndicators}
            onSendMessage={(message, model, enableWebSearch) => chat.sendMessage(message, model, enableWebSearch)}
            modelOverride={chat.currentSession?.model_override}
            onModelChange={(model) => {
              if (chat.currentSessionId) {
                chat.updateSession(chat.currentSessionId, { model_override: model })
              }
            }}
            sessions={chat.sessions}
            currentSessionId={chat.currentSessionId}
            onCreateSession={(title) => chat.createSession({ title })}
            onSelectSession={chat.switchSession}
            onUpdateSession={(sessionId, title) => chat.updateSession(sessionId, { title })}
            onDeleteSession={chat.deleteSession}
            loadingSessions={chat.loadingSessions}
            onCancelStreaming={chat.cancelStreaming}
          />
        </div>
      </div>
    </div>
  )
}
