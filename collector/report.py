#!/usr/bin/env python3
"""Daily Allez email report.

Builds one email with four parts and sends it to the addresses in REPORT_TO:
  1. Today's events and what's new since yesterday (the digest)
  2. Collection health: which sources worked and what was filtered out
  3. History: a day-by-day chart of events collected, by category
  4. Accuracy: missing times, events that moved or disappeared, and a few to spot-check

Environment (set as GitHub repository secrets):
  SMTP_USERNAME   the Gmail address that sends the report
  SMTP_PASSWORD   a Gmail app password for that address (not the normal password)
  REPORT_TO       comma-separated recipient addresses
  COLLECT_OUTCOME set by the workflow: "success" or "failure"

Without the SMTP settings the report is only saved to report_out/ (the workflow keeps it
as a downloadable artifact), so a missing secret never breaks the daily update.

Usage: python3 collector/report.py
"""
from __future__ import annotations

import datetime as dt
import html
import io
import json
import os
import random
import re
import smtplib
import sys
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
EVENTS_FILE = ROOT / "docs" / "events.json"
HISTORY_FILE = ROOT / "collector" / "history.json"
LAST_RUN_FILE = ROOT / "collector" / "last_run.json"
OUT_DIR = ROOT / "report_out"
APP_URL = "https://johnnycrahat-max.github.io/allez/"
REPO_URL = "https://github.com/johnnycrahat-max/allez"
TZ = ZoneInfo("America/Chicago")

CATS = ["music", "food", "volunteer", "health"]
CAT_NAMES = {"music": "Music & Culture", "food": "Food", "volunteer": "Volunteer", "health": "Health & Wellness"}
# Chart colors: the app's category hues, adjusted so all four stay distinguishable for
# colorblind readers (checked with the palette validator).
CAT_COLORS = {"music": "#6233C9", "food": "#D51028", "volunteer": "#00897B", "health": "#5B8DEF"}

NAVY, RED, GOLD, WARM = "#092B51", "#D51028", "#FFBC00", "#FAF9F6"
INK, MUTED, LINE = "#092B51", "#4F6077", "#E3DFD6"
GOOD, WARN, BAD = "#1E7B34", "#8A5D00", "#B3261E"


def esc(x) -> str:
    return html.escape(str(x if x is not None else ""))


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


# ---------- formatting ----------

def parse_start(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s if "T" in s else s + "T00:00")


def when(e: dict) -> str:
    if e.get("ongoing"):
        return e["ongoing"]
    d = parse_start(e["start"])
    day = f"{d:%a %b} {d.day}"
    if e.get("allDay") or "T" not in e["start"]:
        return f"{day} · time not listed" if not e.get("endDate") else f"{day} – {e['endDate'][5:].replace('-', '/')}"
    t = d.strftime("%I:%M %p").lstrip("0").replace(":00 ", " ")
    return f"{day} · {t}"


def link(text: str, url: str | None) -> str:
    if not url:
        return esc(text)
    return f'<a href="{esc(url)}" style="color:{NAVY};text-decoration:underline">{esc(text)}</a>'


def pill(text: str, color: str) -> str:
    return (f'<span style="display:inline-block;padding:2px 9px;border-radius:999px;'
            f'background:{color};color:#fff;font-size:12px;font-weight:700">{esc(text)}</span>')


def cat_tag(c: str) -> str:
    return (f'<span style="display:inline-block;width:9px;height:9px;border-radius:2px;'
            f'background:{CAT_COLORS[c]};margin-right:5px;vertical-align:baseline"></span>')


def section(title: str, body: str, note: str = "") -> str:
    sub = f'<p style="margin:2px 0 12px;color:{MUTED};font-size:13px">{note}</p>' if note else ""
    return (f'<tr><td style="padding:22px 24px 6px"><h2 style="margin:0;font-size:18px;color:{INK};'
            f'font-family:Arial,Helvetica,sans-serif">{title}</h2>{sub}{body}</td></tr>')


def event_rows(events: list[dict], limit: int, show_cats: bool = True) -> str:
    if not events:
        return f'<p style="color:{MUTED};margin:6px 0">None.</p>'
    rows = []
    for e in events[:limit]:
        tags = "".join(cat_tag(c) for c in (e.get("cats") or [])) if show_cats else ""
        check = f' <span style="color:{WARN}">· check details</span>' if e.get("verify") else ""
        rows.append(f'<tr><td style="padding:6px 0;border-top:1px solid {LINE};font-size:14px;color:{INK}">'
                    f'{tags}<b>{link(e["title"], e.get("url"))}</b><br>'
                    f'<span style="color:{MUTED};font-size:13px">{esc(when(e))} · {esc(e.get("venue"))}{check}</span>'
                    f'</td></tr>')
    more = len(events) - limit
    if more > 0:
        rows.append(f'<tr><td style="padding:6px 0;color:{MUTED};font-size:13px">…and {more} more '
                    f'in the <a href="{APP_URL}" style="color:{NAVY}">app</a>.</td></tr>')
    return f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0">{"".join(rows)}</table>'


def short_note(note: str) -> str:
    """Turn 'https://site/long/path/: HTTP 404' into 'one page: HTTP 404 (not published yet?)'."""
    m = re.match(r"https?://\S+?: (.*)", note)
    if not m:
        return note
    reason = m.group(1)
    return "one page: " + reason + (" (not published yet?)" if reason == "HTTP 404" else "")


def stat(label: str, value: str, color: str = INK) -> str:
    return (f'<td style="padding:10px 12px;background:{WARM};border-radius:10px;text-align:left;width:25%">'
            f'<div style="font-size:22px;font-weight:700;color:{color};font-family:Arial,sans-serif">{esc(value)}</div>'
            f'<div style="font-size:12px;color:{MUTED}">{esc(label)}</div></td>')


# ---------- chart ----------

def history_chart(history: list[dict]) -> bytes | None:
    """Stacked bars: events collected each day (next 4 weeks), split by category."""
    if not history:
        return None
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    days = history[-30:]
    labels = [dt.date.fromisoformat(h["date"]) for h in days]
    xs = range(len(days))
    fig, ax = plt.subplots(figsize=(6.4, 2.9), dpi=200)
    fig.patch.set_facecolor("white")
    bottom = [0] * len(days)
    for c in CATS:
        vals = [h.get("by_category", {}).get(c, 0) for h in days]
        ax.bar(xs, vals, bottom=bottom, width=0.62, color=CAT_COLORS[c], label=CAT_NAMES[c],
               edgecolor="white", linewidth=1.2, zorder=3)
        bottom = [b + v for b, v in zip(bottom, vals)]
    for x, (top, h) in enumerate(zip(bottom, days)):  # label the most recent bars only
        if x >= len(days) - 7:
            ax.text(x, top + max(bottom) * 0.02, str(h["total"]), ha="center", va="bottom",
                    fontsize=7, color=INK)
    step = max(1, len(days) // 8)
    last = len(days) - 1
    ax.set_xticks([x for x in xs if (x % step == 0 and last - x >= max(2, step // 2 + 1)) or x == last])
    ax.set_xticklabels([f"{labels[x]:%b} {labels[x].day}" for x in ax.get_xticks()], fontsize=7, color=MUTED)
    ax.tick_params(axis="y", labelsize=7, colors=MUTED, length=0)
    ax.tick_params(axis="x", length=0)
    ax.set_ylabel("Events in the next 4 weeks", fontsize=7, color=MUTED)
    ax.grid(axis="y", color="#ECE9E2", linewidth=0.6, zorder=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#CFCAC0")
    ax.set_xlim(-0.6, max(len(days), 7) - 0.4)
    ax.set_ylim(0, max(bottom) * 1.15 if max(bottom) else 1)
    ax.legend(ncol=4, fontsize=7, frameon=False, loc="lower left", bbox_to_anchor=(0, 1.0),
              handlelength=1, handleheight=1, labelcolor=INK)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="white")
    plt.close(fig)
    return buf.getvalue()


# ---------- report ----------

def build(outcome: str) -> tuple[str, str, bytes | None]:
    """Return (subject, html, chart png)."""
    data = load(EVENTS_FILE, {"events": [], "sources": []})
    history = load(HISTORY_FILE, [])
    run = load(LAST_RUN_FILE, {})
    today = dt.datetime.now(TZ).date()
    events = data.get("events", [])
    dated = [e for e in events if not e.get("ongoing")]
    latest = history[-1] if history else {}
    ran_today = latest.get("date") == today.isoformat() and outcome != "failure"

    # 1. digest
    def on_day(e, day):
        start = e["start"][:10]
        return start <= day.isoformat() <= e.get("endDate", start)
    todays = [e for e in dated if on_day(e, today)]
    sat = today + dt.timedelta(days=(5 - today.weekday()) % 7)
    weekend = [e for e in dated if any(on_day(e, sat + dt.timedelta(days=n)) for n in (-1, 0, 1))
               and e not in todays]
    weekend_picks = sorted(weekend, key=lambda e: (not e.get("featured"), e["start"]))

    digest = ""
    for c in CATS:
        items = [e for e in todays if c in e["cats"]]
        digest += (f'<p style="margin:14px 0 2px;font-size:13px;font-weight:700;color:{INK}">'
                   f'{cat_tag(c)}{CAT_NAMES[c]} today ({len(items)})</p>' + event_rows(items, 5, show_cats=False))
    digest += (f'<p style="margin:18px 0 2px;font-size:13px;font-weight:700;color:{INK}">'
               f'Coming up this weekend</p>' + event_rows(weekend_picks, 6))
    added = run.get("added", []) if ran_today else []
    digest += (f'<p style="margin:18px 0 2px;font-size:13px;font-weight:700;color:{INK}">'
               f'New since yesterday ({len(added)})</p>' + event_rows(added, 8))

    # 2. health
    sources = run.get("sources", []) if ran_today else data.get("sources", [])
    ok = sum(1 for s in sources if s.get("ok"))
    status = (pill("Update ran", GOOD) if ran_today and ok == len(sources) else
              pill("Update ran with problems", WARN) if ran_today else pill("Update failed", BAD))
    prev = history[-2] if len(history) > 1 else {}
    src_rows = ""
    for s in sources:
        mark = f'<span style="color:{GOOD}">✓ read</span>' if s.get("ok") else f'<span style="color:{BAD}">✗ failed</span>'
        notes = "; ".join(short_note(n) for n in (s.get("notes") or []))
        src_rows += (f'<tr><td style="padding:5px 8px 5px 0;border-top:1px solid {LINE};font-size:13px;color:{INK}">{esc(s["name"])}</td>'
                     f'<td style="padding:5px 8px;border-top:1px solid {LINE};font-size:13px;white-space:nowrap">{mark}</td>'
                     f'<td style="padding:5px 8px;border-top:1px solid {LINE};font-size:13px;text-align:right;color:{INK}">{s.get("events", 0)}</td>'
                     f'<td style="padding:5px 0 5px 8px;border-top:1px solid {LINE};font-size:12px;color:{MUTED}">{esc(notes)}</td></tr>')
    dropped = run.get("dropped", {}) if ran_today else {}
    dropped_txt = ", ".join(f"{n} {why}" for why, n in sorted(dropped.items(), key=lambda x: -x[1])) or "nothing"
    by_cat = latest.get("by_category", {})
    delta = latest.get("total", 0) - prev.get("total", latest.get("total", 0))
    health = (
        f'<p style="margin:0 0 12px">{status}</p>'
        f'<table role="presentation" width="100%" cellspacing="6" cellpadding="0"><tr>'
        + stat("events in the next 4 weeks", latest.get("total", len(dated)))
        + stat("change since yesterday", f"{delta:+d}" if prev else "—")
        + stat("sources read", f"{ok} of {len(sources)}", GOOD if ok == len(sources) else WARN)
        + stat("duplicates merged", latest.get("merged", 0)) + '</tr></table>'
        f'<p style="font-size:13px;color:{INK};margin:12px 0 4px">'
        + " &nbsp; ".join(f'{cat_tag(c)}{CAT_NAMES[c]} <b>{by_cat.get(c, 0)}</b>' for c in CATS) + '</p>'
        f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin-top:10px">'
        f'<tr><th align="left" style="font-size:12px;color:{MUTED};padding:4px 8px 4px 0">Source</th>'
        f'<th align="left" style="font-size:12px;color:{MUTED};padding:4px 8px">Status</th>'
        f'<th align="right" style="font-size:12px;color:{MUTED};padding:4px 8px">Events</th>'
        f'<th align="left" style="font-size:12px;color:{MUTED};padding:4px 0 4px 8px">Notes</th></tr>{src_rows}</table>'
        f'<p style="font-size:13px;color:{MUTED};margin:10px 0 0">Left out today: {esc(dropped_txt)}.</p>'
    )

    # 3. history (chart image + the last 7 days as a table, so the numbers are readable without the image)
    chart_png = history_chart(history)
    hist_rows = ""
    for h in reversed(history[-7:]):
        d = dt.date.fromisoformat(h["date"])
        hist_rows += (f'<tr><td style="padding:4px 8px 4px 0;border-top:1px solid {LINE};font-size:13px;color:{INK}">{d:%a %b} {d.day}</td>'
                      + "".join(f'<td align="right" style="padding:4px 6px;border-top:1px solid {LINE};font-size:13px;color:{INK}">{h["by_category"].get(c, 0)}</td>' for c in CATS)
                      + f'<td align="right" style="padding:4px 6px;border-top:1px solid {LINE};font-size:13px;color:{INK}"><b>{h["total"]}</b></td>'
                      f'<td align="right" style="padding:4px 0 4px 6px;border-top:1px solid {LINE};font-size:13px;color:{INK}">{h["sources_ok"]}/{h["sources_total"]}</td></tr>')
    head = "".join(f'<th align="right" style="font-size:11px;color:{MUTED};padding:4px 6px;font-weight:600">{cat_tag(c)}{CAT_NAMES[c].split(" ")[0]}</th>' for c in CATS)
    history_html = (
        ('<img src="cid:CHART" alt="Bar chart of events collected each day, by category" width="592" '
         'style="width:100%;max-width:592px;height:auto;display:block;border:0">' if chart_png else "")
        + f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin-top:12px">'
          f'<tr><th align="left" style="font-size:11px;color:{MUTED};padding:4px 8px 4px 0;font-weight:600">Day</th>{head}'
          f'<th align="right" style="font-size:11px;color:{MUTED};padding:4px 6px;font-weight:600">Total</th>'
          f'<th align="right" style="font-size:11px;color:{MUTED};padding:4px 0 4px 6px;font-weight:600">Sources</th></tr>{hist_rows}</table>'
    )

    # 4. accuracy
    needs = run.get("needs_check", []) if ran_today else [e for e in dated if e.get("verify")]
    moved = run.get("moved", []) if ran_today else []
    gone = run.get("gone", []) if ran_today else []
    rng = random.Random(today.isoformat())  # a different sample each day, repeatable for that day
    sample = rng.sample(dated, min(5, len(dated))) if dated else []
    moved_rows = "".join(
        f'<tr><td style="padding:5px 0;border-top:1px solid {LINE};font-size:13px;color:{INK}">'
        f'<b>{link(m["title"], m.get("url"))}</b><br><span style="color:{MUTED}">was {esc(m["was"])}<br>now {esc(m["now"])}</span></td></tr>'
        for m in moved[:8]) or f'<tr><td style="color:{MUTED};font-size:13px;padding:4px 0">None.</td></tr>'
    accuracy = (
        f'<table role="presentation" width="100%" cellspacing="6" cellpadding="0"><tr>'
        + stat("have a confirmed start time", f'{latest.get("with_time_pct", 0)}%')
        + stat("marked “check details”", len(needs), WARN if needs else GOOD)
        + stat("changed time or place", len(moved))
        + stat("gone before their date", len(gone), WARN if gone else INK) + '</tr></table>'
        f'<p style="margin:16px 0 2px;font-size:13px;font-weight:700;color:{INK}">Spot-check these 5 today</p>'
        f'<p style="margin:0 0 4px;font-size:13px;color:{MUTED}">Open each link and compare the date, time and place '
        f'with the app. Reply-all with anything that’s wrong.</p>' + event_rows(sample, 5)
        + f'<p style="margin:16px 0 2px;font-size:13px;font-weight:700;color:{INK}">Changed since yesterday</p>'
          f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0">{moved_rows}</table>'
        + f'<p style="margin:16px 0 2px;font-size:13px;font-weight:700;color:{INK}">Disappeared before their date '
          f'(possibly cancelled or renamed)</p>' + event_rows(gone, 8)
        + f'<p style="margin:16px 0 2px;font-size:13px;font-weight:700;color:{INK}">Marked “check details” in the app</p>'
        + event_rows(needs, 8)
    )

    failed_banner = "" if ran_today else (
        f'<tr><td style="padding:14px 24px;background:#FDECEA;color:{BAD};font-size:14px">'
        f'<b>Today’s update didn’t finish.</b> The app is still showing the last good list. '
        f'See the <a href="{REPO_URL}/actions" style="color:{BAD}">run log on GitHub</a>.</td></tr>')

    body = f"""<!doctype html><html><body style="margin:0;background:{WARM}">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:{WARM}"><tr><td align="center" style="padding:16px 8px">
<table role="presentation" width="640" cellspacing="0" cellpadding="0" style="max-width:640px;width:100%;background:#fff;border-radius:14px;overflow:hidden;font-family:Arial,Helvetica,sans-serif">
<tr><td style="background:{NAVY};padding:18px 24px;color:#fff">
<div style="font-size:24px;font-weight:800;letter-spacing:-.01em">Allez <span style="color:{GOLD}">·</span> daily report</div>
<div style="font-size:13px;opacity:.85;margin-top:2px">{today:%A, %B} {today.day}, {today.year} · Lafayette, Louisiana</div></td></tr>
<tr><td style="height:4px;background:{RED}"></td></tr>
{failed_banner}
{section("1. Today’s events", digest, f'From the <a href="{APP_URL}" style="color:{NAVY}">Allez app</a>.')}
{section("2. Collection health", health)}
{section("3. Day by day", history_html, "Events in the next four weeks, counted at each morning’s update. The number on each bar is the day’s total; an event in two categories counts in both colors.")}
{section("4. Accuracy", accuracy)}
<tr><td style="padding:20px 24px 24px;color:{MUTED};font-size:12px;border-top:1px solid {LINE}">
Sent automatically after each morning’s update. <a href="{REPO_URL}/actions" style="color:{MUTED}">Run history</a> ·
<a href="{APP_URL}" style="color:{MUTED}">Open Allez</a></td></tr>
</table></td></tr></table></body></html>"""

    total = latest.get("total", len(dated))
    flag = "" if ran_today and ok == len(sources) else (" ⚠ update failed" if not ran_today else " ⚠ check sources")
    subject = f"Allez daily report · {today:%a %b} {today.day} · {total} events{flag}"
    return subject, body, chart_png


def send(subject: str, body: str, chart: bytes | None) -> bool:
    user, password = os.environ.get("SMTP_USERNAME"), os.environ.get("SMTP_PASSWORD")
    to = [a.strip() for a in os.environ.get("REPORT_TO", "").split(",") if a.strip()]
    if not (user and password and to):
        print("Email settings aren't set (SMTP_USERNAME, SMTP_PASSWORD, REPORT_TO). Saved the report only.")
        return False
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, f"Allez reports <{user}>", ", ".join(to)
    msg.set_content("This report is formatted as HTML. Open it in an email app that shows HTML, "
                    f"or see the app at {APP_URL}")
    cid = make_msgid(domain="allez.report")
    msg.add_alternative(body.replace("cid:CHART", f"cid:{cid[1:-1]}"), subtype="html")
    if chart:
        msg.get_payload()[1].add_related(chart, maintype="image", subtype="png", cid=cid, filename="chart.png")
    with smtplib.SMTP_SSL(os.environ.get("SMTP_HOST", "smtp.gmail.com"), int(os.environ.get("SMTP_PORT", "465"))) as s:
        s.login(user, password)
        s.send_message(msg)
    print(f"Sent “{subject}” to {len(to)} recipient(s).")
    return True


def main() -> int:
    subject, body, chart = build(os.environ.get("COLLECT_OUTCOME", "success"))
    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "report.html").write_text(body.replace("cid:CHART", "chart.png"), encoding="utf-8")
    if chart:
        (OUT_DIR / "chart.png").write_bytes(chart)
    print(f"Saved report_out/report.html ({subject})")
    try:
        send(subject, body, chart)
    except (smtplib.SMTPException, OSError) as e:
        print(f"Couldn't send the email: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
