"""CLI：python -m src.measure --sites config/sites.csv"""

from __future__ import annotations

import argparse
from pathlib import Path

from ..common.logging_setup import get_logger
from ..common.paths import PAGELOAD_CSV, SITES_CSV, ensure_dirs
from ..common.schema import validate_pageload, write_pageload_csv
from ..common.settings import load_settings
from .metrics import collect_all


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.measure",
        description="测量网站页面加载性能（Chrome DevTools 协议）",
    )
    parser.add_argument("--sites", default=str(SITES_CSV), help="站点清单 CSV，默认 config/sites.csv")
    parser.add_argument("--site", default=None, help="只测单个站点标识")
    parser.add_argument("--repeats", type=int, default=None, help="每站重复轮数，默认读 settings.yaml")
    parser.add_argument("--out", default=str(PAGELOAD_CSV), help="输出 CSV，默认 data/processed/pageload.csv")
    parser.add_argument(
        "--network-env",
        default=None,
        help="网络环境描述，写入 network_env 字段，例如“有线 · 中国移动 · 2026-11-04 10:00-11:00”",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings()
    repeats = args.repeats if args.repeats is not None else settings["measure"]["repeats"]

    ensure_dirs()
    logger = get_logger("measure")
    logger.info("站点清单=%s repeats=%s", args.sites, repeats)

    runs = collect_all(Path(args.sites), repeats=repeats, only=args.site, network_env=args.network_env)

    valid = []
    for record in runs:
        errors = validate_pageload(record)
        if errors:
            logger.warning(
                "丢弃不合规记录 %s#%s: %s",
                record.get("site"),
                record.get("run_id"),
                "; ".join(errors),
            )
            continue
        valid.append(record)

    if not valid:
        logger.error("没有可用记录，未写入 %s", Path(args.out))
        return 1

    path = write_pageload_csv(Path(args.out), valid)
    logger.info("写入 %d 条记录 → %s", len(valid), path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
