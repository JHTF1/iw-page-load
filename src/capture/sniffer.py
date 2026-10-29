"""访问目标 URL 的同时抓包。"""

from __future__ import annotations

from pathlib import Path


def resolve_server_ip(url: str) -> str:
    """解析 URL 对应的服务器 IP。

    TODO(A): 同时返回 IPv4/IPv6 信息，供抓包过滤和 pcap 校验使用。
    """
    raise NotImplementedError(f"TODO(A): 解析 {url} 的服务器 IP")


def capture_url(
    url: str,
    out_pcap: Path,
    duration_s: float = 8.0,
    iface: str | None = None,
) -> Path:
    """抓取访问 url 的 TCP 流量，返回 pcap 路径。

    TODO(A):
    1. 用子进程执行 curl 发起单连接请求（铁律：只用单连接，避免并行连接干扰首窗口）
    2. scapy.sniff 按目标 IP 与端口过滤并写入 pcap
    """
    raise NotImplementedError(f"TODO(A): 抓取 {url}")
