# B00-UI Design System — Pickleball SOA Arena

## 1. Art Direction
- **Concept**: Contemporary Athletic Club.
- **Principles**: Editorial asymmetric hierarchy, purposeful Pickleball photography, crisp court-inspired geometry, restrained surfaces, high-contrast operational clarity, and zero fabricated social proof or generic SaaS bloat.

## 2. Brand Identity
- **Original SVG Brand Mark**: `frontend/src/components/brand/BrandLogo.tsx` (`BrandMark`, `BrandLockup`) and `frontend/public/favicon.svg`.
- **Geometry**: Rounded athletic emblem combining a Pickleball paddle silhouette, non-volley ("kitchen") boundary line, and perforated ball.
- **Variants**: `lime` (on dark Court Green header/pass), `dark` (on Warm White), `light` (high-contrast neutral).

## 3. Color Tokens (`frontend/tailwind.config.js`)
| Token | Hex | Usage |
| :--- | :--- | :--- |
| `court` | `#142D26` | Primary brand surface, active selections, primary CTAs |
| `court-deep` | `#0D1F1A` | Footer, dark panels, camera scanner frame |
| `court-soft` | `#1E4237` | Hover states on dark surfaces |
| `ball-lime` | `#D9F45C` | Controlled accent for primary CTAs, active sidebar item, brand highlights |
| `warm-white` | `#F6F5EE` | Primary page canvas |
| `charcoal` | `#202521` | Primary body & heading ink |
| `court-muted` | `#64756B` | Secondary labels and metadata |
| `terracotta` | `#C96F48` | Section eyebrows, peak-hour indicators, location accents |

## 4. Typography (100% Locally Bundled, SIL OFL 1.1)
- **Display & Headings**: `@fontsource-variable/bricolage-grotesque` (`Bricolage Grotesque Variable`, Vietnamese subset included).
- **UI & Body**: `@fontsource/be-vietnam-pro` (weights `400`, `500`, `600`, `700`, Vietnamese subset included).
- **Operational Data (Codes, Timers, Prices, Dates)**: `@fontsource/jetbrains-mono` (weights `500`, `700`) with `.tabular-nums`.

## 5. Motion & Accessibility
- Subtle `150ms` transitions on interactive controls; disabled under `@media (prefers-reduced-motion: reduce)`.
- Visible `:focus-visible` outline (`#142D26`), semantic landmarks, `aria-pressed` slot states, and non-color status indicators.
