# Frontend Standards

These rules apply to frontend work under `web/`. They are subordinate to the root Opal Design System requirements in `../AGENTS.md`. Prefer Opal components, Opal `Text`, Opal `Button`, and icons from `web/src/icons/` over raw HTML, legacy components, or external UI libraries.

## Desktop-Only Scope

- This project targets desktop Web only unless the user explicitly requests mobile support in the current task.
- Use 1440px wide as the default design and validation viewport.
- Desktop layouts should work well from 1200px to 1920px.
- Do not design, implement, or QA mobile layouts.
- Do not add phone/tablet breakpoints such as `sm:` or mobile-first layout variants.
- Desktop-only breakpoint behavior for large screens is allowed when it improves 1200px+ layouts.
- Do not add mobile navigation, compact phone layouts, touch-only interaction patterns, or phone/tablet-specific UI behavior.

## Layout

- Use Grid or Flex for strict alignment.
- Use the project spacing scale consistently, especially 8px or 12px multiples such as 8, 16, 24, 32, and 48.
- Prefer stable, content-aware desktop layouts over fixed-width layouts that waste wide-screen space.
- Do not hard-code layout dimensions unless a fixed-format control truly requires it.
- Keep text, controls, progress indicators, and status labels visually separated so they never overlap or crowd each other.

## Components

- Use Opal and production refresh components before creating new primitives.
- Use card-style containers only for repeated entities, framed tools, or sections that genuinely need a contained surface.
- For data-heavy pages, prioritize scanability, information density, and clear hierarchy over decorative layout.
- Empty states, loading states, error states, and progress states must be visually distinct.

## Styling

- Use Tailwind CSS or CSS Modules according to the surrounding code.
- Use `gap-*`, `space-x-*`, and `space-y-*` for spacing between elements.
- Prefer padding over margin for component internals and container spacing.
- Use project design tokens for colors, borders, typography, and status indicators.
- Do not use standard Tailwind color palettes when project tokens are available.
- Chinese text should use comfortable line-height, typically 1.6 to 1.8 for paragraph-like content.

## Workflow

- For substantial redesigns, briefly outline the layout and component structure before editing.
- For small UI changes, implement directly.
- Validate desktop layout quality only unless mobile support is explicitly requested.
- Page-specific design briefs must live in a dedicated docs file or in the user's task prompt, not in this global frontend standards file.
