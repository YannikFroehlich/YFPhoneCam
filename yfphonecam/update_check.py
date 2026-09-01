from __future__ import annotations

import json
import re
import time
import urllib.request
from dataclasses import dataclass
from functools import total_ordering

from .version import GITHUB_REPOSITORY, __version__

_CHECK_INTERVAL_SECONDS = 24 * 60 * 60


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    url: str
    name: str


@total_ordering
@dataclass(frozen=True)
class _SemVersion:
    major: int
    minor: int
    patch: int
    prerelease: tuple[str, ...] | None = None

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, _SemVersion):
            return NotImplemented
        core = (self.major, self.minor, self.patch)
        other_core = (other.major, other.minor, other.patch)
        if core != other_core:
            return core < other_core
        if self.prerelease is None:
            return False
        if other.prerelease is None:
            return True
        for left, right in zip(self.prerelease, other.prerelease, strict=False):
            if left == right:
                continue
            left_numeric = left.isdigit()
            right_numeric = right.isdigit()
            if left_numeric and right_numeric:
                return int(left) < int(right)
            if left_numeric != right_numeric:
                return left_numeric
            return left < right
        return len(self.prerelease) < len(other.prerelease)


def _version_key(value: str) -> _SemVersion:
    match = re.fullmatch(
        r"v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
        r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
        r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?",
        value,
    )
    if not match:
        return _SemVersion(0, 0, 0, ("invalid",))
    major, minor, patch, prerelease = match.groups()
    parts = tuple(prerelease.split(".")) if prerelease else None
    return _SemVersion(int(major), int(minor), int(patch), parts)


def should_check(last_check: int, now: int | None = None) -> bool:
    current = int(time.time()) if now is None else now
    return current - max(0, last_check) >= _CHECK_INTERVAL_SECONDS


def check_for_update(timeout: float = 5.0) -> ReleaseInfo | None:
    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases?per_page=10"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"YFPhoneCam/{__version__}",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        releases = json.load(response)
    current = _version_key(__version__)
    candidates = [item for item in releases if not item.get("draft")]
    candidates.sort(key=lambda item: _version_key(str(item.get("tag_name", ""))), reverse=True)
    for item in candidates:
        version = str(item.get("tag_name", "")).lstrip("v")
        if _version_key(version) > current:
            return ReleaseInfo(
                version=version,
                url=str(item.get("html_url", "")),
                name=str(item.get("name") or item.get("tag_name") or version),
            )
    return None
