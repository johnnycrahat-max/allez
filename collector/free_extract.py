"""Read events without AI (no API key needed).

Three readers:
- jsonld:   events published as schema.org data (the format search engines read),
            used by Moncus Park, the AcA, the Hilliard, Lafayette Travel, Eventbrite
            and the race calendar.
- downtown: Downtown Lafayette's event list, read from its consistent page layout.
- weekly:   fixed weekly schedules written in sources.py (Cajun Road Runners).

Events are sorted into categories by keyword rules plus each source's usual type.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import re
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

TZ = ZoneInfo("America/Chicago")
CATS = ["music", "food", "volunteer", "health"]

# ---------- category rules ----------
# Matched as whole words against the title, venue and description (lowercased).
KEYWORDS = {
    "health": [
        "yoga", "pilates", "zumba", "fitness", "workout", "bootcamp", "boot camp", "run", "runs",
        "running", "runners", "5k", "10k", "half marathon", "marathon", "trot", "race", "walk",
        "walks", "hike", "hikes", "hiking", "bike ride", "cycling", "birding", "bird walk",
        "meditation", "sound bath", "tai chi", "wellness", "blood drive", "health fair",
        "stretch", "kayak", "paddle", "nature walk", "mom walks",
    ],
    "food": [
        "food", "foodies", "farmers market", "artisans market", "food truck", "food trucks",
        "dinner", "brunch", "lunch", "tasting", "wine", "beer", "brewery", "brewing", "cocktail",
        "cocktails", "crawfish", "gumbo", "boudin", "cook-off", "cookoff", "culinary", "chef",
        "supper", "bbq", "barbecue", "tapas", "bakery", "coffee", "feast", "potluck", "pop-up bar",
        "oyster", "seafood", "jambalaya", "recipe", "christmas market", "holiday market",
    ],
    "volunteer": [
        "volunteer", "volunteers", "volunteering", "service day", "day of service", "donation drive",
        "food drive", "toy drive", "coat drive", "clothing drive", "blood drive", "cleanup",
        "clean-up", "clean up", "habitat for humanity", "bell ringing", "bell ringers",
        "giving back", "kindness",
    ],
    "music": [
        "concert", "music", "musical", "band", "zydeco", "jazz", "blues", "symphony", "orchestra",
        "choir", "dj", "festival", "fest", "theater", "theatre", "dance", "danse", "ballet", "film",
        "films", "movie", "movies", "screening", "cinema", "art", "arts", "artist", "artists",
        "gallery", "exhibition", "museum", "book", "books", "author", "poetry", "storytelling",
        "culture", "cultural", "heritage", "comedy", "opera", "songwriter", "performance",
        "accordion", "fiddle", "cajun music", "creole", "artwalk", "zine", "lecture", "talk",
        "tour", "language café", "language cafe", "craft", "crafts", "concert series",
    ],
}
# Events with these words are left out: they fit none of the app's categories.
SKIP = [
    "training", "certification", "servsafe", "networking", "job fair", "career fair", "tryout",
    "tryouts", "webinar", "wrestling", "basketball", "football", "baseball", "softball",
    "volleyball", "soccer", "free parking", "evaluator", "private event", "birthday party",
    "virtual", "online",
]
FEATURE_WORDS = ["festival", "trot", "marathon", "christmas market", "festival of lights", "parade"]

AREA_TOWNS = {
    "lafayette", "broussard", "youngsville", "scott", "carencro", "duson", "milton", "maurice",
    "breaux bridge", "arnaudville", "st. martinville", "st martinville", "saint martinville",
    "abbeville", "opelousas", "new iberia", "sunset", "grand coteau", "cecilia", "rayne",
    "crowley", "eunice", "church point",
}


def _has(text: str, word: str) -> bool:
    return re.search(r"(?<![a-z0-9])" + re.escape(word) + r"(?![a-z0-9])", text) is not None


def categorize(title: str, venue: str, desc: str, default: list[str] | None) -> list[str]:
    """Return the event's categories, or [] if it should be left out."""
    head = f"{title} {venue}".lower()
    body = f"{head} {desc}".lower()
    if any(_has(head, w) for w in SKIP):
        return []
    # Title and venue decide first; the description only fills in when they say nothing.
    cats = [c for c in CATS if any(_has(head, w) for w in KEYWORDS[c])]
    if not cats:
        cats = [c for c in CATS if any(_has(body, w) for w in KEYWORDS[c])]
    if not cats and default:
        cats = list(default)
    return cats


# ---------- shared helpers ----------

def clean(text: str | None, limit: int = 0) -> str:
    """Strip HTML and extra spaces; optionally shorten to whole sentences under `limit`."""
    if not text:
        return ""
    text = BeautifulSoup(html.unescape(str(text)), "html.parser").get_text(" ")
    text = re.sub(r"\s+", " ", text).strip()
    if limit and len(text) > limit:
        cut = text[:limit]
        end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
        text = cut[: end + 1] if end > 60 else cut.rsplit(" ", 1)[0] + "…"
    return text


def make_event(source: dict, title: str, start: dt.datetime | dt.date, end: dt.datetime | dt.date | None,
               venue: str, town: str, address: str, desc: str, url: str, cats: list[str],
               price: str | None = None, free: bool = False, verify: str | None = None) -> dict:
    is_dt = isinstance(start, dt.datetime)
    start_date = start.date() if is_dt else start
    ev = {
        "id": "f" + hashlib.sha1(f"{source['id']}|{title.lower()}|{start_date}".encode()).hexdigest()[:10],
        "cats": cats,
        "title": title,
        "start": start.strftime("%Y-%m-%dT%H:%M") if is_dt else start.isoformat(),
        "venue": venue or town or "Lafayette area",
        "map": " ".join(x for x in [address or venue, town, "LA"] if x),
        "desc": desc or f"Listed by {source['name']}.",
        "source": source["name"],
        "url": url,
    }
    if not is_dt:
        ev["allDay"] = True
    if end is not None:
        end_date = end.date() if isinstance(end, dt.datetime) else end
        if end_date > start_date:
            ev["endDate"] = end_date.isoformat()
        elif is_dt and isinstance(end, dt.datetime) and end > start:
            ev["end"] = end.strftime("%Y-%m-%dT%H:%M")
    if free:
        ev["free"] = True
    elif price:
        ev["price"] = price
    if verify:
        ev["verify"] = verify
    if any(_has(title.lower(), w) for w in FEATURE_WORDS):
        ev["featured"] = True
    return ev


# ---------- reader 1: schema.org event data ----------

def _walk(obj):
    """Yield every schema.org Event object inside a JSON-LD document."""
    if isinstance(obj, list):
        for o in obj:
            yield from _walk(o)
    elif isinstance(obj, dict):
        t = obj.get("@type")
        types = t if isinstance(t, list) else [t]
        if any(isinstance(x, str) and x.endswith("Event") for x in types):
            yield obj
        for k, v in obj.items():
            if k != "superEvent" and isinstance(v, (list, dict)):
                yield from _walk(v)


def _parse_when(value: str | None, offset_applied_twice: bool = False):
    """Parse a schema.org date/time into a local date (no time) or local datetime.

    offset_applied_twice: the site subtracts the time-zone offset from its local times
    and then labels them with that offset again (the AcA does this: a 7:30 PM show
    appears as 13:30-06:00). Adding the offset back gives the real local time.
    """
    if not value or not isinstance(value, str):
        return None
    value = value.strip()
    try:
        if len(value) == 10:
            return dt.date.fromisoformat(value)
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo:
        if offset_applied_twice:
            return parsed.replace(tzinfo=None) - parsed.utcoffset()
        local = parsed.astimezone(TZ).replace(tzinfo=None)
        # A converted time in the middle of the night usually means the site labeled a
        # local clock time with the wrong offset; keep the clock time as written.
        parsed = parsed.replace(tzinfo=None) if local.hour < 5 else local
    if parsed.hour == 0 and parsed.minute == 0:  # midnight usually means "no time given"
        return parsed.date()
    return parsed


def _place(loc) -> tuple[str, str, str, str]:
    """Return (venue, street address, town, state) from a schema.org location."""
    if isinstance(loc, list):
        loc = loc[0] if loc else None
    if isinstance(loc, str):
        return clean(loc), "", "", ""
    if not isinstance(loc, dict):
        return "", "", "", ""
    addr = loc.get("address")
    street = town = region = ""
    if isinstance(addr, dict):
        street = clean(addr.get("streetAddress"))
        town = clean(addr.get("addressLocality"))
        region = clean(addr.get("addressRegion"))
    elif isinstance(addr, str):
        street = clean(addr)
    return clean(loc.get("name")), street, town, region


def _price(offers) -> tuple[str | None, bool]:
    offers = offers if isinstance(offers, list) else [offers] if offers else []
    prices = []
    for o in offers:
        if not isinstance(o, dict):
            continue
        for key in ("price", "lowPrice", "highPrice"):
            try:
                prices.append(float(str(o.get(key)).replace("$", "").replace(",", "")))
            except (TypeError, ValueError):
                pass
    if not prices:
        return None, False
    lo, hi = min(prices), max(prices)
    if hi == 0:
        return None, True
    fmt = lambda p: f"${p:,.0f}" if p == int(p) else f"${p:,.2f}"
    return (fmt(lo) if lo == hi else f"{fmt(lo)}–{fmt(hi)}"), False


def in_area(venue: str, street: str, town: str, region: str, local_source: bool) -> bool:
    if region and region.lower() not in ("la", "louisiana"):
        return False
    if town:
        return town.lower() in AREA_TOWNS
    blob = f"{venue} {street}".lower()
    if any(t in blob for t in AREA_TOWNS):
        return True
    return local_source


def read_jsonld(source: dict, pages: list[tuple[str, str]]) -> list[dict]:
    events = []
    for page_url, page_html in pages:
        soup = BeautifulSoup(page_html, "html.parser")
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                doc = json.loads(tag.string or "")
            except (json.JSONDecodeError, TypeError):
                continue
            for item in _walk(doc):
                status = str(item.get("eventStatus", ""))
                if "Cancelled" in status or "Postponed" in status:
                    continue
                if "Online" in str(item.get("eventAttendanceMode", "")):
                    continue
                title = clean(item.get("name"))
                utc_clock = source.get("offset_applied_twice", False)
                start = _parse_when(item.get("startDate"), utc_clock)
                if not title or start is None:
                    continue
                end = _parse_when(item.get("endDate"), utc_clock)
                if end is not None and not isinstance(start, dt.datetime) and \
                        not isinstance(end, dt.datetime) and (end - start).days == 1:
                    end = None  # a night event ending after midnight, not a two-day event
                if end is not None:
                    span = (end.date() if isinstance(end, dt.datetime) else end) - \
                           (start.date() if isinstance(start, dt.datetime) else start)
                    if span.days > 14:
                        continue  # a months-long exhibition, not a dated event (see manual_events.json)
                venue, street, town, region = _place(item.get("location"))
                if not in_area(venue, street, town, region, source.get("local", False)):
                    continue
                desc = clean(item.get("description"), limit=260)
                cats = categorize(title, venue, desc, source.get("default"))
                if not cats:
                    continue
                price, free = _price(item.get("offers"))
                free = free or item.get("isAccessibleForFree") in (True, "true", "True")
                url = item.get("url") if isinstance(item.get("url"), str) else page_url
                verify = None
                if not isinstance(start, dt.datetime) and end is None:
                    verify = "The start time wasn't listed. Check the event page."
                events.append(make_event(source, title, start, end, venue, town or "Lafayette", street,
                                         desc, url, cats, price, free, verify))
    return _join_daily_repeats(events)


def _join_daily_repeats(events: list[dict]) -> list[dict]:
    """Turn the same all-day event listed on consecutive days into one multi-day event."""
    out: list[dict] = []
    for ev in sorted(events, key=lambda e: (e["title"], e["start"])):
        prev = out[-1] if out else None
        if (prev and ev.get("allDay") and prev.get("allDay") and prev["title"] == ev["title"]):
            last = dt.date.fromisoformat(prev.get("endDate", prev["start"][:10]))
            if dt.date.fromisoformat(ev["start"][:10]) == last + dt.timedelta(days=1):
                prev["endDate"] = ev["start"][:10]
                prev.pop("verify", None)
                continue
        out.append(ev)
    return out


# ---------- reader 2: Downtown Lafayette's list ----------

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})\s*([ap]m)$", re.I)


def _date_for(month: int, day: int, weekday: str, today: dt.date) -> dt.date | None:
    """Pick the year that matches the listed weekday (the page leaves out the year)."""
    for year in (today.year, today.year + 1, today.year - 1):
        try:
            d = dt.date(year, month, day)
        except ValueError:
            continue
        if WEEKDAYS[d.weekday()] == weekday and d >= today - dt.timedelta(days=60):
            return d
    return None


def _time(s: str) -> dt.time | None:
    m = TIME_RE.match(s.strip())
    if not m:
        return None
    h, mi, ap = int(m.group(1)) % 12, int(m.group(2)), m.group(3).lower()
    return dt.time(h + (12 if ap == "pm" else 0), mi)


def read_downtown(source: dict, pages: list[tuple[str, str]], today: dt.date, page_text) -> list[dict]:
    """`page_text` is collect.page_text, passed in to avoid a circular import."""
    events, seen = [], set()
    for page_url, page_html in pages:
        lines = page_text(page_html, page_url).splitlines()
        i = 0
        while i < len(lines) - 6:
            mon, d1, d2, wd = (x.strip().lower() for x in lines[i:i + 4])
            if mon[:3] in MONTHS and len(mon) == 3 and d1.isdigit() and d2.isdigit() and wd in WEEKDAYS:
                j = i + 4
                tag = ""
                if not _time(lines[j]):
                    tag, j = lines[j], j + 1
                t1 = _time(lines[j]) if j < len(lines) else None
                if t1 and j + 4 < len(lines) and lines[j + 1].strip() == "-":
                    t2 = _time(lines[j + 2])
                    title, venue = lines[j + 3].strip(), lines[j + 4].strip()
                    start_day = _date_for(MONTHS[mon[:3]], int(d1), wd, today)
                    if start_day and (title, start_day) not in seen:
                        seen.add((title, start_day))
                        verify = None
                        end_day = None
                        if int(d2) != int(d1):
                            try:
                                month2 = MONTHS[mon[:3]] + (1 if int(d2) < int(d1) else 0)
                                year2 = start_day.year + (1 if month2 == 13 else 0)
                                end_day = dt.date(year2, (month2 - 1) % 12 + 1, int(d2))
                            except ValueError:
                                verify = "The listing's end date is unclear. Check with the venue."
                        cats = categorize(title, f"{venue} {tag}", "", source.get("default"))
                        if cats:
                            start = dt.datetime.combine(start_day, t1)
                            end = dt.datetime.combine(start_day, t2) if t2 else None
                            ev = make_event(source, title.rstrip("!"), start, end, venue, "Lafayette", "",
                                            f"{tag + ' event' if tag else 'Event'} in Downtown Lafayette.",
                                            page_url, cats, verify=verify)
                            if end_day:
                                ev["endDate"] = end_day.isoformat()
                            events.append(ev)
                    i = j + 5
                    continue
            i += 1
    return events


# ---------- reader 3: fixed weekly schedules ----------

def read_weekly(source: dict, today: dt.date, days: int) -> list[dict]:
    events = []
    for run in source["weekly"]:
        h, m = map(int, run["time"].split(":"))
        for n in range(days + 1):
            day = today + dt.timedelta(days=n)
            if WEEKDAYS[day.weekday()] != run["weekday"]:
                continue
            start = dt.datetime.combine(day, dt.time(h, m))
            ev = make_event(source, run["title"], start, None, run["venue"], run.get("town", "Lafayette"),
                            run.get("address", ""), run["desc"], source["pages"][0], run["cats"],
                            price=run.get("price"), free=run.get("free", False))
            ev["map"] = run.get("map", ev["map"])
            ev.pop("featured", None)
            events.append(ev)
    return events
