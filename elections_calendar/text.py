"""Text normalisation shared by every layer (stdlib only)."""

import re
import unicodedata

_WS = re.compile(r"\s+")
_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "`": "'", "´": "'", "ʼ": "'", "ʻ": "'"})
# Accents are dropped only from letters below U+0530 (Latin, IPA, Greek,
# Cyrillic); elsewhere a mark changes the letter (kana voicing).
_ACCENTED_SCRIPTS_END = 0x0530


def collapse_ws(text: str) -> str:
    """Collapse every run of whitespace (including NBSP) to one space and strip."""
    return _WS.sub(" ", text).strip()


def fold(text: str) -> str:
    """Case-fold, unify apostrophes and drop accents: "São Tomé" -> "sao tome".

    Only Latin, IPA, Greek and Cyrillic letters lose their marks; other scripts
    keep theirs, because there a mark makes a different letter.
    """
    kept: list[str] = []
    base = ""
    for c in unicodedata.normalize("NFKD", text.translate(_APOSTROPHES)):
        if not unicodedata.combining(c):
            base = c
        elif base and ord(base) < _ACCENTED_SCRIPTS_END:
            continue
        kept.append(c)
    return unicodedata.normalize("NFC", "".join(kept)).casefold()


def _word_char(c: str) -> bool:
    return c == "'" or unicodedata.category(c)[0] in "LMN"  # letters, marks, numbers


def norm_name(text: str) -> str:
    """Matching key for names: folded, punctuation to spaces, no leading/trailing "the".

    "Gambia (The)", "Gambia, The" and "The Gambia" all give "gambia". Letters
    and digits of every script are kept, so a name in any script has a key.
    """
    folded = fold(text).replace("&", " and ")
    key = collapse_ws("".join(c if _word_char(c) else " " for c in folded).strip(" '"))
    if key.startswith("the "):
        key = key[4:]
    if key.endswith(" the"):
        key = key[:-4]
    return key


def slug(text: str) -> str:
    """Identifier fragment: norm_name with apostrophes dropped and spaces as hyphens."""
    return norm_name(text).replace("'", "").replace(" ", "-")
