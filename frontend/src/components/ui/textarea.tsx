import * as React from "react"

import { cn } from "@/lib/utils"

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "border-input bg-card/70 placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30 aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive flex field-sizing-content min-h-16 min-w-0 w-full rounded-lg border px-3 py-2 text-base shadow-xs transition-[color,background-color,border-color,box-shadow] duration-200 outline-none hover:border-primary/20 disabled:cursor-not-allowed disabled:bg-muted/60 disabled:opacity-60 md:text-sm",
        className
      )}
      {...props}
    />
  )
}

export { Textarea }
