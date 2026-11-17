"""Event sources the daily collector reads.

Each source is a page (or a few pages) that lists upcoming events. `pages` may use
{this_month} / {next_month} placeholders, filled with the month name (e.g. "november"),
or {this_ym} / {next_ym} for "2026-11" style, so monthly calendars stay current.

How each source is read without an API key (`free`):
- "jsonld":   schema.org event data embedded in the page
- "downtown": Downtown Lafayette's list layout
- "weekly":   the fixed schedule in `weekly`
- None:       skipped (only read when a Claude API key is set)

`default`: categories to use when the keyword rules find none (None = leave the event out).
`local`:   True when every event on the page is in Lafayette even if no town is given.
`hint`:    extra context for Claude, used only when an ANTHROPIC_API_KEY is set.

To add a source: append an entry, then run the workflow by hand from the repo's Actions tab
(or locally: python3 collector/collect.py). `python3 collector/collect.py --check` shows
what each source yields.
"""

SOURCES = [
    {
        "id": "moncus",
        "name": "Moncus Park",
        "pages": ["https://moncuspark.org/events/"],
        "free": "jsonld",
        "default": None,
        "local": True,
        "hint": "Park calendar: fitness classes, yoga, walks, hikes, markets, food trucks, "
                "movies and festivals at Moncus Park, 2913 Johnston St, Lafayette. "
                "Programs are free unless the listing says otherwise.",
    },
    {
        "id": "downtown",
        "name": "Downtown Lafayette",
        "pages": [
            "https://www.downtownlafayette.org/events",
            "https://www.downtownlafayette.org/events?9568029a_page=2",
        ],
        "free": "downtown",
        "default": None,
        "local": True,
        "hint": "Downtown Lafayette events: concerts, festivals, ArtWalk, book events, "
                "trivia nights, restaurant pop-ups. Listings often omit the year; use the "
                "weekday to work it out.",
    },
    {
        "id": "aca",
        "name": "Acadiana Center for the Arts",
        "pages": ["https://acadianacenterforthearts.org/whats-happening/"],
        "free": "jsonld",
        "default": ["music"],
        "local": True,
        "offset_applied_twice": True,  # a 7:30 PM show is published as 13:30-06:00
        "hint": "Arts center at 101 W. Vermilion St: concerts, gallery exhibitions, film "
                "festival screenings, artist talks. Gallery exhibitions with no single date "
                "are ongoing and should be skipped.",
    },
    {
        "id": "hilliard",
        "name": "Hilliard Art Museum",
        "pages": [
            "https://hilliardartmuseum.org/upcoming-events/month/{this_ym}/",
            "https://hilliardartmuseum.org/upcoming-events/month/{next_ym}/",
        ],
        "free": "jsonld",
        "default": ["music"],
        "local": True,
        "hint": "University art museum at 710 E. St. Mary Blvd, Lafayette: talks, tours, "
                "gallery yoga, family days.",
    },
    {
        "id": "lafayette_travel",
        "name": "Lafayette Travel",
        "pages": [
            "https://www.lafayettetravel.com/blog/stories/post/{this_month}-events-spotlight/",
            "https://www.lafayettetravel.com/blog/stories/post/{next_month}-events-spotlight/",
        ],
        "free": "jsonld",
        "default": None,
        "local": False,
        "hint": "The tourism bureau's monthly events roundup for Lafayette Parish: festivals, "
                "concerts, Ragin' Cajuns games, cultural days. Skip events in other towns "
                "more than about 30 minutes from Lafayette.",
    },
    {
        "id": "eventbrite",
        "name": "Eventbrite",
        "pages": [
            "https://www.eventbrite.com/d/la--lafayette/all-events/",
            "https://www.eventbrite.com/d/la--lafayette/food-and-drink--events/",
            "https://www.eventbrite.com/d/la--lafayette/music--events/",
        ],
        "free": "jsonld",
        "default": None,
        "local": False,
        "sticky_days": 7,  # search results show a different selection each day
        "hint": "Eventbrite search results for Lafayette, Louisiana. Cards often show only a "
                "weekday or 'Tomorrow'. Skip private parties, trainings, certifications, "
                "business networking and adults-only novelty shows.",
    },
    {
        "id": "crrc",
        "name": "Cajun Road Runners",
        "pages": ["https://cajunroadrunners.com/group-runs/"],
        "free": "weekly",
        "weekly": [
            {"weekday": "mon", "time": "18:30", "title": "Smoothie Monday Run", "cats": ["health"],
             "venue": "Smoothie King, 3012 E Milton Ave", "town": "Youngsville",
             "map": "Smoothie King 3012 E Milton Ave Youngsville LA",
             "desc": "A 3.1-mile group run from Smoothie King in Youngsville. Every Monday."},
            {"weekday": "tue", "time": "17:00", "title": "Speedwork at the Track", "cats": ["health"],
             "venue": "UL Lafayette Track", "map": "University of Louisiana at Lafayette track",
             "price": "Members only",
             "desc": "The Cajun Road Runners Club's weekly track workout. Run any distance. "
                     "Join the club through its RunSignup page."},
            {"weekday": "wed", "time": "18:00", "title": "Tap Room Wednesday Run", "cats": ["health"],
             "venue": "The Tap Room, River Ranch", "map": "The Tap Room River Ranch Lafayette LA",
             "desc": "A social 3.3-mile group run from The Tap Room. Every Wednesday."},
            {"weekday": "thu", "time": "18:00", "title": "Thursday at the Dog", "cats": ["health"],
             "venue": "Adopted Dog Brewing, 329 Dulles Dr", "map": "Adopted Dog Brewing Lafayette LA",
             "desc": "A 3.1-mile group run, then $1 off every beer. Every Thursday."},
            {"weekday": "sat", "time": "06:00", "title": "Saturday Long Run", "cats": ["health"],
             "venue": "Red Lerille's back lot, by Moncus Park",
             "map": "Red Lerille's Health and Racquet Club Lafayette LA",
             "desc": "The Cajun Road Runners' weekly long run, starting at 6 AM sharp. Several "
                     "distances, up to 10+ miles, with water stops along the way."},
            {"weekday": "sun", "time": "17:00", "title": "Sunday Run Day", "cats": ["health"],
             "venue": "Corner Bar, Johnston St", "map": "Corner Bar Johnston Street Lafayette LA",
             "desc": "A social 3.5-mile run, and your first beer is free. Every Sunday "
                     "(6 PM in summer)."},
        ],
        "hint": "Running club. The group-runs page lists WEEKLY runs by weekday (meeting spot, "
                "time, distance): list one event per date that falls in the window.",
    },
    {
        "id": "vitalant",
        "name": "Vitalant",
        "pages": ["https://www.vitalant.org/"],
        "free": None,
        "hint": "Blood donation organization. Only include blood drives in Lafayette Parish "
                "or towns next to it. Tag them health and volunteer.",
    },
    {
        "id": "races",
        "name": "My Mind is Racing",
        "pages": ["https://mymindisracing.com/events/US/LA/Lafayette?tag=Run"],
        "free": "jsonld",
        "default": ["health"],
        "local": False,
        "hint": "Race calendar for the Lafayette area: 5Ks, fun runs, Turkey Trots.",
    },
]
