"""Sanitize announcement HTML content to prevent XSS."""

from __future__ import annotations

import bleach
from bleach.css_sanitizer import CSSSanitizer

_ALLOWED_TAGS = [
    "p",
    "br",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "h1",
    "h2",
    "h3",
    "ul",
    "ol",
    "li",
    "a",
    "img",
    "hr",
    "span",
    "div",
]

_ALLOWED_ATTRIBUTES = {
    "*": ["class"],
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "title", "width", "height", "loading"],
    "span": ["style"],
    "div": ["style"],
    "p": ["style"],
    "h1": ["style"],
    "h2": ["style"],
    "h3": ["style"],
}

_CSS = CSSSanitizer(allowed_css_properties=["color", "background-color", "text-align"])

_CLEANER = bleach.Cleaner(
    tags=_ALLOWED_TAGS,
    attributes=_ALLOWED_ATTRIBUTES,
    css_sanitizer=_CSS,
    strip=True,
)


def sanitize_announcement_html(raw: str | None) -> str:
    if not raw:
        return ""
    cleaned = _CLEANER.clean(raw)
    return cleaned.strip()
