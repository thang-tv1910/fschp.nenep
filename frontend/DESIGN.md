# Design System: FSCHP FPT School

## 1. Visual Theme & Atmosphere
A clean school-operations dashboard with confident FPT orange accents, quiet white surfaces, precise grid rhythm, and soft motion. Density is balanced for daily staff use: scan-first tables, restrained cards, and clear upload flows.

## 2. Color Palette & Roles
- **Campus Canvas** (#F7F8FA) - primary page background.
- **Pure Surface** (#FFFFFF) - panels, forms, table surfaces.
- **Charcoal Ink** (#18181B) - primary text.
- **Slate Note** (#64748B) - metadata and helper text.
- **FPT Orange** (#F37021) - single primary accent for action, active navigation, focus.
- **Academic Blue** (#005BAC) - secondary informational accent only.
- **Success Green** (#16A34A) - success state.
- **Alert Red** (#DC2626) - destructive and error state.
- **Line Mist** (#E5E7EB) - borders and dividers.

## 3. Typography Rules
- **Display:** Geist, Satoshi, or Arial fallback. Compact, confident, no oversized marketing scale inside dashboards.
- **Body:** Geist or Arial fallback, minimum 14px, relaxed line-height.
- **Mono:** JetBrains Mono or Consolas for numbers, IDs, and timestamps.
- **Banned:** Inter as a primary brand choice, pure black, neon glow, generic decorative serif.

## 4. Component Stylings
- **Buttons:** FPT Orange primary fill, white text, 44px minimum touch target, tactile translate on active.
- **Cards/Panels:** 8px radius, thin Line Mist border, subtle shadow only when hierarchy needs it.
- **Inputs:** Label above, visible focus ring in FPT Orange, inline error below.
- **Tables:** Dense but readable, sticky headers where useful, status chips with muted fills.
- **Modals:** Focused sheet composition, clear destructive contrast, no nested cards.

## 5. Layout Principles
Use a fixed sidebar on desktop and single-column collapse on mobile. Keep page sections unframed; use cards only for repeated metrics and tools. Avoid horizontal scroll and never overlap text, buttons, or modal content.

## 6. Motion & Interaction
Use subtle opacity/transform transitions only. Active tabs and upload states can lift by 1px or fade in. Avoid distracting cinematic motion in operational workflows.

## 7. Anti-Patterns
No emojis in new UI, no pure black, no neon, no gradient text headers, no decorative blobs, no 3-column marketing card rows, no visible demo credentials, no localStorage tokens.
