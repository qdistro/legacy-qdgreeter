"""GreetController — boot greeter state.

Smaller surface than the locker's controller because greetd handles PAM
and session creation; we only drive the round-trip, surface auth_messages,
and forward errors to the UI.

Auth flow per `greetd-ipc(7)`:

  create_session(admin)
  loop:
    reply is success            → start_session(cmd) → success → succeeded
    reply is auth_message+secret → post_auth(password)
    reply is auth_message+info  → post_auth(None)              (display, continue)
    reply is error+auth_error   → cancel_session → failed (retryable)
    reply is error+error        → cancel_session → failed (fatal)
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading

from PySide6.QtCore import Property, QObject, Signal, Slot

from .greetd import GreetdClient, GreetdError

log = logging.getLogger("qdgreeter.controller")

DEFAULT_USER = os.environ.get("QDGREETER_USER", "admin")
# greetd execs this as the authenticated user; its lifetime IS the session
# lifetime. A bare `systemctl --user start qdwin-session.target` returns 0
# as soon as the job is enqueued — greetd would see a clean session end
# milliseconds after auth and recycle back to the greeter. The launcher
# (deploy/qdwin-session-launcher.sh) does the right `--wait` semantics and
# surfaces non-zero exits.
DEFAULT_SESSION_CMD = os.environ.get(
    "QDGREETER_SESSION_CMD", "/usr/local/bin/qdwin-session-launcher"
).split()


class GreetController(QObject):
    succeeded = Signal()
    failed = Signal()
    _currentTextChanged = Signal()
    _statusMessageChanged = Signal()
    _busyChanged = Signal()
    _usernameChanged = Signal()

    def __init__(
        self,
        parent: QObject | None = None,
        client: GreetdClient | None = None,
        session_cmd: list[str] | None = None,
        username: str | None = None,
    ) -> None:
        super().__init__(parent)
        self._username = username or DEFAULT_USER
        self._session_cmd = list(session_cmd) if session_cmd else list(DEFAULT_SESSION_CMD)
        self._current_text = ""
        self._status_message = ""
        self._busy = False
        self._client = client or GreetdClient()

    @Property(str, notify=_usernameChanged)
    def username(self) -> str:
        return self._username

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
        if msg == self._status_message:
            return
        self._status_message = msg
        self._statusMessageChanged.emit()

    def _set_busy(self, value: bool) -> None:
        if value == self._busy:
            return
        self._busy = value
        self._busyChanged.emit()

    @Slot()
    def submit(self) -> None:
        """Drive a full greetd round-trip on the current password.

        Runs the asyncio flow in a dedicated worker thread so the Qt
        event loop keeps spinning — otherwise `run_until_complete`
        would block QML signal delivery and any auth_message status
        updates would never paint.
        """
        if self._busy:
            return
        password = self._current_text
        self._set_busy(True)
        self._set_status("")

        def _run() -> None:
            try:
                asyncio.run(self._auth_flow(password))
            finally:
                # Mutating bound Qt properties from a foreign thread is
                # only safe for the small set of writes we do here
                # (no QML connections issue cross-thread signals
                # under PySide6's auto-connection rules) — but the
                # bool/string property writes will queue a notify
                # back onto the GUI thread, which is what we want.
                self._set_busy(False)

        threading.Thread(target=_run, name="qdgreeter-auth", daemon=True).start()

    async def _auth_flow(self, password: str) -> None:
        try:
            await self._client.connect()
            reply = await self._client.create_session(self._username)
            reply = await self._consume_auth_messages(reply, password)
            if reply.get("type") == "success":
                start = await self._client.start_session(self._session_cmd)
                if start.get("type") == "success":
                    self.succeeded.emit()
                    return
                await self._handle_error_reply(start)
            else:
                await self._handle_error_reply(reply)
        except GreetdError as exc:
            self._set_status(exc.description)
            await self._cancel_quiet()
            self.failed.emit()
        except (
            asyncio.IncompleteReadError,
            ConnectionResetError,
            BrokenPipeError,
        ):
            # The socket died mid-flow (typical when greetd closes after
            # an error reply, or restarts under load). The password may
            # well have been correct — labeling this "Authentication
            # failed" misleads the operator. Don't chase the closed
            # socket with cancel_session; just surface the disconnect.
            log.exception("greetd disconnected mid-flow")
            self._set_status("greetd disconnected; retry login")
            self.failed.emit()
        except Exception:  # noqa: BLE001
            # Don't include the password or any payload in the log;
            # `exc` is from socket / json layer, password isn't in it.
            # Don't echo `str(exc)` into the UI — it can carry socket
            # paths or reply bytes; keep details in the journal.
            log.exception("greetd flow raised")
            self._set_status("Authentication failed — see journalctl")
            await self._cancel_quiet()
            self.failed.emit()
        finally:
            await self._client.close()

    async def _consume_auth_messages(
        self, reply: dict, password: str
    ) -> dict:
        """Walk the auth_message ↔ post_auth_message_response loop.

        For `secret` we send the user-entered password (single attempt
        per submit() — repeated greetd prompts within the same auth_flow
        re-use the same string; if greetd needs a different challenge
        the MVP fails and the user retries).
        For `info` / `error` types we acknowledge with a null response
        so greetd can advance to the next stage.
        """
        while reply.get("type") == "auth_message":
            kind = reply.get("auth_message_type", "secret")
            message = reply.get("auth_message", "")
            if kind == "secret":
                reply = await self._client.post_auth(password)
            else:
                # visible / info / error: per greetd-ipc(7), `visible`
                # is a non-secret prompt whose response many PAM modules
                # log in plaintext. NEVER replay the password into one.
                # MVP-safe: display the message and ack with null so the
                # stack advances; the user can retry if they need a real
                # response collected.
                if message:
                    self._set_status(message)
                reply = await self._client.post_auth(None)
        return reply

    async def _handle_error_reply(self, reply: dict) -> None:
        if reply.get("type") == "error":
            description = reply.get("description", "Authentication failed")
            self._set_status(description)
        else:
            self._set_status(reply.get("description", "Authentication failed"))
        # Cancel the session so greetd returns to a clean state and the
        # next submit() can retry from create_session. Per greetd-ipc(7),
        # an `error` reply (auth_error or error) leaves the session in
        # an aborted state on greetd's side, but the client must still
        # send cancel_session for the slot to be reclaimable before the
        # next create_session. This matches the docstring contract at
        # the top of this module ("error+auth_error → cancel_session").
        # _cancel_quiet swallows any post-error socket errors.
        await self._cancel_quiet()
        self.failed.emit()

    async def _cancel_quiet(self) -> None:
        try:
            if self._client.connected:
                await self._client.cancel_session()
        except Exception:  # noqa: BLE001
            pass
