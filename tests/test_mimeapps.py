from pathlib import Path

from seshat.mimeapps import DESKTOP_ID, install, remove


def _load_postrm():
    script = Path("debian/seshat.postrm").read_text(encoding="utf-8")
    code = script.split("<< 'SESHAT_MIME'\n", 1)[1].split("\nSESHAT_MIME", 1)[0]
    code = code.replace("remove(SYSTEM_FILE)\n", "")
    namespace = {"__name__": "embedded"}
    exec(code, namespace)
    return namespace["install"], namespace["remove"]


def test_install_sets_default_and_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "mimeapps.list"
    path.write_text(
        "[Default Applications]\n"
        "text/plain=org.gnome.TextEditor.desktop;\n"
        "text/markdown=other.desktop;\n"
        "\n"
        "[Other]\n"
        "foo=bar\n",
        encoding="utf-8",
    )
    install(path)
    install(path)
    text = path.read_text(encoding="utf-8")
    assert text.count(f"text/markdown={DESKTOP_ID};other.desktop;") == 1
    assert f"text/x-markdown={DESKTOP_ID};" in text
    assert "text/plain=org.gnome.TextEditor.desktop;" in text
    assert "[Other]\nfoo=bar" in text
    assert "[Added Associations]" in text


def test_remove_keeps_other_handlers(tmp_path: Path) -> None:
    path = tmp_path / "mimeapps.list"
    install(path)
    original = path.read_text(encoding="utf-8")
    path.write_text(
        original.replace(
            f"text/markdown={DESKTOP_ID};",
            f"text/markdown={DESKTOP_ID};other.desktop;",
        ),
        encoding="utf-8",
    )
    remove(path)
    text = path.read_text(encoding="utf-8")
    assert DESKTOP_ID not in text
    assert "text/markdown=other.desktop;" in text


def test_remove_missing_file_does_nothing(tmp_path: Path) -> None:
    path = tmp_path / "missing" / "mimeapps.list"
    remove(path)
    assert not path.exists()


def test_postrm_copy_matches_module(tmp_path: Path) -> None:
    embedded_install, embedded_remove = _load_postrm()
    module_path = tmp_path / "module.list"
    embedded_path = tmp_path / "embedded.list"
    seed = "[Default Applications]\ntext/plain=editor.desktop;\n"
    module_path.write_text(seed, encoding="utf-8")
    embedded_path.write_text(seed, encoding="utf-8")
    install(module_path)
    embedded_install(embedded_path)
    assert module_path.read_text(encoding="utf-8") == embedded_path.read_text(encoding="utf-8")
    remove(module_path)
    embedded_remove(embedded_path)
    assert module_path.read_text(encoding="utf-8") == embedded_path.read_text(encoding="utf-8")
