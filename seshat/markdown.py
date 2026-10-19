"""Převod Markdownu na HTML, které pak vykreslí WebKit."""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import emoji
from markdown_it import MarkdownIt
from markdown_it.token import Token
from mdit_py_plugins.deflist import deflist_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.tasklists import tasklists_plugin
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_by_name
from pygments.util import ClassNotFound

from seshat.sanitize import sanitize_html

_HEADING_ID = re.compile(r"^(?P<body>.*?)\s*\{#(?P<ident>[^{}\s]+)\}\s*$")
_CODE_FORMATTER = HtmlFormatter(cssclass="highlight")


@dataclass(frozen=True)
class Heading:
    level: int
    text: str
    anchor: str


@dataclass(frozen=True)
class RenderedDocument:
    html: str
    headings: tuple[Heading, ...]
    title: str | None


def render_markdown(source: str, base_dir: Path) -> RenderedDocument:
    base = Path(base_dir).expanduser().resolve()
    parser = _parser()
    env: dict[str, object] = {}
    tokens = parser.parse(source, env)
    headings = tuple(_headings(tokens))
    body = parser.renderer.render(tokens, parser.options, env)
    title = next((item.text for item in headings if item.level == 1 and item.text), None)
    page = _wrap(sanitize_html(body, base), title)
    return RenderedDocument(html=page, headings=headings, title=title)


def pygments_css(dark: bool) -> str:
    style = "monokai" if dark else "default"
    return HtmlFormatter(style=style, cssclass="highlight").get_style_defs(".highlight")


def _parser() -> MarkdownIt:
    parser = MarkdownIt("gfm-like", {"breaks": False, "html": True})
    parser.use(tasklists_plugin, enabled=False)
    parser.use(footnote_plugin)
    parser.use(deflist_plugin)
    parser.inline.ruler.before("strikethrough", "highlight", _rule_highlight)
    parser.inline.ruler.before("strikethrough", "superscript", _rule_superscript)
    parser.inline.ruler.before("strikethrough", "subscript", _rule_subscript)
    parser.core.ruler.push("heading_anchor", _heading_anchors)
    parser.core.ruler.push("emoji_shortcodes", _emoji_shortcodes)
    parser.renderer.rules["fence"] = _render_fence
    parser.renderer.rules["code_block"] = _render_code_block
    return parser


def _rule_highlight(state, silent: bool) -> bool:
    return _paired(state, silent, "==", "mark", "mark")


def _rule_superscript(state, silent: bool) -> bool:
    return _paired(state, silent, "^", "sup", "sup")


def _rule_subscript(state, silent: bool) -> bool:
    return _paired(state, silent, "~", "sub", "sub")


def _paired(state, silent: bool, marker: str, token_name: str, tag: str) -> bool:
    start = state.pos
    marker_len = len(marker)
    if start + marker_len > state.posMax or state.src[start : start + marker_len] != marker:
        return False
    if start + marker_len < state.posMax and state.src[start + marker_len] == marker[0]:
        return False
    newline = state.src.find("\n", start + marker_len)
    close = state.src.find(marker, start + marker_len)
    if close == -1 or (newline != -1 and close > newline):
        return False
    if close + marker_len < state.posMax and state.src[close + marker_len] == marker[0]:
        return False
    content = state.src[start + marker_len : close]
    if content == "":
        return False
    if silent:
        return True

    opened = state.push(f"{token_name}_open", tag, 1)
    opened.markup = marker
    inner: list[Token] = []
    state.md.inline.parse(content, state.md, state.env, inner)
    state.tokens.extend(inner)
    missing = len(state.tokens) - len(state.tokens_meta)
    if missing > 0:
        state.tokens_meta.extend([None] * missing)
    closed = state.push(f"{token_name}_close", tag, -1)
    closed.markup = marker
    state.pos = close + marker_len
    return True


def _heading_anchors(state) -> None:
    used: set[str] = set()
    tokens = state.tokens
    for index, token in enumerate(tokens):
        if token.type != "heading_open":
            continue
        inline = tokens[index + 1] if index + 1 < len(tokens) else None
        if inline is None or inline.type != "inline":
            continue
        explicit = _explicit_heading_id(inline)
        if explicit is not None:
            body, ident = explicit
            inline.content = body
            inline.children = []
            state.md.inline.parse(body, state.md, state.env, inline.children)
            anchor = _clean_id(ident)
        else:
            anchor = _slugify(_inline_text(inline))
        token.attrSet("id", _unique(anchor, used))


def _explicit_heading_id(token: Token) -> tuple[str, str] | None:
    match = _HEADING_ID.match(token.content)
    if match is None:
        return None
    if token.children:
        last = token.children[-1]
        if last.type == "code_inline" and "{#" in last.content:
            return None
    return match.group("body"), match.group("ident")


def _emoji_shortcodes(state) -> None:
    for token in state.tokens:
        if token.type != "inline" or not token.children:
            continue
        for child in token.children:
            if child.type == "text" and ":" in child.content:
                child.content = emoji.emojize(child.content, language="alias")


def _headings(tokens: list[Token]) -> list[Heading]:
    found: list[Heading] = []
    for index, token in enumerate(tokens):
        if token.type != "heading_open":
            continue
        inline = tokens[index + 1] if index + 1 < len(tokens) else None
        text = _inline_text(inline).strip() if inline is not None else ""
        anchor = token.attrGet("id") or ""
        found.append(Heading(level=int(token.tag[1]), text=text, anchor=anchor))
    return found


def _inline_text(token: Token | None) -> str:
    if token is None:
        return ""
    if token.children:
        parts: list[str] = []
        for child in token.children:
            if child.type in {"text", "code_inline"}:
                parts.append(child.content)
            elif child.children:
                parts.append(_inline_text(child))
        return "".join(parts)
    return token.content


def _slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    without_marks = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    lowered = without_marks.casefold()
    cleaned = re.sub(r"[^\w\s-]", "", lowered, flags=re.UNICODE)
    slug = re.sub(r"[\s_]+", "-", cleaned).strip("-")
    return slug or "nadpis"


def _clean_id(value: str) -> str:
    cleaned = re.sub(r"[^\w.-]+", "-", value, flags=re.UNICODE).strip("-.")
    return cleaned or "nadpis"


def _unique(anchor: str, used: set[str]) -> str:
    candidate = anchor
    number = 1
    while candidate in used:
        candidate = f"{anchor}-{number}"
        number += 1
    used.add(candidate)
    return candidate


def _render_fence(tokens, idx, options, env) -> str:
    token = tokens[idx]
    info = (token.info or "").strip()
    language = info.split(None, 1)[0] if info else ""
    return _highlighted(token.content, language)


def _render_code_block(tokens, idx, options, env) -> str:
    return _highlighted(tokens[idx].content, "")


def _highlighted(code: str, language: str) -> str:
    try:
        lexer = get_lexer_by_name(language) if language else TextLexer()
    except ClassNotFound:
        lexer = TextLexer()
    return highlight(code, lexer, _CODE_FORMATTER)


def _wrap(body: str, title: str | None) -> str:
    safe_title = html.escape(title or "Seshat")
    return (
        "<!DOCTYPE html>\n"
        '<html lang="cs">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>{safe_title}</title>\n"
        "</head>\n"
        "<body>\n"
        '<article class="markdown">\n'
        f"{body}"
        "</article>\n"
        "</body>\n"
        "</html>\n"
    )
