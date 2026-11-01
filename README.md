# tunedex

[![PyPI](https://img.shields.io/pypi/v/tunedex)](https://pypi.org/project/tunedex/)
[![Python](https://img.shields.io/pypi/pyversions/tunedex)](https://pypi.org/project/tunedex/)
[![CI](https://github.com/vonmartins/tunedex/actions/workflows/ci.yml/badge.svg?branch=dev)](https://github.com/vonmartins/tunedex/actions/workflows/ci.yml)
[![License](https://img.shields.io/pypi/l/tunedex)](https://github.com/vonmartins/tunedex/blob/main/LICENSE)

A free, local-first, scriptable DJ library manager. Take control of your library, in
one place.

tunedex cleans the tags of your music, finds duplicates, writes the result into your
files and exports it to your DJ app. Every change is planned first, shown before it
happens and can be undone.

<!-- TODO: demo recording (vhs), docs/assets/demo.gif -->

**Documentation: [vonmartins.github.io/tunedex](https://vonmartins.github.io/tunedex/)**

> [!WARNING]
> **Status: alpha.** It has been tested on a real collection of 11,000 tracks, but try
> it with a scratch home and a test profile of your DJ app before you point it at the
> library you play from.

## Why tunedex

- **Your library is yours.** It lives in your files and in a local database, on your
  computer. No account, no subscription, no cloud, and it works offline.
- **One library, many apps.** Your music folder is the source of truth; DJ apps and
  other tools are sources you import from and targets you export to. Moving to another
  app should never mean starting over.
- **Free and open.** GPL, on Linux, macOS and Windows.

**Not yet:** Rekordbox, Serato and Traktor are not supported, there is no graphical
interface, and tunedex does not analyze BPM or key. Reading Rekordbox and Traktor
libraries is next on the [roadmap](#roadmap).

## What it does

- **Imports** your music folder, Mixxx and beets, read only. More sources are coming.
- **Cleans** tags with bundled fixes (URLs, video ids, "feat." and "remix" in the
  title) and your own rules in YAML.
- **Recognizes** tracks by their sound with AcoustID and fills in their tags from
  MusicBrainz, when you ask it to.
- **Finds and merges duplicates**, keeping the best file and moving the others to the
  system trash.
- **Writes the cleaned tags into your files**, keeping cover art and the audio
  intact, and **renames files** from their tags.
- **Exports** playlists, cues, loops and grids to Mixxx, and playlists to M3U.
- **Undoes** any write: a snapshot is taken before each one.

No accounts, no telemetry, no cloud. Only `enrich` uses the network.

## How it compares

| | tunedex | [Lexicon] | [MIXO] | [beets] | [Picard] |
|---|---|---|---|---|---|
| Price | Free | Free plan, paid plans | Free plan, Gold $7/month | Free | Free |
| Open source | Yes | No | No | Yes | Yes |
| Linux | Yes | No | Yes | Yes | Yes |
| Graphical interface | No | Yes | Yes | No | Yes |
| Command line and scripting | Yes | Partial¹ | No | Yes | Partial² |
| Rekordbox, Serato, Traktor | No (planned) | Yes | Yes | No | No |
| Mixxx | Yes | No | Yes | No | No |
| Fill in tags from online databases | Yes³ | Paid⁴ | No | Yes | Yes³ |
| Clean tags with rules | Yes | Yes | Paid⁵ | Partial⁶ | Yes |
| Find and merge duplicates | Yes | Paid | Paid | Yes⁶ | No |
| Write tags into the files | Yes | Paid | ? | Yes | Yes |
| Rename files from their tags | Yes | Paid⁷ | ? | Yes | Yes |
| BPM and key analysis | No | Yes | No | Partial⁶ | No |
| Undo writes, file tags included | Yes | Partial⁸ | ? | No | No |
| Cloud backup, mobile app | No | Paid | Yes | No | No |

"Paid" means a paid plan only; "?" means the product's public pages do not say.
Checked on 2026-11-01 against each product's website and documentation. Corrections
are welcome in an [issue](https://github.com/vonmartins/tunedex/issues).

1. A local REST API on paid plans, available only while the app is open.
2. A scripting language and plugins inside the app; no command line.
3. MusicBrainz, matching each file by its audio fingerprint (AcoustID).
4. Beatport, Spotify and Discogs, matched by text.
5. Find and replace.
6. Through plugins.
7. Through the watch folder.
8. Backups of its own database and of the DJ apps' libraries before each write;
   not of the audio files.

[Lexicon]: https://www.lexicondj.com/
[MIXO]: https://mixo.dj/
[beets]: https://beets.io/
[Picard]: https://picard.musicbrainz.org/

Lexicon and MIXO are the tools to use if you play with Rekordbox, Serato or Traktor
today. beets and Picard are excellent taggers; tunedex uses the same MusicBrainz data
and adds what DJs need around it: duplicates, playlists, cues and export to a DJ app.

## Install

```sh
uv tool install tunedex
```

or `pipx install tunedex`. Python 3.11 or later, on Linux, macOS and Windows.
Recognizing tracks needs [fpcalc](https://acoustid.org/chromaprint) (Chromaprint).
For the development version, install `git+https://github.com/vonmartins/tunedex@dev`.

## Quick start

Each command shows its plan and writes nothing until you add `--apply`.

```sh
export TUNEDEX_HOME=/tmp/tunedex-try   # a scratch home, to try it safely

tunedex scan ~/Music --apply           # read the music folder into the library
tunedex fix --apply                    # clean the tags in the library
tunedex enrich --apply                 # fill in tags from MusicBrainz
tunedex dupes                          # report duplicates
tunedex write-tags --apply             # write the clean tags into the files
tunedex rename --apply                 # rename the files: "{artist} - {title}"
tunedex export mixxx --apply           # send it all to Mixxx (quit Mixxx first)

tunedex snapshot list                  # every write took a snapshot first
tunedex snapshot restore tags <id>     # and can be undone
```

Then follow the [tutorial](https://vonmartins.github.io/tunedex/tutorial/).

## Building on tunedex

Every command takes `--json` and prints one documented JSON document; errors have
stable codes. Python programs can `import tunedex`. See
[using tunedex from another program](https://vonmartins.github.io/tunedex/guides/from-another-program/).

## Roadmap

1. Read BPM, key, cues and playlists from Rekordbox and Traktor libraries.
2. Discogs, for the tracks MusicBrainz does not know.
3. BPM and key analysis.

Ideas and requests are welcome in the
[issues](https://github.com/vonmartins/tunedex/issues).

## Development

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv sync
uv run tunedex --help
uv run pytest
```

See [CONTRIBUTING.md](https://github.com/vonmartins/tunedex/blob/main/CONTRIBUTING.md)
for the checks, the conventions and how to preview the documentation.

## License

[GPL-3.0-or-later](https://github.com/vonmartins/tunedex/blob/main/LICENSE).
