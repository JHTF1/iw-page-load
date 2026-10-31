"""pcap 读取与 TCP 过滤工具。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scapy.all import IP, IPv6, TCP, rdpcap


def load_packets(pcap_path: Path) -> list[Any]:
    """读取 pcap，返回数据包列表。"""
    path = Path(pcap_path)
    if not path.exists():
        raise FileNotFoundError(f"pcap 文件不存在: {path}")
    return list(rdpcap(str(path)))


def _ip_addresses(packet: Any) -> tuple[str, str] | None:
    if IP in packet:
        layer = packet[IP]
        return layer.src, layer.dst
    if IPv6 in packet:
        layer = packet[IPv6]
        return layer.src, layer.dst
    return None


def tcp_packets(packets: list[Any], server_ip: str | None = None) -> list[Any]:
    """筛出 TCP 数据包，可按服务器 IP 过滤（保留双向流量）。"""
    result = [packet for packet in packets if TCP in packet]
    if server_ip is None:
        return result
    return [
        packet
        for packet in result
        if (addresses := _ip_addresses(packet)) is not None and server_ip in addresses
    ]
