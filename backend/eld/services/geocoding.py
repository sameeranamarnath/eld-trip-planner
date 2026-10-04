"""Forward + reverse geocoding against key-less OpenStreetMap providers.

Design notes
------------
* Forward (text -> coordinates): Nominatim first, Photon as the fallback.
  Both are free and key-less.
* Reverse (coordinates -> "City, ST"): Photon first because it answers in
  well under a second, Nominatim as the fallback.
* Both directions are memoised in-process, so repeating a route costs zero
  external requests.
"""

from __future__ import annotations

import logging
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from django.conf import settings

from eld.exceptions import PlaceNotFoundError
from eld.services.http import get_json

logger = logging.getLogger(__name__)

US_STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "district of columbia": "DC",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID", "illinois": "IL",
    "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY", "louisiana": "LA",
    "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI",
    "minnesota": "MN", "mississippi": "MS", "missouri": "MO", "montana": "MT",
    "nebraska": "NE", "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
    "new mexico": "NM", "new york": "NY", "north carolina": "NC", "north dakota": "ND",
    "ohio": "OH", "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA",
    "rhode island": "RI", "south carolina": "SC", "south dakota": "SD", "tennessee": "TN",
    "texas": "TX", "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}

CA_PROVINCES = {
    "alberta": "AB", "british columbia": "BC", "manitoba": "MB", "new brunswick": "NB",
    "newfoundland and labrador": "NL", "nova scotia": "NS", "ontario": "ON",
    "prince edward island": "PE", "quebec": "QC", "saskatchewan": "SK",
    "yukon": "YT", "nunavut": "NU", "northwest territories": "NT",
}

_ADMIN_CODES = {**US_STATES, **CA_PROVINCES}

# Photon reports what kind of thing it matched in `osm_value`. A truck planner
# wants populated places, so these weights drive the suggestion order: without
# them a bare query like "Nashville" can come back as state-level areas.
_PLACE_RANK = {
    "city": 100,
    "town": 90,
    "village": 80,
    "hamlet": 70,
    "borough": 65,
    "suburb": 55,
    "quarter": 50,
    "neighbourhood": 45,
    "locality": 40,
    "county": 20,
    "state": 10,
    "country": 5,
}
# Anything at or above this is a place a truck can actually be dispatched to.
_POPULATED_RANK = _PLACE_RANK["locality"]

# OSM occasionally stores a sub-county administrative unit where Photon expects
# a city ("North Bluff Precinct", "Boone Township").  Those read badly on a log
# sheet, so fall back to the county for such points.
_PLACEHOLDER_CITY_RE = re.compile(
    r"(precinct|township|district|ward|unorganized|county|no\.?\s*\d+)", re.IGNORECASE
)

_CITY_STATE_RE = re.compile(r"^\s*(?P<city>[^,]+?)\s*,\s*(?P<region>[A-Za-z .]+)\s*$")


@dataclass
class Place:
    """A resolved location."""

    label: str
    lat: float
    lng: float
    city: str = ""
    state: str = ""
    country: str = ""
    source: str = ""
    # True when ``city`` had to be inferred from a county/precinct rather than a
    # real populated place - the caller then tries a more precise provider.
    weak: bool = False
    # Relevance weight from `_PLACE_RANK`; higher is a better trip endpoint.
    rank: int = 0
    raw: dict = field(default_factory=dict)

    @property
    def short_label(self) -> str:
        if self.city and self.state:
            return f"{self.city}, {self.state}"
        return self.label

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "short_label": self.short_label,
            "city": self.city,
            "state": self.state,
            "country": self.country,
            "lat": round(self.lat, 6),
            "lng": round(self.lng, 6),
            "source": self.source,
        }


class _LruCache:
    """Least-recently-used store for geocoder results.

    Guarded by a lock because the planner reverse-geocodes from a worker pool
    and an ``OrderedDict`` is not safe to mutate from several threads.
    """

    def __init__(self, maxsize: int) -> None:
        self._maxsize = max(1, maxsize)
        self._store: OrderedDict[str, Any] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str):
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
                return self._store[key]
            return None

    def set(self, key: str, value) -> None:
        with self._lock:
            self._store[key] = value
            self._store.move_to_end(key)
            while len(self._store) > self._maxsize:
                self._store.popitem(last=False)


def _norm_state(value: str) -> str:
    if not value:
        return ""
    cleaned = value.strip()
    if len(cleaned) == 2:
        return cleaned.upper()
    return _ADMIN_CODES.get(cleaned.lower(), cleaned)


def split_city_state(text: str) -> tuple[str, str]:
    """Best-effort split of ``"Green Bay, WI"`` into ``("Green Bay", "WI")``."""
    match = _CITY_STATE_RE.match(text or "")
    if not match:
        return "", ""
    return match.group("city").strip(), _norm_state(match.group("region"))


def _rank_places(places: list[Place], query: str) -> list[Place]:
    """Best-first ordering for suggestions and for picking a single geocode.

    Populated places beat counties and states; a query that already carries its
    own state rewards a result in that state; an exact name match always wins.
    """
    wanted_city, wanted_state = split_city_state(query)
    needle = (wanted_city or query).strip().lower()

    def score(place: Place) -> tuple[int, int, int, int]:
        name = (place.city or place.label.split(",")[0]).strip().lower()
        exact = 1 if name == needle else 0
        same_state = 1 if wanted_state and place.state == wanted_state else 0
        populated = 1 if place.city else 0
        return (exact, same_state, populated, place.rank)

    ordered = sorted(places, key=score, reverse=True)
    # Once a real populated place is on offer, drop the administrative leftovers
    # that would otherwise geocode to the middle of a state.
    populated_only = [place for place in ordered if place.city]
    return populated_only or ordered


class Geocoder:
    """Cached facade over the configured geocoding providers."""

    def __init__(self) -> None:
        config = settings.SPOTTER
        self._nominatim = config["NOMINATIM_BASE_URL"].rstrip("/")
        self._photon = config["PHOTON_BASE_URL"].rstrip("/")
        self._bigdatacloud = config["BIGDATACLOUD_BASE_URL"].rstrip("/")
        cache_size = int(config.get("GEOCODE_CACHE_SIZE", 512))
        self._forward_cache = _LruCache(cache_size)
        self._reverse_cache = _LruCache(cache_size)

    # -- forward ---------------------------------------------------------
    def geocode(self, query: str) -> Place:
        """Resolve a free-text location ("Green Bay, WI") to coordinates."""
        cleaned = " ".join((query or "").split())
        if not cleaned:
            raise PlaceNotFoundError("Location text is required.")

        cache_key = cleaned.lower()
        cached = self._forward_cache.get(cache_key)
        if cached is not None:
            return cached

        place = self._geocode_nominatim(cleaned) or self._geocode_photon(cleaned)
        if place is None:
            raise PlaceNotFoundError(
                f"Could not find a location matching '{cleaned}'. "
                "Try 'City, ST' (for example 'Springfield, IL').",
                details={"query": cleaned},
            )

        self._forward_cache.set(cache_key, place)
        return place

    def suggest(self, query: str, limit: int = 6) -> list[Place]:
        """Autocomplete helper for the UI. Never raises on an empty result."""
        cleaned = " ".join((query or "").split())
        if len(cleaned) < 2:
            return []
        try:
            # Over-fetch then rank: the provider's own ordering is not tuned for
            # "places a truck can actually be dispatched to".
            results = self._query_photon(cleaned, max(limit * 4, 12))
            ranked = _rank_places(results, cleaned)[:limit]
            if ranked:
                return ranked
        except Exception:  # pragma: no cover - autocomplete must stay non-fatal
            logger.warning("Photon suggestion lookup failed", exc_info=True)
        try:
            found = self._suggest_nominatim(cleaned, max(limit * 2, 8))
            return _rank_places(found, cleaned)[:limit]
        except Exception:  # pragma: no cover
            logger.warning("Nominatim suggestion lookup failed", exc_info=True)
            return []

    def _geocode_nominatim(self, query: str) -> Place | None:
        try:
            payload = get_json(
                f"{self._nominatim}/search",
                {
                    "q": query,
                    "format": "jsonv2",
                    "addressdetails": 1,
                    "limit": 1,
                    "countrycodes": "us,ca",
                },
            )
        except Exception:
            logger.warning("Nominatim geocode failed for %r", query, exc_info=True)
            return None

        if not isinstance(payload, list) or not payload:
            return None
        return self._from_nominatim(payload[0])

    def _geocode_photon(self, query: str) -> Place | None:
        ranked = _rank_places(self._query_photon(query, limit=8), query)
        return ranked[0] if ranked else None

    def _suggest_nominatim(self, query: str, limit: int) -> list[Place]:
        payload = get_json(
            f"{self._nominatim}/search",
            {
                "q": query,
                "format": "jsonv2",
                "addressdetails": 1,
                "limit": limit,
                "countrycodes": "us,ca",
            },
        )
        if not isinstance(payload, list):
            return []
        return [self._from_nominatim(item) for item in payload]

    def _query_photon(self, query: str, limit: int) -> list[Place]:
        payload = get_json(
            f"{self._photon}/api",
            {"q": query, "limit": limit, "lang": "en", "bbox": "-170,15,-50,72"},
        )
        features = (payload or {}).get("features") or []
        return [p for p in (self._from_photon(f) for f in features) if p is not None]

    # -- reverse ---------------------------------------------------------
    def reverse(self, lat: float, lng: float) -> Place:
        """Resolve coordinates to a human readable ``City, ST`` label."""
        key = f"{round(lat, 4)},{round(lng, 4)}"
        cached = self._reverse_cache.get(key)
        if cached is not None:
            return cached

        place = self._reverse_photon(lat, lng)
        # Photon answers in milliseconds but sometimes only knows the state or a
        # county for rural points; ask a second provider for a real locality.
        if place is None or place.weak or not place.city:
            better = self._reverse_bigdatacloud(lat, lng)
            if better is not None:
                place = better
            elif place is None:
                place = self._reverse_nominatim(lat, lng)

        if place is None:
            place = Place(label=f"{lat:.4f}, {lng:.4f}", lat=lat, lng=lng, source="coordinates")

        self._reverse_cache.set(key, place)
        return place

    def _reverse_photon(self, lat: float, lng: float) -> Place | None:
        try:
            payload = get_json(
                f"{self._photon}/reverse",
                {"lat": lat, "lon": lng, "lang": "en", "limit": 5},
            )
        except Exception:
            logger.warning("Photon reverse geocode failed for %s,%s", lat, lng, exc_info=True)
            return None
        features = (payload or {}).get("features") or []
        if not features:
            return None

        weak: Place | None = None
        for feature in features:
            candidate = self._from_photon(feature, lat, lng)
            if candidate is None:
                continue
            if candidate.city and not candidate.weak:
                return candidate
            if weak is None:
                weak = candidate
        return weak

    def _reverse_bigdatacloud(self, lat: float, lng: float) -> Place | None:
        """Key-less fallback that resolves rural points to a real locality."""
        try:
            payload = get_json(
                f"{self._bigdatacloud}/data/reverse-geocode-client",
                {"latitude": lat, "longitude": lng, "localityLanguage": "en"},
            )
        except Exception:
            logger.warning("BigDataCloud reverse failed for %s,%s", lat, lng, exc_info=True)
            return None
        if not isinstance(payload, dict):
            return None

        city = (payload.get("city") or payload.get("locality") or "").strip()
        if not city:
            return None
        state_code = (payload.get("principalSubdivisionCode") or "").split("-")[-1]
        state = _norm_state(state_code or payload.get("principalSubdivision") or "")
        return Place(
            label=f"{city}, {state}" if state else city,
            lat=lat,
            lng=lng,
            city=city,
            state=state,
            country=payload.get("countryName") or "",
            source="bigdatacloud",
        )

    def _reverse_nominatim(self, lat: float, lng: float) -> Place | None:
        try:
            payload = get_json(
                f"{self._nominatim}/reverse",
                {"lat": lat, "lon": lng, "format": "jsonv2", "addressdetails": 1, "zoom": 10},
            )
        except Exception:
            logger.warning("Nominatim reverse geocode failed for %s,%s", lat, lng, exc_info=True)
            return None
        if not isinstance(payload, dict) or not payload:
            return None
        return self._from_nominatim(payload)

    # -- mapping ---------------------------------------------------------
    def _from_nominatim(self, item: dict) -> Place:
        address = item.get("address") or {}
        city = (
            address.get("city")
            or address.get("town")
            or address.get("village")
            or address.get("hamlet")
            or address.get("county")
            or ""
        )
        state = _norm_state(address.get("state") or address.get("state_code") or "")
        display = (item.get("display_name") or "").strip()
        return Place(
            label=display or ", ".join(p for p in (city, state) if p),
            lat=float(item.get("lat", 0.0)),
            lng=float(item.get("lon", 0.0)),
            city=city,
            state=state,
            country=address.get("country") or "",
            source="nominatim",
            raw=item,
        )

    def _from_photon(
        self, feature: dict, lat: float | None = None, lng: float | None = None
    ) -> Place | None:
        props = feature.get("properties") or {}
        coords = (feature.get("geometry") or {}).get("coordinates") or []
        if lat is None or lng is None:
            if len(coords) < 2:
                return None
            lng, lat = float(coords[0]), float(coords[1])

        name = (props.get("name") or "").strip()
        osm_key = (props.get("osm_key") or "").lower()
        osm_value = (props.get("osm_value") or "").lower()
        rank = _PLACE_RANK.get(osm_value, 30)

        city = (
            props.get("city")
            or props.get("town")
            or props.get("village")
            or props.get("locality")
            or ""
        )
        weak = False
        if not city or _PLACEHOLDER_CITY_RE.search(city):
            county = props.get("district") or props.get("county") or ""
            if county and not _PLACEHOLDER_CITY_RE.search(county):
                county = f"{county} County" if "count" not in county.lower() else county
            city = "" if _PLACEHOLDER_CITY_RE.search(county) else county
            weak = bool(city)

        # Photon leaves `city` empty when the match *is* the city, so the place name
        # only survives in `name`. Without this, a suggestion for "Nashville"
        # degrades to the bare state code "TN" and picking it geocodes to the middle
        # of Tennessee.
        if not city and name and not _PLACEHOLDER_CITY_RE.search(name):
            if osm_key == "place" and rank >= _POPULATED_RANK:
                city = name
                weak = False

        state = _norm_state(props.get("state") or props.get("state_code") or "")
        if (props.get("countrycode") or "").lower() not in {"us", "ca"}:
            return None

        label = ", ".join(p for p in (city, state) if p) or name
        return Place(
            label=label,
            lat=float(lat),
            lng=float(lng),
            city=city,
            state=state,
            country=props.get("country") or "",
            source="photon",
            weak=weak,
            rank=rank,
            raw=props,
        )


_geocoder: Geocoder | None = None


def get_geocoder() -> Geocoder:
    """Lazily construct the process-wide geocoder."""
    global _geocoder
    if _geocoder is None:
        _geocoder = Geocoder()
    return _geocoder

