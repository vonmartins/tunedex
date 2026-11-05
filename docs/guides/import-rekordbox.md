# Importing from Rekordbox

Bring your Rekordbox collection into tunedex: tracks, keys, cues, loops, beat grids, playlists and folders. tunedex reads the XML file that Rekordbox exports. It does not open Rekordbox's own database.

## Export the XML from Rekordbox

In Rekordbox, choose **File > Export Collection in xml format** and save the file, for example as `~/rekordbox.xml`. Export again whenever you want tunedex to see newer changes.

## Import it

Scan your music folder first, so that tunedex reads each file's own tags, then import the XML:

```sh
tunedex scan ~/Music --apply
tunedex import rekordbox ~/rekordbox.xml               # show the plan
tunedex import rekordbox ~/rekordbox.xml --apply
```

Scanning first matters because the first import from a source only fills fields that are empty in tunedex. Rekordbox sometimes stores a title it decoded wrongly (`M髎` for `Mós`), and a scanned title wins over it. The same goes for BPM and key: when the file's tags have them, tunedex keeps those, and Rekordbox's values fill only what the tags lack. Cues, loops and beat grids always come from Rekordbox, because files do not have them.

## A collection from another computer

An XML exported on Windows points to paths such as `C:/Users/DJ/Music/...`. If the files are now on this computer in another folder, `--find-in` looks for them there, the way [`relocate`](relocate.md) does, and imports only the tracks it finds:

```sh
tunedex import rekordbox ~/rekordbox.xml --find-in ~/Music --apply
```

Tracks that are not found are left out, along with their playlist entries, and the plan counts them. Run the command again after copying more files: the tracks imported before are recognized.

Rekordbox collections often hold the same song twice, for example once from `D:/` and once from `C:/Users/.../Music/`. When both lead to the same file under the search folder, tunedex keeps one track for it: the copy with the most cues, then the one in the most playlists. Playlist entries of the other copy point to that track, and the plan says how many copies were joined.

## What is imported

- **Track fields:** title, artist, album, genre, composer, grouping, comment, remixer, label, mix, year, track and disc number, BPM, key, rating, color, play count, date added, duration, bitrate, sample rate and file format.
- **Keys:** read in Rekordbox's alphanumeric notation (`8A`) or in musical notation (`Am`). tunedex shows them in Open Key or musical notation and keeps the original text.
- **Cues:** hot cues with their pad, name and color, memory cues, loops and hot loops.
- **Beat grids:** exactly as Rekordbox stores them, including grids with several markers. A grid tunedex cannot hold, for example one with two markers at the same position, is left out with a warning that names the track. The track's BPM is still imported.
- **Playlists and folders:** they go into a `Rekordbox` folder in tunedex, keeping their tree. Each import replaces that folder; nothing else in tunedex is touched.
- **Kept but not used:** Rekordbox's track id, the file kind and size, fade and load markers, and anything else tunedex does not know are kept with the track as [unmapped data](../explanation/adapters.md#unmapped-data).
- **Only read:** the XML and your music files are never changed.

Rekordbox's analysis is imported as it is. If Rekordbox got a BPM or a grid wrong, tunedex has the same value until you fix it.

## Not imported

My Tags, the history, smart playlist rules and anything else that Rekordbox does not put in the XML.

## Importing again

Tracks are matched by Rekordbox's track id, then by path.

- **The first import** only fills fields that are empty in tunedex.
- **Later imports** take the changes made in Rekordbox since the last one. If you also edited the same field in tunedex, tunedex keeps your value and the plan lists a **conflict**.
