---
name: hindi-video-transcript
description: Use when the user gives a YouTube link or playlist to a Hindi or Hinglish video and wants its transcript, wants to "understand" or summarize a Hindi video, or asks for a Roman Hindi / Hinglish version of a Hindi video's captions. Also use for Hindi course, lecture, or tutorial videos where the spoken content matters more than the visuals.
---

# Hindi Video Transcript

Turn a Hindi/Hinglish YouTube video or playlist into two files per video: an
exact Devanagari transcript and a Roman Hindi one.

## Do not use when

- The value is on screen — silent demos, visual walkthroughs
- There is no caption track
- The video is not Hindi — fetch its track directly, skip transliteration

## Layout

One base folder holds one shared `tools/` and one folder per subject.
Glossaries are per subject and must never merge, so each keeps its own.

```
<base>/
├── tools/                    copied once, every project uses it
│     translit.py
│     convert.py
├── Trading Course/
│   ├── 01 - Charting.txt     what the user reads
│   ├── glossary.py           this subject's own
│   ├── _glossary-todo.txt    delete when clean
│   └── raw/                  never opened by hand
│         01 - Charting (hi-orig).txt
│         01 - Charting.json3
└── Cooking Course/           new subject = new folder, nothing else to set up
```

## Step 1 — Ask first

One `AskUserQuestion` call, before downloading anything:

| Ask | Note |
|---|---|
| YouTube link | Detect single video or playlist |
| Base folder | Full path. Never guess, never default |
| Timestamps in the Roman file? | Default **no** |
| How many videos | Playlist only: one / all / batches of N |

Then list `<base>` and ask once more: an existing subject folder, or a new one
and its name. Name it after the content, never after this skill.

## Step 2 — Tooling

Note the OS first. Every command below branches on it.

```bash
yt-dlp --version
python3 -m yt_dlp --version    # Windows: py -3 -m yt_dlp --version
```

Use whichever answers for every later command.

**Found — update it.** A stale yt-dlp stops returning caption tracks without
saying so.

| Found via | Update |
|---|---|
| `python3 -m yt_dlp` | `python3 -m pip install -U "yt-dlp[default]"` |
| the `yt-dlp` command | Take this OS's command from the wiki's Update section |

**Not found — install it.** Do not write the steps from memory. Open the
[yt-dlp Installation wiki](https://github.com/yt-dlp/yt-dlp/wiki/Installation),
read only this OS's section, follow it. Re-run the check before moving on.

## Step 3 — Get the scripts

Check whether this base is already set up:

```bash
ls <base>/tools/translit.py
```

**Already there** — skip the copy. Only run the two tests below.

**Not there** — copy both. Do not write them.

```bash
mkdir -p <base>/tools
SRC=https://raw.githubusercontent.com/AlmaasTalha/youtube-hindi-to-roman-transcript-skill/main
curl -o <base>/tools/translit.py $SRC/translit.py
curl -o <base>/tools/convert.py  $SRC/convert.py
```

Either way, test before converting anything:

```bash
python <base>/tools/translit.py --test
python <base>/tools/convert.py --test
```

Both must print `N/N` with no `FAIL` lines.

**On failure**, check the copy landed:

```bash
head -1 <base>/tools/translit.py    # must read:  # -*- coding: utf-8 -*-
```

Wrong line = the download failed. Re-copy **once**, re-run.

Still failing, or the file looks intact: **stop**. Do not retry again and do not
convert anything. Show the user the `FAIL` lines, say the transcript cannot be
trusted, and give them
<https://github.com/AlmaasTalha/youtube-hindi-to-roman-transcript-skill/issues>.
Do not open the issue yourself.

`glossary.py` is created empty on first run and grows in Step 5.

## Step 4 — Run

```bash
python <base>/tools/convert.py <url> "<base>/<subject folder>" [options]
```

| Flag | Effect |
|---|---|
| `--name "01 - Episode"` | Filename stem. Default: video title |
| `--timestamps` | Keep `[HH:MM:SS]` in the Roman file too |
| `--items all` \| `3` \| `1-5` \| `2,5` | Playlist: which videos |
| `--reroman` | Rebuild every Roman file from the Devanagari on disk. No download |
| `--apply FILE` | Add `roman=english` lines to the glossary |

Playlist: run it bare first to print the list, show the user, then ask which
items. Playlist position often differs from the course's episode numbers — if it
does, run the videos individually with `--name`.

After growing the glossary use `--reroman`, never the downloader again.

Per video it writes:

| File | Where | Contents |
|---|---|---|
| `<stem>.txt` | subject folder | Roman Hindi — the file the user reads |
| `<stem> (hi-orig).txt` | `raw/` | Devanagari, `[HH:MM:SS]` per line |
| `<stem>.json3` | `raw/` | Raw download, backup |
| `_glossary-todo.txt` | subject folder | Unknown words in that folder, ranked |

It prints the track used, then lines, words, glossary hit % and
`devanagari left`. `devanagari left 0` means the conversion is clean.

### Human-written English on the video

| It printed | Meaning | Do |
|---|---|---|
| `STOP —` | English is the only human track. Nothing was converted | Ask, then re-run |
| `NOTE —` | A Hindi track won, but English also exists | Say so before they read the output |

Either way give both sides:

- **Human-written English:** punctuated, spell-checked, roughly a third fewer
  tokens — but a translation, so the speaker's own words and Hindi terms are gone
- **Auto Hindi romanised:** exactly what was said, Hindi terms intact — but no
  punctuation, all lowercase, ASR errors pass through, and it costs more

Human subtitles in any third language are ignored.

## Step 5 — Grow the glossary

Read `_glossary-todo.txt` after the **whole batch**, not per video — it is
rewritten every run and covers the whole folder.

Collect only the words that came out **wrong**, one per line:

```
evrivan=everyone
kost=course
```

```bash
python <base>/tools/convert.py --apply words.txt "<base>/<subject folder>"
python <base>/tools/convert.py --reroman "<base>/<subject folder>"
```

Repeat until it reads clean, then delete the todo file.

Rules:

- Work down to **count >= 3**. English runs the full length of the list; it thins
  in frequency, not in kind. Do not stop where it seems to thin out
- Do not filter the list by a "looks English" rule
- Skip any word that is also common Hindi — `बार` → "bar" breaks `बार-बार`.
  Leave it out and let transliteration handle it
- Before calling a word an ASR error, grep the `(hi-orig)` file. A correctly
  spelled source word that read wrong is a glossary miss
- Never put the glossary in `CLAUDE.md`. Only Python reads it

## Tell the user

| Track used | Expect |
|---|---|
| Human-written | Punctuation and correct spelling, near publication quality |
| Auto-generated | Meaning clear, but no punctuation, all lowercase, ASR errors pass through |

- Hand-correcting auto-caption output costs more than everything else combined.
  Offer it; do not assume it
- Numbers are the weak spot — auto-captions mangle prices, quantities and
  tickers. If a video's value is in its arithmetic, say those figures must be
  checked against the video

## Reading the output

Read the generated `.txt`, never the `.json3`. Read ~150-line chunks with
`sed -n` — a full transcript gets truncated.
