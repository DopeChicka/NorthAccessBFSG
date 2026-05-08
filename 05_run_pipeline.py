"""Minimal pipeline entrypoint used by the guarded runner."""

from __future__ import annotations

from importlib import import_module


def main() -> int:
    filter_quality = import_module("04_filter_quality")
    return int(filter_quality.main())


if __name__ == "__main__":
    raise SystemExit(main())
