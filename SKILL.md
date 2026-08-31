---
name: hindi-video-transcript
description: Use when the user gives a YouTube link or playlist to a Hindi or Hinglish video and wants its transcript, wants to "understand" or summarize a Hindi video, or asks for a Roman Hindi / Hinglish version of a Hindi video's captions. Also use for Hindi course, lecture, or tutorial videos where the spoken content matters more than the visuals.
---

# Hindi Video Transcript

## Overview

Turn a Hindi/Hinglish YouTube video (or a whole playlist) into two text files:
an exact line-by-line transcript in the original Devanagari, and a Roman Hindi
version.

**Core principle:** captions are ~5-8x cheaper in tokens than video frames.
Take the best caption track available — human-made subtitles over
auto-captions, original language over auto-translated.

**This skill ships no code and no glossary.** It is the procedure. The scripts
and the glossary are built **inside the user's project**, because a glossary is
domain vocabulary: a stock-trading course and a cooking course need different
ones, and one shared file would fit neither. A new machine needs only this file.

## When to Use

- User pastes a YouTube link or playlist to a Hindi/Hinglish video and wants it read, summarized, or understood
- User wants a course/lecture transcript they can search or keep
- User asks for Hinglish/Roman Hindi text from a Hindi video

**When NOT to use:**
- The value is in what's *on screen* (silent demos, visual walkthroughs) — captions won't capture it
- Video has no captions at all — skip it; audio + Whisper is a different job
- Non-Hindi videos — fetch the caption track directly, no transliteration needed

## Step 1 — Ask the user first

Ask all of these in ONE AskUserQuestion call, before downloading anything:

| Ask | Why |
|---|---|
| **YouTube link** | Single video or playlist — detect which |
| **Save location** | Full folder path. Never guess this. |
| **Timestamps in the Roman file?** | Default **no**. This file often gets fed back to an agent to read in full; timestamps inflate it. Say yes only if they want to jump back into the video. |
| **How many videos** (playlist only) | One / all / batches of N |

## Step 2 — Check the tooling

`yt-dlp` must be reachable **from the interpreter you launch with**, and that is
the usual first failure: on Windows a bare `python` is often a venv that lacks
it while another Python on the same box has it. Check before assuming:

```bash
py -3 -m yt_dlp --version
```

If that prints a version, run everything with `py -3`. If nothing has it,
`pip install yt-dlp`.

## Step 3 — Build the project's scripts

Create these in a `tools/` folder beside the transcripts, once per project.
Reuse them for every later video in that project.

### `translit.py` — Devanagari to Roman

Split each word into `[consonant, vowel, nasal, has_inherent_schwa]` units,
handling viraam, dependent vowels, nukta forms, and the nasal marks
(`ं ँ ः`). Then apply **schwa deletion** — without it `मतलब` comes out
"matalaba" instead of "matlab":

1. **Word-final:** drop the inherent `a` on the last consonant unit (unless it carries a nasal).
2. **Medial, right to left:** in `V C[a] C V`, drop the `a` — only when both neighbouring units carry vowels and this unit has no nasal.

Then normalise to conventional Roman Hindi spellings, in this order:

| Rule | Effect |
|---|---|
| `ie$` → `iye` | deejie → dijiye |
| `ee` → `i` | bhee → bhi, kee → ki |
| `^oo` → `u` | oopar → upar (leaves hoon, doon alone) |
| `aa$` → `a` | rahaa → raha (leaves aap, kaam, saath alone) |

### `glossary.py` — the project's word list

One dict, `G`, mapping Devanagari-spelled English to real English
(`'रेंज':'range'`). Starts empty and grows through Step 5. Append-only:
later `G.update({...})` blocks override earlier ones, so a correction is
just another line at the bottom.

### `convert.py` — the driver

```bash
python convert.py <url> <out-dir> [options]
```

| Flag | Effect |
|---|---|
| `--name "01 - Episode"` | filename stem (default: video title) |
| `--timestamps` | keep `[HH:MM:SS]` in the Roman file too |
| `--items all` \| `3` \| `1-5` | playlist: which videos. Omit to just **list** the playlist and stop. |
| `--reroman` | rebuild every Roman file from the Devanagari on disk. No download. |
| `--apply FILE` | add `roman=english` lines to the glossary (Step 5) |

What it must do:

- **Pick the track:** manual subtitles beat auto-captions; within each, a `*-orig` track beats an auto-translated one. Print which one it used.
- **Download `json3`**, not VTT — json3 gives one clean event per line. VTT auto-captions roll each line twice with word-level `<c>` tags while manual VTT has none, and one parser cannot cover both.
- **Romanise:** glossary first (exact whole-word match), then `translit.roman()` on whatever is left. Anything matched by the glossary is genuine English; anything left is genuine Hindi.
- **Report per video:** line count, word count, glossary hit %, and how much Devanagari is left in the Roman file. `devanagari left 0` means the conversion is clean.

Per video it writes:

| File | What |
|---|---|
| `... - transcript (hi-orig).txt` | Exact line-by-line Devanagari, `[HH:MM:SS]` per line |
| `... - transcript (roman).txt` | Roman Hindi |
| `... - raw captions.json3` | Untouched download, backup |
| `_glossary-todo.txt` | Every unknown word in the folder, ranked (Step 5) |

Two things about `--reroman` and `--apply` that are easy to get wrong:

- `--reroman` reads the `(hi-orig)` files from the out-dir **or its `backup/`
  subfolder**, and writes the Roman files to the out-dir. The glossary is shared
  across the project, so every time it grows the **whole** course should be
  rebuilt — and going back through the downloader to do that re-fetches captions
  that never changed.
- `--apply` resolves each roman **back** to every Devanagari spelling that
  produced it. That is the point: the ASR writes one word several ways (one
  course spelled "rally" three ways), and you never type Devanagari, so you
  cannot mistype it.

## Step 4 — Run it

For a playlist, run it bare first to show the user the list, then ask which
items. Note the naming: playlist mode numbers files by **playlist position**,
which is often off-by-one from the episode numbers (an intro video at slot 1).
If they differ, run the videos individually with `--name`.

## Step 5 — Grow the glossary

The glossary starts empty, so the first video of a new project has many misses.
`_glossary-todo.txt` lists **every** unknown word across **every** transcript in
the folder, most frequent first. Do not filter it by a "looks English" rule — one
such filter silently hid `renj` (range) and `kansidar` (consider, 487 times).

**The list is long, and the English runs all the way down it.** A 20-video course
produced 5,295 entries. Work down to **count >= 3** — about 2,500 entries, covering
99% of all occurrences. Do **not** stop where English "seems to thin out":
`everyone` sat at rank 708, `course` at 1,803, `comments` at 4,936. Each is rare
on its own, but together they put a wrong word in every few lines, and a reader
sees them immediately.

Most entries are genuine Hindi and are fine. Collect the ones that came out wrong
into a file, one `roman=english` line each:

```
evrivan=everyone
kost=course
krosovar=crossover
```

Then apply them and rebuild:

```bash
python convert.py --apply words.txt "<out-dir>"
python convert.py --reroman "<out-dir>"
```

Repeat until the Roman file reads clean. Then delete the todo file.

**Never put the glossary in CLAUDE.md.** It is a data file only Python reads —
it costs zero context tokens where it is, and would cost thousands there.

## Quality Expectations

Depends entirely on which track the video had:

| Track | Result |
|---|---|
| `manual/*` | Punctuation and correct spelling — close to publication quality |
| `auto/*` | Meaning fully clear, but **no punctuation**, all-lowercase, and source ASR errors pass through |

Hand-correcting auto-caption output needs a model to read and rewrite every line —
that costs more than everything else combined. Offer it, don't assume it.

**Numbers are the weak spot.** Auto-captions mangle prices, quantities and
tickers. If an episode's value is in its arithmetic (position sizing, risk
maths), say so plainly — those figures must be checked against the video.

## Common Mistakes

| Mistake | Fix |
|---|---|
| Skipping Step 1's save-location question | Files land somewhere the user didn't want. Always ask. |
| Feeding a playlist URL with `--items` straight away | Run it bare first to show the user the list, then ask which ones. |
| Reading the `.json3` backup | It's the raw download. Read the generated `.txt`. |
| `cat`-ing a 2+ hour transcript in one go | Harness truncates large output. Read ~150-line chunks with `sed -n`. |
| Adding every todo word to the glossary | Only the ones that came out **wrong**. Genuine Hindi words already transliterate correctly. |
| Mapping a word that is also common Hindi | `बार` → "bar" broke every `बार-बार` ("baar-baar"). When a word has both meanings, leave it out and let transliteration handle it. |
| Calling a wrong word an ASR error | Grep the `(hi-orig)` file first. `टीवीएस मोटर` was spelled right — "tivies Motor" was a plain glossary miss. Blaming ASR hides words you could have fixed. |
| Stopping the todo review where English "thins out" | It thins in **frequency**, not in kind. `kost` (course) sits at rank 1,803, `kaments` at 4,936. Work down to count >= 3 or the transcript still reads broken. |
| Re-running the downloader after growing the glossary | `--reroman` rebuilds from the Devanagari on disk. Re-downloading 20 videos to re-apply a word list is pure waste. |
| Reviewing the todo list per video | It is rewritten every run and is folder-wide. Read it after the **whole batch**. |
