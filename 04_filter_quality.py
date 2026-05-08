"""Minimal quality filter entrypoint for the guarded pipeline.

The real data source is expected in ``orte_deutschland.csv``. This step only
checks that the file is readable and reports how many rows are available.
"""

from __future__ import annotations

import csv
from pathlib import Path

INPUT_FILE = Path("orte_deutschland.csv")


def inspect_input(path: Path = INPUT_FILE) -> dict[str, int | str]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing input file: {path}")

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"Input file has no CSV header: {path}")
        row_count = sum(1 for _ in reader)

    return {"input": str(path), "rows": row_count}


def main() -> int:
    result = inspect_input()
    print(f"FILTER_QUALITY_OK input={result['input']} rows={result['rows']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
