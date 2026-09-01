from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from yfphonecam.version import __version__


def main(candidate: str | None = None) -> int:
    tag = candidate or os.environ.get("GITHUB_REF_NAME", "")
    expected = f"v{__version__}"
    if not re.fullmatch(r"v\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", tag):
        print(f"Invalid release tag: {tag!r}", file=sys.stderr)
        return 1
    if tag != expected:
        print(f"Version mismatch: source expects {expected}, received {tag}", file=sys.stderr)
        return 1
    print(f"Version verified: {tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else None))
