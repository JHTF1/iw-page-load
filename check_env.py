import platform
import sys
import time

import scapy
from scapy.all import conf, sniff


def main() -> None:
    print(f"Python {platform.python_version()}  ({sys.executable})")
    print(f"scapy {scapy.__version__}  pcap backend: {conf.use_pcap}")
    print("\n可用网卡:")
    for iface in conf.ifaces.values():
        print(f"  {iface.name:<32} {iface.description}  {iface.mac}")

    print("\n抓包自检: 监听 5 秒...")
    start = time.perf_counter()
    try:
        packets = sniff(count=1, timeout=5)
    except Exception as exc:
        print(f"抓包失败: {type(exc).__name__}: {exc}")
        print("如果提示权限不足，请用管理员身份启动 PyCharm 再运行。")
        return
    elapsed = time.perf_counter() - start
    if packets:
        print(f"抓包成功: 用 {elapsed:.1f}s 捕获到 1 个包")
        packets.summary()
    else:
        print("5 秒内没有捕获到任何包，可以换个网卡或制造一点流量再试。")


if __name__ == "__main__":
    main()
