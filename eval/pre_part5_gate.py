from __future__ import annotations

import subprocess
import sys
from pathlib import Path


CHECKS = [
    "eval/verify_part2.py",
    "eval/verify_part3.py",
    "eval/verify_part4.py",
]


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    for script in CHECKS:
        script_path = root / script
        print(f"[gate] Running {script} ...")
        completed = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=root,
            check=False,
        )
        if completed.returncode != 0:
            raise SystemExit(f"[gate] FAILED at {script} (exit={completed.returncode})")
        print(f"[gate] PASS {script}")
    print("[gate] All pre-Part-5 checks passed.")


if __name__ == "__main__":
    main()
