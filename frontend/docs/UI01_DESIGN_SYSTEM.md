# UI01 — Modern Pickleball Athletic Club Design System

## 1. Color Tokens (`frontend/tailwind.config.js`)

| Token | Hex | Usage |
| :--- | :--- | :--- |
| `court` | `#142D26` | Primary brand header, primary buttons, active tabs, selected slots |
| `court-deep` | `#0D1F1A` | Dark operational panels, QR scanner viewport, mobile drawer |
| `court-soft` | `#1E4237` | Hover states and subtle dark borders |
| `ball-lime` | `#D9F45C` | High-contrast accents, active nav pill, badges on dark `court` surfaces |
| `warm-white` | `#F6F5EE` | Primary page canvas |
| `charcoal` | `#202521` | Primary body & heading ink |
| `court-muted` | `#64756B` | Secondary labels & metadata |
| `terracotta` | `#C96F48` | Peak-hour (`16h–22h`) and outdoor court indicators |

## 2. Visual Asset Inventory

| Asset | Location | Source & License | Usage |
| :--- | :--- | :--- | :--- |
| `CourtEmblem` | `frontend/src/components/ui/CourtHeroGraphic.tsx` | Original inline SVG authored in UI01 | Brand emblem in `Navbar` |
| `CourtLinesBackdrop` | `frontend/src/components/ui/CourtHeroGraphic.tsx` | Original inline SVG authored in UI01 | Subtle court-line background in `BookingPage` hero |
| `lucide-react` icons | `package.json` (`^0.469.0`) | MIT License (existing dependency) | UI iconography across all pages |

## 3. Frontend-Only Rebuild & Startup Commands

```powershell
# Validate compose & rebuild ONLY web-frontend without touching backend containers
docker compose config --quiet
docker compose up -d --build --no-deps web-frontend
```
