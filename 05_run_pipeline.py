"""Minimal pipeline entrypoint used by the guarded runner."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

FILTER_STEP = Path("04_filter_quality.py")


def main() -> int:
    completed = subprocess.run(
        [sys.executable, str(FILTER_STEP)],
        check=False,
        cwd=Path("."),
    )
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
