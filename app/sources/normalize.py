import re
import unicodedata

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def strip_html(raw: str) -> str:
    return _HTML_TAG_RE.sub(" ", raw)


def clean_text(raw: str, max_chars: int = 8000) -> str:
    text = strip_html(raw)
    text = unicodedata.normalize("NFKC", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    if len(text) > max_chars:
        text = text[:max_chars]
    return text
