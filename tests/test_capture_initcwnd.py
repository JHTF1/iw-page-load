"""initcwnd 算法的单元测试：用合成 pcap 覆盖正常与异常路径。"""

from __future__ import annotations

import pytest

from pcap_builder import (
    handshake_packets,
    make_tcp_packet,
    server_payload_packets,
    write_pcap,
)
from src.capture.initcwnd import first_flight_bytes, measure_initcwnd

CLIENT = "10.0.0.10"
SERVER = "93.184.216.34"
SERVER_B = "151.101.1.1"
CLIENT6 = "2001:db8::10"
SERVER6 = "2001:db8::20"

C_ISN = 1000
S_ISN = 5000
MSS = 1460
FIRST_SEQ = S_ISN + 1
CLIENT_HELLO = b"hello"


def _write(tmp_path, packets):
    pcap_path = tmp_path / "capture.pcap"
    write_pcap(pcap_path, packets)
    return pcap_path


def _base_packets(
    *,
    server=SERVER,
    client=CLIENT,
    client_isn=C_ISN,
    server_isn=S_ISN,
    mss=MSS,
    v6=False,
    client_port=40000,
    server_port=443,
    ts=1000.0,
):
    syn, synack, handshake_ack = handshake_packets(
        server, client, client_isn, server_isn, mss,
        v6=v6, client_port=client_port, server_port=server_port, ts=ts,
    )
    client_hello = make_tcp_packet(
        client, server, client_port, server_port,
        seq=client_isn + 1, ack=server_isn + 1, flags="PA",
        payload=CLIENT_HELLO, v6=v6, ts=ts + 0.05,
    )
    return syn, synack, handshake_ack, client_hello


def _data_ack(
    *,
    server=SERVER,
    client=CLIENT,
    client_isn=C_ISN,
    server_isn=S_ISN,
    ack_bytes,
    v6=False,
    client_port=40000,
    server_port=443,
    ts=1000.2,
):
    return make_tcp_packet(
        client, server, client_port, server_port,
        seq=client_isn + 1 + len(CLIENT_HELLO),
        ack=server_isn + 1 + ack_bytes, flags="A", v6=v6, ts=ts,
    )


def test_handshake_ack_does_not_end_first_flight(tmp_path):
    syn, synack, handshake_ack, hello = _base_packets()
    data = server_payload_packets(SERVER, CLIENT, first_seq=FIRST_SEQ, sizes=[MSS] * 10, ts=1000.06)
    ack = _data_ack(ack_bytes=10 * MSS)

    result = measure_initcwnd(_write(tmp_path, [syn, synack, handshake_ack, hello, *data, ack]))

    assert result["server_ip"] == SERVER
    assert result["ip_version"] == "4"
    assert result["initcwnd_bytes"] == 10 * MSS
    assert result["mss_bytes"] == MSS
    assert result["initcwnd_mss"] == 10.0
    assert result["segment_count"] == 10
    assert result["retrans_count"] == 0
    assert result["confidence"] == "high"


def test_retransmission_is_deduplicated(tmp_path):
    syn, synack, handshake_ack, hello = _base_packets()
    data = server_payload_packets(SERVER, CLIENT, first_seq=FIRST_SEQ, sizes=[MSS] * 3, ts=1000.06)
    duplicate = make_tcp_packet(
        SERVER, CLIENT, 443, 40000,
        seq=FIRST_SEQ + MSS, flags="PA", payload=b"d" * MSS, ts=1000.1,
    )
    ack = _data_ack(ack_bytes=3 * MSS)

    result = measure_initcwnd(_write(tmp_path, [syn, synack, handshake_ack, hello, *data, duplicate, ack]))

    assert result["initcwnd_bytes"] == 3 * MSS
    assert result["segment_count"] == 4
    assert result["retrans_count"] == 1
    assert result["confidence"] == "medium"


def test_out_of_order_segments_are_merged(tmp_path):
    syn, synack, handshake_ack, hello = _base_packets()
    out_of_order = [
        make_tcp_packet(SERVER, CLIENT, 443, 40000, seq=FIRST_SEQ + 2 * MSS,
                        flags="PA", payload=b"d" * MSS, ts=1000.06),
        make_tcp_packet(SERVER, CLIENT, 443, 40000, seq=FIRST_SEQ,
                        flags="PA", payload=b"d" * MSS, ts=1000.07),
        make_tcp_packet(SERVER, CLIENT, 443, 40000, seq=FIRST_SEQ + MSS,
                        flags="PA", payload=b"d" * MSS, ts=1000.08),
    ]
    ack = _data_ack(ack_bytes=3 * MSS)

    result = measure_initcwnd(_write(tmp_path, [syn, synack, handshake_ack, hello, *out_of_order, ack]))

    assert result["initcwnd_bytes"] == 3 * MSS
    assert result["segment_count"] == 3
    assert result["retrans_count"] == 0
    assert result["confidence"] == "high"


def test_gro_merged_segment_keeps_byte_count(tmp_path):
    syn, synack, handshake_ack, hello = _base_packets()
    data = server_payload_packets(SERVER, CLIENT, first_seq=FIRST_SEQ, sizes=[10 * MSS], ts=1000.06)
    ack = _data_ack(ack_bytes=10 * MSS)

    result = measure_initcwnd(_write(tmp_path, [syn, synack, handshake_ack, hello, *data, ack]))

    assert result["initcwnd_bytes"] == 10 * MSS
    assert result["segment_count"] == 1
    assert result["initcwnd_mss"] == 10.0
    assert result["confidence"] == "high"


def test_missing_mss_option_falls_back_to_default(tmp_path):
    syn, synack, handshake_ack, hello = _base_packets(mss=None)
    data = server_payload_packets(SERVER, CLIENT, first_seq=FIRST_SEQ, sizes=[536] * 10, ts=1000.06)
    ack = _data_ack(ack_bytes=10 * 536)

    result = measure_initcwnd(_write(tmp_path, [syn, synack, handshake_ack, hello, *data, ack]))

    assert result["mss_bytes"] == 536
    assert result["initcwnd_bytes"] == 10 * 536
    assert result["initcwnd_mss"] == 10.0
    assert result["confidence"] == "low"
    assert "MSS" in result["notes"]


def test_ipv6_handshake_uses_1440_mss(tmp_path):
    syn, synack, handshake_ack, hello = _base_packets(
        server=SERVER6, client=CLIENT6, mss=1440, v6=True
    )
    data = server_payload_packets(
        SERVER6, CLIENT6, first_seq=FIRST_SEQ, sizes=[1440] * 10, v6=True, ts=1000.06
    )
    ack = _data_ack(server=SERVER6, client=CLIENT6, ack_bytes=10 * 1440, v6=True)

    result = measure_initcwnd(_write(tmp_path, [syn, synack, handshake_ack, hello, *data, ack]))

    assert result["server_ip"] == SERVER6
    assert result["ip_version"] == "6"
    assert result["initcwnd_bytes"] == 10 * 1440
    assert result["mss_bytes"] == 1440
    assert result["confidence"] == "high"


def test_data_after_first_data_ack_is_excluded(tmp_path):
    syn, synack, handshake_ack, hello = _base_packets()
    data = server_payload_packets(SERVER, CLIENT, first_seq=FIRST_SEQ, sizes=[MSS] * 10, ts=1000.06)
    ack = _data_ack(ack_bytes=10 * MSS)
    after_ack = make_tcp_packet(
        SERVER, CLIENT, 443, 40000,
        seq=FIRST_SEQ + 10 * MSS, flags="PA", payload=b"d" * MSS, ts=1000.3,
    )

    result = measure_initcwnd(_write(tmp_path, [syn, synack, handshake_ack, hello, *data, ack, after_ack]))

    assert result["initcwnd_bytes"] == 10 * MSS
    assert result["segment_count"] == 10


def test_multiple_connections_choose_earliest_and_lower_confidence(tmp_path):
    syn_a, synack_a, handshake_ack_a, hello_a = _base_packets(client_port=40000, ts=1000.0)
    data_a = server_payload_packets(
        SERVER, CLIENT, client_port=40000, first_seq=FIRST_SEQ, sizes=[MSS] * 4, ts=1000.06
    )
    ack_a = _data_ack(client_port=40000, ack_bytes=4 * MSS, ts=1000.2)

    syn_b, synack_b, handshake_ack_b, hello_b = _base_packets(
        client_isn=2000, server_isn=7000, client_port=40001, ts=1000.5
    )
    data_b = server_payload_packets(
        SERVER, CLIENT, client_port=40001, first_seq=7001, sizes=[MSS] * 10, ts=1000.56
    )
    ack_b = _data_ack(
        client_isn=2000, server_isn=7000, client_port=40001, ack_bytes=10 * MSS, ts=1000.7
    )

    result = measure_initcwnd(
        _write(
            tmp_path,
            [
                syn_a, synack_a, handshake_ack_a, hello_a, *data_a, ack_a,
                syn_b, synack_b, handshake_ack_b, hello_b, *data_b, ack_b,
            ],
        )
    )

    assert result["initcwnd_bytes"] == 4 * MSS
    assert result["confidence"] == "medium"
    assert "多条" in result["notes"]


def test_server_ip_filter_selects_matching_connection(tmp_path):
    syn_a, synack_a, handshake_ack_a, hello_a = _base_packets(ts=1000.0)
    data_a = server_payload_packets(SERVER, CLIENT, first_seq=FIRST_SEQ, sizes=[MSS] * 4, ts=1000.06)
    ack_a = _data_ack(ack_bytes=4 * MSS, ts=1000.2)

    syn_b, synack_b, handshake_ack_b, hello_b = _base_packets(
        server=SERVER_B, client_isn=2000, server_isn=7000, client_port=40001, ts=1000.5
    )
    data_b = server_payload_packets(
        SERVER_B, CLIENT, client_port=40001, first_seq=7001, sizes=[MSS] * 10, ts=1000.56
    )
    ack_b = _data_ack(
        server=SERVER_B, client_isn=2000, server_isn=7000, client_port=40001,
        ack_bytes=10 * MSS, ts=1000.7,
    )
    packets = [
        syn_a, synack_a, handshake_ack_a, hello_a, *data_a, ack_a,
        syn_b, synack_b, handshake_ack_b, hello_b, *data_b, ack_b,
    ]

    result = measure_initcwnd(_write(tmp_path, packets), server_ip=SERVER_B)

    assert result["server_ip"] == SERVER_B
    assert result["initcwnd_bytes"] == 10 * MSS
    assert result["confidence"] == "high"


def test_missing_data_ack_counts_to_capture_end(tmp_path):
    syn, synack, handshake_ack, hello = _base_packets()
    data = server_payload_packets(SERVER, CLIENT, first_seq=FIRST_SEQ, sizes=[MSS] * 12, ts=1000.06)

    result = measure_initcwnd(_write(tmp_path, [syn, synack, handshake_ack, hello, *data]))

    assert result["initcwnd_bytes"] == 12 * MSS
    assert result["confidence"] == "medium"
    assert "ACK" in result["notes"]


def test_no_handshake_raises(tmp_path):
    packets = [
        make_tcp_packet(CLIENT, SERVER, 40000, 443, seq=C_ISN, ack=S_ISN + 1,
                        flags="PA", payload=b"d" * MSS, ts=1000.0),
    ]

    with pytest.raises(ValueError, match="三次握手"):
        measure_initcwnd(_write(tmp_path, packets))


def test_no_server_payload_raises(tmp_path):
    syn, synack, handshake_ack, hello = _base_packets()

    with pytest.raises(ValueError, match="载荷"):
        measure_initcwnd(_write(tmp_path, [syn, synack, handshake_ack, hello]))


def test_first_flight_bytes_wrapper(tmp_path):
    syn, synack, handshake_ack, hello = _base_packets()
    data = server_payload_packets(SERVER, CLIENT, first_seq=FIRST_SEQ, sizes=[MSS] * 10, ts=1000.06)
    ack = _data_ack(ack_bytes=10 * MSS)

    assert first_flight_bytes([syn, synack, handshake_ack, hello, *data, ack], SERVER) == 10 * MSS
