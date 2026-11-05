"""Timing of importing a 10,000-track Rekordbox XML (reported, not asserted)."""

import time
import tracemalloc
from pathlib import Path

from support.rekordbox import RekordboxXml, playlist
from tunedex.adapters.rekordbox import RekordboxAdapter
from tunedex.planning import Engine, assume_yes

COUNT = 10_000


def large_xml(tmp_path: Path) -> Path:
    xml = RekordboxXml()
    ids: list[str] = []
    for i in range(COUNT):
        track = xml.add_track(
            f"C:/Music/{i:05d}.mp3",
            Name=f"Track {i}",
            Artist=f"Artist {i % 97}",
            AverageBpm="128.00",
            Tonality=f"{i % 12 + 1}A",
            TotalTime="300",
        )
        for marker in range(4):
            xml.add_tempo(track, f"{0.1 + 30 * marker:.3f}", "128.00")
        for slot in range(3):
            xml.add_mark(track, f"{10 + 20 * slot:.3f}", num=slot, rgb=(255, 0, 0))
        ids.append(track)
    xml.nodes = [playlist(f"Playlist {p}", ids[p::20][:200]) for p in range(20)]
    return xml.write(tmp_path / "rekordbox.xml", crlf=True)


def test_import_timings(tmp_path: Path, engine: Engine) -> None:
    path = large_xml(tmp_path)
    adapter = RekordboxAdapter()

    started = time.perf_counter()
    adapter.read(path)
    read = time.perf_counter() - started
    tracemalloc.start()
    adapter.read(path)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    started = time.perf_counter()
    plan = engine.plan_import(adapter, path)
    planned = time.perf_counter() - started
    started = time.perf_counter()
    engine.apply(plan, assume_yes)
    applied = time.perf_counter() - started
    started = time.perf_counter()
    again = engine.plan_import(adapter, path)
    replanned = time.perf_counter() - started

    assert len(plan.tracks) == COUNT and again.empty
    size = path.stat().st_size / 1e6
    print(
        f"\n{COUNT} Rekordbox tracks ({size:.0f} MB XML): read {read:.2f}s"
        f" (peak {peak / 1e6:.0f} MB), plan {planned:.2f}s, apply {applied:.2f}s,"
        f" re-plan {replanned:.2f}s"
    )
