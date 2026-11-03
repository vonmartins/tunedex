# Enrichment fixtures

Real answers from AcoustID (`/v2/lookup`, `meta=recordings`) and MusicBrainz (`/ws/2/recording`, `/ws/2/release`), captured on 2026-10-29 for a few test tracks, and on 2026-11-02 for the release choice (recordings re-captured with `release-groups`). They are public catalogue data; no fingerprint or audio is stored here.

| File | Case |
|---|---|
| `acoustid-dfrnt.json` | One recording, score 0.99: `Headspace (Scuba remix)` |
| `acoustid-lung.json` | Two recordings with the same title and nearly the same length (MusicBrainz duplicates) |
| `acoustid-irrelevant.json` | Recognized (score 0.97), but linked to no MusicBrainz recording |
| `acoustid-marina.json` | Not recognized: no results |
| `acoustid-nanobyte.json` | One recording, `Tek-1` (`recording-82eaaf51-…`, on `release-faeabdc0-…`, *Kalyke EP*) |
| `recording-<id>.json` | Recordings with `inc=artist-credits+releases+isrcs+artist-rels+genres+release-groups` |
| `release-<id>.json` | Releases with `inc=labels+recordings+artist-credits` |
| `search-<title>-<artist>.json` | Recording searches `recording:"<title>" AND arid:<artist id>`, `limit=100`; the file name holds the title in kebab case and the first 8 characters of the artist id |

`recording-6340a9b8-…` (`Black Sun Empire feat. Optiv – Insiders`) shows a credit with a join phrase, an ISRC, a genre and producer relations. None of these recordings has a remixer relation: the remixer is only in the title.

Release-choice cases (2026-11-02):

| File | Case |
|---|---|
| `recording-5fc92bf8-…` | Jaceo – `Jolgorio`, on the EP *Jolgorio - EP* (`release-b2f3ca72-…`, 2015) |
| `recording-ee517604-…` | Jaceo – `Jolgorio`, only on the compilation *Zappi Rocks Ibiza* (`release-7d9dec13-…`, 2016) |
| `search-jolgorio-ec98b948.json` | The three recordings of `Jolgorio` by Jaceo: EP, compilation, and `Jolgorio (original mix)` on a DJ mix |
| `recording-fb3674a4-…` | Panda Dub – `Jessy Bett`, on the compilation *Dub vs. Wild* (`release-69f601a5-…`, 2015, track 3) |
| `recording-2120ba7f-…` | Panda Dub – `Jessy Bett`, only on *Best of 2015* (`release-fe550070-…`, 2021) |
| `search-jessy-bett-08557f73.json` | The two recordings of `Jessy Bett` by Panda Dub |
| `search-afterlife-kryptic-minds-remix-c1090619.json` | The recordings of Lung's `Afterlife (Kryptic Minds remix)`: all on compilations and DJ mixes |
