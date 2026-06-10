from __future__ import annotations

import subprocess
from pathlib import Path
import shutil


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    frontend = root / "frontend"
    if not frontend.exists():
        raise RuntimeError("frontend directory does not exist")

    npm = shutil.which("npm")
    if not npm:
        raise RuntimeError("npm executable not found in PATH")

    build = subprocess.run(
        [npm, "run", "build"],
        cwd=frontend,
        check=False,
        capture_output=True,
        text=True,
    )
    if build.returncode != 0:
        raise RuntimeError(f"frontend build failed:\n{build.stdout}\n{build.stderr}")

    index_html = frontend / "dist" / "index.html"
    if not index_html.exists():
        raise RuntimeError("frontend build did not produce dist/index.html")

    print("Part 7 verification passed.")
    print("Frontend build artifact exists at frontend/dist/index.html")


if __name__ == "__main__":
    main()
