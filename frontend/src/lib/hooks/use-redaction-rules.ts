import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { redactionApi } from '@/lib/api/redaction'
import { QUERY_KEYS } from '@/lib/api/query-client'
import { useToast } from '@/lib/hooks/use-toast'
import { useTranslation } from '@/lib/hooks/use-translation'
import { getApiErrorKey } from '@/lib/utils/error-handler'
import { RedactionRuleCreate, RedactionRuleUpdate } from '@/lib/types/api'

export function useRedactionRules() {
  return useQuery({
    queryKey: QUERY_KEYS.redactionRules,
    queryFn: () => redactionApi.list(),
  })
}

function useRedactionRuleMutation<TArgs, TResult>(
  mutationFn: (args: TArgs) => Promise<TResult>,
  successKey: 'ruleAdded' | 'ruleUpdated' | 'ruleDeleted'
) {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const { t } = useTranslation()

  return useMutation({
    mutationFn,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.redactionRules })
      toast({
        title: t.common.success,
        description: t.settings.redaction[successKey],
      })
    },
    onError: (error: unknown) => {
      toast({
        title: t.common.error,
        description: getApiErrorKey(error, t.common.error),
        variant: 'destructive',
      })
    },
  })
}

export function useCreateRedactionRule() {
  return useRedactionRuleMutation(
    (data: RedactionRuleCreate) => redactionApi.create(data),
    'ruleAdded'
  )
}

export function useUpdateRedactionRule() {
  return useRedactionRuleMutation(
    ({ id, data }: { id: string; data: RedactionRuleUpdate }) =>
      redactionApi.update(id, data),
    'ruleUpdated'
  )
}

export function useDeleteRedactionRule() {
  return useRedactionRuleMutation(
    (id: string) => redactionApi.delete(id),
    'ruleDeleted'
  )
}
