# FreshRoute — Design System

Design tokens, component specs, spacing, and conventions for the frontend.
Extends the existing `globals.css` token system.

---

## Color Palette

All colors use OKLCH so tints remain perceptually consistent across hue shifts.

### Existing tokens (keep)

| Token | Value | Use |
|---|---|---|
| `--bg` | `oklch(97.8% 0.008 82)` | Page background (warm paper) |
| `--bg-elev` | `oklch(99.6% 0.004 82)` | Card/panel surfaces |
| `--bg-elev-2` | `oklch(96% 0.012 78)` | Input backgrounds, hover states |
| `--line` | `oklch(88% 0.010 78)` | Borders |
| `--line-soft` | `oklch(93% 0.008 82)` | Dividers, subtle separators |
| `--fg` | `oklch(22% 0.020 55)` | Primary text |
| `--fg-muted` | `oklch(46% 0.022 55)` | Secondary text |
| `--fg-dim` | `oklch(62% 0.018 60)` | Labels, metadata |
| `--accent` | `oklch(52% 0.190 32)` | Deep rust — primary action, key number |
| `--accent-ink` | `oklch(99% 0.004 82)` | Text on accent backgrounds |
| `--accent-soft` | `oklch(94% 0.045 40)` | Accent tint |
| `--success` | `oklch(52% 0.140 155)` | Farm green — feasible mandi |
| `--danger` | `oklch(52% 0.220 25)` | Spoilage red — infeasible, high risk |

### New tokens (add to globals.css)

```css
:root {
  --warning:       oklch(68% 0.155 75);    /* amber — medium spoilage risk */

  --success-soft:  oklch(94% 0.040 155);   /* green tint — feasible card bg */
  --warning-soft:  oklch(95% 0.040 75);    /* amber tint — medium risk bg */
  --danger-soft:   oklch(95% 0.040 25);    /* red tint — infeasible card bg */

  --spoilage-low:  var(--success);         /* < 5% spoilage */
  --spoilage-mid:  var(--warning);         /* 5–20% spoilage */
  --spoilage-high: var(--danger);          /* > 20% spoilage */
}
```

---

## Typography

Fonts already loaded in `layout.tsx`: Fraunces (serif), Inter (sans), JetBrains Mono.

### Scale

| Name | Size | Font | Weight | Use |
|---|---|---|---|---|
| `decision` | `clamp(2rem, 6vw, 3.5rem)` | Fraunces | 500 | The key ₹/tonne number |
| `heading-1` | `clamp(1.5rem, 4vw, 2.25rem)` | Fraunces | 400/italic | Page titles |
| `heading-2` | `clamp(1.125rem, 2.5vw, 1.5rem)` | Fraunces | 500 | Section headings |
| `body` | `1rem` (16px) | Inter | 400 | Body text — minimum on mobile |
| `small` | `0.875rem` (14px) | Inter | 400/500 | Supporting text |
| `label` | `0.75rem` (12px) | Inter | 400 | Form labels, captions |
| `micro` | `0.6875rem` (11px) | Inter uppercase + tracking | 400 | Metadata, timestamps |

**Rule:** micro text (`font-size: 11px`) is permitted only with `tracking-[0.16em]` and `text-fg-dim`. Never use it for interactive elements.

---

## Spacing System (8px grid)

| Token | Value | Use |
|---|---|---|
| `space-1` | `0.25rem` (4px) | Icon gaps, tight nudges |
| `space-2` | `0.5rem` (8px) | Inline spacing |
| `space-3` | `0.75rem` (12px) | List item gaps |
| `space-4` | `1rem` (16px) | Standard padding |
| `space-5` | `1.25rem` (20px) | Card inner padding |
| `space-6` | `1.5rem` (24px) | Section margins |
| `space-8` | `2rem` (32px) | Large gaps |
| `space-12` | `3rem` (48px) | Section breaks |

---

## Breakpoints

| Name | Min width | Target device |
|---|---|---|
| `sm` | 640px | Large phone / small tablet |
| `md` | 768px | Tablet — desktop nav kicks in here |
| `lg` | 1024px | Desktop |
| `xl` | 1280px | Wide desktop |

Mobile-first: write base styles for 390px (Android mid-range), enhance upward.

---

## Touch Targets

**Minimum 48×48px** for all interactive elements on mobile.

```css
/* Tailwind helper class */
.touch-target {
  min-height: 48px;
  min-width: 48px;
}
```

Form inputs: `py-3 px-4` (≈48px height at 16px base).
Nav links: 48px height via `h-12`.
Buttons: `py-3 px-5` minimum.
Chips/filter pills: `py-2 px-4`.

---

## Component Specifications

### Panel

No change to existing implementation. Rounded 16px, subtle border + shadow.

### Button — Primary

```
Height:     48px (mobile), 40px (desktop)
Background: var(--accent)
Text:       var(--accent-ink), 14px Inter 600
Radius:     9999px (pill)
Padding:    py-3 px-5
Hover:      translateY(-1px)
Disabled:   opacity-60
```

### Button — Secondary

```
Height:     48px (mobile), 40px (desktop)
Background: transparent
Border:     1px solid var(--line)
Text:       var(--fg), 14px Inter 500
Radius:     9999px (pill)
Hover:      bg var(--bg-elev-2)
```

### SpoilageChip

A colored pill showing spoilage percentage.

```
Low  (< 5%):   bg var(--success-soft), text var(--success)   → "2% loss"
Mid  (5–20%):  bg var(--warning-soft), text var(--warning)   → "12% loss"
High (> 20%):  bg var(--danger-soft),  text var(--danger)    → "28% loss"
Radius: 9999px
Padding: py-1 px-2.5
Font: 12px Inter 500
```

### FreshnessBar

10-dot shelf-life indicator. Each dot represents 10% of remaining shelf life.

```
Filled dots: var(--success)
Empty dots:  var(--line)
Dot size: 8px circle
Gap: 4px
```

Example: 7-day shelf life, 4% spoilage = 9.6 of 10 dots filled → show 10 filled.

### RecommendCard

The centrepiece component.

```
Layout: vertical flex in Panel
Header: rank badge + mandi name + district, state
        + SpoilageChip (right-aligned)
Body:   big "₹X,XXX/tonne net" in decision type size
        + metadata strip: distance · transit time · trips
        + collapsible CostWaterfall (expand on tap)
Footer: two buttons — "Details" (secondary) + "Directions" (primary)

States:
  default:   white bg
  feasible:  subtle green left border (2px solid var(--success))
  warning:   amber left border
  infeasible: muted, danger left border, no CTA buttons
```

### CostWaterfall

Itemized deductions table inside RecommendCard detail view.

```
Rows: Gross revenue, Fuel, APMC commission, Cess, Entry fee,
      Labour, Weighment, Spoilage loss (if applicable)
Divider before: Net row (bold)
Each row: left label (fg-muted) + right amount (tabular)
Bar: thin 3px colored bar showing each item as % of gross
```

### BottomNav (mobile only, hidden at md+)

```
Height: 56px + safe area inset
Background: var(--bg-elev) / 95% with backdrop blur
Border top: 1px solid var(--line-soft)
5 tabs: icon (20px) + label (10px)
Active: accent color icon + underline indicator (2px)
Inactive: fg-dim icon
```

### LoadingCard (skeleton)

```
Same dimensions as RecommendCard
Content: animated shimmer using bg-gradient-to-r with line-soft colors
```

---

## Icon Library

Use **Lucide React** (already installed). Consistent stroke-width: 1.5.

| Icon | Lucide name | Use |
|---|---|---|
| Home | `Home` | Bottom nav |
| Find mandi | `Target` | Bottom nav + CTA |
| Prices | `BarChart2` | Bottom nav |
| Costs | `Calculator` | Bottom nav |
| More | `MoreHorizontal` | Bottom nav |
| Truck | `Truck` | Vehicle selector |
| Clock | `Clock` | Transit time |
| Rupee | use `₹` text | Price display |
| Spoilage | `Thermometer` | Freshness section |
| Warning | `AlertTriangle` | Infeasible/caveat |
| Location | `MapPin` | Origin/destination |
| Arrow | `ArrowUpRight` | Link indicator |
| Expand | `ChevronDown` | Collapsible toggle |
| Check | `CheckCircle2` | Feasible confirmation |
| X | `XCircle` | Infeasible indicator |

---

## Animation Guidelines

Prefer compositor-only properties. No layout-thrashing animations.

```
Card expand/collapse: max-height transition (careful) → prefer opacity + transform
Hover lift: translateY(-2px), duration 150ms, ease-out
Loading shimmer: background-position, duration 1.5s, linear, infinite
Chip color change: background-color, 150ms ease
```

Keep animations subtle. Farmers are outdoors; motion should convey state change, not delight.

Respect `prefers-reduced-motion`:
```css
@media (prefers-reduced-motion: reduce) {
  * { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }
}
```

---

## Accessibility

- WCAG AA contrast minimum: 4.5:1 for body text, 3:1 for large/bold text
- Focus visible: existing `outline: 2px solid var(--accent)` — keep
- Screen reader: all icons must have `aria-label` or `aria-hidden` if decorative
- Form inputs: all must have associated `<label>` elements
- SpoilageChip: color alone is never the only indicator — include text value
- Loading states: use `aria-busy` on the container, `aria-live="polite"` for results

---

## i18n (Hindi/English)

Use Next.js App Router i18n routing with `next-intl` or a minimal custom solution.

String keys follow this convention:
```
home.headline          → "Where your produce sells for more."
home.headline.hi       → "आपका माल सबसे ज़्यादा कहाँ बिकेगा।"
recommend.cta          → "Find mandis"
recommend.cta.hi       → "मंडी खोजें"
spoilage.chip.hi       → "%loss% नुकसान"
```

Language toggle: top-right of header on both mobile and desktop. Persists in `localStorage`.

Hindi text is ~15–20% longer than English equivalents. Test all layouts with Hindi strings before finalizing.
