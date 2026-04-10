"""Helper CLI to install the Playwright Chromium browser binary.

``pip install visual-annotation-mcp`` installs the Python package but not the
browser Chromium itself, which Playwright fetches on demand. This script
exposes a thin ``visual-annotation-mcp-install-browsers`` entry point so users
don't have to remember the underlying ``python -m playwright install chromium``
incantation.
"""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    """Run ``python -m playwright install chromium`` in the current interpreter."""
    print("Installing Playwright Chromium for visual-annotation-mcp ...")
    try:
        rc = subprocess.call(
            [sys.executable, "-m", "playwright", "install", "chromium"]
        )
    except FileNotFoundError as exc:
        print(f"Could not launch Python interpreter: {exc}", file=sys.stderr)
        return 1
    if rc == 0:
        print("Done. You can now run `visual-annotation-mcp`.")
    else:
        print(
            "playwright install exited with a non-zero status. "
            "Try running `python -m playwright install chromium` manually.",
            file=sys.stderr,
        )
    return rc


if __name__ == "__main__":
    sys.exit(main())
