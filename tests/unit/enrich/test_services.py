"""Parsing real AcoustID and MusicBrainz answers (tests/fixtures/enrich)."""

import json
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest

from support.enrich import FIXTURES, FakeClock, FakeTransport, catalogue
from tunedex.enrich import EnrichError, acoustid, musicbrainz
from tunedex.enrich.cache import Cache
from tunedex.enrich.http import Client

LUNG_A = "73d6b7b1-2a6b-42b9-b92b-575774a70180"
LUNG_B = "bf6253d6-1245-4d94-a0b2-22a870f1614b"
INSIDERS = "6340a9b8-f427-4d89-a842-971a52ad3ce4"
METAFICTION = "98efe856-2747-4ffc-845a-8f7e97cd6afa"


def load(name: str) -> object:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_one_recording() -> None:
    result = acoustid.parse(load("acoustid-dfrnt.json"))

    (candidate,) = result.candidates
    assert (candidate.title, candidate.artist) == ("Headspace (Scuba remix)", "DFRNT")
    assert candidate.score > 0.98 and candidate.duration == pytest.approx(370.88)


def test_duplicate_recordings() -> None:
    result = acoustid.parse(load("acoustid-lung.json"))

    assert {c.recording_id for c in result.candidates} == {LUNG_A, LUNG_B}
    assert {c.title for c in result.candidates} == {"Afterlife (Kryptic Minds remix)"}


def test_recognized_but_unlinked() -> None:
    result = acoustid.parse(load("acoustid-irrelevant.json"))

    assert result.best_score > 0.9 and result.candidates == ()


def test_not_recognized() -> None:
    assert acoustid.parse(load("acoustid-marina.json")) == acoustid.Lookup(0.0, ())


def test_acoustid_error() -> None:
    with pytest.raises(EnrichError, match="invalid API key"):
        acoustid.parse({"status": "error", "error": {"code": 4, "message": "invalid API key"}})


def test_lookup_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TUNEDEX_ACOUSTID_KEY", "testkey")
    transport, clock = FakeTransport(), FakeClock()
    transport.route(acoustid.LOOKUP, lambda url, data: load("acoustid-dfrnt.json"))
    client = Client(transport, Cache(None), clock=clock, sleep=clock.sleep)

    acoustid.lookup(client, 370.6, "AQAAfp")

    method, url, data, _headers = transport.requests[0]
    assert (method, url) == ("POST", acoustid.LOOKUP)
    assert data is not None and data["client"] == "testkey" and data["duration"] == "371"


def test_key_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TUNEDEX_ACOUSTID_KEY", raising=False)
    assert acoustid.key() == acoustid.ACOUSTID_KEY


def test_recording_with_a_featured_credit() -> None:
    recording = musicbrainz.parse_recording(load(f"recording-{INSIDERS}.json"))

    assert (recording.title, recording.artist) == ("Insiders", "Black Sun Empire feat. Optiv")
    assert recording.isrcs == ("NLCF10700011",)
    assert recording.genres[0] == ("drum and bass", 1)
    assert recording.remixers == ()  # only producer relations
    assert len(recording.artist_ids) == 2


def test_remix_title_without_relation() -> None:
    recording = musicbrainz.parse_recording(load(f"recording-{LUNG_A}.json"))

    assert recording.title == "Afterlife (Kryptic Minds remix)"
    assert recording.remixers == ()
    assert [(r.title, r.status, r.date) for r in recording.releases] == [
        ("Pure Dubstep", "Official", "2010-12-20")
    ]


def test_remixer_relation() -> None:
    data = {
        "id": "r",
        "title": "T (X remix)",
        "artist-credit": [{"name": "A", "joinphrase": "", "artist": {"id": "a"}}],
        "relations": [
            {"type": "remixer", "direction": "backward", "artist": {"id": "x", "name": "X"}},
            {"type": "producer", "artist": {"id": "p", "name": "P"}},
        ],
    }

    assert musicbrainz.parse_recording(data).remixers == ("X",)


def test_release() -> None:
    release = musicbrainz.parse_release(load(f"release-{METAFICTION}.json"))

    assert (release.title, release.date, release.artist) == ("Metafiction", "2009-09", "DFRNT")
    assert (release.label, release.catalog_number) == ("On The Edge", "OTECD001")
    scuba_remix = "b03469f1-8ae8-4e57-a73d-1bb81db98783"
    assert release.positions[scuba_remix] == (2, 9)  # the remix is on the second disc


def test_unexpected_answers() -> None:
    with pytest.raises(EnrichError):
        musicbrainz.parse_recording({"error": "Not Found"})
    with pytest.raises(EnrichError):
        musicbrainz.parse_release([])


def test_no_label() -> None:
    data: Any = load("release-98efe856-2747-4ffc-845a-8f7e97cd6afa.json")
    data["label-info"][0]["label"]["name"] = "[no label]"

    assert musicbrainz.parse_release(data).label is None


JOLGORIO_EP = "5fc92bf8-4d6d-421e-bf74-dd13cf5a92d4"
JOLGORIO_ZAPPI = "ee517604-9f1a-4a33-a1fa-9ad55ab12eb4"
JACEO = "ec98b948-05df-45ae-a1f3-367e695e2905"


def test_release_kinds() -> None:
    ep = musicbrainz.parse_recording(load(f"recording-{JOLGORIO_EP}.json"))
    zappi = musicbrainz.parse_recording(load(f"recording-{JOLGORIO_ZAPPI}.json"))

    (release,) = ep.releases
    assert (release.title, release.primary_type, release.secondary_types) == (
        "Jolgorio - EP",
        "EP",
        (),
    )
    assert release.original
    (compilation,) = zappi.releases
    assert compilation.secondary_types == ("Compilation",) and not compilation.original


def test_dj_mix_is_not_original() -> None:
    ref = musicbrainz.ReleaseRef("r", "Mix", "Official", None, "Album", ("Compilation", "DJ-mix"))
    assert not ref.original
    assert musicbrainz.ReleaseRef("r", "Live", "Official", None, "Album", ("Live",)).original
    assert not musicbrainz.ReleaseRef("r", "Promo", "Promotion", None, "Single").original


def test_search_sends_only_title_and_artist() -> None:
    transport, clock = FakeTransport(), FakeClock()
    transport.route(musicbrainz.API, lambda url, data: load("search-jolgorio-ec98b948.json"))
    client = Client(transport, Cache(None), clock=clock, sleep=clock.sleep)

    found = musicbrainz.search_recordings(client, "Jolgorio", JACEO)

    _method, url, _data, _headers = transport.requests[0]
    query = parse_qs(urlsplit(url).query)
    assert query["query"] == [f'recording:"Jolgorio" AND arid:{JACEO}']
    assert set(query) == {"query", "limit", "fmt"}
    assert [r.title for r in found] == ["Jolgorio", "Jolgorio", "Jolgorio (original mix)"]
    assert [r.releases[0].original for r in found] == [True, False, False]
    assert all(JACEO in r.artist_ids for r in found)


def test_search_escapes_quotes() -> None:
    transport, clock = FakeTransport(), FakeClock()
    transport.route(musicbrainz.API, lambda url, data: {"recordings": []})
    client = Client(transport, Cache(None), clock=clock, sleep=clock.sleep)

    musicbrainz.search_recordings(client, 'Say "Hi"', JACEO)

    query = parse_qs(urlsplit(transport.requests[0][1]).query)["query"][0]
    assert query == f'recording:"Say \\"Hi\\"" AND arid:{JACEO}'


def test_search_fixture_routing() -> None:
    transport = catalogue({})
    client = Client(transport, Cache(None), clock=FakeClock(), sleep=lambda _s: None)

    found = musicbrainz.search_recordings(
        client, "Jessy Bett", "08557f73-6b1c-4281-ad93-ffa660f5b266"
    )

    assert {r.releases[0].title for r in found} == {"Dub vs. Wild", "Best of 2015"}
