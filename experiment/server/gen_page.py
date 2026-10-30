#!/usr/bin/env python3
"""生成受控实验测试页面：index.html + 固定数量的固定大小资源对象。

参数默认取自 config/settings.yaml 的 lab 段，可用命令行参数覆盖。
"""
from __future__ import annotations

import argparse
import random
import struct
import sys
import zlib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SETTINGS = ROOT / "config" / "settings.yaml"
SEED = 20251029
PNG_SIG = b"\x89PNG\r\n\x1a\n"
# 图像宽度固定，行数按目标体积反算；每行含 1 字节过滤字节
_ROW_BYTES = 1 + 160 * 3


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def make_png(target_bytes: int, rng: random.Random) -> bytes:
    """生成体积精确等于 target_bytes 的合法 PNG。

    像素用随机数据且 zlib 采用存储模式（level=0），体积与原始数据基本一致；
    剩余差额用 PNG 规范允许的 tEXt 附注块补齐，Chrome 能正常解码并完整下载。
    """
    rows = max(1, (target_bytes - 320) // _ROW_BYTES)
    raw = b"".join(b"\x00" + rng.randbytes(160 * 3) for _ in range(rows))
    png = (
        PNG_SIG
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", 160, rows, 8, 2, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(raw, 0))
        + _chunk(b"IEND", b"")
    )
    pad = target_bytes - len(png) - 12 - 4  # 12 字节块开销 + "pad\0" 关键字
    if pad < 0:
        raise ValueError(f"目标体积 {target_bytes} 太小，无法生成合法 PNG")
    return png + _chunk(b"tEXt", b"pad\x00" + rng.randbytes(pad))


def log(msg: str) -> None:
    print(f"[gen_page] {msg}")


def load_lab() -> dict:
    with SETTINGS.open(encoding="utf-8") as f:
        return yaml.safe_load(f)["lab"]


def generate(out: Path, count: int, size_kb: int) -> None:
    if count < 1 or size_kb < 1:
        raise ValueError(f"count 与 size-kb 必须为正整数，当前 {count}/{size_kb}")

    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)  # 固定种子，保证页面可复现

    names = []
    target = size_kb * 1024
    for i in range(1, count + 1):
        name = f"obj-{i:02d}.png"
        data = make_png(target, rng)
        assert len(data) == target, f"{name} 体积 {len(data)} != {target}"
        (out / name).write_bytes(data)
        names.append(name)
    log(f"已生成 {count} 个合法 PNG 对象，每个精确 {size_kb} KB，目录 {out}")

    imgs = "\n".join(
        f'  <img src="{n}" width="120" height="90" alt="">' for n in names
    )
    html = f"""<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>iw-page-load 受控实验页</title></head>
<body>
  <h1>受控实验测试页</h1>
  <p>objects={count}, size_kb={size_kb}</p>
{imgs}
</body>
</html>
"""
    (out / "index.html").write_text(html, encoding="utf-8")
    log(f"已生成 index.html（{len(html)} 字节）")


def main() -> int:
    try:
        lab = load_lab()
    except Exception as exc:  # 配置文件缺失或被改动时给出明确提示
        print(f"[gen_page] 无法读取 {SETTINGS}: {exc}", file=sys.stderr)
        return 1

    parser = argparse.ArgumentParser(description="生成受控实验测试页面")
    parser.add_argument("--out", default="/var/www/lab", help="输出目录")
    parser.add_argument("--count", type=int, default=lab["object_count"])
    parser.add_argument("--size-kb", type=int, default=lab["object_size_kb"])
    args = parser.parse_args()

    log(f"配置来源 {SETTINGS}：count={args.count} size_kb={args.size_kb}")
    try:
        generate(Path(args.out), args.count, args.size_kb)
    except Exception as exc:
        print(f"[gen_page] 生成失败: {exc}", file=sys.stderr)
        return 1

    total = args.count * args.size_kb * 1024
    log(f"对象总量约 {total / 1024 / 1024:.2f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
