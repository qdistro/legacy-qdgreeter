"""GreetController — boot greeter state. Smaller surface than the
locker's controller because greetd handles PAM and session creation;
we only drive the round-trip and surface auth_messages."""

from __future__ import annotations

import asyncio
import logging
import os

from PySide6.QtCore import Property, QObject, Signal, Slot

from .greetd import GreetdClient

log = logging.getLogger("qdgreeter.controller")

DEFAULT_USER = os.environ.get("QDGREETER_USER", "admin")
DEFAULT_SESSION_CMD = os.environ.get(
    "QDGREETER_SESSION_CMD", "qdistro-admin-compositor"
).split()


class GreetController(QObject):
    succeeded = Signal()
    failed = Signal()
    _currentTextChanged = Signal()
    _statusMessageChanged = Signal()
    _busyChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._current_text = ""
        self._status_message = ""
        self._busy = False
        self._client = GreetdClient()
        self._loop = asyncio.new_event_loop()

    @Property(str, notify=_currentTextChanged)
    def currentText(self) -> str:
        return self._current_text

    @currentText.setter  # type: ignore[no-redef]
    def currentText(self, value: str) -> None:
        if value == self._current_text:
            return
        self._current_text = value
        self._currentTextChanged.emit()

    @Property(str, notify=_statusMessageChanged)
    def statusMessage(self) -> str:
        return self._status_message

    @Property(bool, notify=_busyChanged)
    def busy(self) -> bool:
        return self._busy

    def _set_status(self, msg: str) -> None:
        self._status_message = msg
        self._statusMessageChanged.emit()

    def _set_busy(self, value: bool) -> None:
        if value == self._busy:
            return
        self._busy = value
        self._busyChanged.emit()

    @Slot()
    def submit(self) -> None:
        """Drive a full greetd round-trip on the current password."""
        if self._busy:
            return
        password = self._current_text
        self._set_busy(True)
        self._loop.run_until_complete(self._auth_flow(password))
        self._set_busy(False)

    async def _auth_flow(self, password: str) -> None:
        try:
            await self._client.connect()
            reply = await self._client.create_session(DEFAULT_USER)
            while reply.get("type") == "auth_message":
                self._set_status(reply.get("auth_message", ""))
                reply = await self._client.post_auth(password)
                # greetd may issue further challenges (PIN, OTP); a
                # full UI would loop here. The MVP submits the same
                # password once.
            if reply.get("type") == "success":
                reply = await self._client.start_session(DEFAULT_SESSION_CMD)
                if reply.get("type") == "success":
                    self.succeeded.emit()
                    return
            self._set_status(reply.get("description", "Authentication failed"))
            self.failed.emit()
        except Exception as exc:  # noqa: BLE001
            log.exception("greetd flow raised")
            self._set_status(str(exc))
            self.failed.emit()
