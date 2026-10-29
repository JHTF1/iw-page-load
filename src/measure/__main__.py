"""CLI：python -m src.measure --sites config/sites.csv"""

from __future__ import annotations

import argparse
from pathlib import Path

from ..common.logging_setup import get_logger
from ..common.paths import PAGELOAD_CSV, SITES_CSV, ensure_dirs
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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings()
    repeats = args.repeats if args.repeats is not None else settings["measure"]["repeats"]

    ensure_dirs()
    logger = get_logger("measure")
    logger.info("站点清单=%s repeats=%s", args.sites, repeats)

    runs = collect_all(Path(args.sites), repeats=repeats, only=args.site)
    logger.info("采集完成，共 %s 轮，输出=%s", len(runs), Path(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
