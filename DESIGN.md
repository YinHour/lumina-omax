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
- Interactive cards use border, surface, and shadow changes without movement
- Amber badges and alerts mean insight or attention
- Floating surfaces share warm popover, 12px radius, border, and surface shadow
- New user-facing strings must be translated in every locale
