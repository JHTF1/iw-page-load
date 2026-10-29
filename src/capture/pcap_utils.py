"""pcap 读取与 TCP 过滤工具。"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def load_packets(pcap_path: Path) -> list[Any]:
    """读取 pcap，返回数据包列表。

    TODO(A): 用 scapy.rdpcap 实现。
    """
    raise NotImplementedError(f"TODO(A): 读取 {pcap_path}")


def tcp_packets(packets: list[Any], server_ip: str | None = None) -> list[Any]:
    """筛出 TCP 数据包，可按服务器 IP 过滤。

    TODO(A)。
    """
    raise NotImplementedError("TODO(A): TCP 过滤")
