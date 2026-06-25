"""Visual-domain taxonomy for FPS-Bench.

This module owns the two-level visual taxonomy that maps a raw YouTube-8M
``video category`` (e.g. ``"Basketball"``) onto:

* ``visual_domain_fine`` -- the fine-grained meta domain (e.g. ``"Sports & Fitness"``)
* ``visual_subdomain``    -- the second-level subdomain (e.g. ``"Team Sports"``)

``CATEGORY_MAP`` is lifted verbatim from the project's ``add_categories_v2.py``
so the release stays consistent with how the data was originally organized, with
one owner-approved addition: lowercase ``"winter sports"`` (the only raw value in
the current spreadsheet that was previously unmapped).

A separate paper-compatible five-way ``visual_domain`` is derived from
``visual_domain_fine`` so users can reproduce the domains shown in the paper's
sunburst figure while still having access to the finer taxonomy.
"""

from __future__ import annotations

from typing import Dict, Tuple

__all__ = [
    "CATEGORY_MAP",
    "VISUAL_DOMAIN_FIVE_WAY",
    "FALLBACK_DOMAIN_FINE",
    "FALLBACK_SUBDOMAIN",
    "FALLBACK_DOMAIN",
    "map_video_category",
    "to_paper_domain",
    "normalize_task_category",
]

# Fallbacks used when a raw category is missing or unmapped.
FALLBACK_DOMAIN_FINE = "Other"
FALLBACK_SUBDOMAIN = "Miscellaneous"
FALLBACK_DOMAIN = "Miscellaneous"

# (raw video category) -> (visual_domain_fine, visual_subdomain)
CATEGORY_MAP: Dict[str, Tuple[str, str]] = {
    # 1. Sports & Fitness -> Team Sports
    "Basketball": ("Sports & Fitness", "Team Sports"),
    "basketball": ("Sports & Fitness", "Team Sports"),
    "Football": ("Sports & Fitness", "Team Sports"),
    "football": ("Sports & Fitness", "Team Sports"),
    "Soccer": ("Sports & Fitness", "Team Sports"),
    "American football": ("Sports & Fitness", "Team Sports"),
    "American Football": ("Sports & Fitness", "Team Sports"),
    "Rugby football": ("Sports & Fitness", "Team Sports"),
    "Baseball": ("Sports & Fitness", "Team Sports"),
    "hockey": ("Sports & Fitness", "Team Sports"),
    "Ice Hockey": ("Sports & Fitness", "Team Sports"),
    "Beach volleyball": ("Sports & Fitness", "Team Sports"),
    "Cricket": ("Sports & Fitness", "Team Sports"),
    "Synchronized swimming": ("Sports & Fitness", "Team Sports"),

    # 1. Sports & Fitness -> Individual Sports
    "Tennis": ("Sports & Fitness", "Individual Sports"),
    "Badminton": ("Sports & Fitness", "Individual Sports"),
    "Boxing": ("Sports & Fitness", "Individual Sports"),
    "Gymnastics": ("Sports & Fitness", "Individual Sports"),
    "Table Tennis": ("Sports & Fitness", "Individual Sports"),
    "Diving": ("Sports & Fitness", "Individual Sports"),
    "Combat": ("Sports & Fitness", "Individual Sports"),
    "Fencing": ("Sports & Fitness", "Individual Sports"),
    "Cycling": ("Sports & Fitness", "Individual Sports"),
    "Aikido": ("Sports & Fitness", "Individual Sports"),
    "Wrestling": ("Sports & Fitness", "Individual Sports"),
    "Horse Racing": ("Sports & Fitness", "Individual Sports"),
    "Dressage": ("Sports & Fitness", "Individual Sports"),
    "Pool": ("Sports & Fitness", "Individual Sports"),
    "Athlete": ("Sports & Fitness", "Individual Sports"),
    "Winter sports": ("Sports & Fitness", "Individual Sports"),
    "Winter Sports": ("Sports & Fitness", "Individual Sports"),
    # Owner-approved addition: lowercase variant present in the current sheet.
    "winter sports": ("Sports & Fitness", "Individual Sports"),
    "Golf": ("Sports & Fitness", "Individual Sports"),
    "Bowling": ("Sports & Fitness", "Individual Sports"),
    "Human swimming": ("Sports & Fitness", "Individual Sports"),
    "Ice dancing": ("Sports & Fitness", "Individual Sports"),
    "Ice Dancing": ("Sports & Fitness", "Individual Sports"),
    "Ice Skating": ("Sports & Fitness", "Individual Sports"),
    "ice skating": ("Sports & Fitness", "Individual Sports"),
    "Ice skating": ("Sports & Fitness", "Individual Sports"),

    # 1. Sports & Fitness -> Fitness & Recreation
    "Jet Ski": ("Sports & Fitness", "Fitness & Recreation"),
    "Skateboarding": ("Sports & Fitness", "Fitness & Recreation"),
    "Kickflip": ("Sports & Fitness", "Fitness & Recreation"),
    "BMX Bike": ("Sports & Fitness", "Fitness & Recreation"),
    "Biking": ("Sports & Fitness", "Fitness & Recreation"),
    "Aerobics": ("Sports & Fitness", "Fitness & Recreation"),
    "Skiing": ("Sports & Fitness", "Fitness & Recreation"),

    # 2. Animals -> Pets
    "Dogs": ("Animals", "Pets"),
    "Dog": ("Animals", "Pets"),
    "Cat": ("Animals", "Pets"),
    "Cats": ("Animals", "Pets"),
    "kitten": ("Animals", "Pets"),
    "Parrot": ("Animals", "Pets"),
    "Pet": ("Animals", "Pets"),
    "pet": ("Animals", "Pets"),
    "Bird": ("Animals", "Pets"),

    # 2. Animals -> Wildlife & Farm
    "Horse": ("Animals", "Wildlife & Farm"),
    "horse": ("Animals", "Wildlife & Farm"),
    "Cheetah": ("Animals", "Wildlife & Farm"),

    # 3. Media & Entertainment -> Film & Animation
    "Comedy": ("Media & Entertainment", "Film & Animation"),
    "Cartoon": ("Media & Entertainment", "Film & Animation"),
    "Animation": ("Media & Entertainment", "Film & Animation"),
    "Movieclips": ("Media & Entertainment", "Film & Animation"),
    "star wars": ("Media & Entertainment", "Film & Animation"),

    # 3. Media & Entertainment -> Music
    "Drums": ("Media & Entertainment", "Music"),
    "Drum": ("Media & Entertainment", "Music"),
    "drum": ("Media & Entertainment", "Music"),
    "Musician": ("Media & Entertainment", "Music"),
    "Concert": ("Media & Entertainment", "Music"),
    "Marching band": ("Media & Entertainment", "Music"),
    "Musical ensemble": ("Media & Entertainment", "Music"),
    "String instrument": ("Media & Entertainment", "Music"),
    "Brass Instrument": ("Media & Entertainment", "Music"),
    "Violin": ("Media & Entertainment", "Music"),
    "saxophone": ("Media & Entertainment", "Music"),
    "music": ("Media & Entertainment", "Music"),
    "Guitar": ("Media & Entertainment", "Music"),
    "Orchestra": ("Media & Entertainment", "Music"),
    "DJ": ("Media & Entertainment", "Music"),
    "Disk Jockey": ("Media & Entertainment", "Music"),

    # 3. Media & Entertainment -> Performing Arts
    "Ballet": ("Media & Entertainment", "Performing Arts"),
    "Juggling": ("Media & Entertainment", "Performing Arts"),
    "Dancing": ("Media & Entertainment", "Performing Arts"),
    "Dance": ("Media & Entertainment", "Performing Arts"),
    "Irish dance": ("Media & Entertainment", "Performing Arts"),
    "Latin dance": ("Media & Entertainment", "Performing Arts"),
    "Performance Art": ("Media & Entertainment", "Performing Arts"),
    "Performance Arts": ("Media & Entertainment", "Performing Arts"),
    "Performance art": ("Media & Entertainment", "Performing Arts"),
    "Music video": ("Media & Entertainment", "Performing Arts"),

    # 4. Hobbies & Gaming -> Video Gaming
    "Video game": ("Hobbies & Gaming", "Video Gaming"),
    "video game": ("Hobbies & Gaming", "Video Gaming"),
    "Video Game": ("Hobbies & Gaming", "Video Gaming"),
    "Call of Duty: Black Ops": ("Hobbies & Gaming", "Video Gaming"),
    "call of duty: black ops II": ("Hobbies & Gaming", "Video Gaming"),
    "GameTrailers": ("Hobbies & Gaming", "Video Gaming"),
    "Mario Kart": ("Hobbies & Gaming", "Video Gaming"),
    "Super Smash Bros": ("Hobbies & Gaming", "Video Gaming"),
    "Fighting Game": ("Hobbies & Gaming", "Video Gaming"),
    "fighting game": ("Hobbies & Gaming", "Video Gaming"),
    "Halo": ("Hobbies & Gaming", "Video Gaming"),
    "League of Legends": ("Hobbies & Gaming", "Video Gaming"),

    # 4. Hobbies & Gaming -> Games & Hobbies
    "Toy": ("Hobbies & Gaming", "Games & Hobbies"),
    "Chess": ("Hobbies & Gaming", "Games & Hobbies"),
    "Poker": ("Hobbies & Gaming", "Games & Hobbies"),
    "Dominoes": ("Hobbies & Gaming", "Games & Hobbies"),
    "Cards": ("Hobbies & Gaming", "Games & Hobbies"),
    "Monopoly": ("Hobbies & Gaming", "Games & Hobbies"),
    "Beyblade": ("Hobbies & Gaming", "Games & Hobbies"),
    "Hunting": ("Hobbies & Gaming", "Games & Hobbies"),
    "Remote controlled Airplane": ("Hobbies & Gaming", "Games & Hobbies"),
    "Marble": ("Hobbies & Gaming", "Games & Hobbies"),

    # 5. Lifestyle -> Food & Drink
    "Beer": ("Lifestyle", "Food & Drink"),
    "Cooking": ("Lifestyle", "Food & Drink"),
    "cooking": ("Lifestyle", "Food & Drink"),

    # 5. Lifestyle -> Art & Beauty
    "Painting": ("Lifestyle", "Art & Beauty"),
    "Spray painting": ("Lifestyle", "Art & Beauty"),
    "Cosmetics": ("Lifestyle", "Art & Beauty"),
    "Makeup": ("Lifestyle", "Art & Beauty"),
    "lipstick/makeup": ("Lifestyle", "Art & Beauty"),
    "Hair": ("Lifestyle", "Art & Beauty"),

    # 6. Technology & Infrastructure -> Tech & Electronics
    "Robot": ("Technology & Infrastructure", "Tech & Electronics"),
    "Personal computer": ("Technology & Infrastructure", "Tech & Electronics"),
    "Computer keyboard": ("Technology & Infrastructure", "Tech & Electronics"),
    "Mobile phone": ("Technology & Infrastructure", "Tech & Electronics"),
    "iPhone": ("Technology & Infrastructure", "Tech & Electronics"),
    "Drone": ("Technology & Infrastructure", "Tech & Electronics"),
    "Machine": ("Technology & Infrastructure", "Tech & Electronics"),
    "GoPro": ("Technology & Infrastructure", "Tech & Electronics"),

    # 6. Technology & Infrastructure -> Tools, Home & Science
    "Hammer": ("Technology & Infrastructure", "Tools, Home & Science"),
    "Knife": ("Technology & Infrastructure", "Tools, Home & Science"),
    "Axe": ("Technology & Infrastructure", "Tools, Home & Science"),
    "Laboratory": ("Technology & Infrastructure", "Tools, Home & Science"),
    "Ceiling Fan": ("Technology & Infrastructure", "Tools, Home & Science"),
    "Expresso machine": ("Lifestyle", "Food & Drink"),  # re-classified to Lifestyle
    "Coffeemaker": ("Lifestyle", "Food & Drink"),       # re-classified to Lifestyle

    # 7. Vehicles -> Ground Vehicles
    "Dashcam": ("Vehicles", "Ground Vehicles"),
    "Car": ("Vehicles", "Ground Vehicles"),
    "Racing": ("Vehicles", "Ground Vehicles"),  # assumed car racing
    "Rallying": ("Vehicles", "Ground Vehicles"),
    "Motorcycle": ("Vehicles", "Ground Vehicles"),
    "motorcycle": ("Vehicles", "Ground Vehicles"),
    "Bicycle": ("Vehicles", "Ground Vehicles"),
    "Train": ("Vehicles", "Ground Vehicles"),

    # 7. Vehicles -> Air & Sea
    "Helicopter": ("Vehicles", "Air & Sea"),

    # 8. Other -> Miscellaneous
    "Stadium": ("Other", "Miscellaneous"),
    "Military parade": ("Other", "Miscellaneous"),
    "Aerosol spray": ("Other", "Miscellaneous"),
    "Bollywood": ("Other", "Miscellaneous"),
    "Farming": ("Other", "Miscellaneous"),
    "Festival": ("Other", "Miscellaneous"),
}

# Paper-compatible five-way visual domain, derived from visual_domain_fine.
VISUAL_DOMAIN_FIVE_WAY: Dict[str, str] = {
    "Sports & Fitness": "Sports & Fitness",
    "Hobbies & Gaming": "Hobbies & Gaming",
    "Media & Entertainment": "Media & Entertainment",
    "Vehicles": "Vehicles",
    "Animals": "Miscellaneous",
    "Lifestyle": "Miscellaneous",
    "Technology & Infrastructure": "Miscellaneous",
    "Other": "Miscellaneous",
}


def map_video_category(raw_category) -> Tuple[str, str, bool]:
    """Map a raw ``video category`` to ``(visual_domain_fine, visual_subdomain)``.

    Returns a third boolean ``needs_review`` that is ``True`` when the raw value
    was missing or unmapped (and therefore fell back to ``Other`` /
    ``Miscellaneous``).
    """
    if raw_category is None:
        return FALLBACK_DOMAIN_FINE, FALLBACK_SUBDOMAIN, True
    key = str(raw_category).strip()
    if not key or key.lower() == "nan":
        return FALLBACK_DOMAIN_FINE, FALLBACK_SUBDOMAIN, True
    if key in CATEGORY_MAP:
        domain_fine, subdomain = CATEGORY_MAP[key]
        return domain_fine, subdomain, False
    return FALLBACK_DOMAIN_FINE, FALLBACK_SUBDOMAIN, True


def to_paper_domain(visual_domain_fine: str) -> str:
    """Collapse a fine visual domain to the paper's five-way ``visual_domain``."""
    return VISUAL_DOMAIN_FIVE_WAY.get(visual_domain_fine, FALLBACK_DOMAIN)


def normalize_task_category(raw: str) -> str:
    """Normalize a raw task category (e.g. ``"repetitive motion"``) to snake_case.

    Lower-cases, collapses internal whitespace, and joins with underscores. The
    result is *not* validated against the allowed set here; callers compare
    against :data:`fpsbench.TASK_CATEGORIES`.
    """
    return "_".join(str(raw).strip().lower().split())
