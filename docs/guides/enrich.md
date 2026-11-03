# Enriching tags

`tunedex enrich` recognizes each track by its sound and takes its tags from [MusicBrainz](https://musicbrainz.org). It is the cure for files with poor or missing tags.

```sh
tunedex enrich                              # show what would change
tunedex enrich --under ~/Music/New --apply
```

It needs `fpcalc`; see [install](../install.md#optional-fpcalc-for-enrich).

## What is sent

`enrich` is the only command that uses the network, and only when you run it.

- To [AcoustID](https://acoustid.org): the fingerprint of the first two minutes of each file, and its length.
- To MusicBrainz: the ids of the recognized recordings and releases, and sometimes a search for other recordings of the same song, by the title and artist id MusicBrainz gave.

No file names, paths or tags are sent. See [network use](../explanation/network.md).

## What changes

The first time a track is enriched, it takes MusicBrainz's title, artist, remixer, album, album artist, year, release date, label, and track and disc numbers. Names are then spelled the same across your library.

- The genre is filled only when it is empty.
- MusicBrainz ids, the ISRC and the catalogue number are kept with the track.
- Every change is shown in the plan, marked `(musicbrainz)`.

## Which release

A song is often on several releases: its EP or album, and compilations and DJ mixes. The album, album artist, year, release date, label and track and disc numbers come from one of them:

1. **The track's own album**, when a release has that title. Case, punctuation and bracketed parts are ignored, so `Dub vs Wild` finds `Dub vs. Wild` and `Jolgorio EP` finds `Jolgorio - EP`. MusicBrainz often lists a song on each compilation as a separate recording, so tunedex also looks for the same song (same title and version, same artist) on a release with the track's album title.
2. **Otherwise, the original release.** A track without an album gets the earliest release that is not a compilation or a DJ mix, even when AcoustID recognized the copy on a compilation. If the song is only on compilations, the earliest of them is used.
3. **When the track has an album and no release matches it**, its album fields are kept as they are, and the plan says so, grouped by album:

```text
albums not found in MusicBrainz, album fields kept: 'DJ Selection 371' (3), 'Ibiza Promo' (1)
```

The title and artist are still taken from MusicBrainz. If an album in that list is not a real one, such as `Downloads`, clear it and run `enrich` again to get MusicBrainz's.

## Later runs

Fields you edit in tunedex are kept. When both you and MusicBrainz changed a field, your value stays and the plan lists the conflict.

## No guessing

These tracks are left unchanged and listed in the plan's warnings:

- tracks with several possible recordings, when their length, title and words cannot tell which. Between `Pitch Black` and `Pitch Black, Brother J`, a track tagged `Pitch Black` gets the first;
- tracks recognized but not in MusicBrainz;
- tracks not recognized;
- tracks whose MusicBrainz id, from beets, points elsewhere;
- tracks whose recording does not fit their own tags. When a track has an artist, in its tags or as `Artist - ` in its file name, the recording's artist must share a word with it; otherwise the title or file name must share a word with the recording's title. This keeps AcoustID's occasional wrong match from replacing good tags. The plan lists the first 20, with what the track says and what AcoustID heard.

Once applied, running it again on an unchanged library just says `Nothing to do.`

## Speed and cache

MusicBrainz allows one request per second, so a first run takes about two seconds per track. A bar shows the progress.

Fingerprints and answers are cached in `cache.db` in the [tunedex home](../reference/environment.md#the-home-directory). Later runs are quick and work offline. `--refresh` asks the services again.

Set `TUNEDEX_ACOUSTID_KEY` to use your own AcoustID application key.
