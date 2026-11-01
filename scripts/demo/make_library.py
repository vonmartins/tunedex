"""Writes a small music folder with messy tags, for the demo recording.

The tracks are quiet noise made with ffmpeg, saved under the names and tags that real
downloads come with. Artists and titles are made up.

    uv run python scripts/demo/make_library.py /tmp/tunedex-demo/Music
"""

import shutil
import subprocess
import sys
from pathlib import Path

from mutagen import id3
from mutagen.flac import FLAC

FFMPEG = shutil.which("ffmpeg") or sys.exit("ffmpeg is needed: install it first")
LENGTH = "211"  # seconds, about a track's length

# File name, then the tags: (artist, title, bpm, key); None leaves the tag out.
MP3S = [
    ("Nightfall_Collective_-_Midnight_Drive.mp3", (None, None, None, None)),
    ("Afterglow.mp3", ("Luna Vale", "Afterglow (feat. Kai Moreno) [xK3vQ9tLmP2]", "124", "8A")),
    ("pulse.mp3", ("Delta Ritual", "Pulse (Mara Lind Remix)", "128", "5A")),
    ("Static Hearts.mp3", ("Echo Harbor", "Static Hearts www.freemusic.example", "122", None)),
    ("Glass Rooms (1).mp3", ("Solenne", "Glass Rooms", "126", "11B")),
]
FLACS = [("Solenne - Glass Rooms.flac", ("Solenne", "Glass Rooms", "126", "11B"))]


def encode(path: Path, *options: str) -> None:
    noise = f"anoisesrc=d={LENGTH}:a=0.02:c=pink"
    subprocess.run(  # noqa: S603 - fixed arguments, no shell
        [
            FFMPEG,
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            noise,
            "-map_metadata",
            "-1",
            *options,
            str(path),
        ],
        check=True,
    )


def write_mp3(
    path: Path,
    source: Path,
    artist: str | None,
    title: str | None,
    bpm: str | None,
    key: str | None,
) -> None:
    shutil.copyfile(source, path)
    tags = id3.ID3()
    for frame, value in ((id3.TPE1, artist), (id3.TIT2, title), (id3.TBPM, bpm), (id3.TKEY, key)):
        if value is not None:
            tags.add(frame(encoding=3, text=value))
    tags.save(path, v2_version=3)


def write_flac(path: Path, source: Path, artist: str, title: str, bpm: str, key: str) -> None:
    shutil.copyfile(source, path)
    audio = FLAC(path)
    audio.update({"artist": artist, "title": title, "bpm": bpm, "initialkey": key})
    audio.save()


def main(folder: Path) -> None:
    if folder.exists():
        sys.exit(f"{folder} exists; give a new folder, this script never writes into one")
    folder.mkdir(parents=True)
    mp3, flac = folder / "source.mp3", folder / "source.flac"
    encode(mp3, "-ac", "2", "-b:a", "320k", "-id3v2_version", "0", "-write_xing", "1")
    encode(flac, "-ac", "2", "-sample_fmt", "s16")
    for name, tags in MP3S:
        write_mp3(folder / name, mp3, *tags)
    for name, (artist, title, bpm, key) in FLACS:
        write_flac(folder / name, flac, artist, title, bpm, key)
    mp3.unlink()
    flac.unlink()


if __name__ == "__main__":
    main(Path(sys.argv[1]))
