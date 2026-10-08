# IRIS ENCODE — User guide

**Version**: 0.8.9.104
**Date**: 2026-10-08

*[Version française : GUIDE.fr.md](GUIDE.fr.md)*

Installation: see [`README.md`](README.md). Internals: see `iris_encode_spec.md`
(in French).

---

## 0. Opening the application

**The "IRIS ENCODE" shortcut on the Desktop**, if it has been created. It is the
only way that guarantees the right terminal: a shortcut aimed straight at
`launch.bat` opens the legacy Windows console, with degraded rendering —
approximate borders, missing glyphs.

To create it, once installed: double-click **`launcher\build.bat`**, which
compiles the launcher and offers the shortcut. Details, and an alternative
without an executable, in **README § 5.1**.

Otherwise `launch.bat` works — preferably started *from* Windows Terminal
rather than by double-click.

**When a new version is published**, startup says so before opening the
application:

```
  Update available: v0.8.9.1 → v0.9.0.0
  Install now? [Y/n]
```

`Enter` (or `y`) installs, then the application restarts on the new version;
`n` postpones (the question comes back at the next start). Your settings, your
profiles and the tools in `bin/` are never touched. Offline, nothing is shown.
To install without asking, or to check nothing anymore: `app = "auto"` or
`app = "off"` under `[updates]` in `config.toml`. Details in **README § 5.2**.

**The interface language** is set in the options (`F5`, then `U`, § 2.7) and
takes effect at the next start.

---

## 1. The path in three steps

```
Home  ──F1──>  Dry run  ──F2──>  Encoding
  │
  └──T──>  Tracks  ──F9──>  Sync  ──F3──>  Mux
```

**Always go through the dry run.** It shows what *will* happen — codec,
bitrate, container, estimated size, encoding time — before you spend hours on
it. That is where you spot an unexpected container or a file that should not
have been checked.

Two different operations, not to be confused:

| | What it does | When |
|---|---|---|
| **Encode** (`F2`) | Re-encodes the video, takes in the added tracks in the same pass | You want a smaller file |
| **Mux** (`F3`) | Adds the tracks without touching the video | You just want to add a dub |

Muxing is **not** a step before encoding: `F2` does both in one pass. See § 4.6
for the only exception.

---

## 1bis. Guided mode

The application opens in **guided mode**: one file at a time, five steps, `↵`
to move on and `⌫` to go back.

The mode shows in three places, because it changes what `↵` does on a file:
the profile bar (`W Guided`), the label of the `W` key in the footer, and **the
color of that footer** — manual mode keeps the usual blue, guided mode takes
the theme's accent.

`W` switches between guided and manual mode. The choice holds for the session.

In the list, `↵` on a file opens the path:

| Step | What you do there |
|---|---|
| 1 — File | Check the file and the active profile |
| 2 — Decision | Codec (`F6`), bitrate (`F7`), tracks to keep (`Space`) — all on the same screen, with the name of the file that will come out and the reason for the video decision |
| 3 — External tracks | `F9` presents a file carrying a dub or subtitles, `D` removes the last one |
| 4 — Launch | `↵` takes the recommended choice; `F3` forces the mux, `F2` forces the encode — even of a `SKIP` file, at the source bitrate, keeping Dolby Vision if the profile keeps it |
| 5 — Done | The result; `↵` goes back to the list |

**The offset measurement is automatic.** As soon as a track is added, it is
measured, and the offset found on the audio is carried over to the subtitles
from the same file. There is nothing to start.

If the measurement fails — different cut, track too short — the offset stays at
zero and guided mode says so. Then use manual mode (`W`), where the Sync screen
offers `G`, `P`, `C` (§ 4.5) and the anchor point `R` (§ 4.5bis).

**In manual mode**, `↵` on a file opens the Tracks screen, and the path is the
one described below.

---

## 2. Screen by screen

### 2.1 Home — browsing and selection

The entry point. One row per file, with its encoding decision computed from the
active profile.

| Key | Action |
|---|---|
| `↵` | On a folder: open it. On a file: **open guided mode**, or the Tracks screen in manual mode |
| `W` | Switch **guided / manual** — changes what `↵` does on a file |
| `⌫` | Go up |
| `Space` | Check / uncheck the file |
| `A` / `N` | Check all / uncheck all |
| `T` | Tracks screen of the file under the cursor, whatever the mode |
| `V` | Open in mpv |
| `Ctrl+D` | **Delete permanently** the file, with its `.nfo` and images created by Jellyfin (confirmation, no recycle bin) |
| `F1` / `F2` | Dry run / Encode the checked files |
| `R` | Encode the folder under the cursor, recursively |
| `F4` / `F5` | Choose a profile / manage profiles |
| `J` | **Join** the checked files end to end into one (§ 2.1bis) |
| `I` | Movie Info card: AlloCiné, then IMDB with `Tab` |
| `L` | **Filter** by picture type: Dolby Vision (all profiles or one), HDR without DV, SDR |
| `Z` | Hide / show the `SKIP` files |
| `Tab` / `Shift+Tab` | Next / previous column |
| `<` / `>` | Narrow / widen the chosen column (widths remembered) |

The **Decision** column says what will be done: `HEVC`, `H264`, `AV1` or
`SKIP`. A `SKIP` file is already compressed enough — checking it anyway forces
it to be encoded at the source bitrate. **The column shows it as soon as you
check it**: the forced decision replaces `← SKIP`, in orange, and a message
recalls it. Same for a `→ HDR10` row (Dolby Vision removal): checked, it is
re-encoded. A Dolby Vision source checked under a profile that keeps DV is
re-encoded keeping DV (`→ HEVC → DV`), at the source bitrate. `F1` and `F2`
with nothing checked say so instead of doing nothing. Checked files go in the
alphabetical order of the list.

**Filtering the list.** `L` shows only one picture type; the choice only offers
the types present in the folder, with their count. `Z` hides the `SKIP` files.
Both add up, hold from one folder to the next during the session, and the
status bar says how many files are hidden. Folders stay visible. **A checked
row is never hidden**: what will go to encoding stays in sight. `A` only checks
what is visible.

**When coming back from an encode**, the list is read again — the outputs
appear — and the files that succeeded are unchecked. A file that failed or was
interrupted stays checked, ready to run again.

**What the application has encoded is recognized by its name.** Every output
ends with `-iris`, preceded by what the processing did: `Movie.2160p.hevc-iris.mkv`,
`Movie.720p.h264-iris.mp4`, `Movie.av1-iris.mkv`, `Movie.dv-iris.mkv` (Dolby
Vision kept), `Movie.hdr10-iris.mkv` (RPU removed). A characteristic the name
already carries is not repeated — `Movie.2160p.DV` comes out as
`Movie.2160p.DV-iris`. These files are grayed out in the list and left out of
the recursive scan and of `A`: offering them again would mean offering to
re-encode over a file already processed, with the generation loss that implies.

A `.mux-iris` is the exception and **stays offered**: it is not an encode but
added tracks, and encoding it afterwards is a normal sequence. So is a
`.join-iris`, for an even stronger reason: a joined file only exists to be
encoded next (§ 2.1bis).

**The release group does not follow.** The last token of a release name,
detached by a dash — `Movie.1080p.x265-GROUP`, `Movie 1080p - GROUP` — signs
the source; the output loses it: `Movie.1080p.hevc-iris.mkv`. It is only
dropped if the rest of the name carries a release tag (`1080p`, `x265`, `HDR`,
`BluRay`, `MULTi`…) and if it is not a tag itself: `Title-Movie.mkv`,
`Title - Subtitle.mkv`, `Movie.1080p.DTS-HD.mkv` keep their ending.

> Since v0.8.8.11, the old names (`_[hevc]`, `_[av1]`…) are no longer
> recognized: they are treated as ordinary sources. Re-encoded, a
> `Movie_[hevc]` comes out as `Movie.hevc-iris`.

> Since v0.8.9.44, the tag is `-iris` (it used to be `.IRIS`). Outputs with the
> old tag are no longer recognized: they become sources again, and a re-encode
> keeps their `.IRIS` in the name — `Movie.1080p.hevc.IRIS` comes out as
> `Movie.1080p.IRIS.hevc-iris`.

> Before v0.8.5.1, only `_[hevc]` and `_[H264]` were recognized. An AV1 output
> therefore showed up in the list again, and since AV1 is not a codec the chain
> can play back, it was classed "to re-encode in HEVC" — with, on a
> `⚠ del.` profile, the original AV1 deleted.

### 2.1bis Join — putting a movie delivered in parts back together

A movie in `part1` / `part2` cannot be encoded as it is: each part taken alone
would come out on its own, and you would have two files where one is needed.
`J`, on the Home screen, joins first — then the file is handled like any other.

**Check the parts with `Space`** (at least two), then `J`.

| Key | Action |
|---|---|
| `Ctrl+↑` / `Ctrl+↓` | Move the part under the cursor up / down one place |
| `F2` | Join — start the join |
| `⌫` | Back to Home — a join in progress is interrupted and its partial file deleted |

**The order is the only thing to check.** It is deduced from the names, and
numbers count as numbers: `part10` comes well after `part2`, where an
alphabetical sort would slip it between `part1` and `part2`. The table is what
will be joined — if it is wrong, `Ctrl+↑/↓` fix it. Two swapped parts produce a
file of the **right length**, hence wrong without anything telling you.

The **Join** column says, row by row, whether the part matches the first one:

| What is shown | What it means |
|---|---|
| **reference** | The first part. It gives the produced file its codecs, its resolution and its set of tracks |
| **✓** | It joins without losing anything |
| **✓ with reservations** | It joins, but carries more (or fewer) audio or subtitle tracks: only the common positions will survive. Details show under the table |
| **✗ incompatible** | Different video codec, resolution or audio format — `F2` is refused |

The file name column is as wide as on the Home screen: if you widened it there
(`Tab` then `>`), the Join screen benefits.

Joining **re-encodes nothing**: mkvmerge shifts the timestamps of each part to
the end of the previous one. It is a disk copy — allow the time to write the
sum of the parts, and plan the space, since the originals stay in place.

**Nothing is deleted.** The parts are kept; `Ctrl+D` on the Home screen
remains the only action that deletes. The produced file is named
`<common name>.join-iris.mkv` — `Movie part1.mkv` + `Movie part2.mkv` give
`Movie.join-iris.mkv` — and the join refuses to overwrite an existing file.

At the end, the screen compares the length obtained with the sum of the parts.
A gap is announced rather than passed over: an interrupted mkvmerge leaves a
playable and **short** file, which would otherwise pass for a successful join.

`⌫` goes back to Home, where the joined file appears with its decision — from
there, `F1`, `F2`, `T` and the rest work on it as on the others.

### 2.2 Tracks — choosing what to keep

From the Home screen with `T`. One row per audio and subtitle track, plus a
video row at the top.

| Key | Action |
|---|---|
| `Space` | Keep / discard the track |
| `↵` | Confirm the row's choice |
| `←/→` `+/-` | On the video row: change codec, bitrate, Dolby Vision handling |
| `F6` / `F7` | Codec / target bitrate |
| `F8` | Delete or keep the source file after encoding (deleted, it takes its `.nfo` and Jellyfin images along, not its `.srt`) |
| `F9` | **Add an external track** — leads to the donor file choice |
| `F4` | Change profile |
| `F1` / `F2` | Dry run / Encode this file only, without going back to the list |

Discarding every image subtitle (PGS, VobSub) frees the MP4 container; keeping
one forces MKV.

A PGS doubled by an SRT of the same language and kind arrives **unchecked**:
Jellyfin would burn it in, hence transcode, to show what the SRT already says.
A forced SRT only doubles a forced PGS, a full SRT a full PGS. Alone in its
language and kind, the PGS stays checked. Checking it again by hand is enough
to keep it.

### 2.3 Donor file choice

After `F9`. You first choose the file that carries the track to add, then its
tracks within that file. The working file is left out of the list.

`↵` chooses the file, then `Space` checks the tracks to add and `↵` confirms.
`Esc` cancels. A single track is preselected. Several donors can follow one
another without leaving the next screen.

**No subtitle on disk? `O` searches OpenSubtitles.com**, in the profile's
subtitle languages. Rows marked `≡` were uploaded for this exact release: they
are already in sync, take them first. `SDH` flags a subtitle for the deaf and
hard of hearing. `↵` downloads the row; the file comes back here as if you had
chosen it, and the rest is the same — track preselected, language deduced,
resync.

You need an application key and an account (free, 20 downloads a day). At
startup, if the key is missing, a window asks for it: **Get a key** opens
opensubtitles.com/consumers, you paste the key, the username and the password,
and **Check and save** (or `Ctrl+S`) checks them with OpenSubtitles and saves
them. To enter or change them later: `F5`, then `K` (§ 2.7).

Without them, the screen says what is missing. The `.srt` is written to the
temporary folder, not next to the movie: it only exists for the added track.

**Read the Name column to the end.** A rip commonly carries six French tracks:
France and Canada, each as normal, `(forced)` and `(SDH)`. They have the same
codec and the same language — **the name is the only thing that tells them
apart**, and it is shown in full.

A `(forced)` track only holds the lines in a foreign language: twenty-three on
an episode. Chosen by mistake, it shows up in the player and almost never
displays anything. It is usually the **first** in the list.

### 2.4 Sync — the screen that asks for the most attention

One row per added track. Fields are walked with `←/→`, values changed with
`+/-`.

**The first line of the banner says what the field under the cursor does**,
and it is never cleared — not for a warning, not for a measurement report,
which take the following lines. That is where you read which keys change the
value shown, and they differ from one field to the next: only the offset has
three steps, the other fields cycle through their values.

| Key | Action |
|---|---|
| `←/→` | Previous / next field |
| `Ctrl+↑/↓` | ±10 ms on the offset — to close in on a measured value |
| `+/-` | ±100 ms on the offset, next value on the other fields |
| `Shift+↑/↓` | ±1 s on the offset |
| `↵` | List of values of the current field |
| `M` | **Measure** the offset automatically |
| `F` | Force the candidate of a refused measurement |
| `G` | Details of the detected **segments** |
| `P` | **Apply the segments** to the track under the cursor |
| `C` | Copy the offset of another track |
| `R` | **Anchor point** — when the measurement does not conclude (§ 4.5bis) |
| `V` | Check in mpv |
| `K` | Check sample, actually muxed |
| `D` | Remove the track |
| `F9` | Add another track |
| `F1` `F2` `F3` | Dry run / Encode / Mux |

**The language is required.** Without it, the track would come out as "und" in
every player, and the mux is refused. The screen opens directly on that field
when a track lacks it.

**Carrying over is automatic.** A successful measurement on an audio track
applies at once to the subtitles from the **same file**: their right offset
*is* the audio's, since they were written on its timing. The banner says how
many tracks followed, and their Sync column shows "copied from #N".

Two kinds of track never follow: those from **another file**, and those you
have already measured or set by hand — a decision made is not overwritten. `C`
is there for those cases.

### 2.5 Dry run — what will be done

| Key | Action |
|---|---|
| `Space` | Include / exclude the row |
| `F6` / `F7` | Change the codec / bitrate **of this row only** |
| `F2` | Start encoding — `↵` starts nothing, on purpose |

The **Est. (Δ%)** and **ETA** columns — the expected encoding time — rest on a
moving average of the speed measured at each encode: they improve with use and
are approximate on the first runs.

### 2.6 Encoding — the queue

**Encoding no longer blocks navigation.** `F2` — from Home, the dry run,
Tracks, Sync or guided mode — puts the files in **a queue**, which starts as
soon as it has an entry and processes them in order. While it runs, go back to
the files (`⌫` or `F12`), choose others and `F2`: they are added after the
others. `F12` switches between the files and the queue. As long as a batch
exists, the header shows it in the middle, on every screen: "F12 Encoding in
progress · 1/3 · 42%", then "F12 Batch done"; from the queue, "F12 Files".

- A file already in the queue is refused, with a message.
- Each file keeps the settings it had when added: changing profile afterwards
  does not affect it.
- Files handed to the queue are unchecked on the Home screen.
- A file waiting or running cannot be deleted (`Ctrl+D`).
- Quitting (`F10`) says how many files are still waiting.

| Key | Action |
|---|---|
| `P` | Pause / resume |
| `S` | Skip the current file, without canceling the rest |
| `Ctrl+↑` / `Ctrl+↓` | Move the waiting file under the cursor up / down one place |
| `Del` | Remove the waiting file under the cursor from the queue |
| `X` | **Stop all** — the current file and the queue; asks for confirmation |
| `E` | **After the batch** — sleep, hibernate or shut down the machine once everything is done |
| `⌫` / `Esc` / `F12` | Back to the files — **encoding continues** |

Once the batch is done, the footer keeps only navigation, and the bottom area
gives the summary: succeeded, failed, skipped, then the path of each produced
file. If you were in the files, a notification announces it; the summary waits
until you have seen it (`F12`), then clears when you leave the view. A new
addition starts a new batch.

**The machine no longer sleeps during processing** — encoding, mux, join,
measurement or resync. The header then shows "☾ sleep blocked". The screen
can still turn off, and a sleep requested by hand (Start menu, lid closed) still
goes through. It can be turned off in the options (`F5`, `U`).

**After the batch** (`E`): once **all** processing is done, the machine
sleeps, hibernates or shuts down — your choice, in the options. By default the
options say **"do nothing"**: `E` then arms nothing and recalls where to choose
an action. The header announces it ("☾ … · then shut down"). A 60 s countdown
comes first: `↵` on "Cancel" (preselected) or `Esc` stops it. The switch starts
unchecked at each new batch, and a batch stopped by `X` triggers nothing.
Windows only.

### 2.7 Profiles (`F5`)

`N` creates, `E` edits, `C` copies, `D` deletes, `↵` activates. Copying opens
the form with the settings of the profile under the cursor and a free name
(`<name>_copie` — a profile name is an identifier, the same in every language):
change what differs, `Ctrl+S` saves the new profile.

`U` opens the **options**: block sleep while tasks run (on by default), what
the machine does after a batch whose "After the batch" is checked ("do
nothing" by default, sleep, hibernate or shut down), and the **interface
language**: each available language is listed under its own name ("English",
"Français"). The change takes effect at the next start. On the very first
start, IRIS ENCODE takes the Windows language if it is translated, English
otherwise.

`K` opens the **API keys** of the online services — OpenSubtitles and OMDb
(full IMDB Info card): each service has its button to the page that issues the
key, and a key is checked with the service before being saved. The same window
opens at startup as long as a key is missing; "Do not ask again" dismisses it
for that service.

The list is exactly that of `profiles.toml`, in the file's order: you can edit
it by hand, the application adds or reorders nothing. Every profile can be
deleted except the last one in the list. Renaming a profile is done in the
file: the form's **Identifier** field can only be typed at creation. A profile
marked `⚠ del.` deletes the source file after a successful encode — check it
before starting a batch.

---

## 3. Use cases

### 3.1 Adding a dub and its subtitles to an original version

**First of all, look at what the target already contains.** A streaming rip
often carries thirty subtitles, French included: then there is only one audio
track to add, and no subtitle resync to do. The Tracks screen (`T`) lists them
all.

1. Home: cursor on the movie, `T`.
2. `F9`, choose the file carrying the dub, then its tracks.
3. On the Sync screen, cursor on the **audio** track, `M`.
4. **Subtitles are resynced after the audio, never before**: its measurement is
   their reference. Depending on what it gave —

   | Measurement result | On each subtitle |
   |---|---|
   | `✓` or `⚠` (§ 4.1, § 4.2) | **nothing — carrying over is automatic** |
   | `✗ different cut — N segments` (§ 4.5) | `P` — and `P` on the audio too |
   | `✗ too few subtitle lines` (§ 4.3) | nothing, unless another donor → `C` |
   | `✗ image subtitle` (§ 4.4) | nothing, unless another donor → `C` |
   | `✗ no common alignment` (§ 4.5bis) | `R` — give an anchor point |

   A successful measurement **carries over by itself** to the subtitles from
   the same file: their Sync column turns to "copied from #N". This is
   intended — subtitles delivered with a dub are written on that dub's timing,
   so their right offset **is** its offset.

   Carrying over never touches a track you have already set, nor a track from
   another file. For those, `C` is there.
5. Fill in the **language** of each track if it is missing.
6. `V` or `K` to check.
7. `F3` to mux without re-encoding, or `F2` to re-encode the video too.

### 3.2 Re-encoding a whole folder tree with the profile

For a whole season, or a library sorted into subfolders.

1. Put the cursor **on a folder** — `R` does nothing on a file.
2. `R`, then confirm. Every video file in the folder **and its subfolders**,
   with no depth limit, is analyzed with the active profile — four at a time;
   the status bar counts them ("Analyzing… 12 / 40").
3. The dry run opens on the result. `Space` removes a row, `F6` and `F7`
   change the codec or bitrate **of that row only**.
4. `F2` starts.

Two things to know before starting:

- **Files already compressed enough are left out** of the list. The dry run
  only shows what will really be encoded — if a file is missing, it had nothing
  to gain.
- **No manual track selection.** Decisions come from the profile, including
  what happens to each language. Check them on a single file (`T`) before
  starting a batch.

A profile marked `⚠ del.` deletes each source after a successful encode. On a
whole folder tree, read this twice.

### 3.3 Making a 4K Dolby Vision that stalls at playback playable

Some players — webOS clients among them — refuse direct play of a Dolby Vision
profile 8 and fall back to transcoding, with audio dropouts. Removing DV
**improves** playback, contrary to what one might think.

With a profile set to `dolby_vision = hdr10` (`F5`, **Dolby Vision** section,
**Handling** field), a DV source the profile has no reason to re-encode comes
out as `.hdr10-iris.mkv` or `.hdr10-iris.mp4`, depending on what its tracks
allow:

- the RPU is removed, **no picture is recomputed**;
- any HDR10+ survives, which no re-encode allows;
- allow two to three minutes for a 15 GB movie, instead of several hours.

The **Decision** column shows `→ HDR10` on these files. It is the most
rewarding case in the application: a lot gained, almost nothing spent.

### 3.4 Slimming down a Dolby Vision without losing it

A profile set to `dolby_vision = dv` (`F5`, **Dolby Vision** section,
**Handling** field) keeps Dolby Vision. Up to v0.8.8.0 it also kept the
bitrate: the video was copied as it was, and a 60 Mb/s movie came out at
60 Mb/s. Now the application takes the DV metadata out before encoding and puts
it back afterwards.

The **Decision** column tells the two cases apart:

| What is shown | What happens |
|---|---|
| `→ HEVC → DV` | the video is re-encoded at the profile's bitrate, Dolby Vision is kept |
| `→ DV (copy)` | the video is copied — the profile's bitrate does not apply |

When you see `→ DV (copy)`, step 2 of guided mode gives the reason under the
video row. Three possible causes:

- **the profile asks for a downscale** (`keep_4k` unchecked on a 4K source).
  DV metadata describes the framing picture by picture: resizing makes it
  wrong. Check `keep_4k` so that re-encoding becomes possible.
- **the source is Dolby Vision profile 5 or 8.4.** Their base layer is not
  HDR10; there is nothing to attach the metadata to. Nothing to do — except set
  the profile to `hdr10` or `sdr` if size comes first.
- **dovi_tool or mkvmerge is missing.** Run the preflight again.

Before starting a batch, know that:

- **the output is always an `.mkv`**, even if the profile asks for MP4 — MP4
  cannot carry this metadata without rewriting;
- **allow twice the size of the encoded video in temporary disk space**, next
  to the source file. The files are deleted at the end, whether the encode
  succeeds or not;
- **encoding takes longer** than an ordinary encode: three passes over the
  stream add to the encode itself.

> The first file produced deserves a check on your TV: the chain is verified
> on short excerpts, not yet on a whole movie.

### 3.5 Keeping only some languages

A streaming rip commonly carries two audio tracks and **forty subtitles**. The
profile decides what goes through.

`F5`, then `E` on the profile:

| Field | Effect |
|---|---|
| **Languages** | Audio tracks kept, by ISO code — `fre, eng` |
| **Subtitle languages** | Same for subtitles. **Empty = all** |

The two sets of ISO codes are reconciled: writing `fre` also keeps tracks
labeled `fra`, and the same for `ger`/`deu`, `dut`/`nld`, `cze`/`ces`.

The first audio track is always kept, whatever its language: it is the
original track, and losing it would mean losing the movie.

For track-by-track control on a single file, `T` then `Space` — the profile
only decides the general case.

### 3.6 Resyncing a subtitle found on the internet

A downloaded `.srt` is almost never in sync with your file.

1. On the movie, `T` then `F9`, and choose the `.srt`.
2. On the Sync screen, `M` on the subtitle row.
3. Depending on what the measurement gives, see § 4 — and if it does not
   conclude at all, `R` gives an anchor point (§ 4.5bis).
4. `V` to check by eye, `K` for a check sample actually muxed.
5. `F3` muxes without re-encoding — a few minutes, picture untouched.

A subtitle is corrected **exactly**: there are only numbers to shift, nothing
to resample. That is what makes this case much safer than an audio resync.

### 3.7 Encoding a disc image (ISO)

1. In Windows, right-click the `.iso` → **Mount**: it appears as a drive.
2. Open that drive from the volume list (`Ctrl+Home`).
   - **Blu-ray**: the drive itself lists the disc's **titles**, one row per
     playlist (`01001.mpls`…), with their length. The longest is the movie;
     titles shorter than 2 minutes (menus, loops) are hidden — the limit is in
     Options (`F5` then `U`, "Blu-ray titles"; `0` lists them all). A title
     made of several clips is joined by mkvmerge before encoding, in the
     output folder: allow its size in free space. The output is named after
     the disc (the folder holding `BDMV`, or the drive label), with the
     playlist number for titles other than the movie, and keeps the disc's
     chapters. An encrypted disc (AACS) is refused: decrypt it first.
     `BDMV\STREAM` still shows the raw clips.
   - **DVD**: the drive itself lists the disc's **titles** (`TITLE_01.dvd`…),
     read from its IFO files, with the same length limit; the longest is the
     movie and comes pre-checked. Reading them needs the **DVD tool**, offered
     at startup (see README, chapter 4). A title is first extracted
     losslessly into the output folder (4 to 8 GB, about a minute), with its
     languages and chapters, then encoded like any file; the extraction is
     deleted afterwards. Same naming as a Blu-ray. An encrypted DVD (CSS) is
     refused. External tracks are added to the output, not to the title — the
     same goes for a Blu-ray title made of several clips.
     `VIDEO_TS` still shows the raw `.VOB` files.
3. Check the file, `F2`. The drive is read-only: IRIS asks for an **output
   folder**. `↵` on the first row accepts the one offered (set in Options,
   `F5` then `U`; your Videos folder by default); the other rows browse to
   another one.
4. Once the batch is done, unmount the drive (right-click → **Eject**).

A disc folder copied to a hard drive (`Movie (2020)\BDMV\…` or
`Movie (2020)\VIDEO_TS\…`) works the same way: open the folder that holds
`BDMV` or `VIDEO_TS`. The output is written next to
it, never inside. The recursive mode keeps only the movie of each disc.

Track languages of a `.m2ts` are read from the disc by mkvmerge (an optional
tool: without it, they stay unknown — and a track whose language is unknown is
kept). A TrueHD track and its AC-3 core give a single track in the output.

A DVD, like a 1080i TV recording, is often **interlaced**: when the source says
so, the encode deinterlaces it (bwdif), at the same frame rate. The decision
(guided mode, `F1` preview) shows it: "deinterlaced". A source that calls
itself progressive is left alone — some TV recordings are wrong about it on
part of their frames (ads, trailers), and those parts keep their comb lines.

---

## 4. Cases met in practice

### 4.1 "✓ +2450 ms (confidence excellent)"

The nominal case. The offset is set. A `V` check remains a good habit but is not
essential.

Confidence reads in words — **none**, **low**, **medium**, **excellent** — not
in numbers: the acceptance threshold varies with the number of subtitle lines
measured, so the same figure does not mean the same thing from one measurement
to another. "Medium" or "excellent" means the measurement was accepted; "low"
or "none", that it was refused.

A successful measurement on the audio carries over to the subtitles of the same
file (§ 2.4). A subtitle from another file keeps its own offset: cursor on it,
`C`, then choose the audio track (§ 3.1, step 4).

### 4.2 "⚠ … — to check"

The correlation is medium and the thirds of the movie did not settle it. The
value is applied but **check before muxing**: `V` by ear, `K` for a check sample
actually muxed.

### 4.2bis "⚠ … durations … apart — check that it is the same cut"

The measurement found a consistent offset, but the two files differ in length
by more than **6 %**. That is a lot: two copies of the same movie only differ
by their credits.

The offset found may be right — a donor missing its end credits stays alignable
over its whole length. It may also mean you took **the wrong file**, or another
version of the movie. `K` settles it in a few minutes: a check sample muxed at
the end of the movie immediately shows whether the alignment holds to the end.

> This warning existed for a long time but **was shown nowhere** before
> v0.8.5.1: it was filed with the failure messages, which the application only
> reads on a refused measurement. A donor from another cut therefore went
> through silently.

### 4.3 "✗ too few subtitle lines"

The subtitle is too short to be measured — typically a **forced** track, which
only holds a few lines. It is not an error. Use `C` to copy the offset of the
audio track.

### 4.4 "✗ image subtitle (PGS, VobSub)"

These subtitles are pictures, with no text to correlate. No measurement is
possible; set the offset by hand or with `C`.

### 4.5 "✗ different cut — N segments"

The two files carry the same content in two different cuts — typically a
broadcast rip, whose commercial breaks shift everything that follows, against
a streaming rip.

**Procedure:**

1. `G` to see the segments. Regular steps (for example five times +2,000 ms)
   confirm the diagnosis; erratic values rather mean the files have nothing to
   do with each other.
2. Cursor on the **audio** track, `P`. The resync takes a few minutes —
   decoding then re-encoding, with a progress bar.
3. Cursor on each **subtitle**, `P`. Instant.
4. `V` or `K` to check, then `F2` or `F3`.

The segments stay in memory as long as no new measurement is started: a single
detection, on the audio, serves all three tracks. It is the safest way — the
signal of an audio track is dense, that of a subtitle is sparse. The
application can still find segments on a subtitle alone, but succeeds less
often; if it does not, `R` (§ 4.5bis).

If the report says "no silence found, insertion on the estimated boundary" on a
boundary, the insertion was placed at the estimated position. Nothing is lost,
but that area deserves a listen.

If the report says "insertion point before the previous one, moved by N s",
two boundaries were too close for each one's silence to hold: the second was
moved just after the first. The inserted duration is intact, only its place
moves — listen to that junction.

> **On an audio track produced by `P` before v0.8.4.5**: two insertion points
> could cross, and the passage between them then ended up **twice** in the
> track. The file passed every check. If you hear a repeated line on an old
> added track, that is why: run `P` again with this version.

> **The resync sometimes froze** before v0.8.4.4 — progress bar stuck, no
> message, no way out but quitting the application. It was ffmpeg hanging on a
> full error pipe. Fixed.

### 4.5bis Nothing works — the anchor point (`R`)

Some subtitles cannot be measured, whatever the setting. The typical case: a
community `.srt` whose **text adaptation differs from the dub's**. Lines are
split and condensed differently, so their rhythm does not trace that of the
speech — measured on a real case, the correlation tops out at less than half
the threshold *even when perfectly aligned*.

The correlation can still be used if it is told **where** to look.

1. `R` **suggests a subtitle line** and the moment it is written for. `↓` and
   `↑` suggest another one, if this one cannot be found.
2. Listen to the movie at that point, and give the moment you actually hear it.
   Accepted formats: `13:22`, `1:13:22`, `13:22.5`, `802`.
3. The search centers on the gap between the two. It then finds the offset,
   and the segments if there are several cuts.

If the analysis finds an offset **very different** from the one you gave, it
says so and applies nothing: it is the sign that one of the two moments is
wrong. Check them again rather than insisting.

### 4.6 "needs a stretch factor"

A sped-up PAL source (25 vs 23.976 frames/s) drifts instead of being simply
offset. mkvmerge can stretch it, ffmpeg cannot: the added track goes
automatically through a pre-mux just before encoding. Nothing to do, unless
mkvmerge is missing — then run the preflight again to install it.

A stretch cannot be previewed in mpv (`audio-delay` only applies a constant
offset): use `K`, which produces two windows, start and end, since the drift
builds up.

> **Check the files produced by this path before v0.8.4.3.** The added track
> was muxed into the intermediate file, then **lost** during re-encoding: the
> application reported success and returned a file without the dub you had just
> resynced. Nothing flagged it. If a stretched file seems to be missing a track,
> it is — add it again.

### 4.7 The produced file does not play on the TV

Fixed in v0.8.1.0: a negative offset moved the whole video away from zero,
which hardware decoders sometimes refuse while mpv and VLC silently normalize
it. If the problem persists on an older file, re-encode it with this version.

### 4.8 Deleting fails on Windows

`Ctrl+D` on a file still open in mpv fails: Windows keeps it locked. Close the
player and try again.

### 4.9 "→ HDR10" on a file that has nothing to re-encode

The **`→ HDR10`** decision, in green, is not an encode: it is a Dolby Vision
removal. It appears when the file is DV **profile 8.1** (or 7), the active
profile asks for `dolby_vision = "hdr10"`, and there is otherwise nothing to
re-encode — bitrate under the threshold, resolution within bounds.

In 8.1, the base layer already *is* HDR10: removing the Dolby Vision metadata
is enough. The picture comes out **bit-identical**, any HDR10+ is kept, and a
5.7 GB 4K movie goes through in a little over two minutes — instead of several
hours for a re-encode, which would damage the picture and lose the HDR10+. The
output is a `<name>.hdr10-iris.mkv` or `.mp4` carrying the source tracks that
were kept; a profile 7 always comes out as MKV.

> **MP4 files produced before v0.8.8.15: redo them.** Their video had lost its
> timestamps. On a TV, playback started with sound only, no picture, then
> crashed. Run the removal again from the source; `.mkv` files are not
> affected.

To re-encode anyway, `F6` on the row forces the codec: the decision starts again
from the source bitrate.

Nothing is shown if `dovi_tool` or mkvmerge is missing — the file stays at
`← SKIP` rather than promising an impossible operation.

### 4.10 The "Bitrate" column does not say the same as my file explorer

The column shows the **video bitrate alone**, while a file explorer or
MediaInfo shows the container bitrate — audio and subtitles included. On a
movie carrying a TrueHD track, the gap exceeds 40 %.

This is intended: the threshold you set in a profile is a video bitrate, and a
video bitrate is what the encoder receives. Comparing a total with a video
threshold would send to re-encoding files whose picture sits well below it.

To get the total bitrate back, add up the tracks: the Tracks screen (`T`) gives
the details of each one.

### 4.11 A TrueHD or DTS track comes out too degraded

By default, a transcoded track follows the profile's fixed rate: 448 kbps in
AC3 for 5.1. That is right for an already compressed source, and a needless
loss on a 3.5 Mbps TrueHD.

The **Handling** field of the **Lossless audio** section of the profile form
(`F5`, then edit) changes the rule for these tracks:

- **`→ fixed 5.1 / 7.1 bitrate below`** — the fixed rate applies, the original
  behavior.
- **`→ AC3 at the source bitrate`** — capped at **640 kbps**: that is the AC3
  maximum, the encoder silently brings everything else down.
- **`→ E-AC3 at the source bitrate`** — capped at **6,144 kbps**. A TrueHD at
  3,501 kbps comes out as E-AC3 at 3,501 kbps.
- **`copy as they are`** — the track is kept lossless (`preserve_hd_audio`),
  which forces MKV.

E-AC3 is the right choice for a recent TV: it is decoded natively and carried
over eARC to a soundbar. AC3 remains the universal fallback.

A limit to know: the AC3 and E-AC3 encoders do not go beyond 5.1, so a 7.1
source is folded down — the decision shows it ("→ eac3 5.1").

The track title is fixed along the way: "ENG VO : TrueHD 5.1" becomes
"ENG VO : E-AC3 5.1", and the Atmos mention disappears since it does not
survive the conversion. A title that does not mention the format ("English")
is left as it is.

### 4.12 "libx265 unavailable here" on a 4K profile

The HDR10 **quality** mode (`hdr10_quality = "quality"`, field **HDR10 mode**
of the profile form) encodes on the **processor**, with libx265: that is what
lets it inject the static HDR10 metadata some TVs expect, which no graphics
card encoder exposes.

Before v0.8.4.3, the application only checked the card's three encoders at
startup, and treated as unavailable anything it had not tried. On a machine
with a graphics card — so on almost all of them — the profile was refused
before even starting, in the name of a test that had not taken place. It works
now.

If the message persists, your ffmpeg really is built without libx265:
`ffmpeg -encoders | findstr x265` confirms it. Then switch the profile to the
**compat** mode, which goes through the card.

### 4.13 "NVENC refused: this ffmpeg needs NVIDIA driver …"

At startup, a "Graphics card" alert announces that HEVC, H264 and AV1 through
the card are all unavailable. Each ffmpeg is compiled for a version of the
NVENC interface, which requires a minimum driver: an ffmpeg newer than the
driver refuses the whole card. The ffmpeg version number is not enough to
predict it (8.1.2 from gyan.dev requires driver 610, 8.1.3 from BtbN is happy
with 597).

Two ways out: update the NVIDIA driver to the version shown, or install an
older ffmpeg. The application takes the ffmpeg on the `PATH` before the one in
`bin/`. To test an ffmpeg:

```
ffmpeg -v error -f lavfi -i testsrc2=d=1 -c:v hevc_nvenc -f null -
```

No output: it works.

### 4.14 An optional tool is missing

`dovi_tool`, `mkvmerge` and `mpv` are optional: when one is missing, a feature
is turned off without blocking startup. The preflight offers to install them at
each start; answer `y`, or put the binaries in `bin/`.

---

## 5. Conventions shared by all screens

- `⌫` or `Esc` go back, everywhere.
- `Ctrl+Home` **goes back to the list of volumes** — the root — from any
  screen: dry run, encoding, mux, guided mode, profiles, Tracks, Sync, and the
  Home screen itself. That is what lets you work through several files without
  climbing back up one screen at a time. The selection is cleared. From
  **Tracks** and **Sync**, a confirmation is asked: those two screens hold work
  that going back does not keep — a selection, added tracks, a measurement.
  From a running **encode** as well: confirming stops the whole batch and
  deletes the partial output. `Home` alone keeps its role, going to the first
  row of the table.
- `F10` quits, always last in the footer. The confirmation says what is running
  — encode, mux, join, measurement — and what quitting does to it, or "No task
  in progress." An encode, a mux or a join is stopped and its partial output
  deleted.
- `Home` `End` `PgUp` `PgDn` move through tables.
- The footer sorts the shortcuts by role, top to bottom: **the screen's own**,
  then **global** ones (navigation, back), then the **function keys** `F1` to
  `F10`, always on the last line. Each band wraps onto as many lines as the
  width requires; no shortcut is hidden, even on a narrow screen.
- Column widths are remembered in `config.toml`, **except on the Home screen**:
  it starts from the default values at each start, to give the same layout from
  one session to the next. Resizing still works during the session.
- Scan errors are logged to `~/.iris_encode/iris_encode.log`.
- **Startup queries the network once a day** to compare your tools with the
  latest published versions. To turn it off, set `check_on_startup = false`
  under `[updates]` in `config.toml` — not under `[ffmpeg]`, which is the wrong
  section. The setting only has an effect since **v0.8.5.2**: until then it was
  read from the wrong place, so it never changed anything. Offline, startup
  carries on without waiting.
- **The key guide** (`H`) lists every key of every screen, built from the keys
  the application actually declares, in the interface language.
