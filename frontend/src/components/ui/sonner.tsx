"use client"

import { useThemeStore } from "@/lib/stores/theme-store"
import { Toaster as Sonner, ToasterProps } from "sonner"

const Toaster = ({ ...props }: ToasterProps) => {
  const theme = useThemeStore((state) => state.theme)
  const systemTheme = useThemeStore((state) => state.getSystemTheme())
  const effectiveTheme = theme === 'system' ? systemTheme : theme

  return (
    <Sonner
      theme={effectiveTheme as ToasterProps["theme"]}
      className="toaster group"
      duration={3000}
      closeButton={true}
      toastOptions={{
        duration: 3000,
      }}
      style={
        {
          "--normal-bg": "var(--popover)",
          "--normal-text": "var(--popover-foreground)",
          "--normal-border": "var(--border)",
          "--success-bg": "color-mix(in oklab, var(--success) 12%, var(--popover))",
          "--success-text": "var(--popover-foreground)",
          "--success-border": "color-mix(in oklab, var(--success) 35%, var(--border))",
          "--warning-bg": "color-mix(in oklab, var(--warning) 12%, var(--popover))",
          "--warning-text": "var(--popover-foreground)",
          "--warning-border": "color-mix(in oklab, var(--warning) 35%, var(--border))",
          "--error-bg": "color-mix(in oklab, var(--destructive) 10%, var(--popover))",
          "--error-text": "var(--popover-foreground)",
          "--error-border": "color-mix(in oklab, var(--destructive) 35%, var(--border))",
        } as React.CSSProperties
      }
      {...props}
    />
  )
}

export { Toaster }
