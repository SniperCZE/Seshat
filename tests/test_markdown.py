from pathlib import Path

from seshat.markdown import render_markdown


def _page(source: str, base: Path) -> str:
    return render_markdown(source, base).html


def test_basic_markup(tmp_path: Path) -> None:
    html = _page(
        "# Nadpis\n\nOdstavec s **tučným** a *kurzívou* a `kódem`.\n\n"
        "> citace\n\n"
        "- jedna\n- dvě\n\n"
        "1. první\n2. druhý\n\n"
        "---\n",
        tmp_path,
    )
    assert "<h1" in html and "Nadpis" in html
    assert "<strong>tučným</strong>" in html
    assert "<em>kurzívou</em>" in html
    assert "<code>kódem</code>" in html
    assert "<blockquote>" in html and "citace" in html
    assert "<ul>" in html and "<ol>" in html
    assert "<hr" in html


def test_soft_and_hard_line_breaks(tmp_path: Path) -> None:
    soft = _page("řádek\nkonec\n", tmp_path)
    hard = _page("řádek  \nkonec\n", tmp_path)
    assert "<br" not in soft
    assert "<br" in hard


def test_table_alignment(tmp_path: Path) -> None:
    html = _page(
        "| Syntax | Description | Test Text |\n"
        "| :--- | :---: | ---: |\n"
        "| Header | Title | Here |\n",
        tmp_path,
    )
    assert "align-left" in html
    assert "align-center" in html
    assert "align-right" in html
    assert "text-align" not in html
    assert "<table>" in html


def test_task_list_is_read_only(tmp_path: Path) -> None:
    html = _page("- [x] Hotovo\n- [ ] Zbývá\n", tmp_path)
    assert html.count('type="checkbox"') == 2
    assert html.count('disabled="disabled"') == 2
    assert 'checked="checked"' in html
    assert "Hotovo" in html and "Zbývá" in html


def test_strikethrough_subscript_superscript_and_highlight(tmp_path: Path) -> None:
    html = _page(
        "~~The world is flat.~~ H~2~O a X^2^ a ==very important words==.\n",
        tmp_path,
    )
    assert "<s>The world is flat.</s>" in html
    assert "H<sub>2</sub>O" in html
    assert "X<sup>2</sup>" in html
    assert "<mark>very important words</mark>" in html


def test_markers_inside_code_stay_literal(tmp_path: Path) -> None:
    html = _page("`H~2~O` a `==ne==`\n", tmp_path)
    assert "<sub>" not in html
    assert "<mark>" not in html
    assert "H~2~O" in html


def test_footnote_and_definition_list(tmp_path: Path) -> None:
    html = _page(
        "Věta s poznámkou.[^1]\n\n"
        "[^1]: Text poznámky.\n\n"
        "First Term\n"
        ": Definice pojmu.\n",
        tmp_path,
    )
    assert 'href="#fn1"' in html
    assert 'class="footnotes"' in html
    assert "Text poznámky." in html
    assert "<dt>First Term</dt>" in html
    assert "<dd>Definice pojmu.</dd>" in html


def test_autolink_and_relative_markdown_link(tmp_path: Path) -> None:
    html = _page(
        "http://www.example.com a [další](dalsi.md#cast)\n",
        tmp_path,
    )
    assert 'href="http://www.example.com"' in html
    target = (tmp_path / "dalsi.md").resolve().as_uri()
    assert f'href="{target}#cast"' in html


def test_images_keep_remote_and_absolutize_local(tmp_path: Path) -> None:
    html = _page(
        '![Alt](img/pic.png "Titulek")\n\n'
        "![Web](https://example.com/a.png)\n",
        tmp_path,
    )
    local = (tmp_path / "img" / "pic.png").resolve().as_uri()
    assert f'src="{local}"' in html
    assert 'alt="Alt"' in html
    assert 'title="Titulek"' in html
    assert 'src="https://example.com/a.png"' in html


def test_emoji_shortcodes(tmp_path: Path) -> None:
    html = _page("Gone camping! :tent: a :not-an-emoji: a `:joy:`\n", tmp_path)
    assert "⛺" in html
    assert ":not-an-emoji:" in html
    assert ":joy:" in html


def test_fenced_and_indented_code(tmp_path: Path) -> None:
    html = _page(
        "```json\n{ \"a\": 1 }\n```\n\n"
        "    prosty\n",
        tmp_path,
    )
    assert 'class="highlight"' in html
    assert html.count('class="highlight"') == 2
    assert "prosty" in html


def test_custom_and_generated_heading_ids(tmp_path: Path) -> None:
    document = render_markdown(
        "# Nadpis stránky\n\n## Část {#cast}\n\n# Nadpis stránky\n",
        tmp_path,
    )
    assert [item.anchor for item in document.headings] == [
        "nadpis-stranky",
        "cast",
        "nadpis-stranky-1",
    ]
    assert document.headings[1].text == "Část"
    assert document.title == "Nadpis stránky"
    assert "{#cast}" not in document.html
    assert 'id="cast"' in document.html


def test_script_iframe_and_event_handlers_are_removed(tmp_path: Path) -> None:
    html = _page(
        "před\n\n"
        "<script>alert(1)</script>\n\n"
        '<img src="a.png" onerror="alert(1)">\n\n'
        '<a href="javascript:alert(1)">odkaz</a>\n\n'
        '<iframe src="http://evil.test"></iframe>\n\n'
        "po\n",
        tmp_path,
    )
    lowered = html.lower()
    assert "<script" not in lowered
    assert "onerror" not in lowered
    assert "javascript:" not in lowered
    assert "<iframe" not in lowered
    assert "evil.test" not in lowered
    assert "alert" not in lowered
    assert "před" in html and "po" in html and "odkaz" in html
    local = (tmp_path / "a.png").resolve().as_uri()
    assert f'src="{local}"' in html
