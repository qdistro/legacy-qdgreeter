"""eglfs software-cursor configuration tests.

Guards the regression where qdgreeter's eglfs/KMS cursor was invisible on
the VM template: the GPU does not scan out a hardware cursor plane, so the
greeter had no visible mouse cursor. The fix forces Qt's GL (software)
cursor via a KMS config with ``"hwcursor": false``. These tests pin that
behaviour so a future env/refactor cannot silently drop it.

See qdgreeter/qdgreeter/app.py::_ensure_eglfs_software_cursor and
qdistro deploy/greetd-config.toml.
"""

from __future__ import annotations

import json
import os
import sys

import pytest


_HEADLESS = sys.platform.startswith("linux") and not os.environ.get("DISPLAY")
if _HEADLESS:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


pytest.importorskip("PyQt6", reason="PyQt6 not installed")

import qdgreeter.app as app  # noqa: E402
from qdgreeter.app import _ensure_eglfs_software_cursor  # noqa: E402


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    """Isolate the env vars the helper reads/writes, with a writable runtime dir.

    Forces the virtualization gate ON by default so the cursor-writing
    tests exercise the VM path; the bare-metal branch has its own test.
    """
    monkeypatch.delenv("QT_QPA_EGLFS_KMS_CONFIG", raising=False)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr(app, "_running_virtualized", lambda: True)
    return tmp_path


@pytest.mark.cheat_aware(
    protects="on eglfs, qdgreeter writes a KMS config that disables the "
    "hardware cursor so the GL/software cursor renders (visible in VMs)",
    severity="high",
    cheats=[
        "assert only that the env var is set, never that hwcursor is false",
        "skip the JSON content check so an empty/garbage config passes",
    ],
    consequence="the greeter ships with an invisible mouse cursor again on "
    "any GPU that does not scan out a hardware cursor plane",
)
def test_eglfs_platform_forces_software_cursor(monkeypatch, clean_env):
    monkeypatch.setenv("QT_QPA_PLATFORM", "eglfs")

    _ensure_eglfs_software_cursor()

    cfg_path = os.environ.get("QT_QPA_EGLFS_KMS_CONFIG")
    assert cfg_path, "QT_QPA_EGLFS_KMS_CONFIG was not set"
    assert cfg_path.startswith(str(clean_env)), "config not written under XDG_RUNTIME_DIR"
    cfg = json.loads(open(cfg_path).read())
    assert cfg.get("hwcursor") is False, f"hardware cursor not disabled: {cfg!r}"
    # No hardcoded device/outputs — Qt must keep auto-probing the DRM node
    # so the config is portable across the VM (card1) and real hardware.
    assert "device" not in cfg
    assert "outputs" not in cfg


def test_non_eglfs_platform_is_noop(monkeypatch, clean_env):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    _ensure_eglfs_software_cursor()

    assert "QT_QPA_EGLFS_KMS_CONFIG" not in os.environ
    # nothing written
    assert not list(clean_env.iterdir())


def test_empty_platform_is_noop(monkeypatch, clean_env):
    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)

    _ensure_eglfs_software_cursor()

    assert "QT_QPA_EGLFS_KMS_CONFIG" not in os.environ


@pytest.mark.cheat_aware(
    protects="an operator-supplied QT_QPA_EGLFS_KMS_CONFIG is never clobbered",
    severity="medium",
    cheats=["overwrite the existing config path unconditionally"],
    consequence="a hand-tuned KMS config (custom outputs, modes, device) is "
    "silently replaced, breaking bespoke deployments",
)
def test_existing_kms_config_is_respected(monkeypatch, clean_env):
    monkeypatch.setenv("QT_QPA_PLATFORM", "eglfs")
    monkeypatch.setenv("QT_QPA_EGLFS_KMS_CONFIG", "/etc/operator-kms.json")

    _ensure_eglfs_software_cursor()

    assert os.environ["QT_QPA_EGLFS_KMS_CONFIG"] == "/etc/operator-kms.json"
    # our default file must not have been written
    assert not (clean_env / "qdgreeter-eglfs-kms.json").exists()


def test_unwritable_runtime_dir_does_not_raise(monkeypatch):
    """A read-only XDG_RUNTIME_DIR must degrade gracefully (warn, no crash),
    not take the whole greeter down before it can render."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "eglfs")
    monkeypatch.delenv("QT_QPA_EGLFS_KMS_CONFIG", raising=False)
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/proc/nonexistent/cannot/write")
    monkeypatch.setattr(app, "_running_virtualized", lambda: True)

    # must not raise
    _ensure_eglfs_software_cursor()

    # on failure we leave the env unset rather than pointing at a missing file
    assert "QT_QPA_EGLFS_KMS_CONFIG" not in os.environ


def test_bare_metal_keeps_hardware_cursor(monkeypatch, clean_env):
    """On real hardware the eglfs hardware cursor works and is cheaper —
    mirror the wlroots precedent (deploy/qdistro-startlxqtwayland.sh) and
    only force the software cursor under virtualization."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "eglfs")
    monkeypatch.setattr(app, "_running_virtualized", lambda: False)

    _ensure_eglfs_software_cursor()

    assert "QT_QPA_EGLFS_KMS_CONFIG" not in os.environ
    assert not (clean_env / "qdgreeter-eglfs-kms.json").exists()


def test_virt_detection_failure_defaults_to_software_cursor(monkeypatch, clean_env):
    """If systemd-detect-virt is missing/errors, prefer a guaranteed-visible
    software cursor over a possibly-invisible hardware one — an unusable
    login screen is the worse outcome."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "eglfs")

    def boom(*a, **k):
        raise FileNotFoundError("systemd-detect-virt")

    monkeypatch.setattr(app.subprocess, "run", boom)

    _ensure_eglfs_software_cursor()

    assert os.environ.get("QT_QPA_EGLFS_KMS_CONFIG")
    cfg = json.loads(open(os.environ["QT_QPA_EGLFS_KMS_CONFIG"]).read())
    assert cfg.get("hwcursor") is False
