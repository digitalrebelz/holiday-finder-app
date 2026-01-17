"""Configuration for supported travel sites and their scrapers."""

from dataclasses import dataclass
from enum import Enum
from typing import List


class SiteType(Enum):
    """Type of travel site."""
    PACKAGE_HOLIDAY = "package_holiday"
    FLIGHT_ONLY = "flight_only"
    ACCOMMODATION = "accommodation"
    CAMPING = "camping"
    REVIEWS = "reviews"


@dataclass
class TravelSite:
    """Configuration for a travel site."""
    name: str
    base_url: str
    site_type: SiteType
    enabled: bool = True
    requires_javascript: bool = False
    rate_limit_seconds: float = 2.0


# Dutch Package Holiday Sites
TUI = TravelSite(
    name="TUI",
    base_url="https://www.tui.nl",
    site_type=SiteType.PACKAGE_HOLIDAY,
    requires_javascript=True,
    rate_limit_seconds=3.0
)

CORENDON = TravelSite(
    name="Corendon",
    base_url="https://www.corendon.nl",
    site_type=SiteType.PACKAGE_HOLIDAY,
    requires_javascript=True
)

SUNWEB = TravelSite(
    name="Sunweb",
    base_url="https://www.sunweb.nl",
    site_type=SiteType.PACKAGE_HOLIDAY,
    requires_javascript=True
)

PRIJSVRIJ = TravelSite(
    name="Prijsvrij",
    base_url="https://www.prijsvrij.nl",
    site_type=SiteType.PACKAGE_HOLIDAY,
    requires_javascript=True
)

DREIZEN = TravelSite(
    name="D-reizen",
    base_url="https://www.d-reizen.nl",
    site_type=SiteType.PACKAGE_HOLIDAY,
    requires_javascript=True
)

NECKERMANN = TravelSite(
    name="Neckermann",
    base_url="https://www.neckermann.nl",
    site_type=SiteType.PACKAGE_HOLIDAY,
    requires_javascript=True
)

# Booking Platforms
BOOKING = TravelSite(
    name="Booking.com",
    base_url="https://www.booking.com",
    site_type=SiteType.ACCOMMODATION,
    requires_javascript=True
)

VAKANTIEDISCOUNTER = TravelSite(
    name="VakantieDiscounter",
    base_url="https://www.vakantiediscounter.nl",
    site_type=SiteType.PACKAGE_HOLIDAY,
    requires_javascript=True
)

EXPEDIA = TravelSite(
    name="Expedia",
    base_url="https://www.expedia.nl",
    site_type=SiteType.ACCOMMODATION,
    requires_javascript=True
)

# Flight Comparison
SKYSCANNER = TravelSite(
    name="Skyscanner",
    base_url="https://www.skyscanner.nl",
    site_type=SiteType.FLIGHT_ONLY,
    requires_javascript=True
)

# Camping Sites
ACSI = TravelSite(
    name="ACSI",
    base_url="https://www.eurocampings.nl",
    site_type=SiteType.CAMPING,
    requires_javascript=False
)

VACANSOLEIL = TravelSite(
    name="Vacansoleil",
    base_url="https://www.vacansoleil.nl",
    site_type=SiteType.CAMPING,
    requires_javascript=True
)

EUROCAMP = TravelSite(
    name="Eurocamp",
    base_url="https://www.eurocamp.nl",
    site_type=SiteType.CAMPING,
    requires_javascript=True
)

ALLCAMPS = TravelSite(
    name="Allcamps",
    base_url="https://www.allcamps.nl",
    site_type=SiteType.CAMPING,
    requires_javascript=True
)

# Review Sites
ZOOVER = TravelSite(
    name="Zoover",
    base_url="https://www.zoover.nl",
    site_type=SiteType.REVIEWS,
    requires_javascript=False
)

TRIPADVISOR = TravelSite(
    name="TripAdvisor",
    base_url="https://www.tripadvisor.nl",
    site_type=SiteType.REVIEWS,
    requires_javascript=True
)


# Lists of sites by category
PACKAGE_HOLIDAY_SITES: List[TravelSite] = [TUI, CORENDON, SUNWEB, PRIJSVRIJ, DREIZEN]
ACCOMMODATION_SITES: List[TravelSite] = [BOOKING]
FLIGHT_SITES: List[TravelSite] = [SKYSCANNER]
CAMPING_SITES: List[TravelSite] = [ACSI, VACANSOLEIL, EUROCAMP, ALLCAMPS]
REVIEW_SITES: List[TravelSite] = [ZOOVER, TRIPADVISOR]

ALL_TRAVEL_SITES: List[TravelSite] = (
    PACKAGE_HOLIDAY_SITES + ACCOMMODATION_SITES + FLIGHT_SITES + CAMPING_SITES
)

# Airport codes
AIRPORTS = {
    "EIN": "Eindhoven Airport",
    "BRU": "Brussels Airport",
    "AMS": "Amsterdam Schiphol",
    "NRN": "Weeze (Niederrhein)",
    "RTM": "Rotterdam The Hague",
    "MST": "Maastricht Aachen",
    "CRL": "Brussels Charleroi",
}
