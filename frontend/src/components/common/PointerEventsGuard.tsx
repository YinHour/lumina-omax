'use client'

import { useEffect } from 'react'

/**
 * Global safety net for a known Radix UI issue where the inline
 * `pointer-events: none` set on <body> (while a Dialog/AlertDialog/Popover/etc.
 * is open) occasionally fails to be cleared after the overlay closes,
 * leaving the whole page unclickable.
 *
 * This guard observes <body> style mutations. Whenever `pointer-events: none`
 * is present but there is no actually-open Radix overlay in the DOM, it strips
 * the stale style so the page becomes interactive again.
 */
export function PointerEventsGuard() {
  useEffect(() => {
    if (typeof document === 'undefined') return

    const body = document.body

    const hasOpenOverlay = (): boolean => {
      // Any Radix layer that legitimately locks the body will have
      // an element with data-state="open" (dialog/alertdialog/popover/menu/etc.)
      return !!document.querySelector('[data-state="open"]')
    }

    const clearIfStale = () => {
      if (body.style.pointerEvents === 'none' && !hasOpenOverlay()) {
        body.style.removeProperty('pointer-events')
      }
    }

    const observer = new MutationObserver(() => {
      // Defer to the next frame so Radix has finished its own DOM updates
      // (it may set data-state="open" slightly after touching body style).
      requestAnimationFrame(clearIfStale)
    })

    observer.observe(body, {
      attributes: true,
      attributeFilter: ['style'],
    })

    // Also re-check on any user interaction as a last-resort recovery.
    const onInteract = () => clearIfStale()
    document.addEventListener('pointerdown', onInteract, true)

    return () => {
      observer.disconnect()
      document.removeEventListener('pointerdown', onInteract, true)
    }
  }, [])

  return null
}
