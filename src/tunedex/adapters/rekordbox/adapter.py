"""The Rekordbox XML adapter class."""

from pathlib import Path

from tunedex.adapters.contract import (
    Capabilities,
    Detection,
    ReadOptions,
    ReadResult,
    WriteOptions,
    WritePlan,
)
from tunedex.adapters.errors import AdapterError, AdapterReadError
from tunedex.adapters.rekordbox import reader
from tunedex.model.cue import CueKind
from tunedex.model.library import Library

CAPABILITIES = Capabilities(
    track_fields=frozenset(
        {
            "title",
            "artist",
            "album",
            "genre",
            "composer",
            "grouping",
            "comment",
            "remixer",
            "label",
            "mix",
            "year",
            "track_number",
            "disc_number",
            "play_count",
            "bitrate",
            "sample_rate",
            "bpm",
            "duration_us",
            "date_added",
            "rating",
            "color",
            "file_format",
            "key",
            "key_original",
        }
    ),
    cue_kinds=frozenset({CueKind.HOT, CueKind.MEMORY, CueKind.LOOP}),
    beatgrid=True,
    folders=True,
    collection=True,
)


class RekordboxAdapter:
    """A Rekordbox XML export (File > Export Collection in xml format). Read only."""

    name = reader.NAME
    display_name = "Rekordbox"
    capabilities: Capabilities = CAPABILITIES

    def detect(self, location: Path) -> Detection:
        try:
            product = reader.inspect(location)
        except AdapterReadError as error:
            return Detection(False, str(error))
        if (product.name or "").casefold() == reader.NAME:
            return Detection(True, f"Rekordbox XML export ({product.describe()})")
        return Detection(True, f"{reader.ROOT_TAG} XML export written by {product.describe()}")

    def read(self, location: Path, options: ReadOptions | None = None) -> ReadResult:
        options = options or ReadOptions()
        rekordbox = reader.RekordboxReader(options.path_mapping)
        library = rekordbox.read(location)
        return ReadResult(library=library, warnings=tuple(rekordbox.warnings), keys=rekordbox.keys)

    def plan_write(
        self, library: Library, location: Path, options: WriteOptions | None = None
    ) -> WritePlan:
        raise AdapterError("writing Rekordbox XML is not supported yet; only reading is")
