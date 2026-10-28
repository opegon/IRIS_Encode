# Contributing to IRIS ENCODE

Thank you for taking the time. IRIS ENCODE is a small project with a single
maintainer, so the most useful contributions are often the simplest: a clear
bug report, a playback test on a screen we do not own, a translation fix.

**Language**: English for issues, discussions and pull requests — **French is
welcome too** (*les échanges en français sont les bienvenus*). The code
comments, the changelog and the wiki are mostly in French; you do not need to
read French to contribute.

---

## Ways to help

| What | Where | Skills needed |
|---|---|---|
| Report a bug | [New issue → Bug report](https://github.com/opegon/IRIS_Encode/issues/new/choose) | None — just the log and a few details |
| Report how an IRIS output plays on your setup | [New issue → Playback report](https://github.com/opegon/IRIS_Encode/issues/new/choose) | A TV, a client, a Jellyfin server |
| Suggest an improvement | [New issue → Feature request](https://github.com/opegon/IRIS_Encode/issues/new/choose) | None |
| Ask a question, share a profile | [Discussions](https://github.com/opegon/IRIS_Encode/discussions) | None |
| Improve the English or French documentation | Pull request | Writing |
| Fix a bug, add a feature | Pull request | Python |
| Help with the **Linux** (2027) and **macOS** ports | Issues labelled `platform` | Python, Linux or macOS |
| Report a vulnerability | **Privately** — see [`SECURITY.md`](SECURITY.md) | — |

### Playback reports are especially valuable

IRIS decides from what each link of the playback chain accepts — TV, client,
server, sound system. The maintainer can only test the devices at home.
A report saying *"this output plays directly on my Samsung / Android TV /
Apple TV / Plex client"*, or *"it still transcodes"*, directly improves the
rules and the shipped profiles.

### Linux and macOS ports

The code already keeps platform-specific parts in `core/platform.py`, and some
of the groundwork exists (Linux download sources in
`data/ffmpeg_releases.toml`, VideoToolbox on macOS). The Linux port is planned
for 2027, macOS after. Before writing code for it, please open or join the
tracking issue so the work is not done twice.

---

## Reporting a bug

A good report lets the maintainer reproduce the problem without a back-and-forth.
The bug form asks for:

- the **IRIS ENCODE version** (top of the screen, or `version.py`);
- **Windows version** and **terminal** (Windows Terminal or the classic
  console);
- the **encoding hardware**: NVIDIA, Intel Quick Sync, or processor only;
- the **profile** used;
- **what you did, what you expected, what happened**;
- the **log**: `%USERPROFILE%\.iris_encode\iris_encode.log`;
- for a file-specific problem, the **source analysis**:
  `ffprobe -hide_banner -show_streams -show_format "your file"` (or a
  MediaInfo text export).

Check the log before attaching it: it contains file paths, which may reveal
folder or movie names you would rather keep private.

---

## Development setup

You need **Python 3.11 or later** and **git**. On Windows, `launch.bat` sets
up everything for users; as a developer you will usually prefer your own
environment:

```bash
git clone https://github.com/opegon/IRIS_Encode.git
cd IRIS_Encode
python -m venv .venv
.venv\Scripts\activate          # Windows; source .venv/bin/activate elsewhere
pip install -r requirements.txt pytest
python main.py
```

ffmpeg and the optional tools are offered for download at first start, into
`bin/` (see [`README.md`](README.md), chapters 3 and 4).

A clone is **never auto-updated** (the updater skips any folder with a
`.git/`): use `git pull`.

### Running the tests

```bash
python -m pytest tests/
```

Two scripts are not part of the pytest run and are started by hand:

```bash
python tests/smoke_tui.py               # headless navigation smoke test, English then French
python tests/shots_tui.py --langue en   # exports every screen as SVG into _shots/en/
```

`shots_tui.py` expects real sample media in `resources_files/`, which is not
in the repository: use your own files.

The test suite also checks the **documentation** — for instance that the
version shown at the top of `README.md`, `README.fr.md`, `GUIDE.md` and
`GUIDE.fr.md` matches `version.py`, and that every key the guide announces
really exists in the interface. If a test fails after a documentation change,
that is usually why.

---

## Code conventions

These rules come from the project's own history; the tests enforce most of
them.

### What the tool must never do

- **Never overwrite a file**: an output that would collide gets `(2)`.
- **Never write into a source folder that is read-only** (a mounted ISO, for
  instance): the output and its intermediate files go to a chosen output
  folder.
- **Never sacrifice a track silently**: if something cannot be kept, it is
  shown on screen.
- **Never install anything outside the application folder**, never require
  administrator rights.
- **Never add a binary download without checking its SHA256 fingerprint.**
  (One known exception remains: `uv`, fetched by `bootstrap.ps1` — see
  [`SECURITY.md`](SECURITY.md).)
- **Never decrypt a disc.** Protected DVDs and Blu-rays are detected and
  refused; a pull request adding decryption will not be accepted.

### Interface text and translations

English is the **source language**; French is a translation
(`locales/fr/LC_MESSAGES/iris_encode.po`). The full rules are at the top of
`core/i18n.py`; in short:

- every displayed text goes through `_()` — `_("{count} files").format(count=n)`,
  **never** `_(f"…")`;
- one whole sentence per message; plurals through `ngettext`;
- text defined at import time (tables, `BINDINGS`) is marked `N_()`;
- a `# TRANSLATORS: …` comment just above the call reaches the translator;
- **never translate what is written to disk** or passed to another program
  (file suffixes, track titles, language codes, settings keys), nor the logs.

After changing any displayed text, regenerate the catalogues — a test checks
they are up to date:

```bash
python outils/i18n.py tout
```

Then complete the French entry in the `.po` file (or leave it for the
maintainer, and say so in the pull request).

### Documentation

- `README`, `GUIDE` and their French twins **move together**: a change in one
  language goes in the other, or the pull request says it is missing.
- Do not change the version number (`version.py` and the document headers):
  the maintainer does it at release time.

---

## Pull requests

1. **Open an issue first** for anything larger than a small fix, so we agree on
   the approach before you spend time on it.
2. Keep each pull request **focused** on one change.
3. **Add or update tests** for any change in behaviour. Decision rules
   (`core/decision.py`, `core/encoder.py`) always need one.
4. Run `python -m pytest tests/` before pushing.
5. In the description, say **what you tested and on what**: Windows version,
   GPU, sample files (type, not name), and, for playback, the screens.
6. Commit messages can be in English or French; just make them describe the
   change.

The `CHANGELOG.md` entry is written by the maintainer at release time.

---

## License

IRIS ENCODE is distributed under the **GNU General Public License, version 3
or any later version** (GPL-3.0-or-later). By submitting a contribution, you
agree that it is distributed under the same license. There is no contributor
licence agreement to sign.

## Behaviour

Be kind and assume good faith. Questions are welcome at every level; nobody is
expected to know ffmpeg or Dolby Vision by heart. Harassment or personal
attacks are not tolerated, and the maintainer may remove such content or block
its author.
