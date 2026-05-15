# qdgreeter

Graphical boot greeter for qdistro. Drop-in replacement for `tuigreet`
on the admin TTY, sharing the Python + QML stack and the qdshell
styling story with sibling repos
[qdlocker](https://codeberg.org/qdistro/qdlocker) and
[qdshell](https://codeberg.org/qdistro/qdshell).

## Relationship to qdlocker

Per `qdistro/doc/sessions.md`, the compositor on tty3 starts in
**locked** state — first-boot admin auth and runtime re-auth could
both live in qdlocker. We're splitting them:

| Path        | When                                          | Process    |
|-------------|-----------------------------------------------|------------|
| Boot login  | tty3, before the compositor's first frame     | qdgreeter  |
| Idle / lid / manual lock | Anytime the compositor is running | qdlocker   |

qdgreeter exits after a successful auth and hands off to qdshell +
qdlocker; from that point on, the compositor stays locked until
qdlocker calls `set_locked(0)`.

The split exists so:

- Boot can have welcome / "first run" branding distinct from the
  runtime lock chrome.
- Boot auth can go through `greetd`'s JSON IPC (which handles
  session-creation, environment, PAM auth) without qdlocker
  needing to know anything about session launch.
- A future multi-admin world could swap greeter implementations
  without touching the locker.

## Layout

Same shape as qdlocker:

```
qdgreeter/
├── qdgreeter/
│   ├── app.py           QGuiApplication + QML
│   ├── controller.py    GreetController (greetd JSON client)
│   ├── greetd.py        UNIX-socket JSON protocol to greetd
│   └── keysyms.py
├── qml/
│   ├── Main.qml
│   └── GreetUI.qml      Reuses qs.Commons / qs.Widgets
├── systemd/
│   └── qdgreeter.service
└── pyproject.toml
```

Reuses qdshell's `qs.Commons` / `qs.Widgets` via the same
QDLOCKER_QDSHELL_PATH-style env override (here:
`QDGREETER_QDSHELL_PATH`).

## Status

Skeleton only — see `qdgreeter/app.py` + `qml/GreetUI.qml`. The
greetd JSON protocol client is the work item:
<https://man.sr.ht/~kennylevinsen/greetd/greetd-ipc.7.scd>.
Auth flow shape is documented in `qdgreeter/greetd.py`.

## Why not just reuse qdlocker on first boot?

We considered it. The downside is operational: qdlocker would have
to know whether it's "fresh boot" or "runtime re-lock" to pick
branding and decide whether to spawn a session vs. reuse one. The
runtime branch is *much* simpler (PAM auth → set_locked(0)), so
keeping greetd integration in a separate binary preserves that.
