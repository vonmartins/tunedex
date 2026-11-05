"""Small helpers shared by the readers of format adapters."""

from collections.abc import Callable
from typing import Any

from tunedex.model.errors import ValidationError
from tunedex.model.track import Track


def build_track(
    make: Callable[[dict[str, Any]], Track], values: dict[str, Any], path: str, warnings: list[str]
) -> Track:
    """Build a track, dropping (with a warning) any value the model rejects."""
    values = dict(values)
    while True:
        try:
            return make(values)
        except ValidationError as error:
            if error.field not in values:
                raise
            warnings.append(f"{path}: ignored invalid {error.field} ({error.message})")
            del values[error.field]


def text(value: object) -> str | None:
    """Stripped text, or ``None`` for non-text and empty values."""
    if not isinstance(value, str):
        return None
    return value.strip() or None
