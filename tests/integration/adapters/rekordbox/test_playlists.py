from pathlib import Path

from support.rekordbox import Node, RekordboxXml, folder, location, playlist
from tunedex.adapters.rekordbox import RekordboxAdapter
from tunedex.model.library import Library
from tunedex.model.playlist import Folder, Playlist

REKORDBOX = RekordboxAdapter()


def read(xml: RekordboxXml, tmp_path: Path) -> tuple[Library, tuple[str, ...]]:
    result = REKORDBOX.read(xml.write(tmp_path / "rekordbox.xml"))
    return result.library, result.warnings


def paths(library: Library, node: Playlist) -> list[str]:
    return [library.tracks[t].path for t in node.entries]


def test_folders_and_playlists_in_order(tmp_path: Path) -> None:
    xml = RekordboxXml()
    ids = [xml.add_track(f"C:/Music/{n:02}.mp3") for n in range(18)]
    xml.nodes = [
        playlist("Lista sin título", []),
        folder("tunedex", playlist("tunedextest", list(reversed(ids)))),
        folder("Archive"),
    ]

    library, warnings = read(xml, tmp_path)

    empty, tunedex, archive = library.playlists
    assert isinstance(empty, Playlist)
    assert (empty.name, empty.entries) == ("Lista sin título", ())
    assert isinstance(tunedex, Folder)
    (test,) = tunedex.children
    assert isinstance(test, Playlist)
    assert test.name == "tunedextest"
    assert paths(library, test) == [f"C:/Music/{n:02}.mp3" for n in reversed(range(18))]
    assert isinstance(archive, Folder)
    assert archive.children == ()
    assert warnings == ()


def test_duplicate_entries_kept(tmp_path: Path) -> None:
    xml = RekordboxXml()
    a = xml.add_track("/music/a.mp3")
    xml.nodes = [playlist("Set", [a, a])]

    library, _ = read(xml, tmp_path)

    (node,) = library.playlists
    assert isinstance(node, Playlist)
    assert len(node.entries) == 2


def test_entries_by_location(tmp_path: Path) -> None:
    xml = RekordboxXml()
    xml.add_track("D:/House/Ñandú.mp3")
    xml.nodes = [playlist("D:", [location("D:/House/Ñandú.mp3")], key_type=1)]

    library, _ = read(xml, tmp_path)

    (node,) = library.playlists
    assert isinstance(node, Playlist)
    assert paths(library, node) == ["D:/House/Ñandú.mp3"]


def test_entries_without_a_track_left_out(tmp_path: Path) -> None:
    xml = RekordboxXml()
    a = xml.add_track("/music/a.mp3")
    xml.nodes = [
        playlist("Set", [a, "999"]),
        playlist("Paths", ["file://localhost/x.mp3"], key_type=1),
    ]

    library, warnings = read(xml, tmp_path)

    first, second = library.playlists
    assert isinstance(first, Playlist)
    assert isinstance(second, Playlist)
    assert (len(first.entries), second.entries) == (1, ())
    assert "playlist entries left out (no such track): 2" in warnings


def test_declared_entries_differ(tmp_path: Path) -> None:
    xml = RekordboxXml()
    a = xml.add_track("/music/a.mp3")
    xml.nodes = [playlist("Set", [a], Entries="3")]

    _, warnings = read(xml, tmp_path)

    assert "playlist 'Set' declares 3 entries but holds 1" in warnings


def test_unknown_node_type_skipped(tmp_path: Path) -> None:
    xml = RekordboxXml()
    xml.nodes = [Node("Smart", attributes={"Type": "2"}), playlist("Kept", [])]

    library, warnings = read(xml, tmp_path)

    assert [n.name for n in library.playlists] == ["Kept"]
    assert "playlist nodes of an unknown type skipped: 1" in warnings


def test_no_playlists(tmp_path: Path) -> None:
    path = tmp_path / "rekordbox.xml"
    path.write_bytes(
        b'<DJ_PLAYLISTS><PRODUCT Name="rekordbox"/><COLLECTION Entries="0"/></DJ_PLAYLISTS>'
    )

    assert REKORDBOX.read(path).library.playlists == ()
