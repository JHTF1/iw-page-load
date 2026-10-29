from __future__ import annotations

import socket
import sys
from pathlib import Path

import pytest

from src.measure import cdp


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_find_chrome_accepts_existing_binary():
    assert cdp.find_chrome(sys.executable) == sys.executable


def test_find_chrome_rejects_missing_binary(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        cdp.find_chrome(str(tmp_path / "chrome.exe"))


def test_session_rejects_missing_binary(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        cdp.ChromeSession(binary=str(tmp_path / "chrome.exe"))


def test_chrome_flags_disable_quic():
    assert "--disable-quic" in cdp._CHROME_FLAGS


def test_next_id_increments():
    session = cdp.ChromeSession(binary=sys.executable)
    assert [session._next_id() for _ in range(3)] == [1, 2, 3]


def test_wait_port_free_when_nothing_listens():
    session = cdp.ChromeSession(binary=sys.executable, port=_free_port())
    assert session._wait_port_free(timeout_s=0.5) is True
