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

Every morning at 5 AM Lafayette time (11:00 UTC), the **Update events** GitHub Action runs
`collector/collect.py`, which:

1. reads each source listed in `collector/sources.py`, following each site's robots.txt;
2. pulls out upcoming Lafayette-area events and tags them Music & Culture, Food, Volunteer
   and/or Health & Wellness;
3. drops past, far-off and out-of-area events, merges duplicates listed by several sites, and
   adds the hand-maintained listings in `collector/manual_events.json`;
4. writes `docs/events.json` and commits it. GitHub Pages republishes within a minute.

If a source can't be read, its last good events are kept. If every source fails, the events file
is left unchanged, and GitHub emails you that the run failed.

### No API key needed

By default the collector runs **without AI and without any key** (`collector/free_extract.py`):

- Most sources publish their events as schema.org data, the format search engines read.
  The collector reads that directly.
- Downtown Lafayette's list is read from its page layout.
- Cajun Road Runners' weekly group runs come from the schedule written in `sources.py`.
- Events are sorted into categories with keyword rules (for example "yoga", "5K" → Health;
  "market", "dinner" → Food), plus each source's usual type. Edit the word lists at the top of
  `free_extract.py` to change how events are sorted, or the `SKIP` list to leave events out.

### Optional: Claude mode

If you add a Claude API key as a repository secret named `ANTHROPIC_API_KEY`
(**Settings → Secrets and variables → Actions**), the collector switches to Claude mode
automatically: Claude reads each page, writes short descriptions and tags events, which gives
better sorting and also covers sources without event data (such as Vitalant). Remove the secret
to switch back.

### Running it by hand

- On GitHub: **Actions → Update events → Run workflow**.
- Locally: `pip install -r collector/requirements.txt`, then `python3 collector/collect.py`.
- To see what each source yields without changing anything: `python3 collector/collect.py --check`.
- To force a mode: `--mode free` or `--mode claude`.

### Adding a source

Add an entry to `collector/sources.py` with the page URL, how to read it without AI (`free`), and
a one-line `hint` for Claude mode. Run `--check` to see what it finds.

### Hand-maintained listings

`collector/manual_events.json` holds exhibitions and volunteer roles with no single date, and
events that are only announced elsewhere. Dated entries drop off automatically once they're past.
