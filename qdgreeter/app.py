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

from PyQt6.QtCore import QCoreApplication, QUrl
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlApplicationEngine

from .controller import GreetController

log = logging.getLogger("qdgreeter.app")

REPO_ROOT = Path(__file__).resolve().parent.parent
QML_ROOT = REPO_ROOT / "qml"


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
    engine.rootContext().setContextProperty("controller", controller)
    engine.load(QUrl.fromLocalFile(str(QML_ROOT / "Main.qml")))

    if not engine.rootObjects():
        log.error("QML failed to load")
        return 2

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
