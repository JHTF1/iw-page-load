"""sniffer 的单元测试：URL 解析、IP 选择、curl 参数与抓包编排。"""

from __future__ import annotations

import socket
import subprocess
import time
from types import SimpleNamespace

import pytest

from src.capture import sniffer as sniffer_module
from src.capture.sniffer import capture_url, resolve_server_ip


class FakeSniffer:
    def __init__(self, results=None, exception=None, start_error=None, **kwargs):
        self.kwargs = kwargs
        self.results = [object()] if results is None else results
        self.exception = exception
        self.start_error = start_error
        self.running = False
        self.stopped = False

    def start(self):
        if self.start_error is not None:
            raise self.start_error
        self.running = True

    def stop(self):
        self.running = False
        self.stopped = True


class FakeTime:
    @staticmethod
    def sleep(seconds):
        return None

    @staticmethod
    def monotonic():
        return time.monotonic()


def install_capture_fakes(monkeypatch, *, sniffer_factory=None, run_result=None):
    created = []
    captured = {"commands": [], "pcap": None}

    def factory(**kwargs):
        instance = (sniffer_factory or FakeSniffer)(**kwargs)
        created.append(instance)
        return instance

    def fake_run(command, **kwargs):
        captured["commands"].append(command)
        if isinstance(run_result, Exception):
            raise run_result
        if callable(run_result):
            return run_result(command, **kwargs)
        if run_result is not None:
            return run_result
        return SimpleNamespace(returncode=0, stderr=b"")

    def fake_wrpcap(path, packets):
        captured["pcap"] = (path, list(packets))

    monkeypatch.setattr(sniffer_module, "AsyncSniffer", factory)
    monkeypatch.setattr(sniffer_module, "_resolve_addresses", lambda host, port: ["203.0.113.9"])
    monkeypatch.setattr(sniffer_module, "load_settings", lambda: {"capture": {"curl_timeout_s": 10}})
    monkeypatch.setattr(sniffer_module.subprocess, "run", fake_run)
    monkeypatch.setattr(sniffer_module, "wrpcap", fake_wrpcap)
    monkeypatch.setattr(sniffer_module, "time", FakeTime)
    return created, captured


def test_parse_target_defaults_https_port():
    assert sniffer_module._parse_target("https://www.baidu.com/") == ("www.baidu.com", 443)


def test_parse_target_honours_custom_port():
    assert sniffer_module._parse_target("http://example.com:8080/a") == ("example.com", 8080)


def test_parse_target_rejects_unsupported_scheme():
    with pytest.raises(ValueError, match="http"):
        sniffer_module._parse_target("ftp://example.com/")


def test_parse_target_rejects_missing_hostname():
    with pytest.raises(ValueError, match="hostname"):
        sniffer_module._parse_target("https:///path")


def test_preferred_address_prefers_ipv4():
    assert sniffer_module._preferred_address(["2001:db8::1", "1.2.3.4"]) == "1.2.3.4"


def test_preferred_address_falls_back_to_ipv6():
    assert sniffer_module._preferred_address(["2001:db8::1"]) == "2001:db8::1"


def test_resolve_addresses_dedupes_in_order(monkeypatch):
    def fake_getaddrinfo(host, port, type=None):
        return [
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2001:db8::1", port, 0, 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.2.3.4", port)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.2.3.4", port)),
        ]

    monkeypatch.setattr(sniffer_module.socket, "getaddrinfo", fake_getaddrinfo)

    assert sniffer_module._resolve_addresses("example.com", 443) == ["2001:db8::1", "1.2.3.4"]


def test_resolve_addresses_rejects_empty_result(monkeypatch):
    monkeypatch.setattr(sniffer_module.socket, "getaddrinfo", lambda *args, **kwargs: [])

    with pytest.raises(RuntimeError, match="解析"):
        sniffer_module._resolve_addresses("example.com", 443)


def test_resolve_server_ip_prefers_ipv4(monkeypatch):
    monkeypatch.setattr(
        sniffer_module,
        "_resolve_addresses",
        lambda host, port: ["2001:db8::1", "1.2.3.4"],
    )

    assert resolve_server_ip("https://example.com/") == "1.2.3.4"


def test_build_bpf_filter_uses_host():
    assert sniffer_module._build_bpf_filter("1.2.3.4") == "tcp and host 1.2.3.4"
    assert sniffer_module._build_bpf_filter("2001:db8::1") == "tcp and host 2001:db8::1"


def test_curl_command_enforces_single_connection_and_proxy_bypass():
    command = sniffer_module._curl_command("https://www.baidu.com/", "110.242.68.66", 443, 8.0)

    assert command[0] == "curl"
    assert "--http1.1" in command
    assert "-L" not in command
    assert command[command.index("--noproxy") + 1] == "*"
    assert command[command.index("--resolve") + 1] == "www.baidu.com:443:110.242.68.66"
    assert command[command.index("--max-time") + 1] == "8"
    assert command[-1] == "https://www.baidu.com/"


def test_curl_command_marks_windows_revocation_best_effort(monkeypatch):
    monkeypatch.setattr(sniffer_module.platform, "system", lambda: "Windows")

    command = sniffer_module._curl_command("https://example.com/", "1.2.3.4", 443, 8.0)

    assert "--ssl-revoke-best-effort" in command


def test_curl_command_omits_windows_flag_on_linux(monkeypatch):
    monkeypatch.setattr(sniffer_module.platform, "system", lambda: "Linux")

    command = sniffer_module._curl_command("https://example.com/", "1.2.3.4", 443, 8.0)

    assert "--ssl-revoke-best-effort" not in command


def test_curl_command_brackets_ipv6_resolve():
    command = sniffer_module._curl_command("https://example.com/", "2001:db8::1", 443, 8.0)

    assert command[command.index("--resolve") + 1] == "example.com:443:[2001:db8::1]"


def test_curl_command_skips_resolve_for_ip_literal():
    command = sniffer_module._curl_command("https://93.184.216.34/", "93.184.216.34", 443, 8.0)

    assert "--resolve" not in command


def test_curl_timeout_is_capped_by_duration_and_config():
    assert sniffer_module._curl_timeout(8.0, 10.0) == 8.0
    assert sniffer_module._curl_timeout(20.0, 10.0) == 10.0
    assert sniffer_module._curl_timeout(0.1, 10.0) == 0.5


def test_capture_url_runs_curl_under_sniffer(tmp_path, monkeypatch):
    created, captured = install_capture_fakes(monkeypatch)

    out_pcap = tmp_path / "site.pcap"
    result = capture_url("https://example.com/", out_pcap, duration_s=5.0)

    assert result == out_pcap
    assert created[0].kwargs["filter"] == "tcp and host 203.0.113.9"
    assert created[0].kwargs["store"] is True
    assert created[0].stopped is True
    assert captured["pcap"][0] == str(out_pcap)
    assert captured["pcap"][1] == created[0].results
    assert "example.com:443:203.0.113.9" in captured["commands"][0]


def test_capture_url_writes_pcap_before_raising_on_curl_error(tmp_path, monkeypatch):
    run_result = SimpleNamespace(returncode=7, stderr=b"Failed to connect")
    _, captured = install_capture_fakes(monkeypatch, run_result=run_result)

    with pytest.raises(RuntimeError, match="curl 退出码 7"):
        capture_url("https://example.com/", tmp_path / "site.pcap", duration_s=5.0)

    assert captured["pcap"] is not None


def test_capture_url_raises_when_no_packets(tmp_path, monkeypatch):
    install_capture_fakes(monkeypatch, sniffer_factory=lambda **kwargs: FakeSniffer(results=[], **kwargs))

    with pytest.raises(RuntimeError, match="未捕获"):
        capture_url("https://example.com/", tmp_path / "site.pcap", duration_s=5.0)


def test_capture_url_raises_on_curl_timeout(tmp_path, monkeypatch):
    install_capture_fakes(
        monkeypatch,
        run_result=subprocess.TimeoutExpired(cmd="curl", timeout=5),
    )

    with pytest.raises(RuntimeError, match="未完成"):
        capture_url("https://example.com/", tmp_path / "site.pcap", duration_s=5.0)


def test_capture_url_rejects_non_positive_duration(tmp_path):
    with pytest.raises(ValueError, match="duration"):
        capture_url("https://example.com/", tmp_path / "site.pcap", duration_s=0)


def test_capture_url_reports_sniffer_start_failure(tmp_path, monkeypatch):
    install_capture_fakes(
        monkeypatch,
        sniffer_factory=lambda **kwargs: FakeSniffer(start_error=PermissionError("denied"), **kwargs),
    )

    with pytest.raises(RuntimeError, match="管理员"):
        capture_url("https://example.com/", tmp_path / "site.pcap", duration_s=5.0)
