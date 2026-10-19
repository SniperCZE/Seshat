# Seshat

Nativní čtečka dokumentů Markdown pro GNOME. Soubor otevře naformátovaný a neupravuje ho.

Okno je GTK 4 a libadwaita. Samotný dokument kreslí WebKitGTK. JavaScript ve stránce je vypnutý.

## Co umí zobrazit

Základní syntaxe i rozšíření z [Markdown Guide](https://www.markdownguide.org/basic-syntax/): nadpisy, odstavce, tučné a kurzíva, citace, seznamy, kód, odkazy, obrázky, vodorovná čára, tabulky včetně zarovnání, ohrazené bloky kódu se zvýrazněním, poznámky pod čarou, vlastní i automatická `id` nadpisů, definiční seznamy, přeškrtnutí, seznamy úkolů, emoji (`:tent:`), zvýraznění `==slovy==`, dolní a horní index, automatické URL.

Surové HTML v dokumentu se vykreslí, ale značky `script`, `iframe`, `object` a podobné se zahodí. Seznam úkolů nejde odškrtnout.

Kliknutí na odkaz `http`, `https` nebo `mailto` otevře systémovou aplikaci. Odkaz na jiný soubor `.md` se načte v Seshat. Osnova vlevo skáče na nadpisy. Hledání je Ctrl+F, přiblížení Ctrl++ a Ctrl+−.

## Spuštění ze zdrojů

Na Debianu 13:

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-webkit-6.0 \
  python3-markdown-it python3-mdit-py-plugins python3-pygments python3-emoji
python3 -m seshat
python3 -m seshat dokument.md
```

## Instalace balíčku

GitHub Actions na větvi `master` sestaví `seshat_*.deb` a vystaví ho jako GitHub Release `v<verze>`, třeba `v0.1.0-1`. Stejný release vznikne i po tagu `v*`.

```bash
sudo apt install ./seshat_0.1.0-1_all.deb
```

Balíček závisí na GTK 4, libadwaitě, WebKitGTK 6 a pythoních balíčcích z Debianu. Pip na cílovém systému nepotřebuje.

## Asociace souborů

Po instalaci se Seshat zapíše jako výchozí aplikace pro `text/markdown` a `text/x-markdown` do `/etc/xdg/mimeapps.list`. Týká se to souborů `.md`, `.mkd` a `.markdown`. Osobní `~/.config/mimeapps.list` má přednost: kdo už má Markdown přiřazený jiné aplikaci, o výběr nepřijde.

Odinstalace záznam zase odebere.

## Sestavení balíčku

```bash
dpkg-buildpackage -us -uc -b
```

Na čistém stromu ve formátu `3.0 (quilt)` je vedle zdrojů potřeba i `../seshat_0.1.0.orig.tar.gz`. Workflow ho před sestavením vytvoří.

## Licence

MIT, Ondrej Flidr.
