"""Hlavní okno. Chrome je GTK, dokument kreslí WebKit a nejde ho upravovat."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

import seshat.gi_versions  # noqa: F401
from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk, Pango, WebKit
from seshat import __version__
from seshat.markdown import Heading, render_markdown
from seshat.style import background_hex, document_stylesheet

_MARKDOWN_SUFFIXES = {".md", ".markdown", ".mkd", ".mdown"}
_ZOOM_MIN = 0.5
_ZOOM_MAX = 2.5
_ZOOM_FACTOR = 1.1
_KEEP_MENU = {
    WebKit.ContextMenuAction.COPY,
    WebKit.ContextMenuAction.COPY_IMAGE_TO_CLIPBOARD,
    WebKit.ContextMenuAction.COPY_IMAGE_URL_TO_CLIPBOARD,
    WebKit.ContextMenuAction.COPY_LINK_TO_CLIPBOARD,
}
_SHORTCUTS = (
    ("<Control>o", "Otevřít"),
    ("<Control>f", "Hledat"),
    ("<Control>g", "Další výskyt"),
    ("<Control><Shift>g", "Předchozí výskyt"),
    ("<Control>plus", "Zvětšit"),
    ("<Control>minus", "Zmenšit"),
    ("<Control>0", "Výchozí velikost"),
    ("F9", "Osnova"),
    ("<Control>q", "Ukončit"),
)


class SeshatWindow(Adw.ApplicationWindow):
    def __init__(self, application: Adw.Application) -> None:
        super().__init__(application=application, title="Seshat", default_width=1100, default_height=760)
        self._source_path: Path | None = None
        self._document_uri: str | None = None
        self._pending_fragment: str | None = None
        self._zoom = 1.0

        self._content = WebKit.UserContentManager()
        self._webview = WebKit.WebView(
            user_content_manager=self._content,
            network_session=WebKit.NetworkSession.new_ephemeral(),
            settings=self._reader_settings(),
        )
        self._webview.set_editable(False)
        self._webview.set_vexpand(True)
        self._webview.set_zoom_level(self._zoom)
        self._webview.connect("decide-policy", self._on_decide_policy)
        self._webview.connect("load-changed", self._on_load_changed)
        self._webview.connect("context-menu", self._on_context_menu)

        self._outline = Gtk.ListBox()
        self._outline.add_css_class("navigation-sidebar")
        self._outline.set_selection_mode(Gtk.SelectionMode.NONE)
        self._outline.connect("row-activated", self._on_heading_activated)

        self._stack = Gtk.Stack()
        self._stack.add_named(self._empty_page(), "empty")
        # WebView si říká o šířku dokumentu a roztáhne okno. Obal mu dá jen
        # volné místo a posouvání nechá na něm.
        self._document_view = Gtk.ScrolledWindow(
            child=self._webview,
            hexpand=True,
            vexpand=True,
            propagate_natural_width=False,
            propagate_natural_height=False,
        )
        self._document_view.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.NEVER)
        self._stack.add_named(self._document_view, "document")
        self._stack.set_visible_child_name("empty")

        self._sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, visible=False)
        self._sidebar.set_size_request(260, -1)
        heading = Gtk.Label(label="Osnova", xalign=0)
        heading.add_css_class("title-4")
        heading.set_margin_top(12)
        heading.set_margin_bottom(6)
        heading.set_margin_start(12)
        heading.set_margin_end(12)
        self._sidebar.append(heading)
        outline_scroll = Gtk.ScrolledWindow(
            vexpand=True,
            child=self._outline,
            propagate_natural_width=False,
        )
        self._sidebar.append(outline_scroll)
        self._stack.set_hexpand(True)
        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        body.append(self._sidebar)
        body.append(self._stack)
        self._toasts = Adw.ToastOverlay(child=body)
        self._search_entry = Gtk.SearchEntry(placeholder_text="Hledat", hexpand=True)
        self._search_entry.connect("search-changed", self._on_search_changed)
        self._search_entry.connect("next-match", self._find_next)
        self._search_entry.connect("previous-match", self._find_previous)
        self._search_bar = Gtk.SearchBar(child=self._search_box())
        self._search_bar.connect_entry(self._search_entry)
        self._search_bar.set_key_capture_widget(self)

        header = Adw.HeaderBar()
        header.pack_start(Gtk.Button(
            icon_name="document-open-symbolic",
            tooltip_text="Otevřít",
            action_name="win.open",
        ))
        self._outline_button = Gtk.ToggleButton(
            icon_name="view-list-symbolic",
            tooltip_text="Osnova",
            visible=False,
        )
        self._outline_button.bind_property(
            "active",
            self._sidebar,
            "visible",
            GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE,
        )
        header.pack_start(self._outline_button)
        search_button = Gtk.ToggleButton(
            icon_name="system-search-symbolic",
            tooltip_text="Hledat",
        )
        self._search_bar.bind_property(
            "search-mode-enabled",
            search_button,
            "active",
            GObject.BindingFlags.BIDIRECTIONAL,
        )
        header.pack_end(Gtk.MenuButton(
            icon_name="open-menu-symbolic",
            tooltip_text="Nabídka",
            menu_model=self._menu(),
            primary=True,
        ))
        header.pack_end(search_button)

        top = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        top.append(header)
        top.append(self._search_bar)
        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(top)
        toolbar.set_content(self._toasts)
        self.set_content(toolbar)

        for name, callback in (
            ("open", self._open_dialog),
            ("search", self._start_search),
            ("find-next", self._find_next),
            ("find-prev", self._find_previous),
            ("zoom-in", self._zoom_in),
            ("zoom-out", self._zoom_out),
            ("zoom-reset", self._zoom_reset),
            ("outline", self._toggle_outline),
            ("shortcuts", self._show_shortcuts),
            ("about", self._show_about),
        ):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)

        for drop_type in (Gdk.FileList, Gio.File):
            target = Gtk.DropTarget.new(drop_type, Gdk.DragAction.COPY)
            target.connect("drop", self._on_drop)
            self.add_controller(target)

        style = Adw.StyleManager.get_default()
        style.connect("notify::dark", self._on_theme)
        self._apply_theme()

    def open_gfile(self, gfile: Gio.File, fragment: str | None = None) -> None:
        path = gfile.get_path()
        if not path:
            self._toast("Seshat umí otevřít jen místní soubory.")
            return
        self.open_path(Path(path), fragment)

    def open_path(self, path: Path, fragment: str | None = None) -> None:
        path = path.expanduser().resolve()
        if path.is_dir():
            self._toast("Seshat umí otevřít soubor, ne složku.")
            return
        if not path.is_file():
            self._toast(f"Soubor {path.name} nejde otevřít.")
            return
        try:
            source = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            self._toast("Soubor není text v kódování UTF-8.")
            return
        except OSError as exc:
            self._toast(exc.strerror or "Soubor se nepodařilo přečíst.")
            return
        try:
            document = render_markdown(source, path.parent)
        except Exception as exc:
            self._toast(f"Dokument nejde zobrazit: {exc}")
            return
        cache = _write_cache(path, document.html)
        self._source_path = path
        self._document_uri = cache.as_uri()
        self._pending_fragment = fragment or None
        self._show_outline(document.headings)
        self.set_title(f"{path.name} — Seshat")
        self._stack.set_visible_child_name("document")
        self._webview.load_uri(self._document_uri)

    def _reader_settings(self) -> WebKit.Settings:
        settings = WebKit.Settings()
        settings.set_enable_javascript(False)
        settings.set_enable_javascript_markup(False)
        settings.set_javascript_can_access_clipboard(False)
        settings.set_javascript_can_open_windows_automatically(False)
        settings.set_enable_developer_extras(False)
        settings.set_enable_write_console_messages_to_stdout(False)
        settings.set_allow_file_access_from_file_urls(True)
        settings.set_allow_universal_access_from_file_urls(False)
        settings.set_enable_media_stream(False)
        settings.set_enable_webrtc(False)
        settings.set_enable_dns_prefetching(False)
        settings.set_enable_back_forward_navigation_gestures(False)
        settings.set_enable_caret_browsing(False)
        settings.set_media_playback_requires_user_gesture(True)
        return settings

    def _empty_page(self) -> Adw.StatusPage:
        button = Gtk.Button(label="Otevřít", action_name="win.open", halign=Gtk.Align.CENTER)
        button.add_css_class("suggested-action")
        return Adw.StatusPage(
            icon_name="io.github.SniperCZE.Seshat",
            title="Otevři dokument",
            description="Vyber soubor Markdown a Seshat ho zobrazí.",
            child=button,
        )

    def _search_box(self) -> Gtk.Box:
        box = Gtk.Box(spacing=6)
        box.set_margin_start(6)
        box.set_margin_end(6)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        previous = Gtk.Button(
            icon_name="go-up-symbolic",
            tooltip_text="Předchozí výskyt",
            action_name="win.find-prev",
        )
        following = Gtk.Button(
            icon_name="go-down-symbolic",
            tooltip_text="Další výskyt",
            action_name="win.find-next",
        )
        box.append(self._search_entry)
        box.append(previous)
        box.append(following)
        return box

    def _menu(self) -> Gio.Menu:
        menu = Gio.Menu()
        view = Gio.Menu()
        view.append("Zvětšit", "win.zoom-in")
        view.append("Zmenšit", "win.zoom-out")
        view.append("Výchozí velikost", "win.zoom-reset")
        menu.append_section(None, view)
        menu.append("Klávesové zkratky", "win.shortcuts")
        menu.append("O aplikaci", "win.about")
        return menu

    def _open_dialog(self, *_args) -> None:
        dialog = Gtk.FileDialog(title="Otevřít Markdown")
        markdown = Gtk.FileFilter()
        markdown.set_name("Markdown")
        markdown.add_mime_type("text/markdown")
        markdown.add_pattern("*.md")
        markdown.add_pattern("*.markdown")
        markdown.add_pattern("*.mkd")
        everything = Gtk.FileFilter()
        everything.set_name("Všechny soubory")
        everything.add_pattern("*")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(markdown)
        filters.append(everything)
        dialog.set_filters(filters)
        dialog.set_default_filter(markdown)
        if self._source_path is not None:
            dialog.set_initial_folder(Gio.File.new_for_path(str(self._source_path.parent)))
        dialog.open(self, None, self._open_done)

    def _open_done(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            chosen = dialog.open_finish(result)
        except GLib.Error:
            return
        self.open_gfile(chosen)

    def _on_drop(self, _target, value, _x, _y) -> bool:
        if hasattr(value, "get_files"):
            files = value.get_files()
            if files:
                self.open_gfile(files[0])
                return True
            return False
        if hasattr(value, "get_path"):
            self.open_gfile(value)
            return True
        return False

    def _show_outline(self, headings: tuple[Heading, ...]) -> None:
        while (row := self._outline.get_row_at_index(0)) is not None:
            self._outline.remove(row)
        for heading in headings:
            item = Gtk.ListBoxRow()
            item.anchor = heading.anchor
            label = Gtk.Label(
                label=heading.text or heading.anchor or "Bez názvu",
                xalign=0,
                hexpand=True,
                ellipsize=Pango.EllipsizeMode.END,
                max_width_chars=28,
            )
            label.set_margin_start(12 + (heading.level - 1) * 12)
            label.set_margin_end(12)
            label.set_margin_top(6)
            label.set_margin_bottom(6)
            item.set_child(label)
            self._outline.append(item)
        visible = bool(headings)
        self._outline_button.set_visible(visible)
        self._sidebar.set_visible(visible)

    def _on_heading_activated(self, _outline, row) -> None:
        anchor = getattr(row, "anchor", "")
        if self._document_uri and anchor:
            self._webview.load_uri(self._fragment_uri(anchor))

    def _fragment_uri(self, anchor: str) -> str:
        return f"{self._document_uri}#{quote(anchor, safe='-_.~')}"

    def _start_search(self, *_args) -> None:
        self._search_bar.set_search_mode(True)
        self._search_entry.grab_focus()

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        finder = self._webview.get_find_controller()
        text = entry.get_text()
        if not text:
            finder.search_finish()
            return
        options = WebKit.FindOptions.CASE_INSENSITIVE | WebKit.FindOptions.WRAP_AROUND
        finder.search(text, options, 1000)

    def _find_next(self, *_args) -> None:
        if not self._search_entry.get_text():
            self._start_search()
            return
        self._webview.get_find_controller().search_next()

    def _find_previous(self, *_args) -> None:
        if not self._search_entry.get_text():
            self._start_search()
            return
        self._webview.get_find_controller().search_previous()

    def _zoom_in(self, *_args) -> None:
        self._set_zoom(self._zoom * _ZOOM_FACTOR)

    def _zoom_out(self, *_args) -> None:
        self._set_zoom(self._zoom / _ZOOM_FACTOR)

    def _zoom_reset(self, *_args) -> None:
        self._set_zoom(1.0)

    def _set_zoom(self, level: float) -> None:
        self._zoom = min(_ZOOM_MAX, max(_ZOOM_MIN, level))
        self._webview.set_zoom_level(self._zoom)

    def _toggle_outline(self, *_args) -> None:
        if self._outline_button.get_visible():
            self._sidebar.set_visible(not self._sidebar.get_visible())

    def _show_shortcuts(self, *_args) -> None:
        dialog = Adw.Dialog(title="Klávesové zkratky", content_width=440, content_height=460)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(12)
        box.set_margin_bottom(18)
        box.set_margin_start(18)
        box.set_margin_end(18)
        for accelerator, label in _SHORTCUTS:
            row = Gtk.Box(spacing=12)
            name = Gtk.Label(label=label, xalign=0, hexpand=True)
            row.append(name)
            row.append(Gtk.ShortcutLabel(accelerator=accelerator))
            box.append(row)
        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(Adw.HeaderBar())
        toolbar.set_content(Gtk.ScrolledWindow(child=box, propagate_natural_height=True))
        dialog.set_child(toolbar)
        dialog.present(self)

    def _show_about(self, *_args) -> None:
        about = Adw.AboutDialog(
            application_name="Seshat",
            application_icon="io.github.SniperCZE.Seshat",
            developer_name="Ondrej Flidr",
            developers=["Ondrej Flidr"],
            version=__version__,
            comments="Čtečka dokumentů Markdown.",
            website="https://github.com/SniperCZE/Seshat",
            issue_url="https://github.com/SniperCZE/Seshat/issues",
            copyright="© 2026 Ondrej Flidr",
            license_type=Gtk.License.MIT_X11,
        )
        about.present(self)

    def _on_theme(self, *_args) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        dark = Adw.StyleManager.get_default().get_dark()
        sheet = WebKit.UserStyleSheet.new(
            document_stylesheet(dark),
            WebKit.UserContentInjectedFrames.TOP_FRAME,
            WebKit.UserStyleLevel.USER,
            None,
            None,
        )
        self._content.remove_all_style_sheets()
        self._content.add_style_sheet(sheet)
        color = Gdk.RGBA()
        color.parse(background_hex(dark))
        self._webview.set_background_color(color)

    def _on_load_changed(self, _webview, event) -> None:
        if event != WebKit.LoadEvent.FINISHED or not self._pending_fragment or not self._document_uri:
            return
        fragment = self._pending_fragment
        self._pending_fragment = None
        self._webview.load_uri(self._fragment_uri(fragment))

    def _on_decide_policy(self, _webview, decision, decision_type) -> bool:
        if decision_type == WebKit.PolicyDecisionType.RESPONSE:
            decision.use()
            return True
        if decision_type not in {
            WebKit.PolicyDecisionType.NAVIGATION_ACTION,
            WebKit.PolicyDecisionType.NEW_WINDOW_ACTION,
        }:
            return False
        action = decision.get_navigation_action()
        uri = action.get_request().get_uri()
        if self._allow_navigation(uri, action.get_navigation_type()):
            decision.use()
            return True
        decision.ignore()
        GLib.idle_add(self._dispatch_uri, uri)
        return True

    def _allow_navigation(self, uri: str, navigation_type) -> bool:
        parsed = urlparse(uri)
        if parsed.scheme == "about":
            return navigation_type != WebKit.NavigationType.LINK_CLICKED
        return self._same_document(uri)

    def _same_document(self, uri: str) -> bool:
        if not self._document_uri:
            return False
        current = _file_path(self._document_uri)
        target = _file_path(uri)
        return current is not None and current == target

    def _dispatch_uri(self, uri: str) -> bool:
        parsed = urlparse(uri)
        if parsed.scheme in {"", "about", "javascript", "data", "vbscript"}:
            return False
        if parsed.scheme == "file":
            path = Path(unquote(parsed.path))
            if path.suffix.lower() in _MARKDOWN_SUFFIXES:
                self.open_path(path, parsed.fragment or None)
                return False
        self._launch_external(uri)
        return False

    def _launch_external(self, uri: str) -> None:
        try:
            Gio.AppInfo.launch_default_for_uri(uri, None)
        except GLib.Error as exc:
            self._toast(exc.message or "Odkaz se nepodařilo otevřít.")

    def _on_context_menu(self, _webview, menu, _hit) -> bool:
        for item in list(menu.get_items() or []):
            if item.is_separator() or item.get_stock_action() not in _KEEP_MENU:
                menu.remove(item)
        return False

    def _toast(self, message: str) -> None:
        self._toasts.add_toast(Adw.Toast.new(message))


def _write_cache(source: Path, page: str) -> Path:
    root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "seshat"
    root.mkdir(parents=True, exist_ok=True)
    name = hashlib.sha256(str(source).encode()).hexdigest() + ".html"
    destination = root / name
    destination.write_text(page, encoding="utf-8")
    return destination


def _file_path(uri: str) -> str | None:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return None
    return str(Path(unquote(parsed.path)).resolve())
