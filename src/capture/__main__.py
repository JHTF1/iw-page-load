"""CLI：python -m src.capture --site <站点> --url <URL>"""

from __future__ import annotations

import argparse
from pathlib import Path

from ..common.logging_setup import get_logger
from ..common.paths import DATA_RAW, INITCWND_CSV, ensure_dirs
from ..common.settings import load_settings
from .batch import capture_sites
from .initcwnd import measure_initcwnd
from .records import build_record, upsert_record, utc_now_iso
from .sniffer import capture_url


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.capture",
        description="抓包并测量服务器的初始拥塞窗口（initcwnd）",
    )
    parser.add_argument("--site", default=None, help="站点标识，与 config/sites.csv 一致（单站模式）")
    parser.add_argument("--url", default=None, help="被测 URL，例如 https://www.baidu.com/（单站模式）")
    parser.add_argument("--duration", type=float, default=None, help="抓包时长（秒），默认读 settings.yaml")
    parser.add_argument("--iface", default=None, help="网卡名称，默认自动选择")
    parser.add_argument("--out", default=None, help="pcap 输出路径，默认 data/raw/<site>.pcap")
    parser.add_argument(
        "--csv",
        default=None,
        help="initcwnd CSV 路径，默认 data/processed/initcwnd.csv",
    )
    parser.add_argument("--sites", default=None, help="批量模式：站点清单 CSV 路径，例如 config/sites.csv")
    parser.add_argument("--only", default=None, help="批量模式：只抓该站点")
    parser.add_argument("--repeats", type=int, default=None, help="批量模式：每站轮数，默认读 settings.yaml")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    ensure_dirs()
    logger = get_logger("capture")

    if args.sites:
        if args.site or args.url:
            parser.error("--sites 不能与 --site/--url 同时使用")
        if args.out:
            parser.error("--sites 模式不支持 --out，pcap 自动写入 data/raw/")
        capture_sites(
            Path(args.sites),
            repeats=args.repeats,
            only=args.only,
            csv_path=Path(args.csv) if args.csv else None,
            duration_s=args.duration,
            iface=args.iface,
        )
        return 0

    if not args.site or not args.url:
        parser.error("单站模式必须提供 --site 和 --url")
    if args.only is not None or args.repeats is not None:
        parser.error("--only 和 --repeats 只能与 --sites 一起使用")

    settings = load_settings()
    duration = args.duration if args.duration is not None else settings["capture"]["duration_s"]

    out_pcap = Path(args.out) if args.out else DATA_RAW / f"{args.site}.pcap"
    logger.info("开始抓包 site=%s url=%s", args.site, args.url)

    timestamp = utc_now_iso()
    pcap_path = capture_url(args.url, out_pcap, duration_s=duration, iface=args.iface)
    result = measure_initcwnd(pcap_path)
    logger.info(
        "initcwnd=%s bytes（%s MSS）",
        result.get("initcwnd_bytes"),
        result.get("initcwnd_mss"),
    )

    record = build_record(result, args.site, args.url, timestamp)
    csv_path = Path(args.csv) if args.csv else INITCWND_CSV
    try:
        written = upsert_record(record, csv_path)
    except ValueError as exc:
        logger.error("写入 initcwnd.csv 失败: %s", exc)
        return 1
    logger.info("已写入 %s", written)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
