"""MusicBrainz: recordings, their credits and releases."""

from dataclasses import dataclass
from typing import Any, cast

from tunedex.enrich.errors import EnrichError
from tunedex.enrich.http import Client
from tunedex.enrich.jsonish import obj, objects, text

API = "https://musicbrainz.org/ws/2"
HOST = "musicbrainz.org"
INTERVAL = 1.0  # MusicBrainz allows one request per second
SEARCH_LIMIT = 100  # the most MusicBrainz returns in one page
NOT_ORIGINAL = frozenset({"Compilation", "DJ-mix"})


@dataclass(frozen=True, slots=True)
class ReleaseRef:
    id: str
    title: str
    status: str | None
    date: str | None
    primary_type: str | None = None
    """The release group's primary type, such as ``Album``, ``EP`` or ``Single``."""
    secondary_types: tuple[str, ...] = ()
    """The release group's secondary types, such as ``Compilation`` or ``DJ-mix``."""

    @property
    def original(self) -> bool:
        """An official release that is neither a compilation nor a DJ mix."""
        return self.status == "Official" and not (NOT_ORIGINAL & set(self.secondary_types))


@dataclass(frozen=True, slots=True)
class Recording:
    id: str
    title: str
    artist: str
    """The artist credit with its join phrases, such as ``A feat. B``."""
    artist_ids: tuple[str, ...]
    length_ms: int | None
    isrcs: tuple[str, ...]
    remixers: tuple[str, ...]
    """From remixer relationships; often missing, in which case the title may name them."""
    genres: tuple[tuple[str, int], ...]
    """(name, votes), most voted first."""
    releases: tuple[ReleaseRef, ...]


@dataclass(frozen=True, slots=True)
class Release:
    id: str
    title: str
    date: str | None
    artist: str
    label: str | None
    catalog_number: str | None
    positions: dict[str, tuple[int, int]]
    """Recording id -> (disc number, track number)."""


def credit(credits: list[dict[str, Any]]) -> str:
    return "".join(
        (text(c.get("name")) or "") + (text(c.get("joinphrase")) or "") for c in credits
    ).strip()


def recording(client: Client, recording_id: str) -> Recording:
    data = client.get(
        f"{API}/recording/{recording_id}",
        {"inc": "artist-credits+releases+isrcs+artist-rels+genres+release-groups", "fmt": "json"},
    )
    return parse_recording(data)


def release(client: Client, release_id: str) -> Release:
    data = client.get(
        f"{API}/release/{release_id}",
        {"inc": "labels+recordings+artist-credits", "fmt": "json"},
    )
    return parse_release(data)


def parse_recording(value: object) -> Recording:
    data = obj(value)
    recording_id = text(data.get("id"))
    if recording_id is None:
        raise EnrichError("MusicBrainz sent an unexpected recording")
    credits = objects(data.get("artist-credit"))
    remixers = tuple(
        name
        for relation in objects(data.get("relations"))
        if relation.get("type") == "remixer"
        and (name := text(obj(relation.get("artist")).get("name")))
    )
    genres = sorted(
        (
            (name, int(g.get("count") or 0))
            for g in objects(data.get("genres"))
            if (name := text(g.get("name")))
        ),
        key=lambda g: (-g[1], g[0]),
    )
    releases = tuple(
        _release_ref(release_id, r)
        for r in objects(data.get("releases"))
        if (release_id := text(r.get("id")))
    )
    length = data.get("length")
    isrcs = data.get("isrcs")
    return Recording(
        id=recording_id,
        title=text(data.get("title")) or "",
        artist=credit(credits),
        artist_ids=tuple(i for c in credits if (i := text(obj(c.get("artist")).get("id")))),
        length_ms=length if isinstance(length, int) else None,
        isrcs=tuple(i for i in (isrcs if isinstance(isrcs, list) else []) if isinstance(i, str)),  # pyright: ignore[reportUnknownVariableType]
        remixers=remixers,
        genres=tuple(genres),
        releases=releases,
    )


def search_recordings(client: Client, title: str, artist_id: str) -> tuple[Recording, ...]:
    """The recordings titled ``title`` by the artist ``artist_id``, with their releases.

    Only MusicBrainz's own title and artist id are sent, never a track's tags.
    """
    phrase = title.replace("\\", "\\\\").replace('"', '\\"')
    data = client.get(
        f"{API}/recording/",
        {
            "query": f'recording:"{phrase}" AND arid:{artist_id}',
            "limit": str(SEARCH_LIMIT),
            "fmt": "json",
        },
    )
    return tuple(parse_recording(r) for r in objects(obj(data).get("recordings")) if r.get("id"))


def _release_ref(release_id: str, data: dict[str, Any]) -> ReleaseRef:
    group = obj(data.get("release-group"))
    secondary = group.get("secondary-types")
    return ReleaseRef(
        release_id,
        text(data.get("title")) or "",
        text(data.get("status")),
        text(data.get("date")),
        primary_type=text(group.get("primary-type")),
        secondary_types=tuple(
            t
            for t in (cast("list[object]", secondary) if isinstance(secondary, list) else [])
            if isinstance(t, str)
        ),
    )


def parse_release(value: object) -> Release:
    data = obj(value)
    release_id = text(data.get("id"))
    if release_id is None:
        raise EnrichError("MusicBrainz sent an unexpected release")
    labels = objects(data.get("label-info"))
    first = labels[0] if labels else {}
    positions: dict[str, tuple[int, int]] = {}
    for medium in objects(data.get("media")):
        disc = int(medium.get("position") or 1)
        for track in objects(medium.get("tracks")):
            recording_id = text(obj(track.get("recording")).get("id"))
            if recording_id and recording_id not in positions:
                positions[recording_id] = (disc, int(track.get("position") or 0))
    return Release(
        id=release_id,
        title=text(data.get("title")) or "",
        date=text(data.get("date")),
        artist=credit(objects(data.get("artist-credit"))),
        label=_label(text(obj(first.get("label")).get("name"))),
        catalog_number=text(first.get("catalog-number")),
        positions=positions,
    )


NO_LABEL = "[no label]"
"""MusicBrainz's label for releases without one."""


def _label(name: str | None) -> str | None:
    return None if name == NO_LABEL else name
