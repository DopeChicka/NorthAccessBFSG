"""Validate that the canonical city input file exists and has usable rows."""

from __future__ import annotations

from app.discovery.place_resolver import DEFAULT_CITY_DATA_PATH, PlaceDataError, load_places


CITY_FILE = DEFAULT_CITY_DATA_PATH


def validate_city_file() -> dict[str, int | str]:
    try:
        places = load_places(CITY_FILE)
    except PlaceDataError:
        raise

    return {"file": str(CITY_FILE), "rows": len(places)}


def main() -> int:
    result = validate_city_file()
    print(f"CITY_GUARD_OK file={result['file']} usable_rows={result['rows']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
