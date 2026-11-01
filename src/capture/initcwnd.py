"""从 pcap 推断服务器的初始拥塞窗口。

算法：
1. 定位三次握手：SYN → SYN-ACK → 客户端确认 SYN-ACK 的 ACK
2. 统计服务器在客户端首次确认其数据（ack > 服务器 ISN + 1）之前发出的载荷，
   按序号区间并集去重
3. MSS 取客户端 SYN 的 MSS 选项；缺失时按协议默认值回退并降低置信度
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scapy.all import IP, IPv6, TCP

from .pcap_utils import load_packets, tcp_packets

SEQ_MOD = 2**32
SEQ_HALF = 2**31
IPV4_DEFAULT_MSS = 536
IPV6_DEFAULT_MSS = 1220


@dataclass(frozen=True)
class _Handshake:
    client_ip: str
    client_port: int
    server_ip: str
    server_port: int
    client_isn: int
    server_isn: int
    mss_bytes: int | None
    synack_index: int


def _endpoints(packet: Any) -> tuple[str, str, int, int] | None:
    if IP in packet:
        layer = packet[IP]
    elif IPv6 in packet:
        layer = packet[IPv6]
    else:
        return None
    tcp = packet[TCP]
    return layer.src, layer.dst, tcp.sport, tcp.dport


def _mss_option(packet: Any) -> int | None:
    for name, value in packet[TCP].options:
        if name in ("MSS", 2):
            return int(value)
    return None


def _find_handshakes(packets: list[Any], server_ip: str | None = None) -> list[_Handshake]:
    syn_by_key: dict[tuple[str, int, str, int, int], Any] = {}
    handshakes: list[_Handshake] = []
    for index, packet in enumerate(packets):
        if TCP not in packet:
            continue
        endpoints = _endpoints(packet)
        if endpoints is None:
            continue
        src_ip, dst_ip, sport, dport = endpoints
        tcp = packet[TCP]
        if tcp.flags.S and not tcp.flags.A:
            key = (src_ip, sport, dst_ip, dport, int(tcp.seq) % SEQ_MOD)
            syn_by_key.setdefault(key, packet)
            continue
        if not (tcp.flags.S and tcp.flags.A):
            continue
        if server_ip is not None and src_ip != server_ip:
            continue
        client_isn = (int(tcp.ack) - 1) % SEQ_MOD
        syn_packet = syn_by_key.get((dst_ip, dport, src_ip, sport, client_isn))
        if syn_packet is None:
            continue
        handshakes.append(
            _Handshake(
                client_ip=dst_ip,
                client_port=dport,
                server_ip=src_ip,
                server_port=sport,
                client_isn=client_isn,
                server_isn=int(tcp.seq) % SEQ_MOD,
                mss_bytes=_mss_option(syn_packet),
                synack_index=index,
            )
        )
    return handshakes


def _unique_connections(handshakes: list[_Handshake]) -> list[_Handshake]:
    seen: set[tuple[str, int, str, int]] = set()
    unique: list[_Handshake] = []
    for handshake in handshakes:
        key = (handshake.client_ip, handshake.client_port, handshake.server_ip, handshake.server_port)
        if key in seen:
            continue
        seen.add(key)
        unique.append(handshake)
    return unique


def _first_data_ack_index(packets: list[Any], handshake: _Handshake) -> int | None:
    client_key = (handshake.client_ip, handshake.server_ip, handshake.client_port, handshake.server_port)
    for index in range(handshake.synack_index + 1, len(packets)):
        packet = packets[index]
        if TCP not in packet:
            continue
        endpoints = _endpoints(packet)
        if endpoints is None or endpoints != client_key:
            continue
        tcp = packet[TCP]
        if not tcp.flags.A:
            continue
        acknowledged = (int(tcp.ack) - handshake.server_isn - 1) % SEQ_MOD
        if 0 < acknowledged < SEQ_HALF:
            return index
    return None


def _payload_segments(packets: list[Any], handshake: _Handshake, stop_index: int) -> list[tuple[int, int]]:
    server_key = (handshake.server_ip, handshake.client_ip, handshake.server_port, handshake.client_port)
    segments: list[tuple[int, int]] = []
    for index in range(handshake.synack_index + 1, stop_index):
        packet = packets[index]
        if TCP not in packet:
            continue
        endpoints = _endpoints(packet)
        if endpoints is None or endpoints != server_key:
            continue
        tcp = packet[TCP]
        length = len(bytes(tcp.payload))
        if length:
            segments.append((int(tcp.seq) % SEQ_MOD, length))
    return segments


def _covered_bytes(ranges: list[tuple[int, int]]) -> int:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return sum(end - start for start, end in merged)


def _analyze_flight(packets: list[Any], server_ip: str | None = None) -> dict[str, Any]:
    tcp_packets_only = tcp_packets(packets, server_ip)
    candidates = _unique_connections(_find_handshakes(tcp_packets_only, server_ip))
    if not candidates:
        raise ValueError("未找到完整三次握手（SYN → SYN-ACK → ACK）")

    handshake = candidates[0]
    ack_index = _first_data_ack_index(tcp_packets_only, handshake)
    stop_index = ack_index if ack_index is not None else len(tcp_packets_only)
    segments = _payload_segments(tcp_packets_only, handshake, stop_index)
    if not segments:
        raise ValueError("首窗口内未观察到服务器载荷")

    ranges: list[tuple[int, int]] = []
    retrans_count = 0
    for seq, length in segments:
        start = (seq - handshake.server_isn - 1) % SEQ_MOD
        # 归一化后落在高半区的序号属于 ISN 之前的其他连接，不能计入首窗口
        if start >= SEQ_HALF:
            continue
        end = start + length
        if any(start < existing_end and existing_start < end for existing_start, existing_end in ranges):
            retrans_count += 1
        ranges.append((start, end))

    initcwnd_bytes = _covered_bytes(ranges)
    ip_version = str(ipaddress.ip_address(handshake.server_ip).version)
    notes: list[str] = []
    confidence = "high"

    if handshake.mss_bytes is None:
        mss_bytes = IPV6_DEFAULT_MSS if ip_version == "6" else IPV4_DEFAULT_MSS
        confidence = "low"
        notes.append(f"客户端 SYN 未携带 MSS 选项，按协议默认值 {mss_bytes} 字节回退")
    else:
        mss_bytes = handshake.mss_bytes

    if retrans_count:
        notes.append(f"首窗口内检测到 {retrans_count} 个重传段，已按序号去重")
        if confidence == "high":
            confidence = "medium"
    if ack_index is None:
        notes.append("未捕获到确认服务器数据的 ACK，按抓包结束截断")
        if confidence == "high":
            confidence = "medium"
    if len(candidates) > 1:
        notes.append(f"检测到多条候选连接（{len(candidates)} 条），取最早一条")
        if confidence == "high":
            confidence = "medium"

    return {
        "server_ip": handshake.server_ip,
        "ip_version": ip_version,
        "initcwnd_bytes": initcwnd_bytes,
        "mss_bytes": mss_bytes,
        "initcwnd_mss": round(initcwnd_bytes / mss_bytes, 2),
        "segment_count": len(ranges),
        "retrans_count": retrans_count,
        "confidence": confidence,
        "notes": "；".join(notes),
    }


def first_flight_bytes(packets: list[Any], server_ip: str) -> int:
    """统计服务器首个 flight 的去重载荷字节数。"""
    return int(_analyze_flight(packets, server_ip)["initcwnd_bytes"])


def measure_initcwnd(pcap_path: Path, server_ip: str | None = None) -> dict[str, Any]:
    """返回 initcwnd 测量结果（测量字段），site/url/method 由调用方补充。"""
    packets = load_packets(Path(pcap_path))
    return _analyze_flight(packets, server_ip)
