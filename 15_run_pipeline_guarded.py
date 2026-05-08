"""Guarded pipeline runner.

The runner fails before execution if any runtime file it depends on is absent.
It references only files that are part of this repository.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REQUIRED_RUNTIME_FILES = (
    "04_filter_quality.py",
    "05_run_pipeline.py",
    "13_city_guard.py",
    "14_evidence_gate.py",
    "orte_deutschland.csv",
)

GUARD_SCRIPTS = (
    "13_city_guard.py",
    "14_evidence_gate.py",
)

PIPELINE_SCRIPT = "05_run_pipeline.py"


def assert_runtime_files_exist(root: Path = Path(".")) -> None:
    missing = [name for name in REQUIRED_RUNTIME_FILES if not (root / name).is_file()]
    if missing:
        missing_list = ", ".join(missing)
        raise FileNotFoundError(f"Missing runtime dependency files: {missing_list}")


def run_python_script(script_name: str) -> None:
    completed = subprocess.run(
        [sys.executable, script_name],
        check=False,
        cwd=Path("."),
    )
    if completed.returncode != 0:
        raise RuntimeError(f"Pipeline step failed: {script_name} exit={completed.returncode}")


def main() -> int:
    assert_runtime_files_exist()
    for script_name in GUARD_SCRIPTS:
        run_python_script(script_name)
    run_python_script(PIPELINE_SCRIPT)
    print("PIPELINE_GUARDED_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
