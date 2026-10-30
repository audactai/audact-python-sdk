"""
PII vault client-side helpers.

``client_hash`` is part of the public contract and must be byte-identical to
the server's client-hash implementation; ``testdata/pii_normalize_vectors.json``
proves it.
The cleartext value never leaves the caller: only the hex hash is sent.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

from ._golower import GO_LOWER_RUNS

__all__ = ["normalize_identifier", "client_hash", "IDENTIFIER_TYPES"]

IDENTIFIER_TYPES = ("name", "email", "phone")

_E164 = re.compile(r"\+[1-9][0-9]{6,14}")
_PHONE_SEPARATORS = str.maketrans("", "", " -.()")


def _is_space(ch: str) -> bool:
    """Mirror Go ``unicode.IsSpace`` (Python's ``str.isspace`` also accepts U+001C-001F)."""
    if ch in "\t\n\v\f\r \u0085 ":
        return True
    return unicodedata.category(ch) in ("Zs", "Zl", "Zp")


# Code point -> lowercase code point, exactly Go's ``unicode.ToLower``.
_GO_LOWER: dict[int, int] = {
    cp: cp + delta
    for lo, hi, stride, delta in GO_LOWER_RUNS
    for cp in range(lo, hi + 1, stride)
}


def _go_lower(value: str) -> str:
    """
    Lowercase per code point exactly like Go ``strings.ToLower``.

    Not ``str.lower``: that applies SpecialCasing (``ΟΔΥΣΣΕΥΣ`` -> final
    ``ς``; ``İ`` -> ``i`` + U+0307) and the interpreter's Unicode version,
    either of which changes the bytes and so the hash.
    """
    return value.translate(_GO_LOWER)


def _trim(value: str) -> str:
    start, end = 0, len(value)
    while start < end and _is_space(value[start]):
        start += 1
    while end > start and _is_space(value[end - 1]):
        end -= 1
    return value[start:end]


def normalize_identifier(type: str, value: str) -> str:  # noqa: A002 - public name per spec
    """
    Canonicalise a subject identifier.

    * ``phone``: strip ``space - . ( )``; must then be E.164. Never guessed.
    * ``email``: trim, lowercase (per code point, as Go), NFC.
    * ``name``: trim, NFC, lowercase (per code point, as Go), collapse
      whitespace. No diacritic stripping.

    Raises :class:`ValueError` for an unsupported type or an invalid value.
    """
    if type == "phone":
        stripped = value.translate(_PHONE_SEPARATORS)
        if not _E164.fullmatch(stripped):
            raise ValueError("normalize phone: not E.164")
        return stripped
    if type == "email":
        out = unicodedata.normalize("NFC", _go_lower(_trim(value)))
        if not out:
            raise ValueError("normalize email: empty value")
        return out
    if type == "name":
        out = _go_lower(unicodedata.normalize("NFC", _trim(value)))
        parts: list[str] = []
        cur: list[str] = []
        for ch in out:
            if _is_space(ch):
                if cur:
                    parts.append("".join(cur))
                    cur = []
            else:
                cur.append(ch)
        if cur:
            parts.append("".join(cur))
        out = " ".join(parts)
        if not out:
            raise ValueError("normalize name: empty value")
        return out
    raise ValueError(f"normalize identifier: unsupported type {type!r}")


def client_hash(type: str, value: str) -> str:  # noqa: A002
    """Return ``sha256_hex(normalize_identifier(type, value))``."""
    return hashlib.sha256(normalize_identifier(type, value).encode("utf-8")).hexdigest()
