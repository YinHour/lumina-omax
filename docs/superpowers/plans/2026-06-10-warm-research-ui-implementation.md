# Warm Research UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a warm, restrained, token-driven UI foundation across Lumiton Omax without changing business workflows or feature information architecture.

**Architecture:** Keep the current Next.js, Tailwind, Shadcn, and Radix component boundaries. Introduce semantic CSS tokens and reusable layout primitives, then update shared components and the application shell before adopting the new layout on representative pages. Mobile navigation remains local UI state in `AppShell`; persistent desktop collapse state remains in the existing Zustand store.

**Tech Stack:** Next.js 16, React 19, TypeScript, Tailwind CSS 4, Radix UI, Class Variance Authority, Zustand, Vitest, Testing Library.

---

## File Map

### New files

- `DESIGN.md`: concise implementation reference for tokens, component rules,
  motion, and usage constraints.
- `frontend/src/app/globals.test.ts`: contract tests for semantic theme tokens
  and removal of legacy scaling rules.
- `frontend/src/components/ui/ui-variants.test.tsx`: shared visual-state tests
  for buttons, cards, badges, alerts, and form controls.
- `frontend/src/components/layout/PageContainer.tsx`: scrollable responsive page
  container with width variants.
- `frontend/src/components/layout/PageHeader.tsx`: reusable page heading,
  description, breadcrumb, and action layout.
- `frontend/src/components/layout/PageHeader.test.tsx`: behavior and responsive
  class contract tests for the layout primitives.
- `frontend/src/components/layout/AppShell.test.tsx`: mobile navigation and shell
  structure tests.

### Modified files

- `frontend/src/app/globals.css`: warm light/dark tokens, semantic status
  colors, shadows, motion, and reduced-motion behavior.
- `frontend/src/components/ui/button.tsx`: restrained control geometry and
  interaction states.
- `frontend/src/components/ui/card.tsx`: CVA-backed default, interactive,
  selected, and insight variants.
- `frontend/src/components/ui/input.tsx`
- `frontend/src/components/ui/textarea.tsx`
- `frontend/src/components/ui/select.tsx`
- `frontend/src/components/ui/checkbox.tsx`
- `frontend/src/components/ui/radio-group.tsx`: unified form surfaces and focus
  states.
- `frontend/src/components/ui/dialog.tsx`
- `frontend/src/components/ui/dropdown-menu.tsx`
- `frontend/src/components/ui/popover.tsx`
- `frontend/src/components/ui/tooltip.tsx`: unified floating surfaces.
- `frontend/src/components/ui/tabs.tsx`
- `frontend/src/components/ui/badge.tsx`
- `frontend/src/components/ui/alert.tsx`
- `frontend/src/components/ui/sonner.tsx`: semantic status presentation.
- `frontend/src/components/layout/AppShell.tsx`: responsive shell and mobile
  navigation trigger.
- `frontend/src/components/layout/AppSidebar.tsx`: warm sidebar, controlled
  mobile drawer, active marker, and removal of scaling behavior.
- `frontend/src/components/layout/AppSidebar.test.tsx`: active, collapsed,
  mobile, and navigation-close behavior.
- `frontend/src/components/layout/SetupBanner.tsx`: semantic alert variants
  instead of literal red/amber classes.
- All `frontend/src/lib/locales/*/index.ts` locale files: accessible labels for
  opening and closing mobile navigation.
- `frontend/src/app/(dashboard)/notebooks/page.tsx`
- `frontend/src/app/(dashboard)/transformations/page.tsx`
- `frontend/src/app/(dashboard)/settings/page.tsx`
- `frontend/src/app/(dashboard)/advanced/page.tsx`
- `frontend/src/app/(dashboard)/search/page.tsx`: representative adoption of
  `PageContainer` and `PageHeader`.

## Task 1: Establish the Design Contract and Semantic Tokens

**Files:**
- Create: `DESIGN.md`
- Create: `frontend/src/app/globals.test.ts`
- Modify: `frontend/src/app/globals.css`

- [ ] **Step 1: Write the failing token contract test**

Create `frontend/src/app/globals.test.ts`:

```ts
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const css = readFileSync(join(process.cwd(), 'src/app/globals.css'), 'utf8')

describe('global design tokens', () => {
  it('defines warm semantic status and surface tokens', () => {
    expect(css).toContain('--color-highlight: var(--highlight);')
    expect(css).toContain('--color-highlight-foreground: var(--highlight-foreground);')
    expect(css).toContain('--color-success: var(--success);')
    expect(css).toContain('--color-warning: var(--warning);')
    expect(css).toContain('--shadow-surface:')
    expect(css).toContain('--motion-standard: 180ms;')
  })

  it('provides both warm light and dark theme values', () => {
    expect(css).toMatch(/:root\s*{[\s\S]*--background:\s*oklch\(/)
    expect(css).toMatch(/\.dark\s*{[\s\S]*--background:\s*oklch\(/)
    expect(css).toContain('--highlight:')
    expect(css).toContain('--sidebar-accent:')
  })

  it('removes legacy hover scaling', () => {
    expect(css).not.toContain('scale-[1.02]')
    expect(css).not.toContain('transform: translateY(-1px)')
  })

  it('respects reduced motion', () => {
    expect(css).toContain('@media (prefers-reduced-motion: reduce)')
  })
})
```

- [ ] **Step 2: Run the token test and verify it fails**

Run:

```bash
cd frontend
npm test -- src/app/globals.test.ts
```

Expected: FAIL because `--highlight`, status tokens, surface shadow, motion
token, and reduced-motion rules do not exist, while legacy scaling remains.

- [ ] **Step 3: Add the approved design reference**

Create `DESIGN.md` with this structure and concrete rules:

```md
# Lumiton Omax Design System

## Direction

Warm, restrained research workspace. Moderately compact, modern sans-serif,
indigo-led, and supported by limited amber highlights.

## Semantic Color Roles

- `background`: warm ivory canvas
- `card` and `popover`: warm elevated surfaces
- `primary`: low-saturation indigo for actions and selection
- `highlight`: amber for AI insight, important notices, and processing
- `success`, `warning`, `destructive`: status-only colors
- `sidebar-*`: navigation-specific surfaces and states

Never use amber as the normal primary action color. Never use literal palette
classes in feature components when a semantic role exists.

## Geometry

- Cards and panels: 12px radius
- Buttons and form controls: 8px radius
- Thin borders before shadows
- Light shadows only for elevation and interactive emphasis

## Density and Type

- Core spacing rhythm: 4, 8, 12, 16, 24, 32px
- Modern sans-serif throughout
- Page title, section title, body/control, metadata hierarchy

## Interaction

- Standard motion: 180ms, acceptable range 150-220ms
- No hover scaling or bounce
- Use color, border, opacity, and restrained shadow changes
- Preserve visible keyboard focus
- Respect reduced motion

## Component Rules

- Primary buttons use indigo
- Interactive cards use border/surface/shadow changes without movement
- Amber badges and alerts mean insight or attention
- Floating surfaces share warm popover, 12px radius, border, and surface shadow
- New user-facing strings must be translated in every locale
```

- [ ] **Step 4: Implement the warm semantic tokens**

Update `frontend/src/app/globals.css`:

```css
@theme inline {
  --color-highlight: var(--highlight);
  --color-highlight-foreground: var(--highlight-foreground);
  --color-success: var(--success);
  --color-success-foreground: var(--success-foreground);
  --color-warning: var(--warning);
  --color-warning-foreground: var(--warning-foreground);
}

:root {
  --radius: 0.75rem;
  --background: oklch(0.982 0.012 88);
  --foreground: oklch(0.245 0.018 55);
  --card: oklch(0.995 0.006 88);
  --card-foreground: oklch(0.245 0.018 55);
  --popover: oklch(0.995 0.006 88);
  --popover-foreground: oklch(0.245 0.018 55);
  --primary: oklch(0.49 0.115 282);
  --primary-foreground: oklch(0.985 0.008 88);
  --secondary: oklch(0.948 0.018 82);
  --secondary-foreground: oklch(0.31 0.026 60);
  --muted: oklch(0.958 0.014 82);
  --muted-foreground: oklch(0.52 0.028 62);
  --accent: oklch(0.925 0.025 282);
  --accent-foreground: oklch(0.34 0.07 282);
  --highlight: oklch(0.86 0.105 78);
  --highlight-foreground: oklch(0.34 0.065 58);
  --success: oklch(0.61 0.12 153);
  --success-foreground: oklch(0.985 0.008 88);
  --warning: oklch(0.72 0.13 72);
  --warning-foreground: oklch(0.29 0.05 55);
  --destructive: oklch(0.58 0.19 28);
  --border: oklch(0.885 0.024 78);
  --input: oklch(0.885 0.024 78);
  --ring: oklch(0.56 0.12 282);
  --sidebar: oklch(0.955 0.018 82);
  --sidebar-foreground: oklch(0.285 0.024 58);
  --sidebar-primary: var(--primary);
  --sidebar-primary-foreground: var(--primary-foreground);
  --sidebar-accent: oklch(0.9 0.035 282);
  --sidebar-accent-foreground: oklch(0.34 0.07 282);
  --sidebar-border: oklch(0.875 0.026 78);
  --sidebar-ring: var(--ring);
  --shadow-surface: 0 1px 2px oklch(0.25 0.02 60 / 0.05),
    0 8px 24px oklch(0.25 0.02 60 / 0.06);
  --shadow-floating: 0 16px 40px oklch(0.2 0.03 60 / 0.14);
  --motion-fast: 150ms;
  --motion-standard: 180ms;
  --motion-slow: 220ms;
}

.dark {
  --background: oklch(0.19 0.016 55);
  --foreground: oklch(0.94 0.012 82);
  --card: oklch(0.235 0.018 55);
  --card-foreground: oklch(0.94 0.012 82);
  --popover: oklch(0.255 0.02 55);
  --popover-foreground: oklch(0.94 0.012 82);
  --primary: oklch(0.7 0.105 282);
  --primary-foreground: oklch(0.2 0.03 282);
  --secondary: oklch(0.29 0.02 55);
  --secondary-foreground: oklch(0.92 0.012 82);
  --muted: oklch(0.275 0.018 55);
  --muted-foreground: oklch(0.71 0.025 75);
  --accent: oklch(0.34 0.045 282);
  --accent-foreground: oklch(0.91 0.025 282);
  --highlight: oklch(0.69 0.09 76);
  --highlight-foreground: oklch(0.19 0.035 55);
  --success: oklch(0.69 0.11 153);
  --success-foreground: oklch(0.18 0.025 153);
  --warning: oklch(0.75 0.105 72);
  --warning-foreground: oklch(0.2 0.035 55);
  --destructive: oklch(0.66 0.17 28);
  --border: oklch(0.36 0.025 58);
  --input: oklch(0.34 0.025 58);
  --ring: oklch(0.7 0.105 282);
  --sidebar: oklch(0.215 0.018 55);
  --sidebar-foreground: oklch(0.91 0.014 82);
  --sidebar-primary: var(--primary);
  --sidebar-primary-foreground: var(--primary-foreground);
  --sidebar-accent: oklch(0.32 0.04 282);
  --sidebar-accent-foreground: oklch(0.91 0.025 282);
  --sidebar-border: oklch(0.33 0.022 58);
  --sidebar-ring: var(--ring);
}
```

Replace legacy `.sidebar-menu-item` and `.card-hover` movement rules with
color/border/shadow transitions:

```css
.sidebar-menu-item,
.card-hover {
  transition:
    color var(--motion-standard) ease,
    background-color var(--motion-standard) ease,
    border-color var(--motion-standard) ease,
    box-shadow var(--motion-standard) ease,
    opacity var(--motion-standard) ease;
}

.card-hover {
  cursor: pointer;
}

.card-hover:hover {
  border-color: color-mix(in oklab, var(--primary) 25%, var(--border));
  box-shadow: var(--shadow-surface);
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    scroll-behavior: auto !important;
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

- [ ] **Step 5: Run the token test**

Run:

```bash
cd frontend
npm test -- src/app/globals.test.ts
```

Expected: PASS, 4 tests.

- [ ] **Step 6: Commit the foundation**

```bash
git add DESIGN.md frontend/src/app/globals.css frontend/src/app/globals.test.ts
git commit -m "feat: establish warm research design tokens"
```

## Task 2: Standardize Buttons, Cards, and Form Controls

**Files:**
- Create: `frontend/src/components/ui/ui-variants.test.tsx`
- Modify: `frontend/src/components/ui/button.tsx`
- Modify: `frontend/src/components/ui/card.tsx`
- Modify: `frontend/src/components/ui/input.tsx`
- Modify: `frontend/src/components/ui/textarea.tsx`
- Modify: `frontend/src/components/ui/select.tsx`
- Modify: `frontend/src/components/ui/checkbox.tsx`
- Modify: `frontend/src/components/ui/radio-group.tsx`

- [ ] **Step 1: Write failing shared-component tests**

Create `frontend/src/components/ui/ui-variants.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Button } from './button'
import { Card } from './card'
import { Input } from './input'
import { Textarea } from './textarea'

describe('warm research UI variants', () => {
  it('uses restrained button geometry and focus treatment', () => {
    render(<Button>Save</Button>)
    expect(screen.getByRole('button')).toHaveClass(
      'rounded-lg',
      'transition-[color,background-color,border-color,box-shadow,opacity]'
    )
  })

  it('supports interactive, selected, and insight cards', () => {
    const { rerender } = render(<Card variant="interactive">Interactive</Card>)
    expect(screen.getByText('Interactive')).toHaveAttribute(
      'data-variant',
      'interactive'
    )

    rerender(<Card variant="selected">Selected</Card>)
    expect(screen.getByText('Selected')).toHaveAttribute('data-variant', 'selected')

    rerender(<Card variant="insight">Insight</Card>)
    expect(screen.getByText('Insight')).toHaveAttribute('data-variant', 'insight')
  })

  it('uses consistent form-control geometry', () => {
    render(
      <>
        <Input aria-label="Title" />
        <Textarea aria-label="Notes" />
      </>
    )
    expect(screen.getByLabelText('Title')).toHaveClass('rounded-lg', 'bg-card/70')
    expect(screen.getByLabelText('Notes')).toHaveClass('rounded-lg', 'bg-card/70')
  })
})
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
cd frontend
npm test -- src/components/ui/ui-variants.test.tsx
```

Expected: TypeScript/render failure because `Card` has no `variant`, followed
by class assertion failures.

- [ ] **Step 3: Implement restrained button styles**

In `button.tsx`, keep the existing API and replace the base and variant
classes:

```ts
const buttonVariants = cva(
  "inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium outline-none transition-[color,background-color,border-color,box-shadow,opacity] duration-200 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4 focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/35 aria-invalid:border-destructive aria-invalid:ring-2 aria-invalid:ring-destructive/20",
  {
    variants: {
      variant: {
        default:
          "border border-primary bg-primary text-primary-foreground shadow-xs hover:bg-primary/92 hover:shadow-sm active:bg-primary/85",
        destructive:
          "border border-destructive bg-destructive text-white shadow-xs hover:bg-destructive/92 focus-visible:ring-destructive/25",
        outline:
          "border border-border bg-card/70 text-foreground shadow-xs hover:border-primary/30 hover:bg-accent/65 hover:text-accent-foreground",
        secondary:
          "border border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/75",
        ghost:
          "border border-transparent hover:bg-accent/65 hover:text-accent-foreground",
        link: "h-auto rounded-none p-0 text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 py-2 has-[>svg]:px-3",
        sm: "h-8 gap-1.5 px-3 has-[>svg]:px-2.5",
        lg: "h-10 px-6 has-[>svg]:px-4",
        icon: "size-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)
```

- [ ] **Step 4: Add semantic card variants**

Convert `Card` to CVA while preserving all child component exports:

```tsx
import { cva, type VariantProps } from "class-variance-authority"

const cardVariants = cva(
  "flex flex-col gap-6 rounded-xl border py-6 text-card-foreground transition-[color,background-color,border-color,box-shadow] duration-200",
  {
    variants: {
      variant: {
        default: "border-border/90 bg-card shadow-xs",
        interactive:
          "cursor-pointer border-border/90 bg-card shadow-xs hover:border-primary/25 hover:bg-card hover:shadow-[var(--shadow-surface)]",
        selected:
          "border-primary/40 bg-accent/55 ring-1 ring-primary/15",
        insight:
          "border-highlight/55 bg-highlight/12 shadow-xs",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

function Card({
  className,
  variant,
  ...props
}: React.ComponentProps<"div"> & VariantProps<typeof cardVariants>) {
  return (
    <div
      data-slot="card"
      data-variant={variant ?? "default"}
      className={cn(cardVariants({ variant }), className)}
      {...props}
    />
  )
}
```

Export `cardVariants` with the existing card exports.

- [ ] **Step 5: Unify form-control surfaces**

Apply this common shape to `Input`, `Textarea`, and `SelectTrigger`, preserving
their existing sizes and behavior:

```text
rounded-lg border-input bg-card/70 shadow-xs
transition-[color,background-color,border-color,box-shadow] duration-200
hover:border-primary/20
focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30
disabled:bg-muted/60 disabled:opacity-60
```

Update `SelectContent` to `rounded-xl border-border/90 shadow-[var(--shadow-floating)]`.
Update `SelectItem` to `rounded-lg`.

Update `Checkbox` and `RadioGroupItem` to use `bg-card/70`, a two-pixel
focus-visible ring, and the same duration without changing their Radix state
selectors.

- [ ] **Step 6: Run focused tests**

Run:

```bash
cd frontend
npm test -- src/components/ui/ui-variants.test.tsx
```

Expected: PASS, 3 tests.

- [ ] **Step 7: Run existing component tests**

Run:

```bash
cd frontend
npm test -- src/components/common/ConfirmDialog.test.tsx
```

Expected: PASS with no dialog/button behavior regression.

- [ ] **Step 8: Commit shared controls**

```bash
git add frontend/src/components/ui/button.tsx \
  frontend/src/components/ui/card.tsx \
  frontend/src/components/ui/input.tsx \
  frontend/src/components/ui/textarea.tsx \
  frontend/src/components/ui/select.tsx \
  frontend/src/components/ui/checkbox.tsx \
  frontend/src/components/ui/radio-group.tsx \
  frontend/src/components/ui/ui-variants.test.tsx
git commit -m "feat: unify core UI control styling"
```

## Task 3: Standardize Feedback and Floating Surfaces

**Files:**
- Modify: `frontend/src/components/ui/ui-variants.test.tsx`
- Modify: `frontend/src/components/ui/dialog.tsx`
- Modify: `frontend/src/components/ui/dropdown-menu.tsx`
- Modify: `frontend/src/components/ui/popover.tsx`
- Modify: `frontend/src/components/ui/tooltip.tsx`
- Modify: `frontend/src/components/ui/tabs.tsx`
- Modify: `frontend/src/components/ui/badge.tsx`
- Modify: `frontend/src/components/ui/alert.tsx`
- Modify: `frontend/src/components/ui/sonner.tsx`
- Modify: `frontend/src/components/layout/SetupBanner.tsx`

- [ ] **Step 1: Add failing semantic feedback tests**

Append to `ui-variants.test.tsx`:

```tsx
import { Badge } from './badge'
import { Alert } from './alert'

it('provides semantic insight and status variants', () => {
  render(
    <>
      <Badge variant="insight">AI insight</Badge>
      <Badge variant="success">Complete</Badge>
      <Alert variant="warning">Needs attention</Alert>
    </>
  )

  expect(screen.getByText('AI insight')).toHaveClass('bg-highlight/18')
  expect(screen.getByText('Complete')).toHaveClass('bg-success/14')
  expect(screen.getByRole('alert')).toHaveClass('border-warning/40')
})
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
cd frontend
npm test -- src/components/ui/ui-variants.test.tsx
```

Expected: FAIL because `insight`, `success`, and `warning` variants are not
defined.

- [ ] **Step 3: Add semantic badge and alert variants**

Add badge variants:

```ts
insight:
  "border-highlight/45 bg-highlight/18 text-highlight-foreground [a&]:hover:bg-highlight/26",
success:
  "border-success/35 bg-success/14 text-success [a&]:hover:bg-success/20",
warning:
  "border-warning/40 bg-warning/16 text-warning-foreground [a&]:hover:bg-warning/24",
```

Expand alert variants:

```ts
default: "border-border/90 bg-card text-card-foreground",
insight:
  "border-highlight/45 bg-highlight/12 text-foreground [&>svg]:text-highlight-foreground",
success:
  "border-success/35 bg-success/10 text-foreground [&>svg]:text-success",
warning:
  "border-warning/40 bg-warning/12 text-foreground [&>svg]:text-warning",
destructive:
  "border-destructive/40 bg-destructive/8 text-foreground [&>svg]:text-destructive",
```

- [ ] **Step 4: Unify floating surfaces**

Apply these rules without changing Radix behavior:

```text
DialogContent:
bg-popover rounded-xl border-border/90 shadow-[var(--shadow-floating)]
max-h-[calc(100vh-2rem)] overflow-y-auto

DropdownMenuContent / DropdownMenuSubContent / PopoverContent / SelectContent:
rounded-xl border-border/90 bg-popover shadow-[var(--shadow-floating)]

DropdownMenuItem / DropdownMenuSubTrigger:
rounded-lg

TooltipContent:
rounded-lg border border-border/80 bg-popover text-popover-foreground
shadow-[var(--shadow-surface)]

TabsList:
rounded-lg border-border/80 bg-muted/65 p-1 shadow-none

TabsTrigger:
rounded-md; active state uses bg-card, text-foreground, border-border/80
```

Change the dialog overlay to `bg-foreground/30 backdrop-blur-[2px]`. Keep
animation duration within the approved range and retain `pointer-events`
cleanup.

- [ ] **Step 5: Map Sonner to semantic status tokens**

Set:

```tsx
style={{
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
} as React.CSSProperties}
```

- [ ] **Step 6: Replace literal SetupBanner palettes**

Use `variant="destructive"` for missing encryption and `variant="warning"` for
migration. Remove literal `red-*` and `amber-*` classes:

```tsx
<Alert variant="destructive">
  <ShieldAlert className="size-4" />
  <AlertTitle>{t.setupBanner.encryptionRequired}</AlertTitle>
  <AlertDescription className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
    <span>{t.setupBanner.encryptionRequiredDescription}</span>
  </AlertDescription>
</Alert>

<Alert variant="warning">
  <AlertTriangle className="size-4" />
  <AlertTitle>{t.setupBanner.migrationAvailable}</AlertTitle>
  <AlertDescription className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
    <span>
      {t.setupBanner.migrationDescription.replace(
        '{count}',
        providersToMigrate.length.toString()
      )}
    </span>
  <Button variant="outline" size="sm" asChild>
      <Link href="/settings/api-keys">
        {t.setupBanner.goToSettings}
        <ArrowRight className="size-4" />
      </Link>
  </Button>
  </AlertDescription>
</Alert>
```

- [ ] **Step 7: Run focused and existing dialog tests**

Run:

```bash
cd frontend
npm test -- src/components/ui/ui-variants.test.tsx \
  src/components/common/ConfirmDialog.test.tsx
```

Expected: PASS.

- [ ] **Step 8: Commit feedback surfaces**

```bash
git add frontend/src/components/ui/ui-variants.test.tsx \
  frontend/src/components/ui/dialog.tsx \
  frontend/src/components/ui/dropdown-menu.tsx \
  frontend/src/components/ui/popover.tsx \
  frontend/src/components/ui/tooltip.tsx \
  frontend/src/components/ui/tabs.tsx \
  frontend/src/components/ui/badge.tsx \
  frontend/src/components/ui/alert.tsx \
  frontend/src/components/ui/sonner.tsx \
  frontend/src/components/layout/SetupBanner.tsx
git commit -m "feat: standardize UI feedback surfaces"
```

## Task 4: Add Page Layout Primitives

**Files:**
- Create: `frontend/src/components/layout/PageContainer.tsx`
- Create: `frontend/src/components/layout/PageHeader.tsx`
- Create: `frontend/src/components/layout/PageHeader.test.tsx`

- [ ] **Step 1: Write failing layout tests**

Create `PageHeader.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { PageContainer } from './PageContainer'
import { PageHeader } from './PageHeader'

describe('page layout primitives', () => {
  it('renders title, description, breadcrumb, and actions', () => {
    render(
      <PageHeader
        eyebrow="Workspace"
        title="Notebooks"
        description="Organize research materials."
        actions={<button type="button">Create</button>}
      />
    )

    expect(screen.getByText('Workspace')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Notebooks' })).toBeInTheDocument()
    expect(screen.getByText('Organize research materials.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Create' })).toBeInTheDocument()
  })

  it('supports readable and wide page widths', () => {
    const { rerender } = render(<PageContainer width="readable">Body</PageContainer>)
    expect(screen.getByText('Body')).toHaveClass('max-w-4xl')

    rerender(<PageContainer width="wide">Body</PageContainer>)
    expect(screen.getByText('Body')).toHaveClass('max-w-7xl')
  })
})
```

- [ ] **Step 2: Run and verify failure**

Run:

```bash
cd frontend
npm test -- src/components/layout/PageHeader.test.tsx
```

Expected: FAIL because the two modules do not exist.

- [ ] **Step 3: Implement PageContainer**

Create:

```tsx
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
```

- [ ] **Step 4: Implement PageHeader**

Create:

```tsx
import * as React from 'react'
import { cn } from '@/lib/utils'

interface PageHeaderProps extends React.ComponentProps<'header'> {
  title: React.ReactNode
  description?: React.ReactNode
  eyebrow?: React.ReactNode
  actions?: React.ReactNode
}

export function PageHeader({
  title,
  description,
  eyebrow,
  actions,
  className,
  ...props
}: PageHeaderProps) {
  return (
    <header
      data-slot="page-header"
      className={cn(
        'flex flex-col gap-4 border-b border-border/70 pb-5 sm:flex-row sm:items-start sm:justify-between',
        className
      )}
      {...props}
    >
      <div className="min-w-0 space-y-1.5">
        {eyebrow && (
          <div className="text-xs font-semibold uppercase tracking-[0.12em] text-primary/80">
            {eyebrow}
          </div>
        )}
        <h1 className="text-2xl font-semibold tracking-tight text-foreground sm:text-[1.75rem]">
          {title}
        </h1>
        {description && (
          <div className="max-w-3xl text-sm leading-6 text-muted-foreground">
            {description}
          </div>
        )}
      </div>
      {actions && (
        <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto sm:justify-end">
          {actions}
        </div>
      )}
    </header>
  )
}
```

- [ ] **Step 5: Run layout tests**

Run:

```bash
cd frontend
npm test -- src/components/layout/PageHeader.test.tsx
```

Expected: PASS, 2 tests.

- [ ] **Step 6: Commit layout primitives**

```bash
git add frontend/src/components/layout/PageContainer.tsx \
  frontend/src/components/layout/PageHeader.tsx \
  frontend/src/components/layout/PageHeader.test.tsx
git commit -m "feat: add reusable page layout primitives"
```

## Task 5: Make the Application Shell Responsive

**Files:**
- Create: `frontend/src/components/layout/AppShell.test.tsx`
- Modify: `frontend/src/components/layout/AppShell.tsx`
- Modify: `frontend/src/components/layout/AppSidebar.tsx`
- Modify: `frontend/src/components/layout/AppSidebar.test.tsx`
- Modify: every `frontend/src/lib/locales/*/index.ts`

- [ ] **Step 1: Add mobile navigation translation keys**

Add these properties under `common` in every locale:

```ts
openNavigation: "Open navigation",
closeNavigation: "Close navigation",
navigationLabel: "Main navigation",
```

Use locale-appropriate translations. Required locale files are:

```text
bn-IN/index.ts
en-US/index.ts
fr-FR/index.ts
it-IT/index.ts
ja-JP/index.ts
pt-BR/index.ts
ru-RU/index.ts
zh-CN/index.ts
zh-TW/index.ts
```

- [ ] **Step 2: Write the failing AppShell mobile test**

Create `AppShell.test.tsx`:

```tsx
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { AppShell } from './AppShell'

vi.mock('./SetupBanner', () => ({
  SetupBanner: () => <div>Setup banner</div>,
}))

vi.mock('./AppSidebar', () => ({
  AppSidebar: ({
    mobileOpen,
    onMobileOpenChange,
  }: {
    mobileOpen: boolean
    onMobileOpenChange: (open: boolean) => void
  }) => (
    <aside data-open={mobileOpen}>
      <button onClick={() => onMobileOpenChange(false)}>Close navigation</button>
    </aside>
  ),
}))

describe('AppShell', () => {
  it('opens and closes mobile navigation', () => {
    render(<AppShell><div>Page body</div></AppShell>)

    const sidebar = screen.getByRole('complementary')
    expect(sidebar).toHaveAttribute('data-open', 'false')

    fireEvent.click(screen.getByRole('button', { name: /open navigation/i }))
    expect(sidebar).toHaveAttribute('data-open', 'true')

    fireEvent.click(screen.getByRole('button', { name: /close navigation/i }))
    expect(sidebar).toHaveAttribute('data-open', 'false')
  })
})
```

- [ ] **Step 3: Extend AppSidebar tests**

Replace the test file's navigation mock with a configurable function:

```tsx
const mockedPathname = vi.fn(() => '')

vi.mock('next/navigation', () => ({
  usePathname: () => mockedPathname(),
}))
```

Update the three existing `render(<AppSidebar />)` calls to:

```tsx
render(<AppSidebar mobileOpen={false} onMobileOpenChange={vi.fn()} />)
```

Then add:

```tsx
it('marks the active navigation item', () => {
  mockedPathname.mockReturnValue('/notebooks')
  render(<AppSidebar mobileOpen={false} onMobileOpenChange={vi.fn()} />)

  expect(screen.getByRole('link', { name: /notebooks/i })).toHaveAttribute(
    'aria-current',
    'page'
  )
})

it('closes mobile navigation after following a link', () => {
  const onMobileOpenChange = vi.fn()
  render(<AppSidebar mobileOpen onMobileOpenChange={onMobileOpenChange} />)

  fireEvent.click(screen.getByRole('link', { name: /notebooks/i }))
  expect(onMobileOpenChange).toHaveBeenCalledWith(false)
})
```

- [ ] **Step 4: Run shell/sidebar tests and verify failure**

Run:

```bash
cd frontend
npm test -- src/components/layout/AppShell.test.tsx \
  src/components/layout/AppSidebar.test.tsx
```

Expected: FAIL because `AppShell` has no mobile trigger and `AppSidebar` has no
controlled mobile props or active link semantics.

- [ ] **Step 5: Implement local mobile state in AppShell**

Update `AppShell`:

```tsx
'use client'

import { useState } from 'react'
import { Menu } from 'lucide-react'
import { AppSidebar } from './AppSidebar'
import { SetupBanner } from './SetupBanner'
import { Button } from '@/components/ui/button'
import { useTranslation } from '@/lib/hooks/use-translation'

export function AppShell({ children }: { children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false)
  const { t } = useTranslation()

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <AppSidebar
        mobileOpen={mobileOpen}
        onMobileOpenChange={setMobileOpen}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex h-14 shrink-0 items-center border-b border-border/70 bg-background/95 px-4 backdrop-blur md:hidden">
          <Button
            variant="ghost"
            size="icon"
            aria-label={t.common.openNavigation}
            onClick={() => setMobileOpen(true)}
          >
            <Menu className="size-5" />
          </Button>
          <span className="ml-3 text-sm font-semibold">Lumiton Omax</span>
        </div>
        <main className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <SetupBanner />
          {children}
        </main>
      </div>
    </div>
  )
}
```

- [ ] **Step 6: Convert AppSidebar into a controlled responsive drawer**

Add props:

```tsx
interface AppSidebarProps {
  mobileOpen: boolean
  onMobileOpenChange: (open: boolean) => void
}
```

Wrap the sidebar with a mobile overlay and use one responsive sidebar element:

```tsx
<>
  {mobileOpen && (
    <button
      type="button"
      aria-label={t.common.closeNavigation}
      className="fixed inset-0 z-40 bg-foreground/25 backdrop-blur-[2px] md:hidden"
      onClick={() => onMobileOpenChange(false)}
    />
  )}
  <aside
    aria-label={t.common.navigationLabel}
    className={cn(
      'app-sidebar fixed inset-y-0 left-0 z-50 flex h-full flex-col border-r',
      'transition-[width,transform] duration-200 md:static md:z-auto md:translate-x-0',
      mobileOpen ? 'translate-x-0' : '-translate-x-full',
      isCollapsed ? 'w-64 md:w-16' : 'w-64'
    )}
  >
    {sidebarHeader}
    {sidebarNavigation}
    {sidebarFooter}
  </aside>
</>
```

Extract the three existing direct-child blocks into local JSX constants named
`sidebarHeader`, `sidebarNavigation`, and `sidebarFooter` immediately before
the return statement. Move their current JSX without changing handlers or
business logic, then render the constants in the order shown above. This keeps
the responsive wrapper readable without duplicating the sidebar contents.

For every navigation `Link`:

```tsx
<Link
  href={item.href}
  aria-current={isActive ? 'page' : undefined}
  onClick={() => onMobileOpenChange(false)}
>
```

Replace the active button classes with:

```text
relative w-full gap-3 text-sidebar-foreground
before:absolute before:inset-y-2 before:left-0 before:w-0.5
before:rounded-full before:bg-transparent
data-active:bg-sidebar-accent data-active:text-sidebar-accent-foreground
data-active:before:bg-sidebar-primary
```

Set `data-active={isActive || undefined}` on the corresponding `Button` so
these selectors have an explicit state source.

Remove literal teal avatar colors and use
`bg-primary/12 text-primary`. Remove redundant explicit primary button colors
already supplied by the shared Button variant.

- [ ] **Step 7: Run shell and sidebar tests**

Run:

```bash
cd frontend
npm test -- src/components/layout/AppShell.test.tsx \
  src/components/layout/AppSidebar.test.tsx
```

Expected: PASS.

- [ ] **Step 8: Commit responsive navigation**

```bash
git add frontend/src/components/layout/AppShell.tsx \
  frontend/src/components/layout/AppShell.test.tsx \
  frontend/src/components/layout/AppSidebar.tsx \
  frontend/src/components/layout/AppSidebar.test.tsx \
  frontend/src/lib/locales/*/index.ts
git commit -m "feat: add responsive application navigation"
```

## Task 6: Adopt the Layout System on Representative Pages

**Files:**
- Modify: `frontend/src/app/(dashboard)/notebooks/page.tsx`
- Modify: `frontend/src/app/(dashboard)/transformations/page.tsx`
- Modify: `frontend/src/app/(dashboard)/settings/page.tsx`
- Modify: `frontend/src/app/(dashboard)/advanced/page.tsx`
- Modify: `frontend/src/app/(dashboard)/search/page.tsx`

- [ ] **Step 1: Add a static adoption check**

Extend `frontend/src/app/globals.test.ts`:

```ts
const representativePages = [
  'src/app/(dashboard)/notebooks/page.tsx',
  'src/app/(dashboard)/transformations/page.tsx',
  'src/app/(dashboard)/settings/page.tsx',
  'src/app/(dashboard)/advanced/page.tsx',
  'src/app/(dashboard)/search/page.tsx',
]

it('uses shared page layout primitives on representative pages', () => {
  for (const page of representativePages) {
    const source = readFileSync(join(process.cwd(), page), 'utf8')
    expect(source, page).toContain('PageContainer')
    expect(source, page).toContain('PageHeader')
  }
})
```

- [ ] **Step 2: Run and verify failure**

Run:

```bash
cd frontend
npm test -- src/app/globals.test.ts
```

Expected: FAIL because none of the representative pages imports both layout
primitives.

- [ ] **Step 3: Migrate the notebook page**

Replace the outer scroll/padding and heading with:

```tsx
<AppShell>
  <PageContainer className="space-y-6">
    <PageHeader
      title={t.notebooks.title}
      actions={
        <>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => refetch()}
            aria-label={t.common.refresh}
          >
            <RefreshCw className="size-4" />
          </Button>
          <Input
            id="notebook-search"
            name="notebook-search"
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            placeholder={t.notebooks.searchPlaceholder}
            autoComplete="off"
            aria-label={
              t.common.accessibility?.searchNotebooks || 'Search notebooks'
            }
            className="w-full sm:w-64"
          />
          <Button variant="outline" onClick={() => setAggregateDialogOpen(true)}>
            <Layers className="size-4" />
            聚合笔记本
          </Button>
          <Button onClick={() => setCreateDialogOpen(true)}>
            <Plus className="size-4" />
            {t.notebooks.newNotebook}
          </Button>
        </>
      }
    />
    <div className="space-y-8">
      {activeNotebookSection}
      {aggregatedNotebookSection}
      {archivedNotebookSection}
    </div>
  </PageContainer>
  <CreateNotebookDialog
    open={createDialogOpen}
    onOpenChange={setCreateDialogOpen}
  />
  <AggregateNotebookDialog
    open={aggregateDialogOpen}
    onOpenChange={setAggregateDialogOpen}
  />
</AppShell>
```

Extract the three existing `NotebookList` JSX blocks into local constants
named `activeNotebookSection`, `aggregatedNotebookSection`, and
`archivedNotebookSection`. Preserve every existing prop and conditional.
`t.common.refresh` already exists in all supported locales and must be used for
the icon-only refresh button.

- [ ] **Step 4: Migrate transformations, settings, and advanced pages**

Apply these exact mappings:

- Transformations: `PageContainer width="wide" className="space-y-6"`;
  `PageHeader title={t.transformations.title}
  description={t.transformations.desc}`; put the existing refresh button in
  `actions`; render the existing `Tabs` immediately after the header.
- Settings: `PageContainer width="readable" className="space-y-6"`;
  `PageHeader title={t.navigation.settings}`; put the existing refresh button
  in `actions`; render `SettingsForm` and `UserApprovalDashboard` after the
  header.
- Advanced: `PageContainer width="readable" className="space-y-6"`;
  `PageHeader title={t.advanced.title} description={t.advanced.desc}`; render
  `SystemInfo` and `RebuildEmbeddings` after the header.

Preserve every hook, tab value, form, and action handler.

- [ ] **Step 5: Migrate the fixed-height search page**

Use `PageContainer` with `scroll={false}`, `width="full"`, and an explicit
flex layout:

```tsx
<PageContainer
  width="full"
  scroll={false}
  className="flex h-full min-h-0 flex-col gap-5"
>
  <PageHeader
    className="shrink-0"
    title={t.searchPage.askAndSearch}
  />
  <Tabs
    value={activeTab}
    onValueChange={(value) => setActiveTab(value as 'ask' | 'search')}
    className="min-h-0 flex-1 space-y-6 overflow-hidden"
  >
    <div className="shrink-0 space-y-2">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {t.searchPage.chooseAMode}
      </p>
      <TabsList
        aria-label={t.common.accessibility.searchKB}
        className="w-full max-w-xl"
      >
        <TabsTrigger value="ask">
          <MessageCircleQuestion className="size-4" />
          {t.searchPage.askBeta}
        </TabsTrigger>
        <TabsTrigger value="search">
          <Search className="size-4" />
          {t('searchPage.search')}
        </TabsTrigger>
      </TabsList>
    </div>
    {askTabContent}
    {searchTabContent}
  </Tabs>
</PageContainer>
```

Extract the two existing `TabsContent` blocks into local constants
`askTabContent` and `searchTabContent` without modifying their children. Do not
change search state, persistence, model selection, or streaming logic.

- [ ] **Step 6: Run the adoption test**

Run:

```bash
cd frontend
npm test -- src/app/globals.test.ts
```

Expected: PASS.

- [ ] **Step 7: Run feature-adjacent tests**

Run:

```bash
cd frontend
npm test -- src/components/search/StreamingResponse.test.tsx \
  src/components/layout/PageHeader.test.tsx
```

Expected: PASS.

- [ ] **Step 8: Commit representative page adoption**

```bash
git add frontend/src/app/globals.test.ts \
  "frontend/src/app/(dashboard)/notebooks/page.tsx" \
  "frontend/src/app/(dashboard)/transformations/page.tsx" \
  "frontend/src/app/(dashboard)/settings/page.tsx" \
  "frontend/src/app/(dashboard)/advanced/page.tsx" \
  "frontend/src/app/(dashboard)/search/page.tsx"
git commit -m "feat: adopt shared page layout across core views"
```

## Task 7: Remove Remaining Global Style Conflicts

**Files:**
- Modify: `frontend/src/components/common/ThemeToggle.tsx`
- Modify: `frontend/src/components/common/LanguageToggle.tsx`
- Modify: `frontend/src/app/(dashboard)/notebooks/components/NotebookCard.tsx`
- Modify: `frontend/src/components/sources/SourceCard.tsx`
- Modify: other files returned by the audit command only when they contain
  legacy global helper classes or literal primary overrides.

- [ ] **Step 1: Audit legacy classes and literal palette usage**

Run:

```bash
cd frontend
rg -n "sidebar-menu-item|card-hover|scale-\\[|translateY|bg-(blue|indigo|amber|red|teal)-|text-(blue|indigo|amber|red|teal)-" src
```

Expected: matches include sidebar toggles, notebook/source cards, SetupBanner
or feature-specific semantic status colors.

- [ ] **Step 2: Add a failing static regression assertion**

Append to `globals.test.ts`:

```ts
it('does not use deprecated global interaction helper classes', () => {
  const files = [
    'src/components/common/ThemeToggle.tsx',
    'src/components/common/LanguageToggle.tsx',
    'src/app/(dashboard)/notebooks/components/NotebookCard.tsx',
    'src/components/sources/SourceCard.tsx',
  ]

  for (const file of files) {
    const source = readFileSync(join(process.cwd(), file), 'utf8')
    expect(source, file).not.toMatch(/\b(sidebar-menu-item|card-hover)\b/)
  }
})
```

- [ ] **Step 3: Run and verify failure**

Run:

```bash
cd frontend
npm test -- src/app/globals.test.ts
```

Expected: FAIL while the helper classes remain.

- [ ] **Step 4: Replace helper classes with semantic component variants**

For `NotebookCard`, replace the opening element with:

```tsx
<Card variant="interactive" className="group" onClick={handleCardClick}>
```

For `SourceCard`, add `variant="interactive"` to its existing `Card` opening
element and preserve its current props and handlers. Remove inline
`cursor: pointer` where the variant supplies it.

Remove `sidebar-menu-item` from theme/language toggles. Their shared Button
variants now own hover and motion behavior.

For literal color matches:

- Replace generic primary/action colors with semantic classes.
- Keep literal colors only where they represent domain data that has no
  semantic token.
- Replace AI insight/attention amber with `highlight` or `warning`.
- Replace destructive red with `destructive`.

- [ ] **Step 5: Run the regression test and audit again**

Run:

```bash
cd frontend
npm test -- src/app/globals.test.ts
rg -n "sidebar-menu-item|card-hover|scale-\\[|translateY" src
```

Expected: tests PASS; audit has no deprecated interaction helper matches.

- [ ] **Step 6: Run card-adjacent tests**

Run:

```bash
cd frontend
npm test -- src/components/source/SourceDetailContent.test.tsx
```

Expected: PASS.

- [ ] **Step 7: Commit integration cleanup**

```bash
git add frontend/src/app/globals.test.ts \
  frontend/src/components/common/ThemeToggle.tsx \
  frontend/src/components/common/LanguageToggle.tsx \
  "frontend/src/app/(dashboard)/notebooks/components/NotebookCard.tsx" \
  frontend/src/components/sources/SourceCard.tsx
git commit -m "refactor: remove legacy UI interaction styles"
```

## Task 8: Run Full Automated Verification

**Files:**
- Modify only files required to fix regressions caused by Tasks 1-7.

- [ ] **Step 1: Run frontend lint**

Run:

```bash
cd frontend
npm run lint
```

Expected: exit 0. Fix only errors introduced or exposed by this work; do not
perform unrelated refactors.

- [ ] **Step 2: Run the full frontend test suite**

Run:

```bash
cd frontend
npm test
```

Expected: all tests PASS.

- [ ] **Step 3: Run the production build**

Run:

```bash
cd frontend
npm run build
```

Expected: Next.js production build completes successfully with no TypeScript
errors.

- [ ] **Step 4: Inspect the final diff**

Run:

```bash
git diff --check
git status --short
git diff --stat main...HEAD
```

Expected: no whitespace errors; only approved design-system, shared-component,
layout, locale, representative-page, test, and documentation files changed.

- [ ] **Step 5: Commit verification fixes if needed**

If verification required code changes, stage only frontend source files:

```bash
git add frontend/src
git commit -m "fix: resolve warm UI integration regressions"
```

If no changes were required, do not create an empty commit.

## Task 9: Perform Browser and Accessibility Verification

**Files:**
- Modify only files required to fix observed regressions caused by this plan.

- [ ] **Step 1: Start the application using the repository's normal local stack**

Run the full development stack:

```bash
make dev
```

Expected: Docker Compose starts the database, API, and frontend. Confirm the
frontend URL printed by the command responds before opening it in Browser.

- [ ] **Step 2: Verify representative desktop pages**

Use the Browser plugin at a desktop viewport of approximately `1440x900`.
Check:

```text
/login
/notebooks
/sources
/search
/settings
```

From `/notebooks`, open the first available notebook card to verify its
workspace. From `/sources`, open the first available source row to verify its
detail page. If either list is empty, verify its empty state instead.

For each page verify:

- warm ivory/charcoal surface hierarchy;
- indigo primary actions and focus;
- amber only for insight/attention;
- no hover scaling;
- consistent 12px panel and 8px control geometry;
- no clipped actions or translated labels.

- [ ] **Step 3: Verify dark theme**

Switch to dark theme and repeat notebooks, search, and settings checks.
Expected:

- no pure-black canvas;
- cards remain distinguishable;
- indigo and amber are readable without glare;
- borders remain visible but low contrast;
- dialogs and menus inherit the dark warm surface.

- [ ] **Step 4: Verify tablet and mobile**

Check approximately `1024x768` and `390x844`.

Expected:

- desktop sidebar collapses cleanly;
- mobile menu trigger is visible below `768px`;
- drawer opens, traps no background pointer actions, and closes by overlay or
  navigation;
- page headers stack actions without overflow;
- search workspace remains operable;
- dialogs remain within viewport and scroll internally.

- [ ] **Step 5: Verify localization and keyboard behavior**

Check Chinese and English:

- sidebar labels;
- mobile navigation labels;
- page headers;
- notebook actions;
- dialog buttons.

Use keyboard navigation to verify visible focus on sidebar links, buttons,
form controls, tabs, dropdown items, and dialog close controls.

- [ ] **Step 6: Record browser evidence**

Capture screenshots for:

```text
notebooks-light-desktop
notebooks-dark-desktop
search-light-tablet
settings-dark-mobile
mobile-navigation-open
```

Save them under a temporary verification directory, not as committed product
assets.

- [ ] **Step 7: Re-run affected tests after visual fixes**

Run:

```bash
cd frontend
npm run lint
npm test
npm run build
```

Expected: all commands exit 0.

- [ ] **Step 8: Commit browser-found fixes if needed**

```bash
git add frontend/src
git commit -m "fix: polish responsive warm UI behavior"
```

Do not commit screenshots or create an empty commit.

## Completion Criteria

The implementation is complete when:

- `DESIGN.md` and semantic tokens define the approved visual system.
- Shared controls and floating surfaces use consistent warm styling.
- Amber is restricted to insight and attention semantics.
- AppShell and AppSidebar support desktop, collapsed, and mobile navigation.
- Representative pages use `PageContainer` and `PageHeader`.
- Legacy hover scaling and helper classes are removed from audited components.
- All locale files include new accessible navigation labels.
- Lint, full tests, and production build pass.
- Browser checks pass in light/dark, desktop/tablet/mobile, Chinese/English.
- No API, data-fetching, business workflow, or state-management behavior has
  changed.
