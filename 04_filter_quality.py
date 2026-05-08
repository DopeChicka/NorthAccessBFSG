"""Minimal quality filter entrypoint for the guarded pipeline.

The real data source is expected at ``data/orte_deutschland.csv``. This step
checks that the raw semicolon-separated CSV is readable and contains usable
rows. It does not perform substring-based city matching.
"""

from __future__ import annotations

from app.discovery.place_resolver import DEFAULT_CITY_DATA_PATH, PlaceDataError, load_places


INPUT_FILE = DEFAULT_CITY_DATA_PATH


def inspect_input() -> dict[str, int | str]:
    try:
        places = load_places(INPUT_FILE)
    except PlaceDataError:
        raise

    return {"input": str(INPUT_FILE), "usable_rows": len(places)}


def main() -> int:
    result = inspect_input()
    print(f"FILTER_QUALITY_OK input={result['input']} usable_rows={result['usable_rows']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
