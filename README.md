# Allez

**Let's go.** A phone-friendly guide to what's happening around Lafayette, Louisiana, sorted into
four categories, each with its own color and section:

- Music & Culture
- Food
- Volunteer
- Health & Wellness

Live app: https://johnnycrahat-max.github.io/allez/

This is a clickable prototype that uses real listings gathered on Nov 16, 2026. Automatic updates
from each venue's website are the next step.

## Brand colors

| Name | Hex |
|---|---|
| Acadiana Navy | `#092B51` |
| Festival Red | `#D51028` |
| Sunshine Gold | `#FFBC00` |
| Warm White | `#FAF9F6` |

Logo files are in `brand/` (full-size wordmark and app icon).

## Files

- `docs/` is the public website that GitHub Pages serves, including app icons and the QR code.
- `prototype/allez.html` is the source page. After editing it, run `python3 build_site.py` to
  rebuild `docs/index.html`.
- `make_qr.py` makes a QR code for the public link: `python3 make_qr.py <url>`. It writes
  `docs/qr-code.png` and `docs/qr-code.svg`.

## Publishing with GitHub Pages

GitHub Pages serves the **main** branch's **/docs** folder (Settings → Pages). Changes go live
about a minute after they're merged into `main`.
