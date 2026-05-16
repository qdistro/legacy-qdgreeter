"""qdgreeter entry point.

Run by greetd as the configured `greeter`. Inherits $GREETD_SOCK
from greetd; exits when the controller emits `succeeded` (greetd
then takes over and starts the session).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from .controller import GreetController

log = logging.getLogger("qdgreeter.app")

REPO_ROOT = Path(__file__).resolve().parent.parent
QML_ROOT = REPO_ROOT / "qml"


def _qdshell_import_path() -> Path | None:
    """qdgreeter is a sibling repo to qdshell under qdistro-org/.
    REPO_ROOT is the qdgreeter repo root, so qdshell lives at
    `../qdshell`. Override with QDGREETER_QDSHELL_PATH for non-
    standard layouts."""
    explicit = os.environ.get("QDGREETER_QDSHELL_PATH")
    if explicit:
        return Path(explicit)
    for candidate in (REPO_ROOT.parent / "qdshell", REPO_ROOT.parent.parent / "qdshell"):
        if (candidate / "Commons" / "Style.qml").exists():
            return candidate
    return None


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=os.environ.get("QDGREETER_LOG", "INFO"),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    argv = argv if argv is not None else sys.argv
    QCoreApplication.setOrganizationName("qdistro")
    QCoreApplication.setApplicationName("qdgreeter")
    app = QGuiApplication(argv)

    controller = GreetController()
    controller.succeeded.connect(app.quit)

    engine = QQmlApplicationEngine()
    qdshell = _qdshell_import_path()
    if qdshell:
        engine.addImportPath(str(qdshell))
        log.info("qdshell QML import path: %s", qdshell)
    engine.rootContext().setContextProperty("controller", controller)
    engine.load(QUrl.fromLocalFile(str(QML_ROOT / "Main.qml")))

    if not engine.rootObjects():
        log.error("QML failed to load")
        return 2

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
