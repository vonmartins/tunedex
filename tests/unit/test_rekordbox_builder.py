import xml.etree.ElementTree as ET
from pathlib import Path

from support.rekordbox import LOOP, RekordboxXml, folder, location, playlist


def test_location_is_percent_encoded() -> None:
    assert location("C:/Music/Kestrel & Moth - Mós.mp3") == (
        "file://localhost/C:/Music/Kestrel%20%26%20Moth%20-%20M%C3%B3s.mp3"
    )
    assert location("/Users/dj/a b.mp3") == "file://localhost/Users/dj/a%20b.mp3"


def test_builder_writes_a_dj_playlists_document(tmp_path: Path) -> None:
    xml = RekordboxXml()
    track = xml.add_track("C:/Music/a.mp3", Name="Glue", Tonality="8A")
    xml.add_tempo(track, "0.227", "128.00", battito="3")
    xml.add_mark(track, "1.000", type=LOOP, num=0, end="2.000", rgb=(1, 2, 3))
    xml.nodes = [folder("Sets", playlist("Peak", [track, track])), playlist("Empty", [])]
    path = xml.write(tmp_path / "rekordbox.xml", crlf=True)

    assert b"\r\n" in path.read_bytes()
    root = ET.parse(path).getroot()
    assert root.tag == "DJ_PLAYLISTS"
    assert root.findall("PRODUCT")[0].attrib["Name"] == "rekordbox"
    element = root.find("COLLECTION/TRACK")
    assert element is not None
    assert element.attrib["Name"] == "Glue"
    assert element.attrib["Location"] == "file://localhost/C:/Music/a.mp3"
    assert element.findall("TEMPO")[0].attrib["Battito"] == "3"
    mark = element.find("POSITION_MARK")
    assert mark is not None
    assert (mark.attrib["Type"], mark.attrib["End"], mark.attrib["Blue"]) == ("4", "2.000", "3")
    nodes = root.findall("PLAYLISTS/NODE/NODE")
    assert [n.attrib["Name"] for n in nodes] == ["Sets", "Empty"]
    peak = nodes[0].find("NODE")
    assert peak is not None
    assert [e.attrib["Key"] for e in peak.findall("TRACK")] == [track, track]
