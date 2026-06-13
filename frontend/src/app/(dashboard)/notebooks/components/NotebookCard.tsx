'use client'

import { useRouter } from 'next/navigation'
import { NotebookResponse } from '@/lib/types/api'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { MoreHorizontal, Archive, ArchiveRestore, Trash2, FileText, StickyNote, KeyRound, Lock, User } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useUpdateNotebook } from '@/lib/hooks/use-notebooks'
import { NotebookDeleteDialog } from './NotebookDeleteDialog'
import { ManageNotebookPasswordDialog } from '@/components/notebooks/ManageNotebookPasswordDialog'
import { useState } from 'react'
import { useTranslation } from '@/lib/hooks/use-translation'
import { getDateLocale } from '@/lib/utils/date-locale'
import { useAuthStore } from '@/lib/stores/auth-store'
import { sameRecordId } from '@/lib/utils/record-id'
interface NotebookCardProps {
  notebook: NotebookResponse
}

export function NotebookCard({ notebook }: NotebookCardProps) {
  const { t, language } = useTranslation()
  const [menuOpen, setMenuOpen] = useState(false)
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  const [showPasswordDialog, setShowPasswordDialog] = useState(false)
  const router = useRouter()
  const updateNotebook = useUpdateNotebook()
  const user = useAuthStore((s) => s.user)
  const canManageNotebook = sameRecordId(notebook.created_by, user?.id)

  const handleArchiveToggle = (e: React.MouseEvent) => {
    e.stopPropagation()
    updateNotebook.mutate({
      id: notebook.id,
      data: { archived: !notebook.archived }
    })
  }

  const handleCardClick = () => {
    router.push(`/notebooks/${encodeURIComponent(notebook.id)}`)
  }

  return (
    <>
      <Card 
        variant="interactive"
        className="group"
        onClick={handleCardClick}
      >
          <CardHeader className="pb-3">
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0 flex items-center gap-2">
                <CardTitle className="text-base truncate group-hover:text-primary transition-colors flex items-center gap-1.5">
                  {notebook.password && <Lock className="h-4 w-4 text-muted-foreground shrink-0" />}
                  {notebook.name}
                </CardTitle>
                {notebook.archived && (
                  <Badge variant="secondary" className="mt-1">
                    {t.notebooks.archived}
                  </Badge>
                )}
              </div>
              
              {canManageNotebook && (
                <DropdownMenu open={menuOpen} onOpenChange={setMenuOpen}>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="sm"
                      aria-label="More actions"
                      className="transition-opacity"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <MoreHorizontal className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
                    <DropdownMenuItem onClick={handleArchiveToggle}>
                      {notebook.archived ? (
                        <>
                          <ArchiveRestore className="h-4 w-4 mr-2" />
                          {t.notebooks.unarchive}
                        </>
                      ) : (
                        <>
                          <Archive className="h-4 w-4 mr-2" />
                          {t.notebooks.archive}
                        </>
                      )}
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={(e) => {
                      e.stopPropagation()
                      setMenuOpen(false)
                      setShowPasswordDialog(true)
                    }}>
                      <KeyRound className="h-4 w-4 mr-2" />
                      {t.notebooks.passwordSettings || 'Password'}
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={(e) => {
                        e.stopPropagation()
                        setMenuOpen(false)
                        setShowDeleteDialog(true)
                      }}
                      className="text-red-600"
                    >
                      <Trash2 className="h-4 w-4 mr-2" />
                      {t.common.delete}
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              )}
            </div>
          </CardHeader>
          
          <CardContent>
            <CardDescription className="line-clamp-2 text-sm">
              {notebook.description || t.chat.noDescription}
            </CardDescription>

            {notebook.is_aggregated && notebook.aggregated_notebooks && notebook.aggregated_notebooks.length > 0 && (
              <div className="mt-2 text-xs text-muted-foreground flex flex-wrap gap-1">
                <span className="font-medium">关联:</span>
                {notebook.aggregated_notebooks.map((name, i) => (
                  <Badge key={i} variant="secondary" className="px-1.5 py-0 text-[10px]">
                    {name}
                  </Badge>
                ))}
              </div>
            )}

            {notebook.password && (
              <Badge variant="outline" className="mt-3 inline-flex items-center gap-1 text-xs">
                <Lock className="h-3 w-3" />
                {t.notebooks.protectedNotebook}
              </Badge>
            )}

            <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
              <span>
                {t.common.updated.replace('{time}', formatDistanceToNow(new Date(notebook.updated), { 
                  addSuffix: true,
                  locale: getDateLocale(language)
                }))}
              </span>
              {notebook.creator_name && (
                <span className="flex items-center gap-1">
                  <User className="h-3 w-3" />
                  {notebook.creator_name}
                </span>
              )}
            </div>

            {/* Item counts footer */}
            <div className="mt-3 flex items-center gap-1.5 border-t pt-3">
              <Badge variant="outline" className="text-xs flex items-center gap-1 px-1.5 py-0.5 text-primary border-primary/50">
                <FileText className="h-3 w-3" />
                <span>{notebook.source_count}</span>
              </Badge>
              <Badge variant="outline" className="text-xs flex items-center gap-1 px-1.5 py-0.5 text-primary border-primary/50">
                <StickyNote className="h-3 w-3" />
                <span>{notebook.note_count}</span>
              </Badge>
            </div>
          </CardContent>
      </Card>

      <NotebookDeleteDialog
        open={showDeleteDialog}
        onOpenChange={setShowDeleteDialog}
        notebookId={notebook.id}
        notebookName={notebook.name}
        hasPassword={!!notebook.password}
      />

      <ManageNotebookPasswordDialog
        open={showPasswordDialog}
        onOpenChange={setShowPasswordDialog}
        notebookId={notebook.id}
        hasPassword={!!notebook.password}
      />
    </>
  )
}
