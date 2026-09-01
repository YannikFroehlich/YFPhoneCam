from __future__ import annotations

import queue

from yfphonecam.state import put_latest


def test_put_latest_drops_stale_item() -> None:
    work: queue.Queue[int] = queue.Queue(maxsize=1)
    put_latest(work, 1)
    put_latest(work, 2)

    assert work.get_nowait() == 2
    assert work.empty()
