"""Event sources the daily collector reads.

Each source is a page (or a few pages) that lists upcoming events. `pages` may use
{this_month} / {next_month} placeholders, filled with the month name (e.g. "november")
or {this_ym} / {next_ym} for "2026-11" style, so monthly calendars stay current.

`hint` is passed to Claude as extra context about what the page usually contains.

To add a source: append an entry, then run the workflow by hand from the repo's
Actions tab (or locally: python3 collector/collect.py).
"""

SOURCES = [
    {
        "id": "moncus",
        "name": "Moncus Park",
        "pages": ["https://moncuspark.org/events/"],
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
        "hint": "Downtown Lafayette events: concerts, festivals, ArtWalk, book events, "
                "trivia nights, restaurant pop-ups. Listings often omit the year; use the "
                "weekday to work it out.",
    },
    {
        "id": "aca",
        "name": "Acadiana Center for the Arts",
        "pages": ["https://acadianacenterforthearts.org/whats-happening/"],
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
        "hint": "Eventbrite search results for Lafayette, Louisiana. Cards often show only a "
                "weekday or 'Tomorrow'. Skip private parties, trainings, certifications, "
                "business networking and adults-only novelty shows.",
    },
    {
        "id": "crrc",
        "name": "Cajun Road Runners",
        "pages": [
            "https://cajunroadrunners.com/group-runs/",
            "https://cajunroadrunners.com/races/",
        ],
        "hint": "Running club. The group-runs page lists WEEKLY runs by weekday (meeting spot, "
                "time, distance): list one event per date that falls in the window. The races "
                "page lists dated races.",
    },
    {
        "id": "vitalant",
        "name": "Vitalant",
        "pages": ["https://www.vitalant.org/"],
        "hint": "Blood donation organization. Only include blood drives in Lafayette Parish "
                "or towns next to it. Tag them health and volunteer.",
    },
    {
        "id": "races",
        "name": "My Mind is Racing",
        "pages": ["https://mymindisracing.com/events/US/LA/Lafayette?tag=Run"],
        "hint": "Race calendar for the Lafayette area: 5Ks, fun runs, Turkey Trots.",
    },
]
