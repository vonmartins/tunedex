"""Building Rekordbox XML exports (``DJ_PLAYLISTS``) for tests."""

import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

# POSITION_MARK types.
CUE, FADE_IN, FADE_OUT, LOAD, LOOP = 0, 1, 2, 3, 4


def location(path: str) -> str:
    """The ``Location`` URL Rekordbox writes for an absolute path."""
    quoted = urllib.parse.quote(path.lstrip("/"), safe="/:()!'*,-._~")
    return f"file://localhost/{quoted}"


@dataclass
class Node:
    """A folder (``children``) or a playlist (``entries``)."""

    name: str
    children: list["Node"] | None = None
    entries: list[str] = field(default_factory=list[str])
    key_type: int = 0
    attributes: dict[str, str] = field(default_factory=dict[str, str])


def folder(name: str, *children: Node) -> Node:
    return Node(name, children=list(children))


def playlist(name: str, entries: list[str], *, key_type: int = 0, **attributes: str) -> Node:
    """``entries`` are TrackIDs for ``key_type`` 0 and locations for 1."""
    return Node(name, entries=list(entries), key_type=key_type, attributes=attributes)


@dataclass
class RekordboxXml:
    product: str = "rekordbox"
    version: str = "7.2.14"
    _tracks: list[ET.Element] = field(default_factory=list[ET.Element])
    _by_id: dict[str, ET.Element] = field(default_factory=dict[str, ET.Element])
    _next_id: int = 1001
    nodes: list[Node] = field(default_factory=list[Node])

    def add_track(
        self, path: str | None = None, *, track_id: str | None = None, **attrs: str
    ) -> str:
        """Add a track and return its TrackID. ``Location`` may be given in ``attrs``."""
        if track_id is None:
            track_id, self._next_id = str(self._next_id), self._next_id + 1
        values = {"TrackID": track_id}
        if path is not None:
            values["Location"] = location(path)
        values |= attrs
        element = ET.Element("TRACK", values)
        self._tracks.append(element)
        self._by_id[track_id] = element
        return track_id

    def add_tempo(
        self, track_id: str, inizio: str, bpm: str, *, metro: str = "4/4", battito: str = "1"
    ) -> None:
        ET.SubElement(
            self._by_id[track_id],
            "TEMPO",
            {"Inizio": inizio, "Bpm": bpm, "Metro": metro, "Battito": battito},
        )

    def add_mark(
        self,
        track_id: str,
        start: str,
        *,
        type: int = CUE,
        num: int = -1,
        name: str = "",
        end: str | None = None,
        rgb: tuple[int, int, int] | None = None,
    ) -> None:
        values = {"Name": name, "Type": str(type), "Start": start}
        if end is not None:
            values["End"] = end
        values["Num"] = str(num)
        if rgb is not None:
            values |= {"Red": str(rgb[0]), "Green": str(rgb[1]), "Blue": str(rgb[2])}
        ET.SubElement(self._by_id[track_id], "POSITION_MARK", values)

    def add_element(self, track_id: str, tag: str, **attrs: str) -> None:
        ET.SubElement(self._by_id[track_id], tag, attrs)

    def to_bytes(self, *, crlf: bool = False) -> bytes:
        root = ET.Element("DJ_PLAYLISTS", {"Version": "1.0.0"})
        ET.SubElement(
            root, "PRODUCT", {"Name": self.product, "Version": self.version, "Company": "Test"}
        )
        collection = ET.SubElement(root, "COLLECTION", {"Entries": str(len(self._tracks))})
        collection.extend(self._tracks)
        playlists = ET.SubElement(root, "PLAYLISTS")
        top = ET.SubElement(
            playlists, "NODE", {"Type": "0", "Name": "ROOT", "Count": str(len(self.nodes))}
        )
        for node in self.nodes:
            _write_node(top, node)
        ET.indent(root)
        body = ET.tostring(root, encoding="unicode")
        text = f'<?xml version="1.0" encoding="UTF-8"?>\n\n{body}\n'
        if crlf:
            text = text.replace("\n", "\r\n")
        return text.encode("utf-8")

    def write(self, path: Path, *, crlf: bool = False) -> Path:
        path.write_bytes(self.to_bytes(crlf=crlf))
        return path


def _write_node(parent: ET.Element, node: Node) -> None:
    if node.children is not None:
        element = ET.SubElement(
            parent, "NODE", {"Name": node.name, "Type": "0", "Count": str(len(node.children))}
        )
        for child in node.children:
            _write_node(element, child)
        return
    values = {
        "Name": node.name,
        "Type": "1",
        "KeyType": str(node.key_type),
        "Entries": str(len(node.entries)),
    }
    element = ET.SubElement(parent, "NODE", values | node.attributes)
    for key in node.entries:
        ET.SubElement(element, "TRACK", {"Key": key})
