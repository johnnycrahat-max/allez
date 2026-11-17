# Allez

**Let's go.** A phone-friendly guide to what's happening around Lafayette, Louisiana, sorted into
four categories, each with its own color and section:

- Music & Culture
- Food
- Volunteer
- Health & Wellness

Live app: https://johnnycrahat-max.github.io/allez/

Events refresh automatically every morning from local event calendars (see **Daily event
updates** below).

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

## Daily event updates

Every morning at 5 AM Lafayette time (11:00 UTC), the **Update events** GitHub Action:

1. reads each source listed in `collector/sources.py`, following each site's robots.txt;
2. asks Claude to pull out upcoming Lafayette-area events and tag them Music & Culture, Food,
   Volunteer and/or Health & Wellness (pages that haven't changed reuse yesterday's results);
3. drops past, far-off and out-of-area events, merges duplicates listed by several sites, and
   adds the hand-maintained listings in `collector/manual_events.json`;
4. writes `docs/events.json` and commits it. GitHub Pages republishes within a minute.

If a source can't be read, its last good events are kept. If every source fails, the events file
is left unchanged, and GitHub emails you that the run failed.

### One-time setup

Add a Claude API key as a repository secret: **Settings → Secrets and variables → Actions → New
repository secret**, name `ANTHROPIC_API_KEY`. Create the key at console.anthropic.com, where you
can also set a monthly spending limit. The key is never visible to visitors or in the code.

### Running it by hand

- On GitHub: **Actions → Update events → Run workflow**.
- Locally: `pip install -r collector/requirements.txt`, then
  `ANTHROPIC_API_KEY=... python3 collector/collect.py`.
- To check which sources can be read without calling Claude: `python3 collector/collect.py --check`.

### Adding a source

Add an entry to `collector/sources.py` with the page URL and a one-line hint about what the page
lists, then run the workflow by hand.

### Hand-maintained listings

`collector/manual_events.json` holds exhibitions and volunteer roles with no single date, and
events that are only announced elsewhere. Dated entries drop off automatically once they're past.
