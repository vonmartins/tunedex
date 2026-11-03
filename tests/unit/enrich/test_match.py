"""Identification rules (specs/metadata-enrich)."""

import json

import pytest

from support.enrich import FIXTURES
from tunedex.enrich import acoustid
from tunedex.enrich.acoustid import Candidate, Lookup
from tunedex.enrich.match import (
    Disagreement,
    Identified,
    Mismatch,
    NotRecognized,
    Unlinked,
    Unresolved,
    comparable,
    identify,
)

FIRST_RELEASES = {
    "73d6b7b1-2a6b-42b9-b92b-575774a70180": "2010-12-20",
    "bf6253d6-1245-4d94-a0b2-22a870f1614b": "2010-12-24",
}


def run(
    lookup: Lookup,
    *,
    duration: float | None = 300.0,
    title: str | None = None,
    carried: str | None = None,
):
    return identify(lookup, duration=duration, title=title, carried_id=carried,
                    first_release=FIRST_RELEASES.get)  # fmt: skip


def fixture(name: str) -> Lookup:
    return acoustid.parse(json.loads((FIXTURES / name).read_text(encoding="utf-8")))


def candidate(id_: str, score: float = 0.97, title: str = "Song", artist: str = "A",
              duration: float | None = 300.0) -> Candidate:  # fmt: skip
    return Candidate(id_, score, title, artist, duration)


def test_one_recording() -> None:
    assert run(fixture("acoustid-dfrnt.json"), duration=370.0) == Identified(
        "b03469f1-8ae8-4e57-a73d-1bb81db98783", fixture("acoustid-dfrnt.json").candidates[0].score
    )


def test_equivalent_recordings() -> None:
    outcome = run(fixture("acoustid-lung.json"), duration=360.5, title="Afterlife")

    assert isinstance(outcome, Identified)
    assert outcome.recording_id == "73d6b7b1-2a6b-42b9-b92b-575774a70180"  # 2010-12-20 first


def test_several_candidates() -> None:
    lookup = Lookup(0.97, (candidate("a", title="One"), candidate("b", title="Two")))

    outcome = run(lookup, title=None)

    assert isinstance(outcome, Unresolved) and len(outcome.candidates) == 2


def test_duration_settles_it() -> None:
    lookup = Lookup(
        0.97, (candidate("a", duration=300.0), candidate("b", title="X", duration=200.0))
    )

    assert run(lookup, duration=302.0) == Identified("a", 0.97)


def test_title_settles_it() -> None:
    lookup = Lookup(
        0.97, (candidate("a", title="Glue (Original Mix)"), candidate("b", title="Other"))
    )

    assert run(lookup, title="glue [aB3x-9Kq_Zt]") == Identified("a", 0.97)


def test_low_score() -> None:
    assert run(Lookup(0.6, (candidate("a", score=0.6),))) == NotRecognized(0.6)


def test_not_recognized() -> None:
    assert run(fixture("acoustid-marina.json")) == NotRecognized(0.0)


def test_unlinked() -> None:
    outcome = run(fixture("acoustid-irrelevant.json"))

    assert isinstance(outcome, Unlinked) and outcome.best_score > 0.9


def test_disagreement() -> None:
    assert run(Lookup(0.97, (candidate("b"),)), carried="a") == Disagreement("a", "b")


def test_agreement_with_a_carried_id() -> None:
    assert run(Lookup(0.97, (candidate("a"),)), carried="a") == Identified("a", 0.97)


def test_comparable_titles() -> None:
    assert comparable("Afterlife (Kryptic Minds remix)") == "afterlife"
    assert comparable("E Trips [6U6S6iXLSmU]") == "etrips"
    assert comparable("\uff34\uff45\uff4b-1") == "tek1"  # full-width letters


# Agreement with the track's own tags, from the real-collection test of 2026-10-31.

REAL_MISMATCHES = [
    # (artist, title, file name), (recording artist, recording title)
    ((None, None, "Kylin Tyce - Stay Together"), ("Vernon Felicity", "RDMX8")),
    ((None, None, "Pirupa & Hollen - Into The Darkness"),
     ("Nique & Dominik", "Earclear (original mix)")),
    ((None, None, "Salvatore Bruno - Brazilectro (Extended Mix)"),
     ("Singas Project", "Brazilectro")),
    (("Khainz", "Tek Donalds (Original Mix)", "x"), ("slem", "Take Two Test")),
    (("Khainz", "That Simple", "x"), ("Korsakoff", "Pendeho (Simple mix)")),
    ((None, None, "NightFunk - Music"), ("Marcapasos feat. Zita", "Music (Original Mix)")),
]  # fmt: skip


def run_tags(found: tuple[str, str], *, artist=None, title=None, file_name=None, carried=None):
    return identify(
        Lookup(candidates=(candidate("rec", title=found[1], artist=found[0]),), best_score=0.97),
        duration=300.0, title=title, carried_id=carried, first_release=FIRST_RELEASES.get,
        artist=artist, file_name=file_name,
    )  # fmt: skip


@pytest.mark.parametrize(("own", "found"), REAL_MISMATCHES)
def test_recording_that_disagrees_with_the_tags(
    own: tuple[str | None, str | None, str], found: tuple[str, str]
) -> None:
    artist, title, file_name = own
    outcome = run_tags(found, artist=artist, title=title, file_name=file_name)

    assert isinstance(outcome, Mismatch)


@pytest.mark.parametrize(
    ("artist", "title", "file_name", "found"),
    [
        (None, None, "Khainz - That Simple", ("Khainz", "That Simple")),
        ("AKA AKA, Thalstroem, Umami", "What Matters", "x",
         ("AKA AKA & Thalstroem", "What Matters")),
        (None, None, "Juanjo_Martin_Albert_Neve_feat_Nalaya_Don_t_Stop_Till_You_Get_Enough",
         ("Juanjo Martin & Albert Neve", "Don't Stop 'Til You Get Enough")),
        ("Ōme", "Guess", "x", ("Ome & Jafu", "Guess Your Not")),
        (None, None, "01", ("Anyone", "Anything")),
        # No artist to compare, and the title fits: accepted, though it may be wrong.
        (None, None, "[HOUSE] Drop_Department_SuitStatic_Bucovina_Extended_Mi",
         ("Niki Reiser", "Bucovina")),
    ],
)  # fmt: skip
def test_recording_that_agrees_with_the_tags(
    artist: str | None, title: str | None, file_name: str, found: tuple[str, str]
) -> None:
    outcome = run_tags(found, artist=artist, title=title, file_name=file_name)

    assert isinstance(outcome, Identified)


def test_carried_id_skips_the_check() -> None:
    outcome = run_tags(("Korsakoff", "Pendeho"), artist="Khainz", carried="rec")

    assert isinstance(outcome, Identified)


def tied(*candidates: Candidate, title: str | None, artist: str | None, file_name: str,
         duration: float = 300.0):  # fmt: skip
    return identify(
        Lookup(0.97, candidates),
        duration=duration,
        title=title,
        carried_id=None,
        first_release=lambda _rid: None,
        artist=artist,
        file_name=file_name,
    )


def test_guest_artist_the_track_does_not_name() -> None:
    outcome = tied(
        candidate("a", title="1000 Mile Drift", artist="Pitch Black", duration=354),
        candidate("b", title="1000 Mile Drift", artist="Pitch Black, Brother J", duration=355),
        title="1000 Mile Drift", artist="Pitch Black", file_name="Pitch Black - 1000 Mile Drift",
        duration=354.5,
    )  # fmt: skip
    assert outcome == Identified("a", 0.97)


def test_guest_artist_from_the_file_name() -> None:
    outcome = tied(
        candidate("a", title="Acid", artist="Abe Duque, Blake Baxter", duration=373),
        candidate("b", title="Acid", artist="Abe Duque", duration=366),
        title=None, artist=None, file_name="Abe Duque - Acid [www.slider.kz]", duration=368,
    )  # fmt: skip
    assert outcome == Identified("b", 0.97)


def test_recording_by_another_artist() -> None:
    outcome = tied(
        candidate("a", title="Do You Want My Love", artist="Demuja", duration=322),
        candidate("b", title="Do You Want My Love", artist="李玟", duration=315),
        title=None, artist=None, file_name="Demuja - Do You Want My Love", duration=320,
    )  # fmt: skip
    assert outcome == Identified("a", 0.97)


def test_other_song_with_a_shared_guest() -> None:
    outcome = tied(
        candidate("a", title="Shinobi", artist="Dubterror, Echo Ranks, Santanu", duration=278),
        candidate("b", title="Technology", artist="Dub Terror, Echo Ranks", duration=281),
        title=None, artist=None,
        file_name="Dub Terror - Technology (ft. Echo Ranks) REGGAE DUB", duration=280,
    )  # fmt: skip
    assert outcome == Identified("b", 0.97)


def test_no_clear_best_match() -> None:
    outcome = tied(
        candidate("a", title="Dropping", artist="Kitbuilders", duration=None),  # 0 s, as parsed
        candidate("b", title="The Marching Dead", artist="Xela", duration=350),
        title=None, artist=None, file_name="Eddy-M-Dropping-Original-Mix-683475092",
        duration=350,
    )  # fmt: skip
    assert isinstance(outcome, Unresolved)


def test_equal_scores_stay_unresolved() -> None:
    outcome = tied(
        candidate("a", title="Song", artist="Alpha"),
        candidate("b", title="Song", artist="Beta"),
        title="Song", artist=None, file_name="Song",
    )  # fmt: skip
    assert isinstance(outcome, Unresolved)


def test_recording_of_unknown_length() -> None:
    answer = {
        "status": "ok",
        "results": [{"score": 0.97, "recordings": [
            {"id": "a", "title": "Dropping", "duration": 0, "artists": [{"name": "Kitbuilders"}]},
        ]}],
    }  # fmt: skip
    lookup = acoustid.parse(answer)

    assert lookup.candidates[0].duration is None
    outcome = identify(lookup, duration=350.0, title="Dropping", carried_id=None,
                       first_release=lambda _rid: None)  # fmt: skip
    assert outcome == Identified("a", 0.97)
