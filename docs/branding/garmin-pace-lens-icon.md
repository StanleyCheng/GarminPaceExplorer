# GarminPaceLens icon

The user supplied `GarminPaceLens.png` on 2026-10-03. The original is a
1254 × 1254 RGBA PNG. `assets/branding/garmin-pace-lens-master.png` is a
byte-identical copy of that source.

All app icons use the supplied artwork, preserving its full canvas, colors,
lettering, rounded corners, and alpha channel. Exports only resize or encode
the image; they do not crop or redraw it.

| Export | Size | Use |
| --- | --- | --- |
| `viz/favicon.ico` | 16, 32, 48 px | Browser favicon |
| `viz/favicon-16x16.png` | 16 × 16 px | Browser favicon |
| `viz/favicon-32x32.png` | 32 × 32 px | Browser favicon |
| `viz/apple-touch-icon.png` | 180 × 180 px | Safari bookmark, home screen, dashboard logo |
| `viz/icons/garmin-pace-lens.png` | 512 × 512 px | App icon |

The dashboard uses the icon URL version `v=garmin-pace-lens-1` to refresh
cached icons after this branding change.

To reproduce the PNG exports with Pillow, open the master image and resize
the full RGBA canvas with `Image.Resampling.LANCZOS`. Save the ICO from the
same master with `sizes=[(16, 16), (32, 32), (48, 48)]`.
