"""Importing a Rekordbox XML through the generic import path."""

import dataclasses
from pathlib import Path

from support.audio import tagged_copy
from support.rekordbox import RekordboxXml, folder, playlist
from tunedex.adapters.rekordbox import RekordboxAdapter
from tunedex.model.playlist import Folder, Playlist
from tunedex.planning import Engine, assume_yes
from tunedex.planning.selection import target_name
from tunedex.store import Store

REKORDBOX = RekordboxAdapter()


def test_tracks_and_playlists_imported(engine: Engine, store: Store, tmp_path: Path) -> None:
    xml = RekordboxXml()
    a = xml.add_track("C:/Users/DJ/Music/a.mp3", Name="A", AverageBpm="128.00", Tonality="8A")
    xml.nodes = [folder("tunedex", playlist("tunedextest", [a]))]
    path = xml.write(tmp_path / "rekordbox.xml")
    before = path.read_bytes(), path.stat().st_mtime_ns

    engine.apply(engine.plan_import(REKORDBOX, path), assume_yes)

    (track,) = store.list_tracks()
    assert (track.title, track.bpm, track.key and track.key.open_key()) == ("A", 128.0, "1m")
    (source,) = store.children()
    assert isinstance(source, Folder)
    assert source.name == "Rekordbox"
    (sub,) = source.children
    assert isinstance(sub, Folder)
    (test,) = sub.children
    assert isinstance(test, Playlist)
    assert (test.name, test.entries) == ("tunedextest", (track.id,))
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before


def test_reimport_unchanged_is_empty(engine: Engine, tmp_path: Path) -> None:
    xml = RekordboxXml()
    a = xml.add_track("/music/a.mp3", Name="A")
    xml.add_tempo(a, "0.100", "128.00")
    xml.add_mark(a, "1.000", num=0)
    xml.nodes = [playlist("Set", [a])]
    path = xml.write(tmp_path / "rekordbox.xml")
    engine.apply(engine.plan_import(REKORDBOX, path), assume_yes)

    plan = engine.plan_import(REKORDBOX, path)

    assert plan.empty


def test_relocated_track_stays_linked(engine: Engine, store: Store, tmp_path: Path) -> None:
    xml = RekordboxXml()
    xml.add_track("C:/Users/DJ/Music/a.mp3", track_id="7", Name="A")
    path = xml.write(tmp_path / "rekordbox.xml")
    engine.apply(engine.plan_import(REKORDBOX, path), assume_yes)
    (track,) = store.list_tracks()
    store.update_track(dataclasses.replace(track, path_origin="/home/me/music/a.mp3"))
    xml = RekordboxXml()
    xml.add_track("C:/Users/DJ/Music/a.mp3", track_id="7", Name="A (edit)")
    xml.write(path)

    engine.apply(engine.plan_import(REKORDBOX, path), assume_yes)

    (after,) = store.list_tracks()
    assert (after.id, after.path, after.title) == (track.id, "/home/me/music/a.mp3", "A (edit)")


def test_scanned_title_kept_over_a_mangled_one(
    engine: Engine, store: Store, tmp_path: Path
) -> None:
    music = tmp_path / "music"
    tagged_copy(music, "mp3", name="Orla Vint - Mós.mp3", title="Mós", artist="Orla Vint")
    engine.apply(engine.plan_scan(music), assume_yes)
    (scanned,) = store.list_tracks()
    xml = RekordboxXml()
    a = xml.add_track(
        "C:/Users/DJ/Music/Orla Vint - Mós.mp3", Name="M髎", Artist="Orla Vint", AverageBpm="160.00"
    )
    xml.add_mark(a, "96.041", num=2, name="something")
    path = xml.write(tmp_path / "rekordbox.xml")

    plan = engine.plan_import(REKORDBOX, path, find_in=music)
    engine.apply(plan, assume_yes)

    (track,) = store.list_tracks()
    assert (track.id, track.path) == (scanned.id, scanned.path)
    assert (track.title, track.bpm, len(track.cues)) == ("Mós", 160.0, 1)
    assert not plan.conflicts


def same_song_twice(tmp_path: Path) -> tuple[Path, Path]:
    music = tmp_path / "music"
    tagged_copy(music, "mp3", name="a.mp3", title="A")
    xml = RekordboxXml()
    xml.add_track("D:/a.mp3", track_id="127", Name="A")
    kept = xml.add_track("C:/Music/a.mp3", track_id="540", Name="A")
    xml.add_mark(kept, "96.041", num=2)
    xml.nodes = [playlist("Set", [kept])]
    return xml.write(tmp_path / "rekordbox.xml"), music


def test_same_song_twice_joined(engine: Engine, store: Store, tmp_path: Path) -> None:
    path, music = same_song_twice(tmp_path)

    plan = engine.plan_import(REKORDBOX, path, find_in=music)
    engine.apply(plan, assume_yes)

    (track,) = store.list_tracks()
    assert Path(track.path) == (music / "a.mp3").absolute()
    assert [c.slot for c in track.cues] == [2]
    (source,) = store.children()
    assert isinstance(source, Folder)
    (set_,) = source.children
    assert isinstance(set_, Playlist)
    assert set_.entries == (track.id,)
    (warning,) = [w for w in plan.warnings if "joined" in w]
    assert warning.startswith("1 source items share a file") and "D:/a.mp3" in warning
    assert not [w for w in plan.warnings if "several files" in w]
    source_name = target_name(REKORDBOX.name, path.absolute())
    assert store.merged_items(source_name) == {"127": track.id}
    assert store.merged_paths() == {"D:/a.mp3": track.id}


def test_joined_item_on_reimport(engine: Engine, tmp_path: Path) -> None:
    path, music = same_song_twice(tmp_path)
    engine.apply(engine.plan_import(REKORDBOX, path, find_in=music), assume_yes)

    plan = engine.plan_import(REKORDBOX, path, find_in=music)

    assert plan.empty
    assert not [w for w in plan.warnings if "joined" in w or "several files" in w]


def test_most_cues_then_most_entries_kept(engine: Engine, store: Store, tmp_path: Path) -> None:
    music = tmp_path / "music"
    tagged_copy(music, "mp3", name="a.mp3", title="A")
    xml = RekordboxXml()
    first = xml.add_track("C:/a.mp3", Name="A", Comments="first")
    second = xml.add_track("D:/a.mp3", Name="A", Comments="second")
    xml.nodes = [playlist("Set", [second, second, first])]
    path = xml.write(tmp_path / "rekordbox.xml")

    engine.apply(engine.plan_import(REKORDBOX, path, find_in=music), assume_yes)

    (track,) = store.list_tracks()
    assert track.comment == "second"
