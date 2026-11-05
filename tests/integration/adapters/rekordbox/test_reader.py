import datetime
from pathlib import Path

import pytest

from support.adapter_contract import tree_state
from support.rekordbox import CUE, FADE_IN, FADE_OUT, LOAD, LOOP, RekordboxXml, playlist
from tunedex.adapters.errors import AdapterReadError
from tunedex.adapters.rekordbox import RekordboxAdapter
from tunedex.model.beatgrid import BeatGrid, BeatMarker
from tunedex.model.cue import Cue, CueKind
from tunedex.model.key import Key, Mode
from tunedex.model.library import Library
from tunedex.model.track import Track

REKORDBOX = RekordboxAdapter()


def read(xml: RekordboxXml, tmp_path: Path) -> tuple[Library, tuple[str, ...]]:
    path = xml.write(tmp_path / "rekordbox.xml")
    before = tree_state(tmp_path)
    result = REKORDBOX.read(path)
    assert tree_state(tmp_path) == before
    return result.library, result.warnings


def only_track(library: Library) -> Track:
    (track,) = library.tracks.values()
    return track


# Detection


def test_detects_a_rekordbox_export(tmp_path: Path) -> None:
    path = RekordboxXml().write(tmp_path / "rekordbox.xml")

    detection = REKORDBOX.detect(path)

    assert detection.matches
    assert "rekordbox 7.2.14" in detection.reason


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        (b'<?xml version="1.0"?><NML VERSION="19"><COLLECTION/></NML>', "'DJ_PLAYLISTS'"),
        (b"\x00\x01 not xml", "not a readable XML"),
    ],
)
def test_foreign_files_do_not_match(tmp_path: Path, content: bytes, reason: str) -> None:
    path = tmp_path / "collection.nml"
    path.write_bytes(content)

    detection = REKORDBOX.detect(path)

    assert not detection.matches
    assert reason in detection.reason


def test_directory_and_missing_file_do_not_match(tmp_path: Path) -> None:
    assert not REKORDBOX.detect(tmp_path).matches
    assert "does not exist" in REKORDBOX.detect(tmp_path / "none.xml").reason


def test_other_product_read_with_a_warning(tmp_path: Path) -> None:
    xml = RekordboxXml(product="Lexicon", version="1.9")
    xml.add_track("/music/a.mp3", Name="A")

    library, warnings = read(xml, tmp_path)

    assert len(library.tracks) == 1
    assert any("Lexicon" in w for w in warnings)
    assert REKORDBOX.detect(tmp_path / "rekordbox.xml").matches


def test_truncated_file_refused(tmp_path: Path) -> None:
    xml = RekordboxXml()
    xml.add_track("/music/a.mp3", Name="A")
    data = xml.to_bytes()
    path = tmp_path / "rekordbox.xml"
    path.write_bytes(data[: data.index(b"<TRACK") + 20])

    with pytest.raises(AdapterReadError, match=r"rekordbox\.xml"):
        REKORDBOX.read(path)


def test_missing_collection_refused(tmp_path: Path) -> None:
    path = tmp_path / "rekordbox.xml"
    path.write_bytes(b'<DJ_PLAYLISTS Version="1.0.0"><PRODUCT Name="rekordbox"/></DJ_PLAYLISTS>')

    with pytest.raises(AdapterReadError, match="COLLECTION"):
        REKORDBOX.read(path)


# Locations


@pytest.mark.parametrize(
    ("url", "path"),
    [
        (
            "file://localhost/C:/Users/DJ/Music/Kestrel%20%26%20Moth%20-%20M%C3%B3s.mp3",
            "C:/Users/DJ/Music/Kestrel & Moth - Mós.mp3",
        ),
        ("file://localhost/Users/dj/Music/a.mp3", "/Users/dj/Music/a.mp3"),
        ("file://localhost/D:/House/%c3%91and%c3%ba.mp3", "D:/House/Ñandú.mp3"),
    ],
)
def test_locations_decoded(tmp_path: Path, url: str, path: str) -> None:
    xml = RekordboxXml()
    xml.add_track(Location=url, Name="A")

    library, _ = read(xml, tmp_path)

    assert only_track(library).path == path


@pytest.mark.parametrize("url", ["http://example.com/a.mp3", "file://localhost/", "a.mp3"])
def test_unsupported_location_skipped(tmp_path: Path, url: str) -> None:
    xml = RekordboxXml()
    xml.add_track(Location=url, Name="Glue", Artist="Bicep")

    library, warnings = read(xml, tmp_path)

    assert not library.tracks
    assert any("Bicep - Glue" in w for w in warnings)


def test_tracks_sharing_a_location(tmp_path: Path) -> None:
    xml = RekordboxXml()
    first = xml.add_track("/music/a.mp3", Name="First")
    second = xml.add_track("/music/./a.mp3", Name="Second")
    xml.nodes = [playlist("Set", [second, first])]

    library, warnings = read(xml, tmp_path)

    track = only_track(library)
    assert track.title == "First"
    (node,) = library.playlists
    assert node.entries == (track.id, track.id)  # type: ignore[union-attr]
    assert "tracks skipped because their location repeats an earlier one: 1" in warnings


# Track fields


def test_texts(tmp_path: Path) -> None:
    xml = RekordboxXml()
    xml.add_track(
        "/music/a.mp3",
        Name="Glue",
        Artist="Bicep",
        Album="",
        Genre="Techno",
        Composer="A. B",
        Grouping="G",
        Comments="Nice",
        Remixer="R",
        Label="Ninja Tune",
        Mix="Original",
    )

    track = only_track(read(xml, tmp_path)[0])

    assert (track.title, track.artist, track.album) == ("Glue", "Bicep", None)
    assert (track.genre, track.composer, track.grouping, track.comment) == (
        "Techno",
        "A. B",
        "G",
        "Nice",
    )
    assert (track.remixer, track.label, track.mix) == ("R", "Ninja Tune", "Original")


def test_wrongly_decoded_title_kept(tmp_path: Path) -> None:
    xml = RekordboxXml()
    xml.add_track("/music/a.mp3", Name="M髎")

    assert only_track(read(xml, tmp_path)[0]).title == "M髎"


def test_numeric_fields(tmp_path: Path) -> None:
    xml = RekordboxXml()
    xml.add_track(
        "/music/a.mp3",
        Year="2017",
        TrackNumber="3",
        DiscNumber="0",
        AverageBpm="126.42",
        TotalTime="363",
        BitRate="320",
        SampleRate="44100",
        DateAdded="2026-08-22",
        PlayCount="2",
    )

    track = only_track(read(xml, tmp_path)[0])

    assert (track.year, track.track_number, track.disc_number) == (2017, 3, None)
    assert track.bpm == 126.42
    assert track.duration_us == 363_000_000
    assert (track.bitrate, track.sample_rate, track.play_count) == (320, 44100, 2)
    assert track.date_added == datetime.date(2026, 8, 22)


def test_unanalysed_track(tmp_path: Path) -> None:
    xml = RekordboxXml()
    xml.add_track("/music/a.mp3", AverageBpm="0.00", Year="0", PlayCount="0", Tonality="")

    track = only_track(read(xml, tmp_path)[0])

    assert (track.bpm, track.year, track.play_count, track.key) == (None, None, None, None)


def test_unreadable_numbers_ignored(tmp_path: Path) -> None:
    xml = RekordboxXml()
    xml.add_track("/music/a.mp3", Year="soon", DateAdded="yesterday", Name="A")

    library, warnings = read(xml, tmp_path)

    assert only_track(library).year is None
    assert "unreadable Year values ignored: 1" in warnings
    assert "unreadable DateAdded values ignored: 1" in warnings


@pytest.mark.parametrize(("raw", "stars"), [("0", None), ("51", 1), ("153", 3), ("255", 5)])
def test_rating(tmp_path: Path, raw: str, stars: int | None) -> None:
    xml = RekordboxXml()
    xml.add_track("/music/a.mp3", Rating=raw)

    assert only_track(read(xml, tmp_path)[0]).rating == stars


def test_colour(tmp_path: Path) -> None:
    xml = RekordboxXml()
    xml.add_track("/music/a.mp3", Colour="0xFF007F")

    assert only_track(read(xml, tmp_path)[0]).color == "#FF007F"


def test_file_format_from_extension(tmp_path: Path) -> None:
    xml = RekordboxXml()
    xml.add_track("/music/a.wav", Kind="Archivo WAV")

    track = only_track(read(xml, tmp_path)[0])

    assert track.file_format == "wav"
    assert track.unmapped["rekordbox"]["Kind"] == "Archivo WAV"  # type: ignore[index]


def test_keys(tmp_path: Path) -> None:
    xml = RekordboxXml()
    xml.add_track("/music/a.mp3", Tonality="3A")
    xml.add_track("/music/b.mp3", Tonality="F#m")
    xml.add_track("/music/c.mp3", Tonality="13A")

    library, warnings = read(xml, tmp_path)

    by_path = {t.path: t for t in library.tracks.values()}
    a, b, c = by_path["/music/a.mp3"], by_path["/music/b.mp3"], by_path["/music/c.mp3"]
    assert a.key == Key(tonic=10, mode=Mode.MINOR)
    assert a.key_original == "3A"
    assert b.key == Key(tonic=6, mode=Mode.MINOR)
    assert (c.key, c.key_original) == (None, "13A")
    assert "keys in an unknown notation, kept only as the original key: 1" in warnings


def test_unmapped_data(tmp_path: Path) -> None:
    xml = RekordboxXml()
    track_id = xml.add_track("/music/a.mp3", Kind="MP3 File", Size="123", Energy="7")
    xml.add_element(track_id, "PHRASE", Kind="Intro")

    track = only_track(read(xml, tmp_path)[0])

    assert track.unmapped == {
        "rekordbox": {
            "TrackID": track_id,
            "Kind": "MP3 File",
            "Size": "123",
            "attributes": {"Energy": "7"},
            "elements": [{"tag": "PHRASE", "attributes": {"Kind": "Intro"}}],
        }
    }


def test_item_keys_are_track_ids(tmp_path: Path) -> None:
    xml = RekordboxXml()
    xml.add_track("/music/a.mp3", track_id="42")
    xml.write(tmp_path / "rekordbox.xml")

    result = REKORDBOX.read(tmp_path / "rekordbox.xml")

    assert list(result.keys.values()) == ["42"]
    assert set(result.keys) == set(result.library.tracks)


def test_repeated_track_id_skipped(tmp_path: Path) -> None:
    xml = RekordboxXml()
    xml.add_track("/music/a.mp3", track_id="42")
    xml.add_track("/music/b.mp3", track_id="42")

    library, warnings = read(xml, tmp_path)

    assert only_track(library).path == "/music/a.mp3"
    assert "tracks skipped because their TrackID repeats an earlier one: 1" in warnings


# Cues and loops


def test_hot_cue(tmp_path: Path) -> None:
    xml = RekordboxXml()
    track_id = xml.add_track("/music/a.mp3")
    xml.add_mark(track_id, "177.512", num=2, name="something", rgb=(230, 40, 40))

    track = only_track(read(xml, tmp_path)[0])

    assert track.cues == (
        Cue(kind=CueKind.HOT, start_us=177_512_000, slot=2, name="something", color="#E62828"),
    )


def test_memory_and_hot_cue_at_the_same_position(tmp_path: Path) -> None:
    xml = RekordboxXml()
    track_id = xml.add_track("/music/a.mp3")
    xml.add_mark(track_id, "0.231")
    xml.add_mark(track_id, "0.231", num=0, rgb=(255, 55, 111))

    track = only_track(read(xml, tmp_path)[0])

    assert track.cues == (
        Cue(kind=CueKind.MEMORY, start_us=231_000),
        Cue(kind=CueKind.HOT, start_us=231_000, slot=0, color="#FF376F"),
    )


def test_loops(tmp_path: Path) -> None:
    xml = RekordboxXml()
    track_id = xml.add_track("/music/a.mp3")
    xml.add_mark(track_id, "10.000", type=LOOP, end="17.500")
    xml.add_mark(track_id, "30.000", type=LOOP, num=1, end="31.000", name="Roll")

    track = only_track(read(xml, tmp_path)[0])

    assert track.cues == (
        Cue(kind=CueKind.LOOP, start_us=10_000_000, end_us=17_500_000),
        Cue(kind=CueKind.LOOP, start_us=30_000_000, end_us=31_000_000, slot=1, name="Roll"),
    )


def test_other_marks_kept_or_skipped(tmp_path: Path) -> None:
    xml = RekordboxXml()
    track_id = xml.add_track("/music/a.mp3")
    xml.add_mark(track_id, "0.000", type=FADE_IN, end="8.000")
    xml.add_mark(track_id, "300.000", type=FADE_OUT)
    xml.add_mark(track_id, "0.100", type=LOAD)
    xml.add_mark(track_id, "1.000", type=9)

    library, warnings = read(xml, tmp_path)

    track = only_track(library)
    assert track.cues == ()
    marks = track.unmapped["rekordbox"]["marks"]  # type: ignore[index]
    assert [m["Type"] for m in marks] == ["1", "2", "3"]  # type: ignore[index,union-attr]
    assert marks[0] == {"Name": "", "Type": "1", "Start": "0.000", "End": "8.000", "Num": "-1"}  # type: ignore[index]
    assert "marks of unknown types skipped: 1" in warnings


def test_cue_details(tmp_path: Path) -> None:
    xml = RekordboxXml()
    track_id = xml.add_track("/music/a.mp3")
    xml.add_mark(track_id, "1.000", num=0, name="")
    xml.add_mark(track_id, "2.000", num=0, name="Again")
    xml.add_mark(track_id, "3.000", type=LOOP, end="3.000")
    xml.add_mark(track_id, "4.000", type=LOOP)
    xml.add_mark(track_id, "later", type=CUE)

    library, warnings = read(xml, tmp_path)

    assert only_track(library).cues == (Cue(kind=CueKind.HOT, start_us=1_000_000, slot=0),)
    assert "cues on a pad already used skipped: 1" in warnings
    assert "loops without an end after their start skipped: 2" in warnings
    assert "cues with an unreadable position or pad skipped: 1" in warnings


# Beat grids


def test_constant_grid(tmp_path: Path) -> None:
    xml = RekordboxXml()
    track_id = xml.add_track("/music/a.mp3")
    xml.add_tempo(track_id, "0.227", "128.00")

    track = only_track(read(xml, tmp_path)[0])

    assert track.beatgrid == BeatGrid(markers=(BeatMarker(position_us=227_000, bpm=128.0),))


def test_markers_with_the_same_bpm_kept(tmp_path: Path) -> None:
    xml = RekordboxXml()
    track_id = xml.add_track("/music/a.mp3")
    for index in range(10):
        xml.add_tempo(track_id, f"{0.152 + 35 * index:.3f}", "124.37", battito=str(index % 4 + 1))

    track = only_track(read(xml, tmp_path)[0])

    assert track.beatgrid is not None
    assert len(track.beatgrid.markers) == 10
    assert track.beatgrid.markers[3] == BeatMarker(position_us=105_152_000, bpm=124.37, beat=4)


@pytest.mark.parametrize(
    ("tempos", "reason"),
    [
        ([("0.271", "174.96", "4/4", "1"), ("0.271", "43.74", "4/4", "1")], "same position"),
        ([("5.000", "120.00", "4/4", "1"), ("1.000", "120.00", "4/4", "1")], "out of order"),
        ([("0.100", "120.00", "3/4", "1")], "not 4/4"),
        ([("0.100", "120.00", "4/4", "5")], "outside 1 to 4"),
        ([("0.100", "0.00", "4/4", "1")], "unreadable"),
    ],
)
def test_grids_the_model_cannot_hold(
    tmp_path: Path, tempos: list[tuple[str, str, str, str]], reason: str
) -> None:
    xml = RekordboxXml()
    track_id = xml.add_track(
        "/music/a.mp3", Name="Hollow Engine", Artist="Brightwater", AverageBpm="87.48"
    )
    for inizio, bpm, metro, battito in tempos:
        xml.add_tempo(track_id, inizio, bpm, metro=metro, battito=battito)

    library, warnings = read(xml, tmp_path)

    track = only_track(library)
    assert track.beatgrid is None
    assert track.bpm == 87.48
    assert track.unmapped["rekordbox"]["tempo"] == [  # type: ignore[index]
        {"Inizio": i, "Bpm": b, "Metro": m, "Battito": t} for i, b, m, t in tempos
    ]
    (warning,) = [w for w in warnings if "beat grid" in w]
    assert warning.startswith("Brightwater - Hollow Engine:")
    assert reason in warning
