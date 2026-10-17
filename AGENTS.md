# AGENTS.md

## Project purpose

This project renders a fixed-size watercolor weather dashboard from Open-Meteo data.

## Invariants

- Keep the final output exactly 800x480 pixels.
- Preserve the three-part upper layout: current text, large current icon, and six hourly tiles.
- Keep exactly six hourly entries at two-hour intervals.
- Keep exactly five future-day entries below the horizontal divider.
- Do not add a heading above the hourly tiles; their meaning is implied by the times.
- Preserve the muted ivory, blue-gray, lavender, ochre, and aqua palette.
- Preserve the icon naming convention: `assets/icons/wmo-{code}-{day|night}.png`.
- Do not replace Open-Meteo with a provider that requires credentials unless explicitly requested.

## Development guidance

- Keep runtime dependencies minimal. The network client intentionally uses Python's standard library.
- New visual elements must remain legible at the final 800x480 size.
- Use Pillow's high-quality Lanczos resampling for raster assets.
- Continue to support `--data-file` so rendering can be tested without network access.
- Handle malformed or incomplete weather payloads with a concise user-facing error.
- Do not modify or regenerate the bundled watercolor assets during ordinary code changes.

## Verification

Before handing off a change:

1. Install dependencies from `requirements.txt`.
2. Render once with live data or a saved Open-Meteo response.
3. Confirm the PNG is 800x480.
4. Inspect the image for clipping, missing icons, overlaps, and unreadable text.
5. Confirm all 56 bundled icon assets are still present.
