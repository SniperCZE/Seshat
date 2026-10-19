"""Vzhled dokumentu ve WebKitu. Barvy sledují světlý a tmavý režim Adwaity."""

from __future__ import annotations

from string import Template

from seshat.markdown import pygments_css

_LIGHT = {
    "scheme": "light",
    "bg": "#fafafa",
    "fg": "#241f31",
    "muted": "#5e5c64",
    "header": "#ebebeb",
    "border": "#d8d8dc",
    "accent": "#1c71d8",
    "mark": "#f8e45c",
    "mark_fg": "#241f31",
    "code_bg": "#f3f3f5",
}
_DARK = {
    "scheme": "dark",
    "bg": "#242424",
    "fg": "#ffffff",
    "muted": "#c0bfbc",
    "header": "#303030",
    "border": "#3d3d3d",
    "accent": "#78aeed",
    "mark": "#e5a50a",
    "mark_fg": "#1a1a1a",
    "code_bg": "#2d2d2d",
}

_CSS = Template(
    """
:root {
  color-scheme: $scheme;
  --bg: $bg;
  --fg: $fg;
  --muted: $muted;
  --header: $header;
  --border: $border;
  --accent: $accent;
  --mark: $mark;
  --mark-fg: $mark_fg;
  --code-bg: $code_bg;
}
html, body {
  background: var(--bg);
  color: var(--fg);
  margin: 0;
}
body {
  font-family: "Adwaita Sans", Cantarell, sans-serif;
  font-size: 17px;
  line-height: 1.6;
}
article.markdown {
  max-width: 74ch;
  margin: 2.25rem auto 4rem;
  padding: 0 1.75rem;
  overflow-wrap: break-word;
}
h1, h2, h3, h4, h5, h6 {
  line-height: 1.25;
  font-weight: 700;
  margin: 1.4em 0 0.5em;
}
h1 { font-size: 2rem; margin-top: 0; letter-spacing: -0.02em; }
h2 { font-size: 1.5rem; border-bottom: 1px solid var(--border); padding-bottom: 0.2em; }
h3 { font-size: 1.25rem; }
a { color: var(--accent); text-underline-offset: 0.15em; }
blockquote {
  margin: 1em 0;
  padding: 0.1em 0 0.1em 1em;
  border-left: 3px solid var(--accent);
  color: var(--muted);
}
code {
  font-family: "Adwaita Mono", "Source Code Pro", monospace;
  font-size: 0.92em;
}
:not(pre) > code {
  background: var(--code-bg);
  padding: 0.1em 0.35em;
  border-radius: 5px;
}
pre {
  font-family: "Adwaita Mono", "Source Code Pro", monospace;
  font-size: 0.92em;
  tab-size: 4;
  overflow: auto;
}
.highlight {
  margin: 1em 0;
  border-radius: 10px;
}
.highlight pre {
  margin: 0;
  padding: 0.9em 1em;
}
table {
  border-collapse: collapse;
  margin: 1em 0;
  max-width: 100%;
  display: block;
  overflow-x: auto;
}
th, td {
  border: 1px solid var(--border);
  padding: 0.4em 0.7em;
  vertical-align: top;
}
th { background: var(--header); }
.align-left { text-align: left; }
.align-center { text-align: center; }
.align-right { text-align: right; }
img { max-width: 100%; height: auto; }
hr, .footnotes-sep {
  border: 0;
  border-top: 1px solid var(--border);
  margin: 2em 0;
}
mark {
  background: var(--mark);
  color: var(--mark-fg);
  padding: 0 0.15em;
  border-radius: 3px;
}
kbd {
  font-family: "Adwaita Mono", monospace;
  border: 1px solid var(--border);
  border-bottom-width: 2px;
  border-radius: 4px;
  padding: 0.05em 0.35em;
  background: var(--header);
}
ul.contains-task-list { list-style: none; padding-left: 0.2em; }
li.task-list-item { list-style: none; }
li.task-list-item input {
  margin-right: 0.45em;
  accent-color: var(--accent);
  vertical-align: middle;
}
dt { font-weight: 700; margin-top: 0.8em; }
dd { margin: 0.2em 0 0.6em 1.2em; }
.footnotes {
  margin-top: 2.5em;
  border-top: 1px solid var(--border);
  color: var(--muted);
  font-size: 0.95em;
}
.footnote-backref { text-decoration: none; }
::selection { background: color-mix(in srgb, var(--accent) 28%, transparent); }
"""
)


def background_hex(dark: bool) -> str:
    return _DARK["bg"] if dark else _LIGHT["bg"]


def document_stylesheet(dark: bool) -> str:
    colors = _DARK if dark else _LIGHT
    return _CSS.substitute(colors) + "\n" + pygments_css(dark)
