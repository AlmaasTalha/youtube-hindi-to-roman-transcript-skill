# YouTube Hindi → Roman Transcript

A Claude Agent Skill that turns a Hindi YouTube video — or a whole course
playlist — into a readable **Roman Hindi (Hinglish)** transcript.

It converts the **script**, not the language. `मतलब` becomes *matlab*, not
*meaning*. For people who understand Hindi but read Roman faster.

```
मतलब क्या है        →   matlab kya hai
इसका फ़ायदा होगा    →   iska faayda hoga
```

## Why it isn't just a character swap

Convert `मतलब` letter by letter and you get *matalaba*. Hindi drops most of
those built-in vowels when spoken, so the skill applies real rules:

| Rule | Without it |
|---|---|
| Schwa deletion | `मतलब` → matalaba, not matlab |
| Nasal by context | `हम` and `हूँ` both end in "m" |
| Nukta | `ज़रूर` → jaroor, `फ़ायदा` → phayda |
| Long vowels kept | `काम` and `कम` collapse into one word |

And speech-to-text writes English words in Devanagari too — `range` comes back
as `रेंज`, which transliterates to *renj*. That is what the glossary fixes.

## Install

```bash
mkdir -p ~/.claude/skills/hindi-video-transcript
curl -o ~/.claude/skills/hindi-video-transcript/SKILL.md \
  https://raw.githubusercontent.com/AlmaasTalha/youtube-hindi-to-roman-transcript-skill/main/SKILL.md
```

For one project only, put `SKILL.md` in that repo's
`.claude/skills/hindi-video-transcript/` instead.
See the [skills docs](https://code.claude.com/docs/en/agent-sdk/skills).

## Use

Paste a Hindi YouTube link and ask for a transcript. The agent asks where to
save, sets itself up, and takes it from there. You only weigh in when it asks.

## What you end up with

```
<your base folder>/
├── tools/                    set up once, every subject uses it
├── Trading Course/
│   ├── 01 - Charting.txt     ← the file you read
│   ├── glossary.py           this subject's word list
│   └── raw/                  Devanagari + original download
└── Cooking Course/           new subject, new folder, new glossary
```

Glossaries never merge across subjects — a cooking course and a trading course
need completely different word lists.

## What's in this repo

| File | Job |
|---|---|
| `SKILL.md` | The procedure the agent follows |
| `translit.py` | Devanagari → Roman. 108 self-tests |
| `convert.py` | Downloads captions, picks the best track, writes the files. 39 self-tests |

Both scripts self-check with `--test` and refuse to run if they fail. There is
no glossary here on purpose — it is built inside your own project.

## Which captions it uses

Human-written Hindi beats auto-generated Hindi. It never uses YouTube's
auto-translated English: that is machine translation stacked on machine
transcription, so meaning drifts twice.

If the video has **human-written English** subtitles, it stops and asks you
first — those are cleaner and cheaper, but they are a translation, so the
speaker's own words and Hindi terms are gone. Your call, not its own.

## Getting it accurate

The first video of a new subject reads rough: the glossary starts empty, so
every English term comes back transliterated. The agent works through a ranked
list of unknown words, fixes the wrong ones, and rebuilds — no re-downloading.
Every correction improves every video in that subject, past and future.

This is the part that decides whether the transcript is readable. Expect a
couple of rounds.

## Limits

- **Roman Hindi has no official spelling.** *nahi / nahin*, *hai / hain* — the
  skill picks one consistent set. You will disagree with some of them.
- **Auto-captions have no punctuation** and are all lowercase. Their own
  recognition errors pass straight through.
- **Numbers are the weak spot.** Prices, quantities and tickers get mangled. If
  a video's value is in its arithmetic, check those against the video.
- **No caption track, no transcript.** Speech recognition from audio is a
  different job.

## Requirements

- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- Python 3
- An agent that supports [Agent Skills](https://code.claude.com/docs/en/agent-sdk/skills)

## License

MIT
