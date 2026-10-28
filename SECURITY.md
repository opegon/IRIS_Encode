# Security policy

## Reporting a vulnerability

**Please do not report security problems in a public issue.**

Use GitHub's private reporting instead:
**[Report a vulnerability](https://github.com/opegon/IRIS_Encode/security/advisories/new)**
(the *Security* tab of the repository → *Report a vulnerability*). Only the
maintainer sees the report.

English or French, both are fine. Please include:

- the IRIS ENCODE version;
- what an attacker could do, and under which conditions;
- the steps or the file needed to reproduce it — a crafted file can be
  attached to the advisory, not to a public issue.

### What to expect

IRIS ENCODE is maintained by one person, on their own time. As a goal, not a
guarantee:

- an acknowledgement **within 7 days**;
- a first assessment **within 30 days**;
- a fix in a new release as soon as it is ready, then a published advisory
  that credits you, unless you prefer to stay anonymous.

## Supported versions

Only the **latest release** receives security fixes. The built-in updater
offers it at startup (see [`README.md`](README.md) § 5.2).

## Scope

IRIS ENCODE runs on the user's own machine and processes files the user
chooses. The areas where a flaw matters most:

| Area | What it does | Examples of what to report |
|---|---|---|
| **Application updater** (`updater.py`) | Downloads the latest GitHub release, checks its SHA256 against the digest GitHub publishes, replaces the application files | A way to make it install something else, write outside the application folder, or touch `config.toml` / `profiles.toml` |
| **Tool installer** (`core/updates.py`, `core/preflight.py`) | Downloads ffmpeg, dovi_tool, mkvmerge, mpv into `bin/`, and refuses any download without a published fingerprint | A bypass of the fingerprint check, an archive that writes outside `bin/` |
| **Python bootstrap** (`bootstrap.ps1`) | Downloads a pinned `uv` release and checks its SHA256 against a fingerprint written in the script; `uv` then installs CPython and the Python dependencies | A bypass of the fingerprint check, a way to make it run another `uv` |
| **Reading untrusted media** | Parses DVD IFO and Blu-ray MPLS files in Python, and passes file names to ffmpeg, dovi_tool and mkvmerge | A crafted disc folder or file name that leads to code execution, a command injection, or a write outside the output folder |
| **Online lookups** | OMDb, AlloCiné, IMDb suggestions, OpenSubtitles | Credentials sent elsewhere than their service, or over plain HTTP |

### Out of scope

- **Vulnerabilities in ffmpeg, dovi_tool, mkvmerge, mpv or uv themselves**:
  please report them to those projects. Do tell us if IRIS ENCODE ships a
  known-vulnerable version, or uses one in a dangerous way.
- **Disc protection**: IRIS ENCODE detects encrypted DVDs (CSS) and Blu-rays
  (AACS) and refuses them. Requests to bypass this are not security reports
  and will not be accepted.
- Problems that require an attacker to already control the user's account or
  the application folder.

## Known limitations

Stated here so that nobody has to discover them:

- **Online credentials are stored in plain text** in `config.toml`, in the
  application folder: the OMDb key, and the OpenSubtitles key, user name and
  password. Anyone who can read that folder can read them. Use an
  OpenSubtitles password you do not use anywhere else.
- **Application updates trust GitHub.** The SHA256 check guarantees that the
  archive is the one published on the release, not who published it: the
  release itself is the trust anchor. A folder cloned with git is never
  updated this way.
- **The log** (`%USERPROFILE%\.iris_encode\iris_encode.log`) contains file
  paths. It is not sent anywhere, but check it before attaching it to a public
  issue.
