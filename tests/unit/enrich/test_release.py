"""Release choice (specs/metadata-enrich: Release choice, album lookup, originals)."""

import json
from collections.abc import Sequence

from support.enrich import FIXTURES
from tunedex.enrich import musicbrainz
from tunedex.enrich.musicbrainz import Recording, ReleaseRef
from tunedex.enrich.release import Choice, resolve, same_album, same_title

JACEO = "ec98b948-05df-45ae-a1f3-367e695e2905"
PANDA_DUB = "08557f73-6b1c-4281-ad93-ffa660f5b266"
JOLGORIO_EP = "5fc92bf8-4d6d-421e-bf74-dd13cf5a92d4"
JOLGORIO_ZAPPI = "ee517604-9f1a-4a33-a1fa-9ad55ab12eb4"
JESSY_DUB_VS_WILD = "fb3674a4-2f5d-4a9e-bb89-786bdfc8c1de"
JESSY_BEST_OF = "2120ba7f-2be3-4e3d-9224-13a2a76e80de"
# MusicBrainz writes a typographic apostrophe: O\u2019Riley.


def load(name: str) -> object:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def fixture_recording(id_: str) -> Recording:
    return musicbrainz.parse_recording(load(f"recording-{id_}.json"))


def fixture_search(name: str) -> tuple[Recording, ...]:
    data = load(name)
    assert isinstance(data, dict)
    return tuple(musicbrainz.parse_recording(r) for r in data["recordings"])  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]


def ref(id_: str, title: str, date: str | None, *types: str, primary: str = "Album") -> ReleaseRef:
    return ReleaseRef(id_, title, "Official", date, primary, tuple(types))


def rec(
    id_: str, *refs: ReleaseRef, title: str = "Song", artists: tuple[str, ...] = ("a",)
) -> Recording:
    return Recording(id_, title, "A", artists, None, (), (), (), refs)


class Searches:
    """A search answering with ``found``; records what was asked."""

    def __init__(self, *found: Recording) -> None:
        self.found = found
        self.asked: list[tuple[str, str]] = []

    def __call__(self, title: str, artist_id: str) -> Sequence[Recording]:
        self.asked.append((title, artist_id))
        return self.found


def fetch_from(*recordings: Recording):
    by_id = {r.id: r for r in recordings}
    return lambda id_: by_id[id_]


def choose(recording: Recording, album: str | None, search: Searches | None = None) -> Choice:
    search = search or Searches()
    return resolve(recording, album, search, fetch_from(recording, *search.found))


def test_loose_album_titles() -> None:
    assert same_album("Dub vs. Wild", "Dub vs Wild")
    assert same_album("Jolgorio - EP", "Jolgorio EP")
    assert same_album("Changes (Deluxe Edition)", "changes")
    assert not same_album("Best of 2015", "Dub vs Wild")
    assert not same_album("Anything", "")


def test_versions_are_different_songs() -> None:
    assert same_title(
        "Baba O\u2019Riley (The Cube Guys remix)", "baba o'riley (the cube guys remix)"
    )
    assert not same_title("Baba O'Riley (UK radio edit)", "Baba O\u2019Riley (The Cube Guys remix)")


def test_album_kept() -> None:
    recording = rec("r", ref("1", "Hits", "2019"), ref("2", "Isles", "2021-01-22"))

    assert choose(recording, "isles") == Choice(recording, recording.releases[1])


def test_album_written_differently() -> None:
    recording = rec("r", ref("1", "Best of 2015", "2021", "Compilation"),
                    ref("2", "Dub vs. Wild", "2015", "Compilation"))  # fmt: skip

    assert choose(recording, "Dub vs Wild").release == recording.releases[1]


def test_earliest_release() -> None:
    recording = rec(
        "r",
        ref("1", "Later", "2021"),
        ref("2", "Earlier", "2019-05"),
        ReleaseRef("3", "Bootleg", "Bootleg", "2001"),
        ref("4", "Undated", None),
    )

    assert choose(recording, None).release == recording.releases[1]


def test_original_before_compilation() -> None:
    recording = rec(
        "r", ref("1", "Hits", "2015", "Compilation"), ref("2", "Song EP", "2016", primary="EP")
    )

    search = Searches()
    assert choose(recording, None, search).release == recording.releases[1]
    assert search.asked == []  # an original is at hand: no search


def test_no_official_release() -> None:
    recording = rec("r", ReleaseRef("1", "Promo", "Promotion", "2019"))

    assert choose(recording, None) == Choice(recording, None)


def test_recording_on_the_tracks_album() -> None:
    best_of = fixture_recording(JESSY_BEST_OF)
    search = Searches(*fixture_search("search-jessy-bett-08557f73.json"))
    dub_vs_wild = fixture_recording(JESSY_DUB_VS_WILD)

    choice = resolve(best_of, "Dub vs Wild", search, fetch_from(dub_vs_wild))

    assert choice.recording == dub_vs_wild
    assert choice.release is not None and choice.release.title == "Dub vs. Wild"
    assert search.asked == [("Jessy Bett", PANDA_DUB)]


def test_other_version_on_the_album() -> None:
    remix = rec("r", ref("1", "Serious Beats 58", "2009", "Compilation"),
                title="Baba O\u2019Riley (The Cube Guys remix)")  # fmt: skip
    search = Searches(
        rec(
            "e",
            ref("2", "Baba O'Riley", "2008", primary="Single"),
            title="Baba O'Riley (UK radio edit)",
        ),
        rec(
            "d",
            ref("2", "Baba O'Riley", "2008", primary="Single"),
            title="Baba O'Riley (Cicada dub)",
        ),
    )

    choice = choose(remix, "Baba O'Riley", search)

    assert choice == Choice(remix, None, album_kept=True)


def test_ep_instead_of_a_compilation() -> None:
    zappi = fixture_recording(JOLGORIO_ZAPPI)
    ep = fixture_recording(JOLGORIO_EP)
    search = Searches(*fixture_search("search-jolgorio-ec98b948.json"))

    choice = resolve(zappi, None, search, fetch_from(ep))

    assert choice.recording == ep
    assert choice.release is not None and choice.release.title == "Jolgorio - EP"
    assert search.asked == [("Jolgorio", JACEO)]


def test_only_compilations_exist() -> None:
    recording = rec(
        "r", ref("1", "Hits 2", "2016", "Compilation"), ref("2", "Hits 1", "2015", "Compilation")
    )

    choice = choose(recording, None, Searches(recording))

    assert choice == Choice(recording, recording.releases[1])


def test_compilation_does_not_replace_the_album() -> None:
    zappi = fixture_recording(JOLGORIO_ZAPPI)
    search = Searches(*fixture_search("search-jolgorio-ec98b948.json"))

    choice = resolve(
        zappi, "Jolgorio EP (Toolroom)", search, fetch_from(fixture_recording(JOLGORIO_EP))
    )
    assert choice.release is not None and choice.release.title == "Jolgorio - EP"

    kept = resolve(zappi, "Some Other Album", search, fetch_from())
    assert kept == Choice(zappi, None, album_kept=True)


def test_other_artist_same_title_is_not_the_song() -> None:
    recording = rec("r", ref("1", "Hits", "2015", "Compilation"), artists=("a",))
    stranger = rec("s", ref("2", "Song", "2010", primary="Single"), artists=("b",))

    assert choose(recording, None, Searches(stranger)).recording == recording
