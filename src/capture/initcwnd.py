"""从 pcap 推断服务器的初始拥塞窗口。

算法要点（TODO(A)）：
1. 定位三次握手：SYN → SYN-ACK → ACK
2. 以服务器 ISN 为起点，统计服务器在收到首个 ACK 之前的载荷字节数
3. 重传按序号区间去重，乱序按区间合并；只统计字节数，不统计段数
   （网卡 GRO/LRO 会合并报文段，段数不可信）
4. MSS 从 SYN 报文的 MSS 选项读取，initcwnd_mss = initcwnd_bytes / mss_bytes
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def first_flight_bytes(packets: list[Any], server_ip: str) -> int:
    """统计服务器首个 flight 的去重载荷字节数。

    TODO(A)。
    """
    raise NotImplementedError("TODO(A): 首窗口字节统计")


def measure_initcwnd(pcap_path: Path, server_ip: str | None = None) -> dict[str, Any]:
    """返回 initcwnd 测量结果，字段与 schema.INITCWND_COLUMNS 对齐。

    TODO(A)。校准标准：受控实验四组真值（2/4/10/20）误差不超过 1 个 MSS。
    """
    raise NotImplementedError(f"TODO(A): 从 {pcap_path} 计算 initcwnd")
