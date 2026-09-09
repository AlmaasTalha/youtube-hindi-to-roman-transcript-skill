# -*- coding: utf-8 -*-
"""Devanagari -> Roman Hindi (Hinglish).

Targets the way people actually type Hindi, not scholarly transliteration:
no diacritics, retroflex and dental collapse onto one Roman letter.

    from translit import roman
    roman("मतलब क्या है")   # -> "matlab kya hai"

Self-check:  python translit.py --test
Ad-hoc:      python translit.py "कुछ हिंदी टेक्स्ट"
"""
import re
import sys
import unicodedata

NUKTA = "़"
VIRAAM = "्"
ANUSVARA = "ं"
CHANDRABINDU = "ँ"
VISARGA = "ः"

CONSONANTS = {
    "क": "k",  "ख": "kh", "ग": "g",  "घ": "gh", "ङ": "ng",
    "च": "ch", "छ": "chh","ज": "j",  "झ": "jh", "ञ": "n",
    "ट": "t",  "ठ": "th", "ड": "d",  "ढ": "dh", "ण": "n",
    "त": "t",  "थ": "th", "द": "d",  "ध": "dh", "न": "n",
    "प": "p",  "फ": "ph", "ब": "b",  "भ": "bh", "म": "m",
    "य": "y",  "र": "r",  "ल": "l",  "व": "v",  "श": "sh",
    "ष": "sh", "स": "s",  "ह": "h",  "ळ": "l",
}

# Loanwords from Urdu, Persian, Arabic and English. ASR often drops the nukta
# entirely, so the bare letter stays valid too and the glossary catches the rest.
NUKTA_FORMS = {
    "क": "q", "ख": "kh", "ग": "g", "ज": "z", "ड": "r", "ढ": "rh", "फ": "f",
}

# Anusvara is homorganic: m before a labial, n everywhere else.
LABIALS = set("पफबभम")

VOWELS = {
    "अ": "a",  "आ": "aa", "इ": "i",  "ई": "ee", "उ": "u",   "ऊ": "oo",
    "ऋ": "ri", "ए": "e",  "ऐ": "ai", "ओ": "o",  "औ": "au",  "ऑ": "o",
    "ऍ": "e",
}

MATRAS = {
    "ा": "aa", "ि": "i",  "ी": "ee", "ु": "u",
    "ू": "oo", "ृ": "ri", "े": "e",  "ै": "ai",
    "ो": "o",  "ौ": "au", "ॉ": "o",  "ॅ": "e",
}

DIGITS = {"०": "0", "१": "1", "२": "2", "३": "3", "४": "4",
          "५": "5", "६": "6", "७": "7", "८": "8", "९": "9"}

DEVANAGARI = re.compile(r"[ऀ-ॿ]+")


def _units(word):
    """Split into units of consonant + vowel + nasal, each with an inherent schwa.

    NFD is what makes the nukta reliable: it decomposes precomposed letters like
    ज़ (U+095B) into ज + U+093C, so one lookahead covers both spellings.
    """
    s = unicodedata.normalize("NFD", word)
    units, i = [], 0
    while i < len(s):
        ch = s[i]

        # ज्ञ is the one conjunct that is not the sum of its parts (j + n != gy).
        # क्ष, त्र, श्र fall out of the viraam rule on their own.
        if s.startswith("ज" + VIRAAM + "ञ", i):
            units.append({"c": "gy", "v": "", "n": "", "schwa": True, "dev": "ज"})
            i += 3
            continue

        if ch in CONSONANTS:
            roman_c = CONSONANTS[ch]
            if s[i + 1:i + 2] == NUKTA:
                roman_c = NUKTA_FORMS.get(ch, roman_c)
                i += 1
            units.append({"c": roman_c, "v": "", "n": "", "schwa": True, "dev": ch})
        elif ch in VOWELS:
            units.append({"c": "", "v": VOWELS[ch], "n": "", "schwa": False, "dev": ch})
        elif ch in MATRAS:
            if units:
                units[-1]["v"] = MATRAS[ch]
                units[-1]["schwa"] = False
            else:
                units.append({"c": "", "v": MATRAS[ch], "n": "", "schwa": False, "dev": ch})
        elif ch == VIRAAM:
            if units:
                units[-1]["schwa"] = False
        elif ch in (ANUSVARA, CHANDRABINDU, VISARGA):
            if units:
                units[-1]["n"] = ch
        elif ch in DIGITS:
            units.append({"c": DIGITS[ch], "v": "", "n": "", "schwa": False, "dev": ch})
        elif ch in ("।", "॥"):
            units.append({"c": ".", "v": "", "n": "", "schwa": False, "dev": ch})
        elif ch == "ऽ":
            pass
        else:
            # Unmapped: pass it through rather than drop it silently, so the
            # caller's "devanagari left" count surfaces the gap.
            units.append({"c": ch, "v": "", "n": "", "schwa": False, "dev": ch})
        i += 1
    return units


def _voiced(unit):
    return bool(unit["v"]) or unit["schwa"]


def _delete_schwa(units):
    """Without this मतलब reads "matalaba" instead of "matlab"."""
    if units and units[-1]["c"] and units[-1]["schwa"] and not units[-1]["n"]:
        units[-1]["schwa"] = False

    # Medial, right to left: in V C[a] C V the schwa goes.
    for i in range(len(units) - 2, 0, -1):
        u = units[i]
        if not (u["c"] and u["schwa"] and not u["n"]):
            continue
        # A nasal coda closes the syllable before it, which takes this schwa out
        # of the V C[a] C V environment: कंपनी is "kampani", not "kampni".
        if units[i - 1]["n"]:
            continue
        if _voiced(units[i - 1]) and _voiced(units[i + 1]):
            u["schwa"] = False
    return units


def _nasal(unit, following):
    mark = unit["n"]
    if not mark:
        return ""
    if mark == CHANDRABINDU:
        return "n"
    if mark == VISARGA:
        return "h"
    return "m" if following and following["dev"] in LABIALS else "n"


def _render(units):
    out = []
    for i, u in enumerate(units):
        out.append(u["c"])
        out.append(u["v"] or ("a" if u["schwa"] else ""))
        out.append(_nasal(u, units[i + 1] if i + 1 < len(units) else None))
    return "".join(out)


def _normalise(s):
    """ee/oo are produced first, then reduced only where that reads better."""
    s = re.sub(r"ie\b", "iye", s)      # deejie  -> dijiye
    s = s.replace("ee", "i")           # bhee    -> bhi
    s = re.sub(r"\boo", "u", s)        # oopar   -> upar   (leaves hoon, zaroor)
    s = re.sub(r"aa\b", "a", s)        # rahaa   -> raha   (leaves aap, kaam)
    s = s.replace("hkh", "kh")         # duhkh   -> dukh   (visarga)
    return s


def roman(text):
    """Transliterate every Devanagari run in `text`; leave everything else alone."""
    return DEVANAGARI.sub(
        lambda m: _normalise(_render(_delete_schwa(_units(m.group())))), text
    )


# --------------------------------------------------------------------------
# Self-check. Roman Hindi has no official spelling standard, so these pairs are
# this project's chosen conventions, not a claim of correctness. They exist so a
# change that breaks a word gets caught immediately.
# --------------------------------------------------------------------------
CASES = [
    # --- schwa deletion: the rule the whole thing rests on ---
    ("मतलब", "matlab"), ("समझ", "samajh"), ("करना", "karna"), ("चलना", "chalna"),
    ("रहना", "rahna"), ("देखना", "dekhna"), ("बोलना", "bolna"), ("सोचना", "sochna"),
    ("अंदर", "andar"), ("बाहर", "baahar"), ("शहर", "shahar"), ("बंदर", "bandar"),
    ("नमक", "namak"), ("कमल", "kamal"), ("पहला", "pahla"), ("अगला", "agla"),
    ("कंपनी", "kampani"), ("गंदगी", "gandagi"),   # nasal coda blocks the deletion

    # --- the trap: word-final m is a real letter, not a nasal mark ---
    ("हम", "ham"), ("काम", "kaam"), ("नाम", "naam"), ("तुम", "tum"),
    ("कम", "kam"), ("राम", "raam"), ("जनम", "janam"), ("गरम", "garam"),

    # --- ... while these end in a nasal mark and must give n ---
    ("हूँ", "hoon"), ("हैं", "hain"), ("मैं", "main"), ("नहीं", "nahin"),
    ("दोस्तों", "doston"), ("क्यों", "kyon"), ("यहाँ", "yahaan"), ("कहाँ", "kahaan"),
    ("वहाँ", "vahaan"), ("माँ", "maan"),

    # --- anusvara is homorganic: m before a labial, n otherwise ---
    ("लंबा", "lamba"), ("अंब", "amb"), ("हिंदी", "hindi"), ("बंद", "band"),
    ("रंग", "rang"), ("संग", "sang"), ("संभव", "sambhav"), ("संख्या", "sankhya"),

    # --- conjuncts ---
    ("क्षेत्र", "kshetr"), ("ज्ञान", "gyaan"), ("श्रम", "shram"), ("प्रेम", "prem"),
    ("स्कूल", "skool"), ("विद्या", "vidya"), ("क्या", "kya"), ("स्वागत", "svaagat"),
    ("पत्र", "patr"), ("मित्र", "mitr"),

    # --- nukta: without these zaroor reads "jaroor" and fayda reads "phayda" ---
    ("ज़रूर", "zaroor"), ("फ़ायदा", "faayda"), ("ख़ास", "khaas"), ("ग़लत", "galat"),
    ("बड़ा", "bara"), ("क़ीमत", "qimat"),
    # Same words with the nukta dropped, which ASR does constantly. The rules
    # cannot know better here; these are the glossary's job, not translit's.
    ("जरूर", "jaroor"), ("फायदा", "phaayda"), ("सफर", "saphar"),

    # --- independent vowels ---
    ("आम", "aam"), ("इधर", "idhar"), ("ईमान", "imaan"), ("उधर", "udhar"),
    ("ऊपर", "upar"), ("ऋषि", "rishi"), ("एक", "ek"), ("ऐसा", "aisa"),
    ("ओर", "or"), ("और", "aur"), ("अब", "ab"),

    # --- normalisation rules ---
    ("भी", "bhi"), ("की", "ki"), ("रहा", "raha"), ("दीजिए", "dijiye"),
    ("चाहिए", "chaahiye"), ("पानी", "paani"), ("दुःख", "dukh"),

    # --- everyday words ---
    ("है", "hai"), ("हो", "ho"), ("था", "tha"), ("थी", "thi"), ("थे", "the"),
    ("कुछ", "kuchh"), ("सब", "sab"), ("बहुत", "bahut"), ("अच्छा", "achchha"),
    ("आप", "aap"), ("साथ", "saath"), ("बात", "baat"), ("लोग", "log"),

    # --- Long vowels stay long. Shortening them (kaam->kam, poora->pura) reads
    # --- more like casual Hinglish and measured ~7% fewer tokens, but it merges
    # --- distinct words, which costs far more than it saves. Do not "simplify".
    ("काम", "kaam"), ("कम", "kam"),
    ("बात", "baat"), ("बत", "bat"),
    ("दूर", "door"), ("दुर", "dur"),
    ("पूरा", "poora"), ("पुरा", "pura"),
    ("जान", "jaan"), ("जन", "jan"),

    # --- word boundaries, digits, mixed script ---
    ("बार-बार", "baar-baar"), ("१२३", "123"),
    ("मतलब क्या है", "matlab kya hai"),
    ("ये RSI है", "ye RSI hai"),
]


def _test():
    bad = [(d, w, roman(d)) for d, w in CASES if roman(d) != w]
    for d, want, got in bad:
        print("FAIL  %-12s want %-12s got %s" % (d, want, got))
    print("%d/%d" % (len(CASES) - len(bad), len(CASES)))
    return not bad


if __name__ == "__main__":
    if "--test" in sys.argv:
        sys.exit(0 if _test() else 1)
    elif len(sys.argv) > 1:
        print(roman(" ".join(sys.argv[1:])))
    else:
        print(__doc__)
