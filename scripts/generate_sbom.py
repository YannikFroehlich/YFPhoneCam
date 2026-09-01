from __future__ import annotations

import json
import re
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from yfphonecam.version import __version__


def components_from_lock(path: Path) -> list[dict[str, object]]:
    components: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+)==([^ ;\\]+)", line)
        if not match:
            continue
        name, version = match.groups()
        key = (name.lower(), version)
        if key in seen:
            continue
        seen.add(key)
        components.append(
            {
                "type": "library",
                "name": name,
                "version": version,
                "purl": f"pkg:pypi/{name.lower().replace('_', '-')}@{version}",
            }
        )
    return components


def main() -> int:
    destination = Path(sys.argv[1] if len(sys.argv) > 1 else "dist/YFPhoneCam.cdx.json")
    document = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(UTC).isoformat(),
            "component": {
                "type": "application",
                "name": "YFPhoneCam",
                "version": __version__,
            },
        },
        "components": components_from_lock(Path("requirements.lock")),
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
