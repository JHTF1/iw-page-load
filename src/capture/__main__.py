"""CLI：python -m src.capture --site <站点> --url <URL>"""

from __future__ import annotations

import argparse
from pathlib import Path

from ..common.logging_setup import get_logger
from ..common.paths import DATA_RAW, ensure_dirs
from ..common.settings import load_settings
from .initcwnd import measure_initcwnd
from .sniffer import capture_url


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.capture",
        description="抓包并测量服务器的初始拥塞窗口（initcwnd）",
    )
    parser.add_argument("--site", required=True, help="站点标识，与 config/sites.csv 一致")
    parser.add_argument("--url", required=True, help="被测 URL，例如 https://www.baidu.com/")
    parser.add_argument("--duration", type=float, default=None, help="抓包时长（秒），默认读 settings.yaml")
    parser.add_argument("--iface", default=None, help="网卡名称，默认自动选择")
    parser.add_argument("--out", default=None, help="pcap 输出路径，默认 data/raw/<site>.pcap")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings()
    duration = args.duration if args.duration is not None else settings["capture"]["duration_s"]

    ensure_dirs()
    out_pcap = Path(args.out) if args.out else DATA_RAW / f"{args.site}.pcap"
    logger = get_logger("capture")
    logger.info("开始抓包 site=%s url=%s", args.site, args.url)

    pcap_path = capture_url(args.url, out_pcap, duration_s=duration, iface=args.iface)
    result = measure_initcwnd(pcap_path)
    logger.info(
        "initcwnd=%s bytes（%s MSS）",
        result.get("initcwnd_bytes"),
        result.get("initcwnd_mss"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
