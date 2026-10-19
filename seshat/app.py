"""Aplikace GNOME. Jedno okno, soubory z Nautilu i z příkazové řádky."""

from __future__ import annotations

import os
from pathlib import Path

import seshat.gi_versions  # noqa: F401
from gi.repository import Adw, Gdk, Gio, Gtk
from seshat import APP_ID
from seshat.window import SeshatWindow

_ICON_INDEX = """[Icon Theme]
Name=Hicolor
Comment=Seshat
Directories=scalable/apps

[scalable/apps]
Size=128
MinSize=16
MaxSize=256
Context=Applications
Type=Scalable
"""


class SeshatApplication(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_OPEN)

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)
        _register_source_icon()
        if self.lookup_action("quit") is None:
            action = Gio.SimpleAction.new("quit", None)
            action.connect("activate", lambda *_args: self.quit())
            self.add_action(action)
        self.set_accels_for_action("win.open", ["<Control>o"])
        self.set_accels_for_action("win.search", ["<Control>f"])
        self.set_accels_for_action("win.find-next", ["<Control>g", "F3"])
        self.set_accels_for_action("win.find-prev", ["<Control><Shift>g", "<Shift>F3"])
        self.set_accels_for_action("win.zoom-in", ["<Control>plus", "<Control>equal", "<Control>KP_Add"])
        self.set_accels_for_action("win.zoom-out", ["<Control>minus", "<Control>KP_Subtract"])
        self.set_accels_for_action("win.zoom-reset", ["<Control>0", "<Control>KP_0"])
        self.set_accels_for_action("win.outline", ["F9"])
        self.set_accels_for_action("app.quit", ["<Control>q"])

    def do_activate(self) -> None:
        self._window().present()

    def do_open(self, files, n_files, hint) -> None:
        window = self._window()
        window.present()
        if n_files:
            window.open_gfile(files[0])

    def _window(self) -> SeshatWindow:
        active = self.get_active_window()
        if isinstance(active, SeshatWindow):
            return active
        return SeshatWindow(application=self)


def _register_source_icon() -> None:
    icon = Path(__file__).resolve().parent.parent / "data" / f"{APP_ID}.svg"
    if not icon.is_file():
        return
    cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    theme_root = cache / "seshat" / "icons"
    apps = theme_root / "hicolor" / "scalable" / "apps"
    apps.mkdir(parents=True, exist_ok=True)
    index = theme_root / "hicolor" / "index.theme"
    if not index.is_file():
        index.write_text(_ICON_INDEX, encoding="utf-8")
    destination = apps / icon.name
    data = icon.read_bytes()
    if not destination.is_file() or destination.read_bytes() != data:
        destination.write_bytes(data)
    display = Gdk.Display.get_default()
    if display is None:
        return
    Gtk.IconTheme.get_for_display(display).add_search_path(str(theme_root))
