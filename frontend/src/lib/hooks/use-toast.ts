import { toast as sonnerToast } from 'sonner'
import { useTranslation } from '@/lib/hooks/use-translation'

type ToastProps = {
  title?: string
  description?: string
  variant?: 'default' | 'destructive'
}

export function useToast() {
  const { t } = useTranslation()

  return {
    toast: ({ title, description, variant = 'default' }: ToastProps) => {
      if (variant === 'destructive') {
        sonnerToast.error(title || t.common.error, {
          description,
          duration: 3000,
        })
      } else {
        sonnerToast.success(title || t.common.success, {
          description,
          duration: 3000,
        })
      }
    }
  }
}

// Wrapped toast with guaranteed 3000ms duration for all call sites
// that import { toast } from sonner directly
const createDurationToast = () => {
  const handler: Record<string, unknown> = {}

  const wrap = (method: 'success' | 'error' | 'message' | 'loading' | 'custom') => {
    handler[method] = (message: string | React.ReactNode, options?: any) => {
      const mergedOptions = { ...(options || {}), duration: 3000 }
      if (method === 'message' || method === 'custom') {
        return (sonnerToast as any)(message, mergedOptions)
      }
      return (sonnerToast as any)[method](message, mergedOptions)
    }
  }

  wrap('success')
  wrap('error')
  wrap('message')
  wrap('loading')
  wrap('custom')

  return handler as Pick<typeof sonnerToast, 'success' | 'error' | 'message' | 'loading' | 'custom'>
}

export const toast = createDurationToast()
