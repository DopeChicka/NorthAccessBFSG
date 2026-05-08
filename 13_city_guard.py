"""Validate that the city input file exists and is readable.

This guard intentionally performs only structural checks. It does not invent or
modify city data.
"""

from __future__ import annotations

import csv
from pathlib import Path

CITY_FILE = Path("orte_deutschland.csv")


def validate_city_file(path: Path = CITY_FILE) -> dict[str, int | str]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing city source file: {path}")

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"City source file has no header: {path}")
        row_count = sum(1 for _ in reader)

    return {"file": str(path), "rows": row_count}


def main() -> int:
    result = validate_city_file()
    print(f"CITY_GUARD_OK file={result['file']} rows={result['rows']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
