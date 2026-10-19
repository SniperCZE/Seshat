"""Projede HTML z Markdownu a nechá v něm jen bezpečné značky a adresy."""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

_ALIGN_STYLE = re.compile(r"^\s*text-align\s*:\s*(left|center|right)\s*;?\s*$", re.IGNORECASE)
_ATTR_NAME = re.compile(r"^[a-zA-Z_:][-a-zA-Z0-9_:]*$")
_URL_ATTRS = {"href", "src"}
_DROP_WITH_CONTENT = {"script", "style", "noscript"}
_DROP_TAG = _DROP_WITH_CONTENT | {"iframe", "object", "embed", "form", "base", "meta", "link"}
_VOID = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "source",
    "track",
    "wbr",
}


def sanitize_html(source: str, base_dir: Path) -> str:
    parser = _Sanitizer(Path(base_dir))
    parser.feed(source)
    parser.close()
    return parser.text()


def _rewrite_url(value: str, base_dir: Path, attr: str) -> str | None:
    value = value.strip()
    if not value or any(ch.isspace() or ord(ch) < 32 for ch in value):
        return None
    if value.startswith("#"):
        return value
    lowered = value.lower()
    if lowered.startswith(("javascript:", "vbscript:")):
        return None
    if lowered.startswith("data:"):
        if attr == "src" and lowered.startswith("data:image/"):
            return value
        return None
    if lowered.startswith("//"):
        value = "https:" + value
        lowered = value.lower()
    if lowered.startswith(("http://", "https://", "mailto:")):
        return value
    fragment = ""
    path_part = value
    if lowered.startswith("file:"):
        parsed = urlparse(value)
        if parsed.fragment:
            fragment = "#" + quote(parsed.fragment, safe="-_.~")
        path = Path(unquote(parsed.path))
        if not path.is_absolute():
            path = base_dir / path
        return path.resolve().as_uri() + fragment
    if "#" in path_part:
        path_part, frag = path_part.split("#", 1)
        fragment = "#" + quote(frag, safe="-_.~")
    path_part = path_part.split("?", 1)[0]
    if path_part == "":
        return fragment or None
    return (base_dir / path_part).resolve().as_uri() + fragment


class _Sanitizer(HTMLParser):
    def __init__(self, base_dir: Path) -> None:
        super().__init__(convert_charrefs=False)
        self._base_dir = base_dir
        self._out: list[str] = []
        self._skip = 0

    def text(self) -> str:
        return "".join(self._out)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._start(tag, attrs)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._start(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _DROP_WITH_CONTENT:
            if self._skip:
                self._skip -= 1
            return
        if self._skip or tag in _DROP_TAG or tag in _VOID:
            return
        self._out.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._out.append(html.escape(data, quote=False))

    def handle_entityref(self, name: str) -> None:
        if not self._skip:
            self._out.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if not self._skip:
            self._out.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        return

    def handle_decl(self, decl: str) -> None:
        return

    def handle_pi(self, data: str) -> None:
        return

    def _start(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if self._skip:
            if tag in _DROP_WITH_CONTENT:
                self._skip += 1
            return
        if tag in _DROP_WITH_CONTENT:
            self._skip = 1
            return
        if tag in _DROP_TAG:
            return
        if tag == "input":
            self._emit_checkbox(attrs)
            return
        cleaned = self._clean_attrs(attrs)
        self._out.append(_format_tag(tag, cleaned))

    def _emit_checkbox(self, attrs: list[tuple[str, str | None]]) -> None:
        values = {(name or "").lower(): value or "" for name, value in attrs}
        if values.get("type", "").lower() != "checkbox":
            return
        css = values.get("class") or "task-list-item-checkbox"
        parts = [
            f'class="{html.escape(css, quote=True)}"',
            'disabled="disabled"',
            'type="checkbox"',
        ]
        if "checked" in values:
            parts.append('checked="checked"')
        self._out.append("<input " + " ".join(parts) + ">")

    def _clean_attrs(self, attrs: list[tuple[str, str | None]]) -> list[tuple[str, str]]:
        cleaned: list[tuple[str, str]] = []
        classes: list[str] = []
        align: str | None = None
        for raw_name, raw_value in attrs:
            if not raw_name:
                continue
            name = raw_name.lower()
            value = "" if raw_value is None else raw_value
            if name.startswith("on") or not _ATTR_NAME.match(name):
                continue
            if name == "style":
                match = _ALIGN_STYLE.match(value)
                if match:
                    align = match.group(1).lower()
                continue
            if name in {"srcset", "formaction", "action", "ping", "poster"}:
                continue
            if name in _URL_ATTRS:
                rewritten = _rewrite_url(value, self._base_dir, name)
                if rewritten is None:
                    continue
                value = rewritten
            if name == "class" and value:
                classes.append(value)
                continue
            if name == "align" and value.lower() in {"left", "center", "right"}:
                align = value.lower()
                continue
            cleaned.append((name, value))
        if align:
            classes.append(f"align-{align}")
        if classes:
            cleaned.append(("class", " ".join(classes)))
        return cleaned


def _format_tag(tag: str, attrs: list[tuple[str, str]]) -> str:
    rendered = "".join(
        f' {name}="{html.escape(value, quote=True)}"' for name, value in attrs
    )
    return f"<{tag}{rendered}>"
