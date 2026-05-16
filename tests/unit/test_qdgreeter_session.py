"""GreetController flow tests.

Drives the controller's _auth_flow against a scripted fake greetd
client (no Qt event loop needed — Signal connections still fire
synchronously when run on the calling thread).
"""

from __future__ import annotations

import asyncio
import os
import sys

import pytest


_HEADLESS = sys.platform.startswith("linux") and not os.environ.get("DISPLAY")
if _HEADLESS:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


PySide6 = pytest.importorskip("PySide6", reason="PySide6 not installed")
from PySide6.QtCore import QCoreApplication  # noqa: E402

from qdgreeter.controller import GreetController  # noqa: E402


class _FakeClient:
    """Stand-in for GreetdClient that replays a scripted exchange."""

    def __init__(self, replies: list[dict]) -> None:
        self._replies = list(replies)
        self.sent: list[dict] = []
        self._connected = False
        self.closed = False

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        self._connected = True

    async def close(self) -> None:
        self._connected = False
        self.closed = True

    async def create_session(self, username: str) -> dict:
        self.sent.append({"type": "create_session", "username": username})
        return self._replies.pop(0)

    async def post_auth(self, response):  # noqa: ANN001
        self.sent.append({"type": "post_auth_message_response", "response": response})
        return self._replies.pop(0)

    async def start_session(self, cmd, env=None):  # noqa: ANN001
        self.sent.append({"type": "start_session", "cmd": cmd, "env": env or []})
        return self._replies.pop(0)

    async def cancel_session(self) -> dict:
        self.sent.append({"type": "cancel_session"})
        if self._replies:
            return self._replies.pop(0)
        return {"type": "success"}


@pytest.fixture(scope="module")
def qapp():
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


def _run(controller: GreetController, password: str) -> None:
    controller._current_text = password
    asyncio.run(controller._auth_flow(password))


def test_success_path_emits_succeeded(qapp):
    client = _FakeClient(
        [
            {"type": "auth_message", "auth_message_type": "secret", "auth_message": "Password:"},
            {"type": "success"},
            {"type": "success"},
        ]
    )
    ctl = GreetController(client=client, session_cmd=["qdwin-session.target"])
    fired = {"ok": 0, "fail": 0}
    ctl.succeeded.connect(lambda: fired.__setitem__("ok", fired["ok"] + 1))
    ctl.failed.connect(lambda: fired.__setitem__("fail", fired["fail"] + 1))

    _run(ctl, "hunter2")

    assert fired == {"ok": 1, "fail": 0}
    assert [m["type"] for m in client.sent] == [
        "create_session",
        "post_auth_message_response",
        "start_session",
    ]
    assert client.sent[0]["username"] == "admin"
    assert client.sent[1]["response"] == "hunter2"
    assert client.sent[2]["cmd"] == ["qdwin-session.target"]
    assert client.closed


def test_auth_error_emits_failed_and_status(qapp):
    client = _FakeClient(
        [
            {"type": "auth_message", "auth_message_type": "secret", "auth_message": "Password:"},
            {
                "type": "error",
                "error_type": "auth_error",
                "description": "incorrect password",
            },
            {"type": "success"},  # reply to cancel_session
        ]
    )
    ctl = GreetController(client=client)
    fired = {"ok": 0, "fail": 0}
    ctl.succeeded.connect(lambda: fired.__setitem__("ok", fired["ok"] + 1))
    ctl.failed.connect(lambda: fired.__setitem__("fail", fired["fail"] + 1))

    _run(ctl, "wrong")

    assert fired == {"ok": 0, "fail": 1}
    assert ctl.statusMessage == "incorrect password"
    # The controller must call cancel_session so the next submit() can
    # retry from a clean greetd state.
    assert {"type": "cancel_session"} in client.sent


def test_fatal_error_propagates_description(qapp):
    client = _FakeClient(
        [
            {
                "type": "error",
                "error_type": "error",
                "description": "PAM module exploded",
            },
            {"type": "success"},
        ]
    )
    ctl = GreetController(client=client)
    fired = {"fail": 0}
    ctl.failed.connect(lambda: fired.__setitem__("fail", fired["fail"] + 1))

    _run(ctl, "anything")

    assert fired["fail"] == 1
    assert ctl.statusMessage == "PAM module exploded"


def test_info_auth_message_displays_then_continues(qapp):
    client = _FakeClient(
        [
            {
                "type": "auth_message",
                "auth_message_type": "info",
                "auth_message": "Last login: yesterday",
            },
            {
                "type": "auth_message",
                "auth_message_type": "secret",
                "auth_message": "Password:",
            },
            {"type": "success"},
            {"type": "success"},
        ]
    )
    ctl = GreetController(client=client)
    _run(ctl, "hunter2")

    # info acknowledges with null response, then the secret prompt
    # gets the real password.
    null_acks = [m for m in client.sent if m.get("response") is None]
    pw_acks = [m for m in client.sent if m.get("response") == "hunter2"]
    assert len(null_acks) == 1
    assert len(pw_acks) == 1


def test_username_defaults_to_admin(qapp):
    client = _FakeClient([{"type": "success"}, {"type": "success"}])
    ctl = GreetController(client=client)
    assert ctl.username == "admin"
    _run(ctl, "")
    assert client.sent[0]["username"] == "admin"
