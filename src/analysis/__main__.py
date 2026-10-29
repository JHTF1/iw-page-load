"""CLI：python -m src.analysis"""

from __future__ import annotations

import argparse

from ..common.logging_setup import get_logger
from ..common.paths import INITCWND_CSV, PAGELOAD_CSV, RESULTS_FIGURES, RESULTS_TABLES
from ..common.schema import read_initcwnd_csv, read_pageload_csv, validate_initcwnd, validate_pageload
from .merge import merge


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.analysis",
        description="合并数据、统计检验并生成图表",
    )
    parser.add_argument("--initcwnd", default=str(INITCWND_CSV), help="initcwnd CSV 路径")
    parser.add_argument("--pageload", default=str(PAGELOAD_CSV), help="pageload CSV 路径")
    parser.add_argument("--figures", default=str(RESULTS_FIGURES), help="图表输出目录")
    parser.add_argument("--tables", default=str(RESULTS_TABLES), help="统计表输出目录")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logger = get_logger("analysis")

    initcwnd_rows = read_initcwnd_csv(args.initcwnd)
    pageload_rows = read_pageload_csv(args.pageload)

    initcwnd_errors = [error for row in initcwnd_rows for error in validate_initcwnd(row)]
    pageload_errors = [error for row in pageload_rows for error in validate_pageload(row)]
    if initcwnd_errors or pageload_errors:
        logger.error("数据校验未通过：initcwnd %s 条，pageload %s 条", len(initcwnd_errors), len(pageload_errors))
        for error in (initcwnd_errors + pageload_errors)[:10]:
            logger.error("  %s", error)
        return 1

    merged = merge(initcwnd_rows, pageload_rows)
    logger.info(
        "合并完成：initcwnd=%s 行，pageload=%s 行，合并后=%s 行",
        len(initcwnd_rows),
        len(pageload_rows),
        len(merged),
    )
    logger.info("图表输出目录=%s，统计表输出目录=%s", args.figures, args.tables)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
