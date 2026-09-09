# -*- coding: utf-8 -*-
"""Download a YouTube caption track and write it as Devanagari + Roman Hindi.

    python convert.py <url> <out-dir> [--name STEM] [--timestamps] [--items ...]
    python convert.py --reroman <out-dir>
    python convert.py --apply words.txt <out-dir>

Self-check (offline):  python convert.py --test

Needs `translit.py` beside it. `glossary.py` is created empty on first run.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from translit import roman, DEVANAGARI  # noqa: E402

# The out-dir holds what the user reads. Everything they never open goes in raw/.
RAW_DIR = "raw"
ROMAN_SUFFIX = ".txt"
HI_SUFFIX = " (hi-orig).txt"
RAW_SUFFIX = ".json3"
TODO_NAME = "_glossary-todo.txt"
GLOSSARY_NAME = "glossary.py"


# --------------------------------------------------------------------------
# yt-dlp — the only part that touches the network
# --------------------------------------------------------------------------

def ytdlp_cmd():
    """Whichever yt-dlp this interpreter can actually reach."""
    for cmd in ([sys.executable, "-m", "yt_dlp"], ["yt-dlp"]):
        try:
            subprocess.run(cmd + ["--version"], capture_output=True, check=True)
            return cmd
        except (OSError, subprocess.CalledProcessError):
            continue
    sys.exit("yt-dlp not found. See the skill's Step 2.")


def probe(url, flat=False):
    cmd = ytdlp_cmd() + ["-J", "--skip-download", url]
    if flat:
        cmd.insert(-1, "--flat-playlist")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit("yt-dlp failed:\n" + r.stderr.strip()[-800:])
    return json.loads(r.stdout)


# --------------------------------------------------------------------------
# Track choice — fixed rules, no network
# --------------------------------------------------------------------------

def base_lang(code):
    """`hi`, `hi-IN`, `hi-Latn`, `hi-orig` all answer to `hi`.

    Match every track on this, never on the raw code: matching one branch
    exactly and another by prefix leaves variants falling through both.
    """
    return code.split("-")[0].lower()


def pick_track(info):
    """Return (kind, lang, note). kind is 'manual', 'other', 'auto' or None.

    'other' means human subtitles exist but not in Hindi. That is a translation,
    not a romanisation — a different product — so the caller must ask the user
    rather than choose.
    """
    subs = info.get("subtitles") or {}
    auto = info.get("automatic_captions") or {}

    # Human-written subtitles in a third language (Tamil, French) are no use for
    # this job, so they are ignored. English is the one the user might genuinely
    # prefer, so it is always reported even when a Hindi track wins.
    english = sorted(k for k in subs if base_lang(k) == "en")
    alt = english[0] if english else None

    hindi = sorted(k for k in subs if base_lang(k) == "hi")
    if hindi:
        return "manual", hindi[0], "human-written Hindi", alt
    if alt:
        return "other", alt, "human-written English (a translation)", alt

    # -orig is the one track the machine actually heard; every other language in
    # this bucket is a translation of it.
    hindi_auto = sorted((k for k in auto if base_lang(k) == "hi"),
                        key=lambda k: (not k.endswith("-orig"), k))
    if hindi_auto:
        return "auto", hindi_auto[0], "auto-generated Hindi", alt
    return None, None, "no usable Hindi caption track", alt


def track_url(info, kind, lang):
    bucket = info.get("subtitles" if kind in ("manual", "other") else "automatic_captions") or {}
    for fmt in bucket.get(lang, []):
        if fmt.get("ext") == "json3":
            return fmt["url"]
    return None


def coverage_minutes(events):
    """Last caption time. A manual track that stops early is a partial track."""
    return max((t for t, _ in events), default=0) / 60000.0


# --------------------------------------------------------------------------
# json3 -> lines. No network.
# --------------------------------------------------------------------------

def parse_json3(raw):
    """Return [(start_ms, text)]. Drops the empty spacer events YouTube emits."""
    data = json.loads(raw) if isinstance(raw, str) else raw
    out = []
    for ev in data.get("events", []):
        segs = ev.get("segs")
        if not segs:
            continue
        text = "".join(s.get("utf8", "") for s in segs).strip()
        if text:
            out.append((ev.get("tStartMs", 0), text))
    return out


def stamp(ms):
    s = int(ms // 1000)
    return "[%02d:%02d:%02d]" % (s // 3600, s % 3600 // 60, s % 60)


# --------------------------------------------------------------------------
# Glossary
# --------------------------------------------------------------------------

def glossary_path(outdir):
    """Beside the transcripts, not beside the scripts.

    Glossaries are per subject and must never merge. Keying them to the out-dir
    makes that structural: one tools/ folder reused for two courses still gets
    two separate glossaries.
    """
    return os.path.join(outdir, GLOSSARY_NAME)


def load_glossary(outdir):
    path = glossary_path(outdir)
    if not os.path.exists(path):
        os.makedirs(outdir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("# -*- coding: utf-8 -*-\n"
                    "# Devanagari-spelled English -> real English. Grows via --apply.\n"
                    "G = {}\n")
    ns = {}
    exec(compile(open(path, encoding="utf-8").read(), path, "exec"), ns)
    return ns.get("G", {})


PUNCT = "\"'()[]{}<>,.!?;:—–-…।॥"


def romanise(line, G):
    """Glossary first, transliteration for the rest.

    A glossary hit means the word was English all along; anything left is Hindi.
    """
    out, hits, total = [], 0, 0
    for tok in re.split(r"(\s+)", line):
        if not tok.strip():
            out.append(tok)
            continue
        total += 1
        core = tok.strip(PUNCT)
        lead = tok[: len(tok) - len(tok.lstrip(PUNCT))]
        tail = tok[len(tok.rstrip(PUNCT)):] if tok.rstrip(PUNCT) != tok else ""
        if core in G:
            hits += 1
            out.append(lead + G[core] + tail)
        else:
            out.append(roman(tok))
    return "".join(out), hits, total


# --------------------------------------------------------------------------
# Files
# --------------------------------------------------------------------------

def hi_files(outdir):
    """Devanagari files, from raw/ or loose in the out-dir (older layouts)."""
    found = []
    for d in (os.path.join(outdir, RAW_DIR), outdir):
        if os.path.isdir(d):
            found += [os.path.join(d, f) for f in sorted(os.listdir(d))
                      if f.endswith(HI_SUFFIX)]
    return found


def read_hi(path):
    """Devanagari file back into [(ms, text)]."""
    out = []
    for line in open(path, encoding="utf-8"):
        m = re.match(r"\[(\d+):(\d+):(\d+)\]\s?(.*)", line.rstrip("\n"))
        if m:
            h, mi, s, txt = m.groups()
            out.append(((int(h) * 3600 + int(mi) * 60 + int(s)) * 1000, txt))
    return out


def write_outputs(outdir, stem, events, G, timestamps):
    raw_dir = os.path.join(outdir, RAW_DIR)
    os.makedirs(raw_dir, exist_ok=True)
    hi_path = os.path.join(raw_dir, stem + HI_SUFFIX)
    ro_path = os.path.join(outdir, stem + ROMAN_SUFFIX)

    with open(hi_path, "w", encoding="utf-8") as f:
        for ms, text in events:
            f.write("%s %s\n" % (stamp(ms), text))

    hits = total = 0
    with open(ro_path, "w", encoding="utf-8") as f:
        for ms, text in events:
            line, h, t = romanise(text, G)
            hits += h
            total += t
            f.write(("%s %s\n" % (stamp(ms), line)) if timestamps else line + "\n")

    left = sum(len(m) for m in DEVANAGARI.findall(open(ro_path, encoding="utf-8").read()))
    print("  lines %d  words %d  glossary %.1f%%  devanagari left %d"
          % (len(events), total, 100.0 * hits / total if total else 0.0, left))
    return hi_path, ro_path


def write_todo(outdir, G):
    """Every unknown Devanagari word across the whole folder, most frequent first.

    Folder-wide on purpose: it is rewritten every run, so read it after a batch,
    not per video. Do not filter by a "looks English" rule — one such filter hid
    renj (range) and kansidar (consider).
    """
    counts = Counter()
    for path in hi_files(outdir):
        for _, text in read_hi(path):
            for word in DEVANAGARI.findall(text):
                if word not in G:
                    counts[word] += 1
    if not counts:
        return 0
    with open(os.path.join(outdir, TODO_NAME), "w", encoding="utf-8") as f:
        for word, n in counts.most_common():
            f.write("%-24s %6d  %s\n" % (word, n, roman(word)))
    return len(counts)


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

def do_video(url, outdir, stem, timestamps, G):
    info = probe(url)
    kind, lang, note, alt = pick_track(info)
    if kind is None:
        print("  SKIP — %s" % note)
        return False
    if kind == "other":
        print("  STOP — %s. Ask the user which they want before continuing." % note)
        return False

    print("  track: %s [%s]" % (note, lang))
    if alt:
        print("  NOTE — human-written English [%s] is also on this video."
              " Tell the user it exists before they read the output." % alt)
    url_json3 = track_url(info, kind, lang)
    if not url_json3:
        print("  SKIP — no json3 for that track")
        return False

    try:
        raw = urllib.request.urlopen(url_json3, timeout=60).read().decode("utf-8")
    except Exception as e:
        print("  SKIP — caption download failed: %s" % e)
        return False

    stem = stem or re.sub(r'[\\/:*?"<>|]', "_", info.get("title", "video"))[:120]
    raw_dir = os.path.join(outdir, RAW_DIR)
    os.makedirs(raw_dir, exist_ok=True)
    with open(os.path.join(raw_dir, stem + RAW_SUFFIX), "w", encoding="utf-8") as f:
        f.write(raw)

    events = parse_json3(raw)
    if kind == "manual":
        dur = (info.get("duration") or 0) / 60.0
        cov = coverage_minutes(events)
        if dur and cov < dur * 0.8:
            print("  WARNING — manual track stops at %.1f min of %.1f. Partial." % (cov, dur))
    write_outputs(outdir, stem, events, G, timestamps)
    return True


def do_reroman(outdir, timestamps, G):
    files = hi_files(outdir)
    if not files:
        sys.exit("No %s files in %s" % (HI_SUFFIX.strip(), outdir))
    for path in files:
        stem = os.path.basename(path)[: -len(HI_SUFFIX)]
        print(stem)
        write_outputs(outdir, stem, read_hi(path), G, timestamps)


def do_apply(words_file, outdir, G):
    """roman=english lines -> every Devanagari spelling that produced that roman.

    ASR writes one word several ways and you never type Devanagari, so resolving
    backwards is the only way to catch all of them.
    """
    back = {}
    for path in hi_files(outdir):
        for _, text in read_hi(path):
            for word in DEVANAGARI.findall(text):
                back.setdefault(roman(word), set()).add(word)

    added = {}
    missing = []
    for raw_line in open(words_file, encoding="utf-8"):
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, english = (p.strip() for p in line.split("=", 1))
        spellings = back.get(key)
        if not spellings:
            missing.append(key)
            continue
        for dev in spellings:
            added[dev] = english

    if added:
        with open(glossary_path(outdir), "a", encoding="utf-8") as f:
            f.write("\nG.update({\n")
            for dev in sorted(added):
                f.write("    %r: %r,\n" % (dev, added[dev]))
            f.write("})\n")
    print("added %d spellings for %d words" % (len(added), len(set(added.values()))))
    if missing:
        print("not found in this folder: " + ", ".join(missing[:20]))


def parse_items(spec, total):
    if spec in (None, "", "all"):
        return list(range(1, total + 1))
    picked = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-", 1)
            picked += list(range(int(a), int(b) + 1))
        else:
            picked.append(int(part))
    return [i for i in picked if 1 <= i <= total]


# --------------------------------------------------------------------------
# Self-check — offline, on a synthetic caption file
# --------------------------------------------------------------------------

FIXTURE = {"events": [
    {"tStartMs": 0},
    {"tStartMs": 1000, "segs": [{"utf8": "दोस्तों "}, {"utf8": "नमस्कार"}]},
    {"tStartMs": 65000, "segs": [{"utf8": "इसका मतलब क्या है"}]},
    {"tStartMs": 3725000, "segs": [{"utf8": "रेंज देखो"}]},
    {"tStartMs": 3726000, "segs": [{"utf8": "   "}]},
]}


def _test():
    bad, ran = [], []

    def check(name, got, want):
        ran.append(name)
        if got != want:
            bad.append("%s\n    want %r\n    got  %r" % (name, want, got))

    ev = parse_json3(json.dumps(FIXTURE))
    check("parse drops empty events", len(ev), 3)
    check("parse joins segs", ev[0][1], "दोस्तों नमस्कार")
    check("stamp 0", stamp(0), "[00:00:00]")
    check("stamp 1m5s", stamp(65000), "[00:01:05]")
    check("stamp 1h2m5s", stamp(3725000), "[01:02:05]")
    check("coverage minutes", round(coverage_minutes(ev), 2), 62.08)

    check("pick manual hi", pick_track({"subtitles": {"hi": []}})[:2], ("manual", "hi"))
    check("pick asks on manual en",
          pick_track({"subtitles": {"en": []}})[0], "other")
    check("pick auto -orig over hi",
          pick_track({"automatic_captions": {"hi": [], "hi-orig": []}})[:2], ("auto", "hi-orig"))
    check("pick auto hi when no -orig",
          pick_track({"automatic_captions": {"hi": []}})[:2], ("auto", "hi"))
    check("never picks auto en",
          pick_track({"automatic_captions": {"en": []}})[0], None)
    check("manual hi beats auto",
          pick_track({"subtitles": {"hi": []}, "automatic_captions": {"hi-orig": []}})[:2],
          ("manual", "hi"))
    check("manual hi-IN is still manual Hindi",
          pick_track({"subtitles": {"hi-IN": []},
                      "automatic_captions": {"hi-orig": []}})[:2], ("manual", "hi-IN"))
    check("manual hi-Latn is still manual Hindi",
          pick_track({"subtitles": {"hi-Latn": []},
                      "automatic_captions": {"hi-orig": []}})[:2], ("manual", "hi-Latn"))
    check("auto hi-IN counts as Hindi",
          pick_track({"automatic_captions": {"hi-IN": []}})[:2], ("auto", "hi-IN"))
    check("base_lang strips region and script",
          [base_lang(c) for c in ("hi", "hi-IN", "hi-Latn", "hi-orig", "en-GB")],
          ["hi", "hi", "hi", "hi", "en"])
    check("manual hi wins but English is still reported",
          pick_track({"subtitles": {"hi": [], "en": []}}),
          ("manual", "hi", "human-written Hindi", "en"))
    check("auto Hindi still reports manual English",
          pick_track({"subtitles": {"en": []},
                      "automatic_captions": {"hi-orig": []}})[0], "other")
    check("a third language is ignored, not asked about",
          pick_track({"subtitles": {"ta": []},
                      "automatic_captions": {"hi-orig": []}})[:2], ("auto", "hi-orig"))
    check("a third language alone is not usable",
          pick_track({"subtitles": {"ta": []}})[0], None)

    check("glossary hit wins", romanise("रेंज देखो", {"रेंज": "range"})[0], "range dekho")
    check("no glossary -> translit", romanise("रेंज देखो", {})[0], "renj dekho")
    check("glossary through punctuation",
          romanise("रेंज,", {"रेंज": "range"})[0], "range,")
    check("english passes through", romanise("ye RSI hai", {})[0], "ye RSI hai")

    check("items all", parse_items("all", 4), [1, 2, 3, 4])
    check("items range", parse_items("1-3", 9), [1, 2, 3])
    check("items list", parse_items("2,5", 9), [2, 5])
    check("items clamped", parse_items("8-12", 9), [8, 9])

    tmp = tempfile.mkdtemp()
    other = tempfile.mkdtemp()
    try:
        check("glossary starts empty", load_glossary(tmp), {})
        hi, ro = write_outputs(tmp, "01 - Test", ev, {"रेंज": "range"}, False)
        check("roundtrip devanagari", read_hi(hi), ev)
        check("roman file", open(ro, encoding="utf-8").read().split("\n")[1],
              "iska matlab kya hai")
        check("roman sits in the out-dir", os.path.dirname(ro), tmp)
        check("devanagari sits in raw/", os.path.dirname(hi),
              os.path.join(tmp, RAW_DIR))
        check("roman filename carries no jargon", os.path.basename(ro),
              "01 - Test.txt")
        check("reroman still finds it", hi_files(tmp), [hi])
        check("todo lists unknown words", write_todo(tmp, {"रेंज": "range"}), 7)
        with open(os.path.join(tmp, "w.txt"), "w", encoding="utf-8") as f:
            f.write("renj=range\n")
        do_apply(os.path.join(tmp, "w.txt"), tmp, {})
        check("apply wrote glossary", load_glossary(tmp).get("रेंज"), "range")
        check("glossary lives in the out-dir",
              os.path.exists(os.path.join(tmp, GLOSSARY_NAME)), True)
        check("a second out-dir gets its own", load_glossary(other), {})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(other, ignore_errors=True)

    for b in bad:
        print("FAIL  " + b)
    print("%d/%d" % (len(ran) - len(bad), len(ran)))
    return not bad


# --------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(add_help=True)
    p.add_argument("url", nargs="?")
    p.add_argument("outdir", nargs="?")
    p.add_argument("--name")
    p.add_argument("--timestamps", action="store_true")
    p.add_argument("--items")
    p.add_argument("--reroman", action="store_true")
    p.add_argument("--apply", metavar="FILE")
    p.add_argument("--test", action="store_true")
    a = p.parse_args()

    if a.test:
        sys.exit(0 if _test() else 1)
    if not a.outdir and a.url and os.path.isdir(a.url):
        a.url, a.outdir = None, a.url
    if not a.outdir:
        p.error("out-dir is required")

    G = load_glossary(a.outdir)

    if a.apply:
        return do_apply(a.apply, a.outdir, G)
    if a.reroman:
        return do_reroman(a.outdir, a.timestamps, G)
    if not a.url:
        p.error("url is required")

    head = probe(a.url, flat=True)
    entries = head.get("entries")
    if entries:
        entries = [e for e in entries if e]
        if not a.items:
            print("%d videos. Re-run with --items to choose.\n" % len(entries))
            for i, e in enumerate(entries, 1):
                print("%3d. %s" % (i, e.get("title", "?")))
            return
        done = 0
        for i in parse_items(a.items, len(entries)):
            e = entries[i - 1]
            print("\n%3d. %s" % (i, e.get("title", "?")))
            done += do_video(e.get("url") or e["id"], a.outdir,
                             a.name and "%s %02d" % (a.name, i), a.timestamps, G)
    else:
        done = do_video(a.url, a.outdir, a.name, a.timestamps, G)

    # Only after something was actually written — otherwise the count is stale
    # from an earlier run and reads like this run produced it.
    if done:
        n = write_todo(a.outdir, G)
        if n:
            print("\n%s: %d unknown words" % (TODO_NAME, n))


if __name__ == "__main__":
    main()
