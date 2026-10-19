"""Spuštění aplikace."""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    from seshat.app import SeshatApplication

    app = SeshatApplication()
    return app.run(sys.argv if argv is None else argv)
