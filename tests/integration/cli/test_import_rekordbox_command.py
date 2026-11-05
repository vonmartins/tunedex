"""``tunedex import rekordbox`` (specs/cli)."""

import json
from pathlib import Path

from typer.testing import CliRunner

from support.audio import tagged_copy
from support.rekordbox import RekordboxXml, playlist
from tunedex.cli import app
from tunedex.store import Store

runner = CliRunner()


def test_import_from_an_export(tmp_path: Path) -> None:
    xml = RekordboxXml()
    xml.nodes = [playlist("Peak", [xml.add_track("/music/a.mp3", Name="A")])]
    path = xml.write(tmp_path / "rekordbox.xml")
    before = path.read_bytes(), path.stat().st_mtime_ns

    result = runner.invoke(
        app,
        ["--home", str(tmp_path / "home"), "import", "rekordbox", str(path), "--apply", "--yes"],
    )

    assert result.exit_code == 0, result.stderr
    assert "Applied." in result.stdout
    with Store.open(tmp_path / "home" / "library.db") as store:
        assert [t.title for t in store.list_tracks()] == ["A"]
        assert [n.name for n in store.children()] == ["Rekordbox"]
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before


def test_not_a_rekordbox_xml(tmp_path: Path) -> None:
    path = tmp_path / "collection.nml"
    path.write_text('<?xml version="1.0"?><NML VERSION="19"/>', encoding="utf-8")

    result = runner.invoke(
        app, ["--home", str(tmp_path / "home"), "import", "rekordbox", str(path)]
    )

    assert result.exit_code == 1
    assert "collection.nml is not a Rekordbox XML export" in result.stderr
    assert result.stderr.count("\n") == 1


def test_missing_file_as_json(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "--home",
            str(tmp_path / "home"),
            "import",
            "rekordbox",
            str(tmp_path / "x.xml"),
            "--json",
        ],
    )

    assert result.exit_code == 1
    assert json.loads(result.stderr)["error"]["code"] == "not_found"


def test_missing_argument(tmp_path: Path) -> None:
    result = runner.invoke(app, ["--home", str(tmp_path / "home"), "import", "rekordbox"])

    assert result.exit_code == 2
    assert not (tmp_path / "home" / "library.db").exists()


def test_collection_from_another_computer(tmp_path: Path) -> None:
    here = tmp_path / "from-pc"
    tagged_copy(here, "mp3", name="a.mp3", title="A")
    xml = RekordboxXml()
    xml.add_track("C:/Users/DJ/Music/a.mp3", Name="A")
    xml.add_track("C:/Users/DJ/Music/b.mp3", Name="B")
    path = xml.write(tmp_path / "rekordbox.xml")

    result = runner.invoke(
        app,
        [
            "--home",
            str(tmp_path / "home"),
            "import",
            "rekordbox",
            str(path),
            "--find-in",
            str(here),
            "--apply",
            "--yes",
        ],
    )

    assert result.exit_code == 0, result.stderr
    with Store.open(tmp_path / "home" / "library.db") as store:
        (track,) = store.list_tracks()
    assert (track.title, Path(track.path)) == ("A", (here / "a.mp3").absolute())
