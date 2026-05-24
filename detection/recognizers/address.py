"""PII_ADDRESS — street-address recognizer to supplement Presidio's LOCATION
(which is city/state-level)."""
from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

# Full US street suffix list (matches Faker's faker.providers.address.en_US so
# our 100-run leakage test covers the realistic variety). Order short-suffixes
# last in the alternation so longer matches win.
_STREET_SUFFIXES = sorted(
    [
        "Alley", "Avenue", "Branch", "Bridge", "Brook", "Brooks", "Burg",
        "Burgs", "Bypass", "Camp", "Canyon", "Cape", "Causeway", "Center",
        "Centers", "Circle", "Circles", "Cliff", "Cliffs", "Club", "Common",
        "Corner", "Corners", "Course", "Court", "Courts", "Cove", "Coves",
        "Creek", "Crescent", "Crest", "Crossing", "Crossroad", "Curve", "Dale",
        "Dam", "Divide", "Drive", "Drives", "Estate", "Estates", "Expressway",
        "Extension", "Extensions", "Fall", "Falls", "Ferry", "Field", "Fields",
        "Flat", "Flats", "Ford", "Fords", "Forest", "Forge", "Forges", "Fork",
        "Forks", "Fort", "Freeway", "Garden", "Gardens", "Gateway", "Glen",
        "Glens", "Green", "Greens", "Grove", "Groves", "Harbor", "Harbors",
        "Haven", "Heights", "Highway", "Hill", "Hills", "Hollow", "Inlet",
        "Island", "Islands", "Isle", "Junction", "Junctions", "Key", "Keys",
        "Knoll", "Knolls", "Lake", "Lakes", "Land", "Landing", "Lane", "Light",
        "Lights", "Loaf", "Lock", "Locks", "Lodge", "Loop", "Mall", "Manor",
        "Manors", "Meadow", "Meadows", "Mews", "Mill", "Mills", "Mission",
        "Motorway", "Mount", "Mountain", "Mountains", "Neck", "Orchard",
        "Oval", "Overpass", "Park", "Parks", "Parkway", "Parkways", "Pass",
        "Passage", "Path", "Pike", "Pine", "Pines", "Place", "Plain", "Plains",
        "Plaza", "Point", "Points", "Port", "Ports", "Prairie", "Radial",
        "Ramp", "Ranch", "Rapid", "Rapids", "Rest", "Ridge", "Ridges", "River",
        "Road", "Roads", "Route", "Row", "Rue", "Run", "Shoal", "Shoals",
        "Shore", "Shores", "Skyway", "Spring", "Springs", "Spur", "Spurs",
        "Square", "Squares", "Station", "Stravenue", "Stream", "Street",
        "Streets", "Summit", "Terrace", "Throughway", "Trace", "Track",
        "Trafficway", "Trail", "Tunnel", "Turnpike", "Underpass", "Union",
        "Unions", "Valley", "Valleys", "Via", "Viaduct", "View", "Views",
        "Village", "Villages", "Ville", "Vista", "Walk", "Walks", "Wall",
        "Way", "Ways", "Well", "Wells",
        # Short common abbreviations (Faker doesn't use these but real-world text does).
        "St", "Ave", "Rd", "Blvd", "Dr", "Ln", "Ct", "Pl", "Hwy", "Pkwy",
        "Cir", "Ter",
    ],
    key=lambda s: -len(s),  # longest first in the alternation
)

_SUFFIX_PATTERN = "|".join(s.replace(".", r"\.") for s in _STREET_SUFFIXES)


class StreetAddressRecognizer(PatternRecognizer):
    """US street address: digits + 1-4 capitalized words + street suffix.
    Also matches apartment/unit secondary fragments."""

    def __init__(self) -> None:
        super().__init__(
            supported_entity="PII_ADDRESS",
            patterns=[
                Pattern(
                    name="street_address",
                    regex=(
                        r"\b\d{1,6}\s+"
                        r"(?:[A-Z][a-zA-Z]+\s+){1,4}"
                        rf"(?:{_SUFFIX_PATTERN})\.?\b"
                    ),
                    score=0.85,
                ),
                Pattern(
                    name="apt_suite",
                    regex=r"\b(?:apt|suite|ste|unit)\.?\s?[A-Z0-9-]+\b",
                    score=0.4,
                ),
            ],
            context=["address", "lives at", "located at", "street"],
        )
