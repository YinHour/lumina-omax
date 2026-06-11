# Warm Research Workspace UI Design

**Status:** Approved
**Date:** 2026-06-10
**Scope:** First-pass global UI unification for the Lumiton Omax frontend

## 1. Objective

Create a coherent, warm, restrained research workspace across the application
without changing existing business workflows, API behavior, state management,
or page information architecture.

The first pass is design-token driven and incremental. It establishes the
visual foundation, updates the global application shell, and standardizes
shared UI primitives. Feature-specific redesigns for notebooks, sources,
search, chat, podcasts, and transformations will follow as separate projects.

## 2. Design Direction

The approved direction is a **warm, restrained research workspace**:

- Warm and thoughtful rather than cold or overtly technical.
- Structured and efficient rather than decorative.
- Moderately compact, with enough spacing to clarify hierarchy.
- Modern sans-serif typography throughout the interface.
- Restrained soft depth: 12px cards, 8px controls, thin borders, and light
  shadows.
- Low-saturation indigo as the primary interaction color.
- Amber as a limited secondary accent for AI insight and attention states.

The visual system should support sustained reading and research while
preserving the efficiency expected from a professional productivity tool.

## 3. Implementation Strategy

Use semantic design tokens and migrate the interface progressively:

1. Define the visual rules and semantic tokens.
2. Update global light and dark theme values.
3. Standardize shared Shadcn/Radix primitives.
4. Update the application shell and sidebar.
5. Add reusable page layout primitives.
6. Repair visual inconsistencies exposed by the global changes.
7. Verify accessibility, responsive behavior, themes, and localization.

Do not create a parallel legacy theme. Do not perform a global CSS-only
reskin. Component APIs should remain stable unless a narrowly scoped addition
is needed for consistent variants.

## 4. Design Tokens

### 4.1 Color Roles

Colors must be consumed through semantic roles rather than page-level literal
values.

| Role | Purpose |
| --- | --- |
| `background` | Warm ivory application canvas |
| `foreground` | Warm charcoal primary text |
| `card` / `surface` | Cards, panels, sidebar, and elevated content |
| `popover` | Menus, tooltips, popovers, and dialogs |
| `primary` | Low-saturation indigo for primary actions and selection |
| `primary-foreground` | Accessible text and icons on primary surfaces |
| `secondary` | Quiet neutral controls and grouped surfaces |
| `accent` | Hovered and selected neutral surfaces |
| `highlight` | Amber for AI insight, important notice, and processing states |
| `muted` | Low-emphasis surfaces |
| `muted-foreground` | Supporting text and metadata |
| `border` / `input` | Low-contrast warm gray boundaries |
| `ring` | Indigo keyboard focus indication |
| `success` | Successful completion only |
| `warning` | Caution requiring user awareness |
| `destructive` | Errors and destructive actions only |

Amber must not replace the primary action color. It is reserved for:

- AI-generated insight or recommendation.
- Important but non-destructive notices.
- Processing or attention states.
- Small brand details where they do not compete with task actions.

### 4.2 Light Theme

- Page canvas: warm ivory rather than pure white.
- Cards and panels: warm white with subtle contrast against the canvas.
- Sidebar: a slightly deeper warm neutral than the page canvas.
- Text: charcoal with a subtle brown undertone.
- Borders: visible without creating a dense grid.
- Indigo: muted enough for long sessions while retaining clear affordance.

### 4.3 Dark Theme

- Page canvas: deep warm gray, not pure black.
- Cards and panels: slightly lighter charcoal surfaces.
- Text: warm off-white.
- Indigo: raised in lightness to maintain accessible contrast.
- Amber: reduced in saturation to avoid glare.
- Borders: established primarily through controlled lightness differences.

Both themes must preserve the same hierarchy and component meaning.

### 4.4 Geometry and Depth

- Card and panel radius: approximately `12px`.
- Inputs and buttons: approximately `8px`.
- Small badges and compact controls may use a smaller proportional radius.
- Use thin borders as the default separation mechanism.
- Use light shadows only for elevated or interactive surfaces.
- Avoid glassmorphism, heavy gradients, neon colors, and deep drop shadows.

### 4.5 Spacing and Density

Use the existing Tailwind scale around a core rhythm of:

`4px`, `8px`, `12px`, `16px`, `24px`, and `32px`.

The interface should remain moderately compact:

- Controls retain efficient heights.
- Related controls remain visually grouped.
- Page sections receive clearer vertical separation.
- Empty space communicates hierarchy rather than decoration.
- Large cards and oversized dashboard tiles are avoided.

### 4.6 Typography

Use modern sans-serif typography throughout Chinese and Latin interfaces.

Define four clear levels:

1. Page title.
2. Section title.
3. Body and control text.
4. Supporting description and metadata.

Hierarchy should rely on size, weight, color, and spacing. Avoid adding a serif
font in the first pass. Text must remain stable across all supported locales.

### 4.7 Motion

- Standard transitions: `150-220ms`.
- Prefer color, border, opacity, and subtle shadow changes.
- Remove hover scaling from navigation items and cards.
- Avoid pronounced translation or bounce effects.
- Respect `prefers-reduced-motion`.

## 5. Global Application Framework

### 5.1 Application Shell

`AppShell` remains the common layout boundary. The redesign should:

- Apply the warm application canvas.
- Preserve the fixed-height workspace behavior.
- Keep system and setup notices above page content.
- Provide consistent content overflow behavior.
- Support desktop sidebar, collapsed sidebar, and mobile navigation.

### 5.2 Sidebar

Retain the current information architecture and collapse behavior.

Update:

- Brand area alignment and spacing.
- Navigation group labels.
- Primary create action.
- Selected navigation state.
- Hover, focus, and pressed states.
- Bottom utility and account controls.
- Tooltip presentation in collapsed mode.

The selected item should use a quiet indigo-tinted surface and a clear marker.
It must not depend on scaling or a heavy shadow. Icons remain Lucide icons,
normally at `16px`.

### 5.3 Page Container and Header

Introduce reusable layout primitives:

- `PageContainer`: responsive page padding and optional readable max width.
- `PageHeader`: optional breadcrumb, title, description, primary actions, and
  secondary actions.

The header must support:

- One-line desktop layouts where space permits.
- Wrapped actions at medium widths.
- Stacked title and action regions on mobile.
- Long translated labels without clipping.

Feature pages will adopt these primitives progressively. The first pass should
replace repeated page-shell markup where it is low risk, without redesigning
feature information architecture.

### 5.4 Global Notices

Setup, migration, connection, and system notices should share a common visual
language:

- Consistent placement at the top of the workspace.
- Clear severity and action hierarchy.
- Amber only for attention or processing states.
- Red only for failures requiring corrective action.

## 6. Shared Component Design

The following shared components are first-pass priorities.

### 6.1 Button

Standardize:

- Primary, secondary, outline, ghost, and destructive variants.
- Control heights and icon spacing.
- Hover, active, focus-visible, disabled, and loading states.
- Icon-only hit areas and accessible labels.

Primary buttons use indigo. Amber is not a general button variant.

### 6.2 Card

Support explicit visual states:

- Default.
- Clickable.
- Selected.
- Highlighted insight.

Clickable cards change border, surface, or shadow subtly. They must not scale
on hover. Card content spacing should be consistent across features.

### 6.3 Form Controls

Unify `Input`, `Textarea`, `Select`, checkbox, and radio controls:

- Heights, padding, labels, descriptions, and error messages.
- Indigo focus-visible ring.
- Accessible error and disabled states.
- Warm neutral backgrounds in both themes.

### 6.4 Dialog and Floating Surfaces

Unify dialogs, dropdowns, popovers, and tooltips:

- Border, radius, shadow, and warm surfaces.
- Consistent dialog header, body, and footer spacing.
- Clear primary and secondary footer actions.
- Predictable mobile sizing and scrolling.
- Existing Radix focus management and keyboard behavior remain intact.

### 6.5 Tabs, Badges, Alerts, and Toasts

- Tabs use either a restrained underline or quiet selected surface.
- Badges communicate category and state without excessive color.
- Alerts distinguish neutral information, AI insight, warning, success, and
  destructive states.
- Toasts share the same semantic status colors and typography.

## 7. Responsive Behavior

### Desktop: `>= 1280px`

- Full sidebar available.
- Standard content margins and page header layout.
- Workspace panels retain efficient information density.

### Tablet: `768px-1279px`

- Sidebar can collapse.
- Page actions may wrap.
- Cards and forms reflow without reducing hit-target size.

### Mobile: `< 768px`

- Sidebar becomes an accessible drawer.
- Page title, description, and actions stack vertically.
- Dialogs and menus remain within the viewport.
- Complex workspaces preserve operability using explicit panel switching or
  horizontal overflow as appropriate; this first pass does not redesign those
  workflows.

## 8. Accessibility and Localization

- Primary text and controls must meet WCAG AA contrast.
- Keyboard focus must always be visible.
- Color must not be the only state indicator.
- Icon-only controls require accessible names.
- Motion respects reduced-motion preferences.
- All new user-facing text uses the existing i18n system.
- Test long English labels and supported CJK locales for clipping and wrapping.

## 9. Testing and Validation

### Automated

- Preserve existing component and page tests.
- Add or update focused tests for shared variants and sidebar interaction.
- Verify class/state behavior for selected, disabled, destructive, and
  focus-visible states where practical.
- Run frontend lint, tests, and production build.

### Browser Verification

Verify representative pages in both light and dark themes:

- Login.
- Notebook list.
- Notebook workspace.
- Sources list and source detail.
- Search.
- Settings.

Check desktop, tablet, and mobile widths. Verify both Chinese and English for
navigation, page headers, dialogs, and action groups.

### Acceptance Criteria

- Global surfaces, typography, controls, and navigation feel like one system.
- Light and dark themes have no obvious visual discontinuities.
- Interactive states are distinct and keyboard accessible.
- No existing business flow, API request, or state behavior changes.
- Existing tests pass, with targeted coverage added for changed shared
  behavior.
- Key pages remain usable across the defined breakpoints and locales.

## 10. Delivery Phases

### Phase 1: Foundation

- Add the project `DESIGN.md` implementation reference.
- Define semantic color, radius, spacing, shadow, typography, and motion rules.
- Update `globals.css` light and dark theme tokens.

### Phase 2: Shared Components

- Update Button, Card, form controls, Dialog, Tabs, Badge, Alert, Toast,
  Dropdown, Tooltip, and Popover.
- Preserve public APIs where possible.
- Add narrowly scoped variants only where semantic reuse requires them.

### Phase 3: Global Framework

- Update AppShell and AppSidebar.
- Introduce PageContainer and PageHeader.
- Standardize global notices.

### Phase 4: Integration Repairs

- Correct obvious spacing, contrast, and layout issues caused by the shared
  changes.
- Progressively adopt PageHeader on representative pages.
- Do not restructure feature-specific workflows.

### Phase 5: Verification

- Run lint, tests, and build.
- Perform browser checks across themes, breakpoints, and languages.
- Record remaining feature-specific redesign work for later projects.

## 11. Out of Scope

The first pass does not include:

- Redesigning notebook, source, search, chat, podcast, or transformation
  information architecture.
- Changing API behavior, data fetching, Zustand stores, or TanStack Query
  behavior.
- Adding a compact/comfortable density preference.
- Introducing serif typography.
- Replacing Lucide icons.
- Adding a parallel legacy/new theme switch.
- Reproducing another product's branded interface.

## 12. Follow-Up Projects

After the global system is stable, plan separate redesigns for:

1. Notebook list and notebook workspace.
2. Sources list, source creation, and source detail.
3. Search and AI response presentation.
4. Chat and research context controls.
5. Podcasts, transformations, settings, and advanced administration.

Each follow-up must reuse the semantic tokens and shared components established
by this design.
