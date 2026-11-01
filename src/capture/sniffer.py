"""访问目标 URL 的同时抓包。"""

from __future__ import annotations

import ipaddress
import platform
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit

from scapy.all import AsyncSniffer, wrpcap

from ..common.settings import load_settings

SUPPORTED_SCHEMES = {"http": 80, "https": 443}
SNIFF_GRACE_S = 0.3
START_WAIT_S = 1.0
CURL_EXTRA_TIMEOUT_S = 2.0
MIN_CURL_TIMEOUT_S = 0.5


def _parse_target(url: str) -> tuple[str, int]:
    parts = urlsplit(url)
    if parts.scheme not in SUPPORTED_SCHEMES:
        raise ValueError(f"仅支持 http/https URL，收到: {url}")
    if not parts.hostname:
        raise ValueError(f"URL 缺少 hostname: {url}")
    return parts.hostname, parts.port or SUPPORTED_SCHEMES[parts.scheme]


def _resolve_addresses(host: str, port: int) -> list[str]:
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    addresses: list[str] = []
    for info in infos:
        address = info[4][0]
        if address not in addresses:
            addresses.append(address)
    if not addresses:
        raise RuntimeError(f"无法解析域名: {host}")
    return addresses


def _preferred_address(addresses: list[str]) -> str:
    for address in addresses:
        if ":" not in address:
            return address
    return addresses[0]


def resolve_server_ip(url: str) -> str:
    """解析 URL 并返回优先使用的服务器 IP（IPv4 优先）。"""
    host, port = _parse_target(url)
    return _preferred_address(_resolve_addresses(host, port))


def _build_bpf_filter(server_ip: str) -> str:
    return f"tcp and host {server_ip}"


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def _curl_command(url: str, server_ip: str, port: int, timeout_s: float) -> list[str]:
    host, _ = _parse_target(url)
    command = [
        "curl",
        "--silent",
        "--show-error",
        "--http1.1",
        "--noproxy",
        "*",
        "--max-time",
        f"{timeout_s:g}",
    ]
    if not _is_ip_literal(host):
        resolved = f"[{server_ip}]" if ":" in server_ip else server_ip
        command.extend(["--resolve", f"{host}:{port}:{resolved}"])
    if platform.system() == "Windows":
        command.append("--ssl-revoke-best-effort")
    command.append(url)
    return command


def _curl_timeout(duration_s: float, configured_timeout_s: float) -> float:
    return max(MIN_CURL_TIMEOUT_S, min(float(duration_s), float(configured_timeout_s)))


def _wait_until_running(sniffer: AsyncSniffer, timeout_s: float = START_WAIT_S) -> None:
    deadline = time.monotonic() + timeout_s
    while not getattr(sniffer, "running", True) and time.monotonic() < deadline:
        time.sleep(0.01)


def capture_url(
    url: str,
    out_pcap: Path,
    duration_s: float = 8.0,
    iface: str | None = None,
) -> Path:
    """抓取访问 url 的 TCP 流量，返回 pcap 路径。"""
    if duration_s <= 0:
        raise ValueError("duration_s 必须大于 0")

    host, port = _parse_target(url)
    server_ip = _preferred_address(_resolve_addresses(host, port))
    out_path = Path(out_pcap)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    settings = load_settings()
    timeout_s = _curl_timeout(duration_s, settings["capture"]["curl_timeout_s"])

    sniffer = AsyncSniffer(filter=_build_bpf_filter(server_ip), iface=iface, store=True)
    try:
        sniffer.start()
    except Exception as exc:
        raise RuntimeError("抓包启动失败：请用管理员权限运行，并检查 WinPcap 是否正常") from exc
    _wait_until_running(sniffer)

    curl_error: str | None = None
    try:
        completed = subprocess.run(
            _curl_command(url, server_ip, port, timeout_s),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=timeout_s + CURL_EXTRA_TIMEOUT_S,
        )
        if completed.returncode != 0:
            stderr = (completed.stderr or b"").decode("utf-8", "replace").strip()
            curl_error = f"curl 退出码 {completed.returncode}: {stderr}"
    except subprocess.TimeoutExpired:
        curl_error = f"curl 超过 {timeout_s:g} 秒未完成"
    finally:
        time.sleep(SNIFF_GRACE_S)
        try:
            sniffer.stop()
        except Exception:
            pass

    packets = list(getattr(sniffer, "results", None) or [])
    wrpcap(str(out_path), packets)

    sniffer_error = getattr(sniffer, "exception", None)
    if sniffer_error is not None:
        raise RuntimeError(f"抓包失败: {sniffer_error}") from sniffer_error
    if curl_error:
        raise RuntimeError(f"{curl_error}（pcap 已保存: {out_path}）")
    if not packets:
        raise RuntimeError(
            "未捕获到任何数据包：确认以管理员运行、网卡选择正确（可用 check_env.py 查看），"
            "并确认目标站点可直连（抓包必须绕过代理）"
        )
    return out_path
