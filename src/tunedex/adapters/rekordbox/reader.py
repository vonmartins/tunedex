"""Reading a Rekordbox XML export (``DJ_PLAYLISTS``) into the canonical model.

The file is parsed as a stream: each collection track is mapped and then dropped, so
memory does not grow with the whole document. Nothing is ever written.
"""

import datetime
import re
import urllib.parse
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tunedex.adapters._values import build_track, text
from tunedex.adapters.errors import AdapterReadError
from tunedex.adapters.pathmap import PathMapping
from tunedex.adapters.rekordbox.keys import key_from_tonality
from tunedex.model.beatgrid import BeatGrid, BeatMarker
from tunedex.model.cue import Cue, CueKind
from tunedex.model.errors import ValidationError
from tunedex.model.ids import TrackId
from tunedex.model.library import Library
from tunedex.model.paths import format_of_extension, normalize_path
from tunedex.model.playlist import Folder, Node, Playlist
from tunedex.model.track import Track
from tunedex.model.unmapped import JSONValue

NAME = "rekordbox"
ROOT_TAG = "DJ_PLAYLISTS"
_LOCATION_PREFIX = "file://localhost/"
_WINDOWS_PATH = re.compile(r"^[A-Za-z]:/")
_STAR = 51  # Rekordbox stores ratings as 0, 51, ... 255.

# POSITION_MARK types.
_CUE, _FADE_IN, _FADE_OUT, _LOAD, _LOOP = "0", "1", "2", "3", "4"
# NODE types.
_FOLDER, _PLAYLIST = "0", "1"

# XML attribute -> track field, for texts.
_TEXTS = {
    "Name": "title",
    "Artist": "artist",
    "Album": "album",
    "Genre": "genre",
    "Composer": "composer",
    "Grouping": "grouping",
    "Comments": "comment",
    "Remixer": "remixer",
    "Label": "label",
    "Mix": "mix",
}
# XML attribute -> track field, for whole numbers where 0 means "not set".
_COUNTS = {
    "Year": "year",
    "TrackNumber": "track_number",
    "DiscNumber": "disc_number",
    "PlayCount": "play_count",
    "BitRate": "bitrate",
    "SampleRate": "sample_rate",
}
# Attributes kept verbatim in ``unmapped`` under their own name.
_KEPT = ("TrackID", "Kind", "Size")
_KNOWN = {
    *_TEXTS,
    *_COUNTS,
    *_KEPT,
    "Location",
    "AverageBpm",
    "TotalTime",
    "DateAdded",
    "Rating",
    "Colour",
    "Tonality",
}


@dataclass(frozen=True, slots=True)
class Product:
    """The ``PRODUCT`` that wrote an XML, as far as detection read it."""

    name: str | None
    version: str | None

    def describe(self) -> str:
        return " ".join(p for p in (self.name, self.version) if p) or "an unknown product"


def inspect(location: Path) -> Product:
    """The product of a ``DJ_PLAYLISTS`` file; raises ``AdapterReadError`` otherwise.

    Only the start of the document is parsed.
    """
    if location.is_dir():
        raise AdapterReadError(location, "it is a directory, not a Rekordbox XML file")
    if not location.is_file():
        raise AdapterReadError(location, "the file does not exist")
    try:
        with location.open("rb") as file:
            events = ET.iterparse(file, events=("start",))  # noqa: S314 - see _stream
            _, root = next(events)
            if root.tag != ROOT_TAG:
                raise AdapterReadError(
                    location, f"the root element is {root.tag!r}, not {ROOT_TAG!r}"
                )
            for _, element in events:
                if element.tag == "PRODUCT":
                    return Product(element.get("Name"), element.get("Version"))
                if element.tag == "COLLECTION":
                    break
    except (ET.ParseError, StopIteration) as error:
        raise AdapterReadError(location, f"not a readable XML file ({error})") from error
    except OSError as error:
        raise AdapterReadError(location, str(error)) from error
    return Product(None, None)


def decode_location(url: str) -> str | None:
    """The path a ``file://localhost/`` URL names, or ``None`` for other URLs."""
    if not url.startswith(_LOCATION_PREFIX):
        return None
    try:
        path = urllib.parse.unquote(url[len(_LOCATION_PREFIX) :], errors="strict")
    except UnicodeDecodeError:
        return None
    if not path:
        return None
    return path if _WINDOWS_PATH.match(path) else "/" + path


@dataclass
class RekordboxReader:
    path_mapping: PathMapping = field(default_factory=PathMapping)
    warnings: list[str] = field(default_factory=list[str])
    keys: dict[TrackId, str] = field(default_factory=dict[TrackId, str])
    """The Rekordbox ``TrackID`` of each track of the last read."""
    _tracks: dict[TrackId, Track] = field(default_factory=dict[TrackId, Track])
    _by_id: dict[str, TrackId] = field(default_factory=dict[str, TrackId])
    _by_path: dict[str, TrackId] = field(default_factory=dict[str, TrackId])
    _counts: Counter[str] = field(default_factory=Counter[str])

    def read(self, location: Path) -> Library:
        product = inspect(location)
        if (product.name or "").casefold() != NAME:
            self.warnings.append(
                f"this XML was written by {product.describe()}, not Rekordbox;"
                " it is read as a Rekordbox export"
            )
        playlists: ET.Element | None = None
        seen_collection = False
        try:
            for element, parent in _stream(location):
                if element.tag == "COLLECTION":
                    seen_collection = True
                elif element.tag == "TRACK" and parent == "COLLECTION":
                    self._track(element)
                elif element.tag == "PLAYLISTS" and parent == ROOT_TAG:
                    playlists = element
        except ET.ParseError as error:
            raise AdapterReadError(location, f"the XML is malformed ({error})") from error
        except OSError as error:
            raise AdapterReadError(location, str(error)) from error
        if not seen_collection:
            raise AdapterReadError(location, "the XML has no COLLECTION element")
        nodes = self._nodes(playlists)
        self._report()
        return Library.build(self._tracks.values(), nodes)

    # Tracks

    def _track(self, element: ET.Element) -> None:
        attrs = element.attrib
        track_id = attrs.get("TrackID")
        url = attrs.get("Location", "")
        name = _describe(attrs)
        if track_id is not None and track_id in self._by_id:
            self._counts["tracks skipped because their TrackID repeats an earlier one"] += 1
            return
        decoded = decode_location(url)
        if decoded is None:
            self.warnings.append(f"skipped {name}: unsupported location {url!r}")
            return
        try:
            path = self.path_mapping.to_library(decoded)
        except ValidationError as error:
            self.warnings.append(f"skipped {name}: {error.message}")
            return
        kept = self._by_path.get(normalize_path(path))
        if kept is not None:
            self._counts["tracks skipped because their location repeats an earlier one"] += 1
            if track_id is not None:
                self._by_id[track_id] = kept
            return

        unmapped: dict[str, JSONValue] = {k: attrs[k] for k in _KEPT if k in attrs}
        unknown = {k: v for k, v in attrs.items() if k not in _KNOWN}
        if unknown:
            unmapped["attributes"] = dict(unknown)
        values: dict[str, Any] = {f: text(attrs.get(a)) for a, f in _TEXTS.items()}
        values |= {f: self._count(attrs, a) for a, f in _COUNTS.items()}
        values |= {
            "bpm": self._positive_float(attrs, "AverageBpm"),
            "duration_us": _seconds_to_us(self._positive_float(attrs, "TotalTime")),
            "date_added": self._date(attrs, "DateAdded"),
            "rating": self._rating(attrs),
            "color": self._colour(attrs),
            "file_format": format_of_extension(path),
            "cues": self._cues(element, unmapped),
            "beatgrid": self._grid(name, element, unmapped),
        }
        tonality = text(attrs.get("Tonality"))
        if tonality is not None:
            values["key"] = key_from_tonality(tonality)
            values["key_original"] = tonality
            if values["key"] is None:
                self._counts["keys in an unknown notation, kept only as the original key"] += 1
        others: list[JSONValue] = [
            {"tag": child.tag, "attributes": dict[str, JSONValue](child.attrib)}
            for child in element
            if child.tag not in ("TEMPO", "POSITION_MARK")
        ]
        if others:
            unmapped["elements"] = others

        track = build_track(
            lambda v: Track(path_origin=path, unmapped={NAME: unmapped}, **v),
            values,
            path,
            self.warnings,
        )
        self._tracks[track.id] = track
        self._by_path[track.path] = track.id
        if track_id is not None:
            self._by_id[track_id] = track.id
            self.keys[track.id] = track_id

    def _count(self, attrs: dict[str, str], name: str) -> int | None:
        raw = attrs.get(name)
        if raw is None or not raw.strip():
            return None
        try:
            value = int(raw)
        except ValueError:
            self._counts[f"unreadable {name} values ignored"] += 1
            return None
        return value if value > 0 else None

    def _positive_float(self, attrs: dict[str, str], name: str) -> float | None:
        raw = attrs.get(name)
        if raw is None or not raw.strip():
            return None
        value = _float(raw)
        if value is None:
            self._counts[f"unreadable {name} values ignored"] += 1
            return None
        return value if value > 0 else None

    def _date(self, attrs: dict[str, str], name: str) -> datetime.date | None:
        raw = (attrs.get(name) or "").strip()
        if not raw:
            return None
        try:
            return datetime.date.fromisoformat(raw)
        except ValueError:
            self._counts[f"unreadable {name} values ignored"] += 1
            return None

    def _rating(self, attrs: dict[str, str]) -> int | None:
        value = self._count(attrs, "Rating")
        return None if value is None else min(5, round(value / _STAR)) or None

    def _colour(self, attrs: dict[str, str]) -> str | None:
        raw = (attrs.get("Colour") or "").strip()
        if not raw:
            return None
        try:
            value = int(raw, 16)
        except ValueError:
            self._counts["unreadable Colour values ignored"] += 1
            return None
        return f"#{value & 0xFFFFFF:06X}"

    # Cues and loops

    def _cues(self, element: ET.Element, unmapped: dict[str, JSONValue]) -> tuple[Cue, ...]:
        cues: list[Cue] = []
        slots: set[int] = set()
        marks: list[JSONValue] = []
        for mark in element.iter("POSITION_MARK"):
            kind = mark.get("Type")
            if kind in (_FADE_IN, _FADE_OUT, _LOAD):
                marks.append(dict(mark.attrib))
                continue
            if kind not in (_CUE, _LOOP):
                self._counts["marks of unknown types skipped"] += 1
                continue
            start = _seconds_to_us(_float(mark.get("Start", "")), allow_zero=True)
            num = _int(mark.get("Num", "-1"))
            if start is None or num is None:
                self._counts["cues with an unreadable position or pad skipped"] += 1
                continue
            slot = num if num >= 0 else None
            if slot is not None and slot in slots:
                self._counts["cues on a pad already used skipped"] += 1
                continue
            name, color = text(mark.get("Name")), _rgb(mark)
            if kind == _LOOP:
                end = _seconds_to_us(_float(mark.get("End", "")), allow_zero=True)
                if end is None or end <= start:
                    self._counts["loops without an end after their start skipped"] += 1
                    continue
                cue = Cue(
                    kind=CueKind.LOOP, start_us=start, end_us=end, slot=slot, name=name, color=color
                )
            elif slot is not None:
                cue = Cue(kind=CueKind.HOT, start_us=start, slot=slot, name=name, color=color)
            else:
                cue = Cue(kind=CueKind.MEMORY, start_us=start, name=name, color=color)
            if slot is not None:
                slots.add(slot)
            cues.append(cue)
        if marks:
            unmapped["marks"] = marks
        return tuple(cues)

    # Beat grids

    def _grid(
        self, name: str, element: ET.Element, unmapped: dict[str, JSONValue]
    ) -> BeatGrid | None:
        tempos = element.findall("TEMPO")
        if not tempos:
            return None
        markers: list[BeatMarker] = []
        reason: str | None = None
        for tempo in tempos:
            position = _seconds_to_us(_float(tempo.get("Inizio", "")), allow_zero=True)
            bpm = _float(tempo.get("Bpm", ""))
            beat = _int(tempo.get("Battito", ""))
            if tempo.get("Metro", "4/4").strip() != "4/4":
                reason = f"metre {tempo.get('Metro')!r} is not 4/4"
            elif position is None or bpm is None or bpm <= 0 or beat is None:
                reason = "a marker has an unreadable position, BPM or beat"
            elif not 1 <= beat <= 4:
                reason = f"beat {beat} is outside 1 to 4"
            elif markers and position <= markers[-1].position_us:
                reason = "two markers are at the same position or out of order"
            else:
                markers.append(BeatMarker(position_us=position, bpm=bpm, beat=beat))
                continue
            break
        if reason is not None:
            unmapped["tempo"] = [dict(t.attrib) for t in tempos]
            self.warnings.append(
                f"{name}: beat grid not read ({reason}); Rekordbox's markers are kept"
            )
            return None
        return BeatGrid(markers=tuple(markers))

    # Playlists and folders

    def _nodes(self, playlists: ET.Element | None) -> tuple[Node, ...]:
        if playlists is None:
            return ()
        root = playlists.find("NODE")
        if root is None:
            return ()
        return tuple(n for child in root.findall("NODE") if (n := self._node(child)) is not None)

    def _node(self, element: ET.Element) -> Node | None:
        name = text(element.get("Name")) or "Untitled"
        kind = element.get("Type")
        if kind == _FOLDER:
            children = (self._node(child) for child in element.findall("NODE"))
            return Folder(name=name, children=tuple(c for c in children if c is not None))
        if kind != _PLAYLIST:
            self._counts["playlist nodes of an unknown type skipped"] += 1
            return None
        by_location = element.get("KeyType", "0").strip() == "1"
        keys = [entry.get("Key", "") for entry in element.findall("TRACK")]
        declared = _int(element.get("Entries", ""))
        if declared is not None and declared != len(keys):
            self.warnings.append(
                f"playlist {name!r} declares {declared} entries but holds {len(keys)}"
            )
        entries: list[TrackId] = []
        for key in keys:
            track = self._entry(key, by_location=by_location)
            if track is None:
                self._counts["playlist entries left out (no such track)"] += 1
            else:
                entries.append(track)
        return Playlist(name=name, entries=tuple(entries))

    def _entry(self, key: str, *, by_location: bool) -> TrackId | None:
        if not by_location:
            return self._by_id.get(key)
        decoded = decode_location(key)
        if decoded is None:
            return None
        try:
            return self._by_path.get(normalize_path(self.path_mapping.to_library(decoded)))
        except ValidationError:
            return None

    def _report(self) -> None:
        for reason, count in self._counts.items():
            self.warnings.append(f"{reason}: {count}")


def _stream(location: Path) -> Iterator[tuple[ET.Element, str | None]]:
    """Each complete element with its parent's tag; collection tracks are freed after use."""
    stack: list[ET.Element] = []
    with location.open("rb") as file:
        # expat (>= 2.4 with Python >= 3.11) limits entity expansion, and ElementTree
        # never loads external entities or DTDs, so a user's XML cannot do harm here.
        for event, element in ET.iterparse(file, events=("start", "end")):  # noqa: S314
            if event == "start":
                stack.append(element)
                continue
            stack.pop()
            parent = stack[-1] if stack else None
            yield element, None if parent is None else parent.tag
            if parent is not None and parent.tag == "COLLECTION" and element.tag == "TRACK":
                parent.remove(element)


def _describe(attrs: dict[str, str]) -> str:
    artist, title = text(attrs.get("Artist")), text(attrs.get("Name"))
    if artist and title:
        return f"{artist} - {title}"
    return title or attrs.get("Location") or f"TrackID {attrs.get('TrackID')}"


def _float(raw: str) -> float | None:
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if value == value and abs(value) != float("inf") else None


def _int(raw: str) -> int | None:
    try:
        return int(raw.strip())
    except ValueError:
        return None


def _seconds_to_us(seconds: float | None, *, allow_zero: bool = False) -> int | None:
    if seconds is None or seconds < 0 or (seconds == 0 and not allow_zero):
        return None
    return round(seconds * 1_000_000)


def _rgb(mark: ET.Element) -> str | None:
    parts = [_int(mark.get(c, "")) for c in ("Red", "Green", "Blue")]
    if any(p is None or not 0 <= p <= 255 for p in parts):
        return None
    red, green, blue = (p or 0 for p in parts)
    return f"#{red:02X}{green:02X}{blue:02X}"
