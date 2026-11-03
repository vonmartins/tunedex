"""Choosing the release, and sometimes the recording, whose data a track gets.

MusicBrainz often keeps one recording of a song per compilation, and AcoustID may link a
file to any of them. So the release is not always among the identified recording's own:
the track's album, or an original release, may hold another recording of the same song.
"""

import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from tunedex.enrich.match import comparable
from tunedex.enrich.musicbrainz import Recording, ReleaseRef

Search = Callable[[str, str], Sequence[Recording]]
"""Recordings titled like the first argument by the artist id in the second."""
Fetch = Callable[[str], Recording]
"""A recording, by id, with everything a track takes from it."""


@dataclass(frozen=True, slots=True)
class Choice:
    recording: Recording
    """The identified recording, or another recording of the same song that replaces it."""
    release: ReleaseRef | None
    """The release whose fields the track gets; ``None`` gives no release fields."""
    album_kept: bool = False
    """The track's own album matched no release, so its album fields stay as they are."""


def same_album(release_title: str, album: str) -> bool:
    """Album titles compared without case, punctuation or bracketed parts."""
    wanted = comparable(album)
    return bool(wanted) and comparable(release_title) == wanted


def same_title(a: str, b: str) -> bool:
    """Song titles compared without case or punctuation; versions in brackets count."""
    return _plain(a) == _plain(b) != ""


def resolve(recording: Recording, album: str | None, search: Search, fetch: Fetch) -> Choice:
    """The release a track with ``album`` gets from ``recording``.

    1. A release of the recording with the track's album title.
    2. When the track has an album, or the recording is only on compilations and DJ mixes:
       another recording of the same song on a release with that album title, or else
       (without an album) on an original release.
    3. With an album and nothing found: no release fields, and the album is kept.
    4. Otherwise the earliest original release, or the earliest official one.
    """
    official = [r for r in recording.releases if r.status == "Official"]
    if album:
        named = [r for r in official if same_album(r.title, album)]
        if named:
            return Choice(recording, _earliest(named))
    if album or (official and not any(r.original for r in official)):
        found = _other_recording(recording, album, search)
        if found is not None:
            other, ref = found
            return Choice(recording if other.id == recording.id else fetch(other.id), ref)
    if album:
        return Choice(recording, None, album_kept=True)
    if not official:
        return Choice(recording, None)
    return Choice(recording, _earliest([r for r in official if r.original] or official))


def _other_recording(
    recording: Recording, album: str | None, search: Search
) -> tuple[Recording, ReleaseRef] | None:
    if not recording.title or not recording.artist_ids:
        return None
    artists = set(recording.artist_ids)
    pairs = [
        (other, ref)
        for other in search(recording.title, recording.artist_ids[0])
        if same_title(other.title, recording.title) and artists & set(other.artist_ids)
        for ref in other.releases
        if ref.status == "Official" and (same_album(ref.title, album) if album else ref.original)
    ]
    if not pairs:
        return None
    return min(pairs, key=lambda pair: (pair[1].date or "9999", pair[1].id, pair[0].id))


def _earliest(refs: Sequence[ReleaseRef]) -> ReleaseRef:
    return min(refs, key=lambda r: (r.date or "9999", r.id))


def _plain(text: str) -> str:
    folded = unicodedata.normalize("NFKC", text).casefold()
    return "".join(c for c in folded if c.isalnum())
