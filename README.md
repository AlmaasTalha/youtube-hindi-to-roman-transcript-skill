# YouTube Hindi → Roman Transcript (Claude Agent Skill)

Turn a Hindi or Hinglish YouTube video — or an entire course playlist — into two
clean text files: an exact line-by-line **Devanagari** transcript, and a readable
**Roman Hindi (Hinglish)** version.

> **This repo ships a procedure, not a program.** It contains one file,
> `SKILL.md`. There is nothing to install and no CLI to run. The skill teaches a
> Claude agent how to build three small Python scripts *inside your own project*,
> then how to run and refine them. That is deliberate — see
> [How it works](#how-it-works).

## The problem

You have found a long Hindi YouTube video — a lecture, a multi-hour course, a
tutorial — and you want an AI model to actually *read* it, so you can question
it, summarise it, or learn from it.

But there is no transcript to hand it.

Four things stand in the way:

1. **Feeding the video itself is expensive.** Processing hours of frames costs
   far more than reading the words that were spoken — enough that transcribing a
   whole course stays theoretical instead of something you just do.
2. **The captions that do exist come back in Devanagari.** Many fluent Hindi
   speakers read and type in Roman script; a Devanagari wall of text is slow to
   read, or unreadable, for exactly the people who understand the content best.
3. **Naive transliteration produces gibberish.** Convert `मतलब` character by
   character and you get *matalaba*, not *matlab*. And because speech-to-text
   writes spoken English words in Devanagari too, *range* comes back as *renj*
   and *consider* as *kansidar* — every few lines reads broken.
4. **Devanagari is expensive to feed back to a model.** Mainstream tokenizers are
   trained on overwhelmingly English text, so Indic scripts fragment into many
   small pieces and cost noticeably more tokens for the same meaning
   ([Tokenizer Tax, 2026](https://arxiv.org/html/2607.24276)).

The useful fact underneath all this: **a long Hindi video almost always has a
caption track, even when no transcript is published anywhere.** This skill's job
is to find the best track available, pull it, and turn it into text that both you
and your model can read — cheaply, and in the script you actually use.

## How it works

### Does your video need this skill?

Not every video does. The skill checks what the video already has and takes the
shortest honest path:

| What the video has | What happens |
|---|---|
| Human-written subtitles in **English** | Just download them. No transliteration, no glossary — this is a plain download job and the skill says so instead of inventing work. |
| Human-written subtitles in **Roman Hindi / Hinglish** | Just download them. Already in the script you want. Uncommon, but it happens, and it is worth checking before doing anything else. |
| An **auto-translated English** track on a Hindi video | Deliberately *not* used. It is machine translation stacked on machine transcription — two lossy steps, and meaning drifts. The skill prefers the original Hindi track and romanises that instead. |
| Human-written **Devanagari** subtitles | The skill runs, and this is its best case. Punctuation and correct spelling survive the conversion, so the output lands close to publication quality. |
| **Auto-generated Devanagari** captions | The main case, and where the skill earns its place. Schwa deletion plus a growing glossary turn a raw, unpunctuated fragment stream into readable Hinglish. |
| **No caption track at all** | Out of scope. Speech recognition from the audio is a different job and this skill will tell you so rather than guess. |

Within each category the rule is the same: **human-written beats automatic, and
original-language beats auto-translated.** The skill reports which track it
picked, so you always know what quality to expect.

### Captions, not video

The skill never processes video or audio. It pulls the video's **caption track**
and works from that. Captions carry the same spoken content at a small fraction
of the cost of video frames, which is what makes transcribing a whole course
affordable rather than theoretical.

### Three scripts, built in your project

The skill ships no code on purpose. The hardest part of this job is a **glossary
of domain vocabulary**, and that is different for every subject — a cooking
course, a physics lecture and a software tutorial need completely different word
lists. One shared glossary would fit none of them. So the scripts are generated
per project:

| Script | Job |
|---|---|
| `translit.py` | The transliteration engine. Breaks each Devanagari word into consonant / vowel / nasal units and applies **schwa deletion** — the rule that turns `मतलब` into *matlab* instead of *matalaba* — then normalises to conventional Hinglish spellings. |
| `glossary.py` | A plain dictionary mapping Devanagari-spelled English back to real English (`'रेंज' → 'range'`). **Starts empty** and grows as you work. Append-only, so a correction is one more line at the bottom. |
| `convert.py` | The driver. Downloads the caption track, applies the glossary first and transliteration to whatever is left, writes the files, and reports the stats. |

### Why the Roman file is the cheap one

Devanagari is **not** token-efficient. Mainstream LLM tokenizers are trained on
overwhelmingly English text, so Indic scripts fragment into many small pieces and
cost noticeably more tokens than the same meaning in Latin script
([Tokenizer Tax, 2026](https://arxiv.org/html/2607.24276)).

So the Roman file is not just easier for a human to read — it is the **cheaper
one to feed back to an AI agent**. That is why the skill defaults to leaving
timestamps *out* of the Roman file: it is the file you will re-read in full, and
timestamps inflate it for no benefit.

### The glossary loop

After the first batch, the skill writes a `_glossary-todo.txt` listing every
unknown word across the folder, ranked by frequency. You skim it, collect only
the words that came out **wrong** into a file of `roman=english` lines, and apply
them:

```bash
python convert.py --apply words.txt "<out-dir>"
python convert.py --reroman  "<out-dir>"
```

`--reroman` rebuilds every Roman file from the Devanagari already on disk — **no
re-downloading**. Improving the glossary for a 20-video course does not mean
fetching 20 videos again. Accuracy compounds: every correction improves every
past and future video in that project.

## What you get

Per video:

| File | Contents |
|---|---|
| `... - transcript (hi-orig).txt` | Exact Devanagari, one line per caption, `[HH:MM:SS]` stamped |
| `... - transcript (roman).txt` | The Roman Hindi version (timestamps optional, off by default) |
| `... - raw captions.json3` | The untouched download, kept as a backup |
| `_glossary-todo.txt` | Every unknown word in the folder, ranked by frequency |

Plus a per-video report: line count, word count, glossary hit rate, and how much
Devanagari is left in the Roman file. `devanagari left 0` means the conversion is
clean.

### Roughly what a 2-hour video costs

A 2-hour lecture at a typical [100–130 words per minute](https://virtualspeech.com/blog/average-speaking-rate-words-per-minute)
is somewhere around **12,000–16,000 spoken words**. As text that lands in the tens
of thousands of tokens — the Roman file materially cheaper than the Devanagari
one, and both far below what the same content costs as video.

These are order-of-magnitude figures, not a benchmark. Actual token counts vary
with the tokenizer, the speaker's pace, and how much of the video is speech.
Measure your own files if the number matters to your budget.

## Accuracy and limitations

Read this before trusting the output.

**Roman Hindi has no official spelling standard.** *hai / hain / he*,
*nahi / nahin*, *kya / kyaa* — everyone writes it differently and there is no
authority to be correct against. The skill applies **one consistent set of
conventions**, so output is internally consistent across your whole project, but
it will not match your personal preference on every word. Expect to disagree with
some spellings; that is the nature of the task, not a defect.

**Transliteration is rule-based, not a language model.** Schwa deletion is a
two-rule heuristic. It handles the overwhelming majority of words and will get
some exceptions wrong.

**The first video in a new subject reads rough.** The glossary starts empty, so
every English term the speaker used comes back transliterated. This is the part
people skip, and it is the part that decides whether the transcript is readable.
Budget real effort: a 20-video course produced over 5,000 distinct unknown words;
working down to those appearing 3 or more times covered around 99% of all
occurrences. Do not stop where English "seems to thin out" — it thins in
frequency, not in kind. Common words like *everyone* and *course* sit far down
the list, and each one still puts a wrong word on screen every few lines.

Proper nouns and people's names are unknown words too, so they stay approximate
until you add them.

**Everything depends on which caption track the video had:**

| Track | What you get |
|---|---|
| Human-written subtitles | Punctuation and correct spelling — close to publication quality |
| Auto-captions | Meaning is fully clear, but **no punctuation**, all lowercase, and the source system's own recognition errors pass straight through |

**Numbers are the weak spot.** Auto-captions mangle prices, quantities,
measurements and any spoken figures. If a video's value is in its arithmetic,
those numbers must be checked against the video itself. The skill is instructed to
say so plainly rather than let you assume they are right.

**Where this does not apply:**

- Videos whose value is on screen — silent demos, visual walkthroughs. Captions
  cannot capture what was never said.
- Videos with no caption track at all. Audio plus speech recognition is a
  different job.

## How to use

**1. Install the skill.** For use across all your projects, put it in your
personal skills folder:

```bash
mkdir -p ~/.claude/skills/hindi-video-transcript
curl -o ~/.claude/skills/hindi-video-transcript/SKILL.md \
  https://raw.githubusercontent.com/AlmaasTalha/youtube-hindi-to-roman-transcript-skill/main/SKILL.md
```

For one project only, put `SKILL.md` in `.claude/skills/hindi-video-transcript/`
inside that repository instead — anyone who clones it gets the skill too. See the
[skills documentation](https://code.claude.com/docs/en/agent-sdk/skills).

*(The repository is named for what it does; the skill's own internal name is
`hindi-video-transcript`, so keep the installed folder named that.)*

**2. Trigger it.** Paste a Hindi YouTube video or playlist link and ask for a
transcript, a summary, or a Hinglish version. The skill picks itself up from the
request.

**3. Answer four questions.** Before downloading anything it asks for the link,
where to save, whether you want timestamps in the Roman file, and how many videos
from a playlist. It never guesses where your files should go.

**4. Grow the glossary.** After the first batch, work through
`_glossary-todo.txt` as described above, then `--apply` and `--reroman`. Repeat
until it reads clean.

## Requirements

- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- Python 3
- An agent that supports [Agent Skills](https://code.claude.com/docs/en/agent-sdk/skills)

## License

MIT
