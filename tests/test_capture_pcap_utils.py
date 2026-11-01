"""pcap_utils 的单元测试：读取 pcap 与 TCP 过滤。"""

from __future__ import annotations

import pytest

from pcap_builder import make_tcp_packet, make_udp_packet, write_pcap
from src.capture.pcap_utils import load_packets, tcp_packets


def test_load_packets_returns_all_packets(tmp_path):
    pcap_path = tmp_path / "mixed.pcap"
    write_pcap(
        pcap_path,
        [
            make_tcp_packet("10.0.0.1", "10.0.0.2", ts=1.0),
            make_udp_packet("10.0.0.1", "10.0.0.2", ts=2.0),
            make_tcp_packet("10.0.0.2", "10.0.0.1", ts=3.0),
        ],
    )

    packets = load_packets(pcap_path)

    assert len(packets) == 3


def test_load_packets_missing_file_raises(tmp_path):
    missing = tmp_path / "nope.pcap"

    with pytest.raises(FileNotFoundError, match="nope.pcap"):
        load_packets(missing)


def test_tcp_packets_drops_non_tcp(tmp_path):
    packets = [
        make_tcp_packet("10.0.0.1", "10.0.0.2", ts=1.0),
        make_udp_packet("10.0.0.1", "10.0.0.2", ts=2.0),
        make_tcp_packet("10.0.0.2", "10.0.0.1", ts=3.0),
    ]

    result = tcp_packets(packets)

    assert len(result) == 2
    assert all(packet.haslayer("TCP") for packet in result)


def test_tcp_packets_filters_by_server_ip_keeping_both_directions():
    packets = [
        make_tcp_packet("10.0.0.1", "10.0.0.2", ts=1.0),
        make_tcp_packet("10.0.0.2", "10.0.0.1", ts=2.0),
        make_tcp_packet("10.0.0.1", "10.0.0.3", ts=3.0),
    ]

    result = tcp_packets(packets, server_ip="10.0.0.2")

    assert len(result) == 2
    assert [packet["IP"].dst for packet in result] == ["10.0.0.2", "10.0.0.1"]


def test_tcp_packets_filters_by_ipv6_server_ip():
    packets = [
        make_tcp_packet("2001:db8::1", "2001:db8::2", v6=True, ts=1.0),
        make_tcp_packet("2001:db8::2", "2001:db8::1", v6=True, ts=2.0),
        make_tcp_packet("2001:db8::1", "2001:db8::3", v6=True, ts=3.0),
    ]

    result = tcp_packets(packets, server_ip="2001:db8::2")

    assert len(result) == 2
    assert all(packet["IPv6"].src == "2001:db8::2" or packet["IPv6"].dst == "2001:db8::2" for packet in result)
