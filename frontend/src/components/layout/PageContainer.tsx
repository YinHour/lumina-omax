import * as React from 'react'
import { cn } from '@/lib/utils'

type PageWidth = 'full' | 'wide' | 'readable'

const widthClasses: Record<PageWidth, string> = {
  full: 'max-w-none',
  wide: 'max-w-7xl',
  readable: 'max-w-4xl',
}

interface PageContainerProps extends React.ComponentProps<'div'> {
  width?: PageWidth
  scroll?: boolean
}

export function PageContainer({
  className,
  width = 'wide',
  scroll = true,
  ...props
}: PageContainerProps) {
  return (
    <div className={cn('min-h-0 flex-1', scroll && 'overflow-y-auto')}>
      <div
        data-slot="page-container"
        className={cn(
          'mx-auto w-full px-4 py-5 sm:px-6 sm:py-6 lg:px-8',
          widthClasses[width],
          className
        )}
        {...props}
      />
    </div>
  )
}
