"""greetd JSON IPC client.

greetd exposes a length-prefixed JSON protocol over a UNIX socket at
$GREETD_SOCK. The protocol is documented in `greetd-ipc(7)`:

  → {"type":"create_session","username":"admin"}
  ← {"type":"success"}                                   # no auth needed
  ← {"type":"auth_message","auth_message_type":"secret","auth_message":"Password:"}
  → {"type":"post_auth_message_response","response":"hunter2"}
  ← {"type":"success"}
  → {"type":"start_session","cmd":["qdwin-session.target"],"env":[]}
  ← {"type":"success"}
  ← {"type":"error","error_type":"error|auth_error","description":"..."}

Length prefix is a 4-byte native-endian unsigned int (greetd's choice,
confirmed against greetd 0.10 source `greetd-ipc/src/codec.rs`).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import struct
from typing import Any

log = logging.getLogger("qdgreeter.greetd")

_HEADER_FMT = "=I"
_HEADER_SIZE = struct.calcsize(_HEADER_FMT)


def encode_frame(payload: dict[str, Any]) -> bytes:
    """Serialize a greetd JSON payload as a length-prefixed frame."""
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return struct.pack(_HEADER_FMT, len(body)) + body


def decode_frame(data: bytes) -> dict[str, Any]:
    """Inverse of encode_frame. Raises ValueError if the prefix lies."""
    if len(data) < _HEADER_SIZE:
        raise ValueError("frame shorter than header")
    (length,) = struct.unpack(_HEADER_FMT, data[:_HEADER_SIZE])
    body = data[_HEADER_SIZE : _HEADER_SIZE + length]
    if len(body) != length:
        raise ValueError(f"frame body length mismatch: header={length} actual={len(body)}")
    return json.loads(body)


class GreetdError(RuntimeError):
    """Raised when greetd returns an error reply.

    `error_type` distinguishes `auth_error` (wrong password — recoverable
    by cancel_session + retry) from `error` (protocol or backend failure).
    """

    def __init__(self, error_type: str, description: str) -> None:
        super().__init__(f"{error_type}: {description}")
        self.error_type = error_type
        self.description = description


class GreetdClient:
    def __init__(self, sock_path: str | None = None) -> None:
        self._path = sock_path or os.environ.get("GREETD_SOCK", "")
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    @property
    def connected(self) -> bool:
        return self._writer is not None

    async def connect(self) -> None:
        if not self._path:
            raise RuntimeError("GREETD_SOCK not set — qdgreeter must run under greetd")
        if self._writer is not None:
            return
        self._reader, self._writer = await asyncio.open_unix_connection(self._path)

    async def close(self) -> None:
        if self._writer is not None:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass
        self._reader = None
        self._writer = None

    async def _send(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self._writer is None or self._reader is None:
            raise RuntimeError("greetd client not connected; call connect() first")
        frame = encode_frame(payload)
        self._writer.write(frame)
        await self._writer.drain()
        header = await self._reader.readexactly(_HEADER_SIZE)
        (length,) = struct.unpack(_HEADER_FMT, header)
        body = await self._reader.readexactly(length)
        reply = json.loads(body)
        # Never log the payload itself — `post_auth_message_response`
        # carries the plaintext password. Log the type for tracing,
        # nothing more.
        log.debug("greetd: sent=%s recv=%s", payload.get("type"), reply.get("type"))
        return reply

    async def create_session(self, username: str) -> dict[str, Any]:
        return await self._send({"type": "create_session", "username": username})

    async def post_auth(self, response: str | None) -> dict[str, Any]:
        payload: dict[str, Any] = {"type": "post_auth_message_response"}
        # Per spec, response is optional (omitted for info / error
        # auth_message_types). null is the wire encoding; we map None → null.
        payload["response"] = response
        return await self._send(payload)

    async def start_session(
        self, cmd: list[str], env: list[str] | None = None
    ) -> dict[str, Any]:
        return await self._send(
            {"type": "start_session", "cmd": cmd, "env": env or []}
        )

    async def cancel_session(self) -> dict[str, Any]:
        return await self._send({"type": "cancel_session"})
