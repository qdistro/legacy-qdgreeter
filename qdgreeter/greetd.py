"""greetd JSON IPC client.

greetd exposes a length-prefixed JSON protocol over a UNIX socket at
$GREETD_SOCK. The protocol is documented in `greetd-ipc(7)`:

  → {"type":"create_session","username":"admin"}
  ← {"type":"success"}
  ← {"type":"auth_message","auth_message_type":"secret","auth_message":"Password:"}
  → {"type":"post_auth_message_response","response":"hunter2"}
  ← {"type":"success"}
  → {"type":"start_session","cmd":["qdistro-admin-compositor"],"env":[]}
  ← {"type":"success"}

This module wraps the socket so qdgreeter.controller can `await
client.create_session("admin")` etc.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import struct

log = logging.getLogger("qdgreeter.greetd")


class GreetdClient:
    def __init__(self, sock_path: str | None = None) -> None:
        self._path = sock_path or os.environ.get("GREETD_SOCK", "")
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    async def connect(self) -> None:
        if not self._path:
            raise RuntimeError("GREETD_SOCK not set — qdgreeter must run under greetd")
        self._reader, self._writer = await asyncio.open_unix_connection(self._path)

    async def _send(self, payload: dict) -> dict:
        assert self._writer and self._reader
        body = json.dumps(payload).encode("utf-8")
        self._writer.write(struct.pack("=I", len(body)) + body)
        await self._writer.drain()
        header = await self._reader.readexactly(4)
        (length,) = struct.unpack("=I", header)
        data = await self._reader.readexactly(length)
        reply = json.loads(data)
        log.debug("greetd: send=%r recv=%r", payload, reply)
        return reply

    async def create_session(self, username: str) -> dict:
        return await self._send({"type": "create_session", "username": username})

    async def post_auth(self, response: str | None) -> dict:
        return await self._send(
            {"type": "post_auth_message_response", "response": response}
        )

    async def start_session(self, cmd: list[str], env: list[str] | None = None) -> dict:
        return await self._send(
            {"type": "start_session", "cmd": cmd, "env": env or []}
        )

    async def cancel_session(self) -> dict:
        return await self._send({"type": "cancel_session"})
