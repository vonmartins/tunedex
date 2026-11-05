import pytest

from tunedex.adapters.rekordbox.keys import key_from_tonality
from tunedex.model.key import Key, Mode

# Alphanumeric -> musical, from Rekordbox's key display (each step is a fifth).
ALPHANUMERIC = {
    "1A": "Abm", "2A": "Ebm", "3A": "Bbm", "4A": "Fm", "5A": "Cm", "6A": "Gm",
    "7A": "Dm", "8A": "Am", "9A": "Em", "10A": "Bm", "11A": "F#m", "12A": "Dbm",
    "1B": "B", "2B": "F#", "3B": "Db", "4B": "Ab", "5B": "Eb", "6B": "Bb",
    "7B": "F", "8B": "C", "9B": "G", "10B": "D", "11B": "A", "12B": "E",
}  # fmt: skip


@pytest.mark.parametrize(("text", "musical"), ALPHANUMERIC.items())
def test_every_alphanumeric_key(text: str, musical: str) -> None:
    key = key_from_tonality(text)

    assert key is not None
    assert key.musical() == musical


def test_alphanumeric_key() -> None:
    key = key_from_tonality("3A")

    assert key == Key(tonic=10, mode=Mode.MINOR)
    assert key is not None
    assert key.open_key() == "8m"


def test_musical_key() -> None:
    assert key_from_tonality("F#m") == Key(tonic=6, mode=Mode.MINOR)


@pytest.mark.parametrize("text", ["13A", "0B", "8C", "", "H", "8 A"])
def test_unknown_key_text(text: str) -> None:
    assert key_from_tonality(text) is None
