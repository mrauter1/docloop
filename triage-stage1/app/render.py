from __future__ import annotations

import re

import bleach
from markdown_it import MarkdownIt
from markupsafe import Markup


_MARKDOWN = MarkdownIt("commonmark", {"html": False})
_ALLOWED_TAGS = set(bleach.sanitizer.ALLOWED_TAGS).union(
    {"p", "pre", "code", "br", "ul", "ol", "li", "strong", "em", "blockquote"}
)
_ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "target", "rel"],
}


def normalize_plain_text(text: str) -> str:
    collapsed = text.replace("\r\n", "\n").replace("\r", "\n")
    collapsed = re.sub(r"[ \t]+", " ", collapsed)
    collapsed = re.sub(r"\n{3,}", "\n\n", collapsed)
    return collapsed.strip()


def markdown_to_plain_text(markdown: str) -> str:
    rendered = _MARKDOWN.render(markdown or "")
    text = bleach.clean(rendered, tags=[], strip=True)
    return normalize_plain_text(text)


def markdown_to_safe_html(markdown: str) -> Markup:
    rendered = _MARKDOWN.render(markdown or "")
    sanitized = bleach.clean(
        rendered,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        strip=True,
    )
    linkified = bleach.linkify(sanitized)
    return Markup(linkified)
