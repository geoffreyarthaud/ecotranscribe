"""Point d'entrée `ecotranscribe-desktop` et mode `--diagnose`."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from ecotranscribe.core.config import APP_NAME, APP_SLUG
from ecotranscribe.gui.availability import collect_diagnostic
from ecotranscribe.gui.dialogs import QtDialogService
from ecotranscribe.gui.logging_setup import configure_logging
from ecotranscribe.gui.main_window import MainWindow
from ecotranscribe.gui.pricing import OpenRouterPricingClient
from ecotranscribe.gui.settings import AppSettings, KeyringStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ecotranscribe-desktop",
        description="EcoTranscribe Desktop — édition lite OpenRouter.",
    )
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="Écrit un JSON de diagnostic et quitte sans fenêtre.",
    )
    parser.add_argument(
        "--diagnose-output",
        type=Path,
        default=None,
        help="Écrit aussi le diagnostic dans ce fichier.",
    )
    return parser


def run_diagnostic(output: Path | None) -> int:
    configure_logging()
    diagnostic = collect_diagnostic()
    text = json.dumps(diagnostic, ensure_ascii=False, indent=2)
    if sys.stdout is not None:
        print(text)
    if output is not None:
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    ok = bool(diagnostic.get("ffmpeg_path")) and bool(
        diagnostic.get("ffprobe_path")
    )
    return 0 if ok else 1


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.diagnose:
        return run_diagnostic(args.diagnose_output)

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_SLUG)

    configure_logging()
    window = MainWindow(
        settings=AppSettings(QSettings()),
        key_store=KeyringStore(),
        dialogs=QtDialogService(),
        pricing_client=OpenRouterPricingClient(),
    )
    app.aboutToQuit.connect(window.save_settings)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
