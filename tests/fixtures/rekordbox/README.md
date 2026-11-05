# Rekordbox fixtures

- `rekordbox-7.2.14.xml`: a hand-written Rekordbox XML export. It has the structure of a
  real Rekordbox 7.2.14 export with a Spanish UI: UTF-8 without BOM, CRLF line endings,
  `Kind` localized as `Archivo MP3` / `Archivo WAV`, the full set of 25 track attributes,
  percent-encoded `file://localhost/C:/` and `D:/` locations, alphanumeric `Tonality`,
  and `TEMPO` / `POSITION_MARK` children. Every artist, title, path and number is invented.
  Unit tests build other documents with `tests/support/rekordbox.py`.

## What `rekordbox-7.2.14.xml` contains

| TrackID | Track | Case covered |
|---|---|---|
| 90000001 | Nadia Ferro – Lowland Drift | `3A` = B♭ minor (`8m`), BPM 128, one grid marker at 212,000 µs; hot cues 0 (75,212,000 µs, `#FF376F`) and 1 (120,212,000 µs, `#45ACDB`) |
| 90000002 | Orla Vint – `M髎` | A title mangled by Rekordbox: `Mós` encoded as cp1252 and read as GBK. Read as it is. Path `.../Orla Vint - Mós.mp3` (lower-case percent escapes); year and track number 0 are absent; hot cue 2 named `something` |
| 90000003 | Kestrel & Moth – Tempo Watch | Three same-BPM grid markers (127.93 BPM, beat 2) kept as they are; a memory cue (no colour) and hot cue 0 both at 231,000 µs; hot cue 7 named `Drop`; rating 204 = 4; disc 1, track 4, play count 3, remixer, mix, composer |
| 90000004 | Brightwater – Hollow Engine | Two `TEMPO` at the same position (174.96 and 43.74 BPM): no grid, raw markers in `unmapped`, warning; BPM 87.48 from `AverageBpm`; `D:/` path; `5B` = E♭ major (`10d`) |
| 90000005 | Ferro Unit – Signal Pool | WAV (`Archivo WAV`), 48 kHz, 1411 kbps; `Colour="0xFF007F"`; rating 153 = 3; `9B` = G major (`2d`); memory loop 10,000,000–17,500,000 µs; hot loop 1 `Roll` 30,144,000–31,909,000 µs; fade-in (type 1) and load (type 3) marks kept in `unmapped` |
| 90000006 | Ñandú Collective – Café Noir | Non-ASCII path `D:/House/Ñandú Collective - Café Noir.mp3`; two grid markers; rating 51 = 1; `2B` = F♯ major (`7d`) |
| 90000007 | – Untitled Sketch | Unanalysed: BPM, key, year, duration, bitrate, sample rate and artist absent |
| 90000008 | Nadia Ferro – Lowland Drift | Same location as 90000001: skipped with a warning; entries point to 90000001 |

Playlists, in order, under `ROOT`:

- `Lista sin título`: empty playlist.
- `Warmup` (`KeyType` 0): 90000006, 90000001, 90000001 (the duplicate 90000008), and an unknown `Key` 90000099 left out with a warning.
- `Sets` folder → `Peak`: 90000003, 90000004, 90000005, 90000002, 90000003.
- `D:` (`KeyType` 1, entries by location): 90000004, 90000006.
- `Archive`: empty folder.
