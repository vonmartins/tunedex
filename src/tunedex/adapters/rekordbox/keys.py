"""Rekordbox's ``Tonality`` text: alphanumeric (``8A``) or musical (``Am``) notation.

The alphanumeric notation is only read here and never written: tunedex renders keys in
Open Key and musical notation.
"""

import re

from tunedex.model.key import Key, parse_musical, parse_open_key

_ALPHANUMERIC = re.compile(r"^0?([1-9]|1[0-2])([AaBb])$")


def key_from_tonality(text: str) -> Key | None:
    """The key a ``Tonality`` text names, or ``None`` when it is in neither notation."""
    text = text.strip()
    match = _ALPHANUMERIC.match(text)
    if match is not None:
        # 8A is A minor (Open Key 1m) and 8B is C major (Open Key 1d).
        number = (int(match.group(1)) - 8) % 12 + 1
        suffix = "m" if match.group(2) in "Aa" else "d"
        return parse_open_key(f"{number}{suffix}")
    return parse_musical(text)
