"""Validate that the evidence output directory can be used by the pipeline."""

from __future__ import annotations

from pathlib import Path

EVIDENCE_DIR = Path("evidence-data")


def ensure_evidence_dir(path: Path = EVIDENCE_DIR) -> dict[str, str]:
    path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir():
        raise NotADirectoryError(f"Evidence path is not a directory: {path}")

    probe = path / ".write_check"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink()
    return {"directory": str(path)}


def main() -> int:
    result = ensure_evidence_dir()
    print(f"EVIDENCE_GATE_OK directory={result['directory']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
