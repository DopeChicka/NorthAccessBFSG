"""City and postal-code resolution for lead discovery.

The resolver reads the raw Deutsche Post-style city data from
``data/orte_deutschland.csv``. The source is treated as mixed raw input: rows may
contain real places, organizations, or special postal recipients. Resolution is
therefore exact after normalization and never substring-based.
"""

from __future__ import annotations

import csv
import re
from dataclasses import asdict, dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CITY_DATA_PATH = PROJECT_ROOT / "data" / "orte_deutschland.csv"
REQUIRED_COLUMNS = {"plz", "stadt"}
POSTAL_CODE_PATTERN = re.compile(r"^\d{5}$")
WHITESPACE_PATTERN = re.compile(r"\s+")
UMLAUT_TRANSLATION = str.maketrans(
    {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "ß": "ss",
    }
)


class PlaceResolverError(ValueError):
    """Base error for place resolver failures."""


class PlaceDataError(PlaceResolverError):
    """Raised when the configured city data file is missing or invalid."""


class PlaceNotFoundError(PlaceResolverError):
    """Raised when a city cannot be resolved from usable city rows."""


@dataclass(frozen=True)
class PlaceMatch:
    city: str
    postal_code: str
    country: str = "DE"

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def normalize_city_name(value: str) -> str:
    normalized = value.strip().casefold().translate(UMLAUT_TRANSLATION)
    return WHITESPACE_PATTERN.sub(" ", normalized)


def _loose_umlaut_key(value: str) -> str:
    return value.replace("ae", "a").replace("oe", "o").replace("ue", "u")


def _match_keys(value: str) -> set[str]:
    normalized = normalize_city_name(value)
    if not normalized:
        return set()
    return {normalized, _loose_umlaut_key(normalized)}


def _normalized_fieldnames(fieldnames: list[str] | None) -> dict[str, str]:
    if not fieldnames:
        return {}
    return {name.strip().casefold(): name for name in fieldnames if name}


def _is_usable_row(postal_code: str, city: str) -> bool:
    return bool(POSTAL_CODE_PATTERN.match(postal_code.strip()) and city.strip())


def load_places(data_path: Path | str = DEFAULT_CITY_DATA_PATH) -> list[PlaceMatch]:
    path = Path(data_path)
    if not path.is_file():
        raise PlaceDataError(f"City data file is missing: {path}")

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, delimiter=";")
            fields = _normalized_fieldnames(reader.fieldnames)
            missing_columns = REQUIRED_COLUMNS - set(fields)
            if missing_columns:
                missing = ", ".join(sorted(missing_columns))
                raise PlaceDataError(f"City data file is missing required columns: {missing}")

            postal_field = fields["plz"]
            city_field = fields["stadt"]
            places = []
            seen = set()
            for row in reader:
                postal_code = (row.get(postal_field) or "").strip()
                city = (row.get(city_field) or "").strip()
                if not _is_usable_row(postal_code, city):
                    continue

                key = (postal_code, city)
                if key in seen:
                    continue
                seen.add(key)
                places.append(PlaceMatch(city=city, postal_code=postal_code))
    except UnicodeDecodeError as exc:
        raise PlaceDataError(f"City data file is not readable as UTF-8: {path}") from exc
    except csv.Error as exc:
        raise PlaceDataError(f"City data file is not readable CSV: {path}") from exc

    if not places:
        raise PlaceDataError(f"City data file has no usable city rows: {path}")

    return places


def resolve_city(city: str, data_path: Path | str = DEFAULT_CITY_DATA_PATH) -> list[PlaceMatch]:
    requested_keys = _match_keys(city)
    if not requested_keys:
        raise PlaceNotFoundError("No city name provided")

    matches = [
        place
        for place in load_places(data_path)
        if _match_keys(place.city) & requested_keys
    ]
    matches.sort(key=lambda place: (place.postal_code, place.city))

    if not matches:
        raise PlaceNotFoundError(f"No places found for city: {city}")

    return matches
