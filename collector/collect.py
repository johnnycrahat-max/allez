#!/usr/bin/env python3
"""Daily event collector for Allez.

Reads each source in sources.py, pulls out upcoming Lafayette-area events, tags them
Music & Culture / Food / Volunteer / Health & Wellness, merges duplicates, adds the
hand-maintained listings in manual_events.json, and writes docs/events.json, which the
app loads. If a source fails, its last good events are kept.

Two modes:
- free (default, no API key): reads the event data sites publish for search engines,
  plus a couple of simple page layouts, and sorts events with keyword rules.
  See free_extract.py.
- claude (when ANTHROPIC_API_KEY is set): Claude reads each page and tags events.
  Pages that haven't changed reuse earlier results, so Claude only reads what's new.

Usage:
  python3 collector/collect.py              # free mode, or claude mode if a key is set
  python3 collector/collect.py --mode free  # force free mode
  python3 collector/collect.py --check      # show what each source yields, change nothing
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib import robotparser
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
import free_extract  # noqa: E402
from sources import SOURCES  # noqa: E402

try:  # only needed in claude mode
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None

ROOT = Path(__file__).resolve().parent.parent
OUT_FILE = ROOT / "docs" / "events.json"
STATE_FILE = ROOT / "collector" / "state.json"
MANUAL_FILE = ROOT / "collector" / "manual_events.json"
HISTORY_FILE = ROOT / "collector" / "history.json"     # one summary per day, for the report chart
LAST_RUN_FILE = ROOT / "collector" / "last_run.json"   # details of the latest run, for the report

TZ = ZoneInfo("America/Chicago")
SHOW_DAYS = 28          # the app's longest date filter is "Next 4 Weeks"
EXTRACT_DAYS = 60       # extract further ahead so cached results stay useful as days pass
REEXTRACT_AFTER_DAYS = 7  # re-read unchanged pages weekly so new dates enter the window
MODEL = "claude-opus-5-5"
MAX_PAGE_CHARS = 150_000
USER_AGENT = "AllezEventsBot/1.0 (+https://johnnycrahat-max.github.io/allez/)"
HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
CATS = ["music", "food", "volunteer", "health"]

SYSTEM_PROMPT = """You extract upcoming events from web pages for Allez, a phone app that lists \
things to do in and around Lafayette, Louisiana. People use it to decide where to go this week, \
so accuracy matters more than coverage: an event with a wrong date or time sends someone to an \
empty venue.

Return every event on the page that falls inside the date range you are given and fits at \
least one of these categories:
- music: Music & Culture. Concerts, live music, dance and theater performances, film \
screenings and festivals, art talks and tours, book events, cultural and heritage festivals.
- food: Food & drink. Farmers markets, food trucks, food festivals, cook-offs, tastings, \
special dinners, restaurant pop-ups, community meals.
- volunteer: Ways to help. Volunteer shifts, service days, donation drives, blood drives.
- health: Health & Wellness. Fitness classes, yoga, pilates, group runs and races, walks, \
hikes, nature and birding outings, meditation and sound baths, blood drives, health fairs.

An event may have more than one category. Skip anything that fits none of them, such as \
spectator sports, business networking, trainings and certifications, private parties, and \
adults-only novelty shows.

Rules:
- Only include events in the Lafayette area: Lafayette Parish and towns within about 30 \
minutes (Broussard, Youngsville, Scott, Carencro, Duson, Milton, Maurice, Breaux Bridge, \
Arnaudville, St. Martinville, Abbeville, Opelousas). Set in_lafayette_area to false for \
anything else and it will be dropped.
- Many listings omit the year. Work it out from today's date and the weekday shown. If a \
date is ambiguous, pick the most likely one and explain the uncertainty in check_note.
- For a weekly or recurring event, list one entry for each date that falls in the range.
- A multi-day event (a festival, a run of performances) is one entry with start_date and \
end_date.
- Use 24-hour HH:MM times. If the page gives no time, use null. Never invent a time, price, \
venue or link.
- If performances have different times on different days, put them in time_note, for \
example "Thu & Fri 7 PM · Sat 2 PM & 7 PM".
- check_note: a short, plain sentence telling the reader what to confirm (a missing start \
time, conflicting times on the page, a date you inferred). Use null when the listing is clear.
- description: one or two plain sentences in your own words saying what the event is. No \
hype or exclamation marks.
- url: the event's own page, taken from the links shown as <https://...> next to the event. \
If there is none, use null.
- free: true only when the page says the event is free.
- highlight: true only for a notable one-off event a local would not want to miss (a major \
concert, a festival, an annual race). Most events are false.
- Gallery exhibitions and ongoing programs with no specific date: skip them."""

EVENT_SCHEMA = {
    "type": "object",
    "properties": {
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "end_date": {"type": ["string", "null"], "description": "YYYY-MM-DD for multi-day events, else null"},
                    "start_time": {"type": ["string", "null"], "description": "24-hour HH:MM, or null"},
                    "end_time": {"type": ["string", "null"], "description": "24-hour HH:MM, or null"},
                    "time_note": {"type": ["string", "null"]},
                    "venue": {"type": "string"},
                    "address": {"type": ["string", "null"]},
                    "town": {"type": "string"},
                    "in_lafayette_area": {"type": "boolean"},
                    "price": {"type": ["string", "null"]},
                    "free": {"type": "boolean"},
                    "description": {"type": "string"},
                    "url": {"type": ["string", "null"]},
                    "categories": {"type": "array", "items": {"type": "string", "enum": CATS}},
                    "highlight": {"type": "boolean"},
                    "check_note": {"type": ["string", "null"]},
                },
                "required": [
                    "title", "start_date", "end_date", "start_time", "end_time", "time_note",
                    "venue", "address", "town", "in_lafayette_area", "price", "free",
                    "description", "url", "categories", "highlight", "check_note",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["events"],
    "additionalProperties": False,
}

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def log(msg: str) -> None:
    print(msg, flush=True)


# ---------- fetching ----------

_robots: dict[str, robotparser.RobotFileParser | None] = {}


def robots_allows(url: str) -> bool:
    """Respect each site's robots.txt. A missing robots.txt allows everything."""
    p = urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in _robots:
        rp = robotparser.RobotFileParser()
        try:
            r = requests.get(base + "/robots.txt", headers=HEADERS, timeout=20)
            if r.status_code in (401, 403):
                rp.parse(["User-agent: *", "Disallow: /"])
            elif r.status_code >= 400:
                rp.parse([])
            else:
                rp.parse(r.text.splitlines())
        except requests.RequestException:
            rp.parse([])
        _robots[base] = rp
    return _robots[base].can_fetch(USER_AGENT, url)


def page_text(html: str, url: str) -> str:
    """Turn HTML into readable text, keeping links as <url> so Claude can cite them."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "iframe", "form", "header", "footer", "nav"]):
        tag.decompose()
    for a in soup.find_all("a", href=True):
        href = urljoin(url, a["href"])
        if href.startswith("http") and a.get_text(strip=True):
            a.append(f" <{href}>")
    lines = (re.sub(r"\s+", " ", line).strip() for line in soup.get_text("\n").splitlines())
    return "\n".join(line for line in lines if line)


def fill(url: str, today: dt.date) -> str:
    nxt = (today.replace(day=1) + dt.timedelta(days=32)).replace(day=1)
    return url.format(
        this_month=today.strftime("%B").lower(), next_month=nxt.strftime("%B").lower(),
        this_ym=today.strftime("%Y-%m"), next_ym=nxt.strftime("%Y-%m"),
    )


def fetch_source(source: dict, today: dt.date) -> tuple[list[tuple[str, str]], list[str]]:
    """Return ([(url, html), ...], problems). The list is empty if nothing could be read."""
    pages, problems = [], []
    for raw in source["pages"]:
        url = fill(raw, today)
        if not robots_allows(url):
            problems.append(f"{url}: blocked by robots.txt")
            continue
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
        except requests.RequestException as e:
            problems.append(f"{url}: {type(e).__name__}")
            continue
        if r.status_code != 200:
            problems.append(f"{url}: HTTP {r.status_code}")
            continue
        pages.append((url, r.text))
        time.sleep(1)  # be polite to small sites
    return pages, problems


def pages_as_text(pages: list[tuple[str, str]], problems: list[str]) -> str:
    """Combine pages into one text for Claude, keeping each under MAX_PAGE_CHARS."""
    parts = []
    for url, page_html in pages:
        text = page_text(page_html, url)
        if len(text) > MAX_PAGE_CHARS:
            problems.append(f"{url}: page text cut from {len(text):,} to {MAX_PAGE_CHARS:,} characters")
            text = text[:MAX_PAGE_CHARS]
        parts.append(f"=== PAGE: {url} ===\n{text}")
    return "\n\n".join(parts)


def read_free(source: dict, pages: list[tuple[str, str]], today: dt.date) -> list[dict]:
    """Read a source without AI, using the method named in its `free` setting."""
    how = source.get("free")
    if how == "jsonld":
        return free_extract.read_jsonld(source, pages)
    if how == "downtown":
        return free_extract.read_downtown(source, pages, today, page_text)
    if how == "weekly":
        return free_extract.read_weekly(source, today, SHOW_DAYS)
    return []


# ---------- extraction ----------

def extract(client: anthropic.Anthropic, source: dict, text: str, today: dt.date) -> list[dict]:
    until = today + dt.timedelta(days=EXTRACT_DAYS)
    prompt = (
        f"Today is {today.strftime('%A, %B %-d, %Y')} (America/Chicago).\n"
        f"Date range: {today.isoformat()} through {until.isoformat()}.\n"
        f"Source: {source['name']}. About this source: {source['hint']}\n\n"
        f"<pages>\n{text}\n</pages>"
    )
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=64000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": EVENT_SCHEMA}},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        message = stream.get_final_message()

    if message.stop_reason == "refusal":
        raise RuntimeError("Claude declined to process this page")
    if message.stop_reason == "max_tokens":
        raise RuntimeError("response was cut off (too many events on the page)")
    body = next((b.text for b in message.content if b.type == "text"), "")
    events = json.loads(body)["events"]
    log(f"    Claude found {len(events)} events "
        f"({message.usage.input_tokens:,} in / {message.usage.output_tokens:,} out tokens)")
    return events


# ---------- shaping for the app ----------

def to_app_event(ev: dict, source: dict, page_url: str) -> dict | None:
    """Validate one extracted event and convert it to the app's event format."""
    if not ev.get("in_lafayette_area"):
        return None
    cats = [c for c in CATS if c in ev.get("categories", [])]
    start_date, end_date = ev.get("start_date") or "", ev.get("end_date")
    if not cats or not DATE_RE.match(start_date) or not ev.get("title", "").strip():
        return None
    if end_date and (not DATE_RE.match(end_date) or end_date <= start_date):
        end_date = None
    start_time = ev.get("start_time") if TIME_RE.match(ev.get("start_time") or "") else None
    end_time = ev.get("end_time") if TIME_RE.match(ev.get("end_time") or "") else None

    title = ev["title"].strip()
    key = f"{source['id']}|{title.lower()}|{start_date}"
    out = {
        "id": "a" + hashlib.sha1(key.encode()).hexdigest()[:10],
        "cats": cats,
        "title": title,
        "start": f"{start_date}T{start_time}" if start_time else start_date,
        "venue": ev.get("venue") or ev.get("town") or "Lafayette area",
        "map": " ".join(x for x in [ev.get("address") or ev.get("venue"), ev.get("town"), "LA"] if x),
        "desc": ev.get("description", "").strip(),
        "source": source["name"],
        "url": ev.get("url") or page_url,
    }
    if not start_time:
        out["allDay"] = True
    if start_time and end_time and end_time > start_time:
        out["end"] = f"{start_date}T{end_time}"
    if end_date:
        out["endDate"] = end_date
    if ev.get("time_note"):
        out["timeNote"] = ev["time_note"]
    if ev.get("free"):
        out["free"] = True
    elif ev.get("price"):
        out["price"] = ev["price"]
    if ev.get("check_note"):
        out["verify"] = ev["check_note"]
    if ev.get("highlight"):
        out["featured"] = True
    return out


STOP_WORDS = {"the", "a", "an", "at", "of", "and", "annual", "with", "in", "on", "2026", "2027"}


def title_words(t: str) -> set[str]:
    words = re.sub(r"[^a-z0-9 ]+", " ", t.lower()).split()
    return {w for w in words if w not in STOP_WORDS and not re.fullmatch(r"\d+(st|nd|rd|th)", w)}


def same_event(a: str, b: str) -> bool:
    """Titles match when nearly all words of the shorter one appear in the longer one."""
    wa, wb = title_words(a), title_words(b)
    small = min(len(wa), len(wb))
    return small >= 2 and len(wa & wb) / small >= 0.75 or (wa == wb and small > 0)


def merge_duplicates(events: list[dict]) -> list[dict]:
    """Merge the same event listed by several sources (same day, matching titles)."""
    kept: list[dict] = []
    for ev in events:
        day = ev["start"][:10]
        twin = next((k for k in kept if k["start"][:10] == day and same_event(k["title"], ev["title"])), None)
        if twin is None:
            kept.append(ev)
            continue
        twin["cats"] = [c for c in CATS if c in twin["cats"] or c in ev["cats"]]
        if "endDate" in ev and "endDate" not in twin:
            twin["endDate"] = ev["endDate"]
        if twin.get("allDay") and not ev.get("allDay"):  # prefer the listing that has a time
            for k in ("start", "end", "allDay"):
                twin.pop(k, None)
            twin.update({k: ev[k] for k in ("start", "end", "allDay") if k in ev})
        twin["featured"] = twin.get("featured") or ev.get("featured")
        if not twin["featured"]:
            twin.pop("featured")
    return kept


def in_window(ev: dict, today: dt.date) -> bool:
    last_day = today + dt.timedelta(days=SHOW_DAYS)
    if ev.get("ongoing"):
        return not ev.get("until") or ev["until"] >= today.isoformat()
    start = ev["start"][:10]
    end = ev.get("endDate", start)
    return end >= today.isoformat() and start <= last_day.isoformat()


# ---------- main ----------

def choose_mode() -> str:
    if "--mode" in sys.argv:
        return sys.argv[sys.argv.index("--mode") + 1]
    return "claude" if os.environ.get("ANTHROPIC_API_KEY") else "free"


def keep_recently_seen(source: dict, events: list[dict], previous: list[dict], today: dt.date) -> list[dict]:
    """For sources that show a different selection each day (search pages), keep events
    seen in the last `sticky_days` days that are still upcoming."""
    days = source.get("sticky_days", 0)
    if not days:
        return events
    for e in events:
        e["seen"] = today.isoformat()
    ids = {e["id"] for e in events}
    for e in previous:
        seen = e.get("seen")
        if e["id"] not in ids and seen and (today - dt.date.fromisoformat(seen)).days <= days \
                and e.get("start", "")[:10] >= today.isoformat():
            events.append(e)
    return events


def check_sources() -> int:
    """--check: show what each source yields in free mode, without saving anything."""
    today = dt.datetime.now(TZ).date()
    for source in SOURCES:
        pages, problems = ([], []) if source.get("free") == "weekly" else fetch_source(source, today)
        if not source.get("free"):
            log(f"• {source['name']}: read only in claude mode")
            continue
        events = [e for e in read_free(source, pages, today) if in_window(e, today)]
        log(f"• {source['name']}: {len(events)} events in the next {SHOW_DAYS} days")
        for p in problems:
            log(f"    note: {p}")
        for e in events[:40]:
            log(f"    {e['start'][:16]:16}  {'/'.join(e['cats']):18}  {e['title'][:60]}")
    return 0


def main() -> int:
    if "--check" in sys.argv:
        return check_sources()
    mode = choose_mode()
    if mode not in ("free", "claude"):
        log("--mode must be free or claude")
        return 2
    if mode == "claude" and (anthropic is None or not os.environ.get("ANTHROPIC_API_KEY")):
        log("Claude mode needs the anthropic package and ANTHROPIC_API_KEY. Nothing was changed.")
        return 1

    now = dt.datetime.now(TZ)
    today = now.date()
    log(f"Collecting events in {mode} mode for {today.isoformat()}")
    client = anthropic.Anthropic() if mode == "claude" else None
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    report, collected = [], []

    for source in SOURCES:
        if mode == "free" and not source.get("free"):
            continue
        log(f"• {source['name']}")
        key = f"{mode}:{source['id']}"
        cached = state.get(key, {})
        needs_pages = not (mode == "free" and source.get("free") == "weekly")
        pages, problems = fetch_source(source, today) if needs_pages else ([], [])
        entry = {"name": source["name"], "ok": True, "notes": problems}

        if needs_pages and not pages:
            entry["ok"] = False
            log("    could not read any page; keeping last good events")
        elif mode == "free":
            try:
                events = read_free(source, pages, today)
                events = keep_recently_seen(source, events, cached.get("events", []), today)
                cached = {"events": events, "read_on": today.isoformat()}
                state[key] = cached
                log(f"    {len(events)} events")
            except Exception as e:  # a layout change on one site shouldn't stop the run
                entry["ok"] = False
                entry["notes"].append(f"reading failed: {type(e).__name__}: {e}")
                log(f"    reading failed ({e}); keeping last good events")
        else:
            text = pages_as_text(pages, problems)
            digest = hashlib.sha256(text.encode()).hexdigest()
            last = cached.get("extracted_on")
            fresh = last and (today - dt.date.fromisoformat(last)).days < REEXTRACT_AFTER_DAYS
            if cached.get("hash") == digest and fresh:
                log("    unchanged since last run; reusing events")
            else:
                try:
                    raw = extract(client, source, text, today)
                    page_url = fill(source["pages"][0], today)
                    events = [e for e in (to_app_event(r, source, page_url) for r in raw) if e]
                    cached = {"hash": digest, "extracted_on": today.isoformat(), "events": events}
                    state[key] = cached
                except (anthropic.APIError, RuntimeError, json.JSONDecodeError, KeyError) as e:
                    entry["ok"] = False
                    entry["notes"].append(f"extraction failed: {e}")
                    log(f"    extraction failed ({e}); keeping last good events")
        for p in problems:
            log(f"    note: {p}")

        source_events = [e for e in cached.get("events", []) if in_window(e, today)]
        entry["events"] = len(source_events)
        collected.extend(source_events)
        report.append(entry)

    if not any(r["ok"] for r in report):
        log("Every source failed. Leaving docs/events.json as it was.")
        return 1

    manual = [m for m in json.loads(MANUAL_FILE.read_text())["events"] if in_window(m, today)]
    dated_manual = [m for m in manual if not m.get("ongoing")]
    ongoing = [m for m in manual if m.get("ongoing")]
    # Exhibitions are listed once as "ongoing"; drop daily copies some sites publish.
    collected = [e for e in collected if not any(same_event(e["title"], m["title"]) for m in ongoing)]
    # Hand-maintained entries go first so their wording wins when a source lists the same event.
    before_merge = dated_manual + sorted(collected, key=lambda e: e["start"])
    events = merge_duplicates(before_merge) + ongoing
    merged_count = len(before_merge) + len(ongoing) - len(events)
    events.sort(key=lambda e: (bool(e.get("ongoing")), e.get("start", "")))
    previous = json.loads(OUT_FILE.read_text())["events"] if OUT_FILE.exists() else []

    output = {
        "updated": now.isoformat(timespec="minutes"),
        "today": today.isoformat(),
        "showThrough": (today + dt.timedelta(days=SHOW_DAYS)).isoformat(),
        "mode": mode,
        "sources": report,
        "events": events,
    }
    OUT_FILE.write_text(json.dumps(output, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    STATE_FILE.write_text(json.dumps(state, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    record_run(today, mode, report, events, previous, merged_count)
    log(f"Wrote {len(events)} events ({len(manual)} hand-maintained) to docs/events.json")
    return 0


def _key(e: dict) -> str:
    return f"{e['title'].lower()}|{e.get('start', e.get('ongoing', ''))[:10]}"


def record_run(today: dt.date, mode: str, report: list[dict], events: list[dict],
               previous: list[dict], merged: int) -> None:
    """Save today's numbers (history.json) and the details behind them (last_run.json)."""
    dated = [e for e in events if not e.get("ongoing")]
    old = {_key(e): e for e in previous if not e.get("ongoing")}
    new = {_key(e): e for e in dated}
    added = [e for k, e in new.items() if k not in old]
    # Gone before its date: may have been cancelled, renamed or moved.
    gone = [e for k, e in old.items() if k not in new and e.get("start", "")[:10] >= today.isoformat()]
    moved = []
    for k, e in new.items():
        before = old.get(k)
        if before and (before.get("start") != e.get("start") or before.get("venue") != e.get("venue")):
            moved.append({"title": e["title"], "was": f"{before.get('start')} · {before.get('venue')}",
                          "now": f"{e.get('start')} · {e.get('venue')}", "url": e.get("url")})
    timed = [e for e in dated if not e.get("allDay")]
    entry = {
        "date": today.isoformat(),
        "mode": mode,
        "total": len(dated),
        "ongoing": len(events) - len(dated),
        "by_category": {c: sum(1 for e in dated if c in e["cats"]) for c in CATS},
        "sources_ok": sum(1 for r in report if r["ok"]),
        "sources_total": len(report),
        "with_time_pct": round(100 * len(timed) / len(dated)) if dated else 0,
        "check_details": sum(1 for e in dated if e.get("verify")),
        "added": len(added), "gone": len(gone), "moved": len(moved), "merged": merged,
    }
    history = json.loads(HISTORY_FILE.read_text()) if HISTORY_FILE.exists() else []
    history = [h for h in history if h["date"] != entry["date"]] + [entry]
    HISTORY_FILE.write_text(json.dumps(history[-400:], indent=1) + "\n", encoding="utf-8")

    slim = lambda e: {k: e.get(k) for k in ("title", "start", "venue", "cats", "url", "verify", "source")}
    details = {
        "date": today.isoformat(),
        "sources": report,
        "dropped": dict(free_extract.DROPPED),
        "added": [slim(e) for e in added],
        "gone": [slim(e) for e in gone],
        "moved": moved,
        "needs_check": [slim(e) for e in dated if e.get("verify")],
    }
    LAST_RUN_FILE.write_text(json.dumps(details, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
