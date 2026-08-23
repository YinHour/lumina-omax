'use client'

import { useState } from 'react'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { ConfirmDialog } from '@/components/common/ConfirmDialog'
import { Plus, ShieldCheck, Trash2 } from 'lucide-react'
import { useTranslation } from '@/lib/hooks/use-translation'
import { useAuthStore } from '@/lib/stores/auth-store'
import { useSettings, useUpdateSettings } from '@/lib/hooks/use-settings'
import {
  useCreateRedactionRule,
  useDeleteRedactionRule,
  useRedactionRules,
  useUpdateRedactionRule,
} from '@/lib/hooks/use-redaction-rules'

const CATEGORY_VALUES = [
  'company',
  'address',
  'person',
  'phone',
  'well',
  'product',
  'custom',
] as const

export function RedactionCard() {
  const { t } = useTranslation()
  const { user } = useAuthStore()
  const text = t.settings.redaction
  const { data: settings } = useSettings()
  const updateSettings = useUpdateSettings()
  const { data: rules, isLoading, error } = useRedactionRules()
  const createRule = useCreateRedactionRule()
  const updateRule = useUpdateRedactionRule()
  const deleteRule = useDeleteRedactionRule()

  const [original, setOriginal] = useState('')
  const [alias, setAlias] = useState('')
  const [category, setCategory] = useState<string>('person')
  const [deleteTarget, setDeleteTarget] = useState<{
    id: string
    original: string
  } | null>(null)

  // Dictionary entries contain the sensitive originals the gateway protects:
  // the backend enforces admin-only access, hide the card for everyone else.
  if (user?.role !== 'admin') {
    return null
  }

  const enabled = settings?.redaction_enabled ?? false

  const handleToggle = async (value: string) => {
    await updateSettings.mutateAsync({ redaction_enabled: value === 'yes' })
  }

  const handleAdd = async () => {
    const trimmedOriginal = original.trim()
    const trimmedAlias = alias.trim()
    if (!trimmedOriginal || !trimmedAlias) return
    await createRule.mutateAsync({
      original: trimmedOriginal,
      alias: trimmedAlias,
      category,
    })
    setOriginal('')
    setAlias('')
  }

  const handleToggleRule = async (id: string, nextEnabled: boolean) => {
    await updateRule.mutateAsync({ id, data: { enabled: nextEnabled } })
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    await deleteRule.mutateAsync(deleteTarget.id)
    setDeleteTarget(null)
  }

  const categoryLabel = (value: string) =>
    text.categories[value as keyof typeof text.categories] ?? value

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ShieldCheck className="h-5 w-5" />
          {text.title}
        </CardTitle>
        <CardDescription>{text.description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-3">
          <Label htmlFor="redaction_enabled">{text.enableLabel}</Label>
          <Select
            value={enabled ? 'yes' : 'no'}
            onValueChange={handleToggle}
            disabled={updateSettings.isPending}
          >
            <SelectTrigger id="redaction_enabled" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="yes">{t.common.yes}</SelectItem>
              <SelectItem value="no">{t.common.no}</SelectItem>
            </SelectContent>
          </Select>
          <p className="text-sm text-muted-foreground">{text.enableHelp}</p>
        </div>

        <div className="space-y-3">
          <div>
            <h3 className="text-sm font-medium">{text.dictTitle}</h3>
            <p className="text-sm text-muted-foreground">{text.dictHelp}</p>
          </div>

          <div className="grid gap-2 sm:grid-cols-[1fr_1fr_auto_auto]">
            <div className="space-y-1">
              <Label htmlFor="redaction_original">{text.original}</Label>
              <Input
                id="redaction_original"
                value={original}
                placeholder={text.originalPlaceholder}
                onChange={(e) => setOriginal(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="redaction_alias">{text.alias}</Label>
              <Input
                id="redaction_alias"
                value={alias}
                placeholder={text.aliasPlaceholder}
                onChange={(e) => setAlias(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="redaction_category">{text.category}</Label>
              <Select value={category} onValueChange={setCategory}>
                <SelectTrigger id="redaction_category" className="w-[140px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CATEGORY_VALUES.map((value) => (
                    <SelectItem key={value} value={value}>
                      {categoryLabel(value)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-end">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleAdd}
                disabled={
                  createRule.isPending || !original.trim() || !alias.trim()
                }
              >
                <Plus className="h-4 w-4" />
                {text.addRule}
              </Button>
            </div>
          </div>

          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <LoadingSpinner size="md" />
            </div>
          ) : error ? (
            <Alert variant="destructive">
              <AlertTitle>{t.common.error}</AlertTitle>
              <AlertDescription>
                {error instanceof Error ? error.message : t.common.error}
              </AlertDescription>
            </Alert>
          ) : !rules || rules.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              {text.noRules}
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="py-2 pr-4 font-medium">{text.original}</th>
                    <th className="py-2 pr-4 font-medium">{text.alias}</th>
                    <th className="py-2 pr-4 font-medium">{text.category}</th>
                    <th className="py-2 pr-4 font-medium">{text.source}</th>
                    <th className="py-2 pr-4 font-medium">{text.status}</th>
                    <th className="py-2 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {rules.map((rule) => (
                    <tr key={rule.id} className="border-b last:border-b-0">
                      <td className="py-2 pr-4">{rule.original}</td>
                      <td className="py-2 pr-4">{rule.alias}</td>
                      <td className="py-2 pr-4">{categoryLabel(rule.category)}</td>
                      <td className="py-2 pr-4 text-muted-foreground">
                        {rule.source === 'auto' ? text.autoSource : text.manualSource}
                      </td>
                      <td className="py-2 pr-4">
                        <button
                          type="button"
                          className={
                            rule.enabled
                              ? 'text-emerald-600 dark:text-emerald-400 hover:underline'
                              : 'text-muted-foreground hover:underline'
                          }
                          onClick={() => handleToggleRule(rule.id, !rule.enabled)}
                          disabled={updateRule.isPending}
                        >
                          {rule.enabled ? text.enabledLabel : text.disabledLabel}
                        </button>
                      </td>
                      <td className="py-2 text-right">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() =>
                            setDeleteTarget({
                              id: rule.id,
                              original: rule.original,
                            })
                          }
                          aria-label={text.deleteRule}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </CardContent>

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        title={text.deleteConfirmTitle}
        description={text.deleteConfirmDescription.replace(
          '{original}',
          deleteTarget?.original ?? ''
        )}
        confirmText={text.deleteRule}
        confirmVariant="destructive"
        onConfirm={handleDelete}
        isLoading={deleteRule.isPending}
      />
    </Card>
  )
}
