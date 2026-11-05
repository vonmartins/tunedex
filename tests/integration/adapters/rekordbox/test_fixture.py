"""The hand-made Rekordbox 7.2.14 export; expected values are in its README."""

import datetime
from pathlib import Path

import pytest

from support.adapter_contract import assert_plan_writes_nothing, assert_read_only
from tunedex.adapters.errors import AdapterError
from tunedex.adapters.registry import get_adapter
from tunedex.adapters.rekordbox import RekordboxAdapter
from tunedex.model.beatgrid import BeatMarker
from tunedex.model.cue import Cue, CueKind
from tunedex.model.library import Library
from tunedex.model.playlist import Folder, Playlist
from tunedex.model.track import Track

FIXTURE = Path(__file__).parents[3] / "fixtures" / "rekordbox" / "rekordbox-7.2.14.xml"
REKORDBOX = RekordboxAdapter()


@pytest.fixture(scope="module")
def result() -> tuple[Library, tuple[str, ...], dict[str, Track]]:
    read = assert_read_only(REKORDBOX, FIXTURE)
    by_id = {read.keys[t]: read.library.tracks[t] for t in read.library.tracks}
    return read.library, read.warnings, by_id


def test_detected() -> None:
    detection = REKORDBOX.detect(FIXTURE)

    assert detection.matches
    assert detection.reason == "Rekordbox XML export (rekordbox 7.2.14)"


def test_registered() -> None:
    adapter = get_adapter("rekordbox")

    assert isinstance(adapter, RekordboxAdapter)
    assert adapter.capabilities.folders and adapter.capabilities.beatgrid
    assert not adapter.capabilities.tags and not adapter.capabilities.smartlists
    assert set(adapter.capabilities.cue_kinds) == set(CueKind)


def test_write_refused(tmp_path: Path) -> None:
    with pytest.raises(AdapterError, match="not supported yet"):
        assert_plan_writes_nothing(REKORDBOX, Library(), tmp_path / "rekordbox.xml")
    assert not (tmp_path / "rekordbox.xml").exists()


def test_tracks(result: tuple[Library, tuple[str, ...], dict[str, Track]]) -> None:
    library, _, by_id = result

    assert len(library.tracks) == 7
    drift = by_id["90000001"]
    assert drift.path == "C:/Users/DJ/Music/Nadia Ferro - Lowland Drift.mp3"
    assert (drift.bpm, drift.key and drift.key.open_key(), drift.key_original) == (128, "8m", "3A")
    assert drift.beatgrid is not None
    assert drift.beatgrid.markers == (BeatMarker(position_us=212_000, bpm=128.0),)
    assert drift.cues == (
        Cue(kind=CueKind.HOT, start_us=75_212_000, slot=0, color="#FF376F"),
        Cue(kind=CueKind.HOT, start_us=120_212_000, slot=1, color="#45ACDB"),
    )
    assert (drift.album, drift.label, drift.track_number, drift.disc_number) == (
        "Lowlands",
        "Example Records",
        2,
        None,
    )
    assert drift.date_added == datetime.date(2026, 8, 22)
    assert drift.unmapped["rekordbox"]["Kind"] == "Archivo MP3"  # type: ignore[index]

    mos = by_id["90000002"]
    assert (mos.title, mos.album) == ("M髎", "Mós")
    assert mos.path == "C:/Users/DJ/Music/Orla Vint - Mós.mp3"
    assert (mos.year, mos.track_number) == (None, None)
    assert mos.cues == (
        Cue(kind=CueKind.HOT, start_us=96_041_000, slot=2, name="something", color="#7DC13D"),
    )

    watch = by_id["90000003"]
    assert watch.artist == "Kestrel & Moth"
    assert watch.beatgrid is not None
    assert [m.position_us for m in watch.beatgrid.markers] == [231_000, 37_752_000, 75_272_000]
    assert {m.beat for m in watch.beatgrid.markers} == {2}
    assert watch.cues == (
        Cue(kind=CueKind.MEMORY, start_us=231_000),
        Cue(kind=CueKind.HOT, start_us=231_000, slot=0, color="#FF376F"),
        Cue(kind=CueKind.HOT, start_us=60_250_000, slot=7, name="Drop", color="#E62828"),
    )
    assert (watch.rating, watch.disc_number, watch.track_number, watch.play_count) == (4, 1, 4, 3)
    assert (watch.remixer, watch.mix, watch.composer) == (
        "Pale Signal",
        "Dub",
        "K. Moth/R. Kestrel",
    )

    engine = by_id["90000004"]
    assert (engine.beatgrid, engine.bpm, engine.key and engine.key.open_key()) == (
        None,
        87.48,
        "10d",
    )
    assert len(engine.unmapped["rekordbox"]["tempo"]) == 2  # type: ignore[arg-type,index]

    pool = by_id["90000005"]
    assert (pool.file_format, pool.sample_rate, pool.bitrate) == ("wav", 48000, 1411)
    assert (pool.color, pool.rating, pool.key and pool.key.open_key()) == ("#FF007F", 3, "2d")
    assert pool.cues == (
        Cue(kind=CueKind.LOOP, start_us=10_000_000, end_us=17_500_000),
        Cue(
            kind=CueKind.LOOP,
            start_us=30_144_000,
            end_us=31_909_000,
            slot=1,
            name="Roll",
            color="#45ACDB",
        ),
    )
    assert [m["Type"] for m in pool.unmapped["rekordbox"]["marks"]] == ["1", "3"]  # type: ignore[index,union-attr]

    noir = by_id["90000006"]
    assert noir.path == "D:/House/Ñandú Collective - Café Noir.mp3"
    assert (noir.rating, noir.key and noir.key.open_key()) == (1, "7d")
    assert noir.beatgrid is not None
    assert len(noir.beatgrid.markers) == 2

    sketch = by_id["90000007"]
    assert (sketch.artist, sketch.bpm, sketch.key, sketch.year) == (None, None, None, None)
    assert (sketch.duration_us, sketch.bitrate, sketch.sample_rate) == (None, None, None)


def test_playlists(result: tuple[Library, tuple[str, ...], dict[str, Track]]) -> None:
    library, _, by_id = result
    ids = {track.id: key for key, track in by_id.items()}

    def keys(node: Playlist) -> list[str]:
        return [ids[t] for t in node.entries]

    empty, warmup, sets, by_location, archive = library.playlists
    assert isinstance(empty, Playlist)
    assert (empty.name, empty.entries) == ("Lista sin título", ())
    assert isinstance(warmup, Playlist)
    assert keys(warmup) == ["90000006", "90000001", "90000001"]
    assert isinstance(sets, Folder)
    (peak,) = sets.children
    assert isinstance(peak, Playlist)
    assert keys(peak) == ["90000003", "90000004", "90000005", "90000002", "90000003"]
    assert isinstance(by_location, Playlist)
    assert (by_location.name, keys(by_location)) == ("D:", ["90000004", "90000006"])
    assert isinstance(archive, Folder)
    assert (archive.name, archive.children) == ("Archive", ())


def test_warnings(result: tuple[Library, tuple[str, ...], dict[str, Track]]) -> None:
    _, warnings, _ = result

    assert set(warnings) == {
        "Brightwater - Hollow Engine: beat grid not read (two markers are at the same"
        " position or out of order); Rekordbox's markers are kept",
        "tracks skipped because their location repeats an earlier one: 1",
        "playlist entries left out (no such track): 1",
    }
