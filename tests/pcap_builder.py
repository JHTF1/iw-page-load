"""合成 pcap 的测试工具：构造可读的 TCP/UDP 数据包。"""

from __future__ import annotations

from scapy.all import IP, IPv6, TCP, Raw, UDP, wrpcap


def make_tcp_packet(
    src: str,
    dst: str,
    sport: int = 40000,
    dport: int = 443,
    seq: int = 0,
    ack: int = 0,
    flags: str = "A",
    payload: bytes = b"",
    mss: int | None = None,
    v6: bool = False,
    ts: float = 1.0,
) -> object:
    l3 = IPv6(src=src, dst=dst) if v6 else IP(src=src, dst=dst)
    options = [("MSS", mss)] if mss is not None else []
    packet = l3 / TCP(sport=sport, dport=dport, seq=seq, ack=ack, flags=flags, options=options)
    if payload:
        packet = packet / Raw(load=payload)
    packet.time = ts
    return packet


def make_udp_packet(src: str, dst: str, sport: int = 5353, dport: int = 53, ts: float = 1.0) -> object:
    packet = IP(src=src, dst=dst) / UDP(sport=sport, dport=dport) / Raw(load=b"x")
    packet.time = ts
    return packet


def handshake_packets(
    server_ip: str,
    client_ip: str,
    client_isn: int = 1000,
    server_isn: int = 5000,
    mss: int | None = 1460,
    v6: bool = False,
    client_port: int = 40000,
    server_port: int = 443,
    ts: float = 1000.0,
) -> tuple[object, object, object]:
    syn = make_tcp_packet(
        client_ip, server_ip, client_port, server_port,
        seq=client_isn, flags="S", mss=mss, v6=v6, ts=ts,
    )
    synack = make_tcp_packet(
        server_ip, client_ip, server_port, client_port,
        seq=server_isn, ack=client_isn + 1, flags="SA", mss=mss, v6=v6, ts=ts + 0.001,
    )
    ack = make_tcp_packet(
        client_ip, server_ip, client_port, server_port,
        seq=client_isn + 1, ack=server_isn + 1, flags="A", v6=v6, ts=ts + 0.1,
    )
    return syn, synack, ack


def server_payload_packets(
    server_ip: str,
    client_ip: str,
    server_port: int = 443,
    client_port: int = 40000,
    first_seq: int = 5001,
    sizes: list[int] | None = None,
    v6: bool = False,
    ts: float = 1000.002,
) -> list[object]:
    packets = []
    seq = first_seq
    for index, size in enumerate(sizes or []):
        packets.append(
            make_tcp_packet(
                server_ip, client_ip, server_port, client_port,
                seq=seq, flags="PA", payload=b"d" * size, v6=v6,
                ts=ts + index * 0.0005,
            )
        )
        seq += size
    return packets


def write_pcap(path, packets) -> None:
    wrpcap(str(path), list(packets))
