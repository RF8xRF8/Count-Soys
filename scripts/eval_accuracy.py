#!/usr/bin/env python
"""识别准确率评估脚本：用 examples/ 里带真值的图片跑 count_objects，输出误差统计。

文件名即真值：`soy53.JPG` 表示应为 53 个，`soy69_1.jpg` 表示 69 个（同数量的另一次拍摄）。
调参、换算法后都跑一遍这个脚本，用数字说话，不要凭感觉改。

用法（在仓库根目录执行）：

    uv run python scripts/eval_accuracy.py                      # 默认 mode=beans
    uv run python scripts/eval_accuracy.py --mode pills
    uv run python scripts/eval_accuracy.py --param fg_ratio=0.65
    uv run python scripts/eval_accuracy.py --sweep-resolution   # 扫多个长边，挑最优
    uv run python scripts/eval_accuracy.py --dump-worst out/    # 导出误差最大的标注图
    uv run python scripts/eval_accuracy.py --max-mae 1.5        # 超过阈值退出码 1（给 CI 用）

判读指标：MAE（平均绝对误差）看整体精度，bias（平均带符号误差）看是否系统性多算/少算，
exact 看多少张完全正确，max_error 看最坏情况。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.services.counting import count_objects  # noqa: E402
from backend.app.services.image_io import load_image  # noqa: E402

LABEL_RE = re.compile(r"soy(\d+)", re.IGNORECASE)
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
SWEEP_DEFAULT = (1600, 1920, 2200, 2600)
DEFAULT_MIN_AREA = {"beans": 500, "pills": 100, "cells": 100}


@dataclass
class Case:
    name: str
    path: Path
    expected: int


@dataclass
class Result:
    case: Case
    got: int
    elapsed_ms: float
    annotated: np.ndarray | None = field(default=None, repr=False)

    @property
    def error(self) -> int:
        return self.got - self.case.expected


def discover(directory: Path, only: str | None = None) -> list[Case]:
    """扫描目录，按文件名里的 `soy<数字>` 取真值。文件名大小写不同只算一次。"""
    cases: dict[str, Case] = {}
    for path in sorted(directory.iterdir()):
        if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        key = path.name.lower()
        if key in cases:
            continue
        match = LABEL_RE.search(path.stem)
        if not match:
            print(f"跳过（文件名里没有 soy<数字> 真值）：{path.name}", file=sys.stderr)
            continue
        if only and only.lower() not in key:
            continue
        cases[key] = Case(name=path.name, path=path, expected=int(match.group(1)))
    return sorted(cases.values(), key=lambda item: item.name.lower())


def evaluate(cases: list[Case], mode: str, params: dict, max_side: int, keep_images: bool = False) -> list[Result]:
    results: list[Result] = []
    for case in cases:
        image, _, _ = load_image(case.path.read_bytes(), max_side)
        started = time.perf_counter()
        annotated, instances, _ = count_objects(image, mode, dict(params))
        elapsed_ms = (time.perf_counter() - started) * 1000
        results.append(Result(case=case, got=len(instances), elapsed_ms=elapsed_ms, annotated=annotated if keep_images else None))
    return results


def summarize(results: list[Result]) -> dict:
    errors = np.array([item.error for item in results], dtype=float)
    absolute = np.abs(errors)
    return {
        "images": len(results),
        "exact": int((absolute == 0).sum()),
        "mae": float(absolute.mean()),
        "bias": float(errors.mean()),
        "rmse": float(np.sqrt((errors**2).mean())),
        "max_error": int(absolute.max()),
        "max_percent": float((absolute / np.array([item.case.expected for item in results])).max() * 100),
        "mean_ms": float(np.mean([item.elapsed_ms for item in results])),
        "max_ms": float(max(item.elapsed_ms for item in results)),
    }


def format_summary(name: str, stats: dict) -> str:
    return (
        f"{name:>26}  exact={stats['exact']:2}/{stats['images']:<3} MAE={stats['mae']:6.2f} "
        f"bias={stats['bias']:+6.2f} RMSE={stats['rmse']:6.2f} max={stats['max_error']:3} "
        f"({stats['max_percent']:4.1f}%) 耗时 均{stats['mean_ms'] / 1000:.2f}s 峰{stats['max_ms'] / 1000:.2f}s"
    )


def print_table(results: list[Result]) -> None:
    print(f"  {'图片':<16}{'应为':>6}{'实得':>6}{'误差':>6}{'耗时':>9}")
    for item in sorted(results, key=lambda entry: (-abs(entry.error), entry.case.name.lower())):
        flag = "" if item.error == 0 else ("  ← 少算" if item.error < 0 else "  ← 多算")
        print(f"  {item.case.name:<16}{item.case.expected:>6}{item.got:>6}{item.error:>+6}{item.elapsed_ms / 1000:>8.2f}s{flag}")


def parse_params(pairs: list[str]) -> dict:
    params: dict = {}
    for pair in pairs:
        key, _, value = pair.partition("=")
        if not _:
            raise SystemExit(f"--param 需要 KEY=VALUE 形式，收到：{pair}")
        params[key] = float(value) if "." in value else int(value)
    return params


def main() -> int:
    parser = argparse.ArgumentParser(description="用 examples/ 的带真值图片评估计数准确率")
    parser.add_argument("--dir", default=str(REPO_ROOT / "examples"), help="标注图片目录，默认 examples/")
    parser.add_argument("--mode", default="beans", choices=("pills", "beans", "cells"))
    parser.add_argument("--max-side", type=int, default=None, help="处理时缩放到的最长边，默认取后端配置")
    parser.add_argument("--min-area", type=int, default=None, help="覆盖 min_area")
    parser.add_argument("--param", action="append", default=[], metavar="KEY=VALUE", help="覆盖任意 count_objects 参数，可重复")
    parser.add_argument("--only", default=None, help="只跑文件名包含该子串的图片")
    parser.add_argument("--sweep-resolution", nargs="*", type=int, default=None, metavar="N", help=f"比较多个长边，默认 {SWEEP_DEFAULT}")
    parser.add_argument("--dump-worst", metavar="DIR", default=None, help="把误差最大的 3 张标注图写入该目录")
    parser.add_argument("--json", action="store_true", help="额外输出一行 JSON 汇总")
    parser.add_argument("--max-mae", type=float, default=None, help="MAE 超过该值时退出码 1")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    directory = Path(args.dir)
    if not directory.is_dir():
        raise SystemExit(f"目录不存在：{directory}")
    cases = discover(directory, args.only)
    if not cases:
        raise SystemExit(f"{directory} 里没有可评估的图片（文件名需形如 soy53.JPG）")

    params = parse_params(args.param)
    params.setdefault("min_area", args.min_area if args.min_area is not None else DEFAULT_MIN_AREA[args.mode])

    configured = args.max_side
    if configured is None:
        try:
            from backend.app.config import settings

            configured = settings.default_max_side
        except Exception:
            configured = 1600

    print(f"共 {len(cases)} 张 | mode={args.mode} | max_side={configured} | min_area={params['min_area']} | 其他参数={ {k: v for k, v in params.items() if k != 'min_area'} or '默认'}")

    results = evaluate(cases, args.mode, params, configured)
    stats = summarize(results)
    print_table(results)
    print()
    print(format_summary(f"mode={args.mode} max_side={configured}", stats))

    worst: list[Result] = []
    if args.dump_worst:
        out_dir = Path(args.dump_worst)
        out_dir.mkdir(parents=True, exist_ok=True)
        worst = sorted(results, key=lambda item: -abs(item.error))[:3]
        for item in evaluate([entry.case for entry in worst], args.mode, params, configured, keep_images=True):
            target = out_dir / f"{item.case.path.stem}_got{item.got}_want{item.case.expected}{item.case.path.suffix}"
            cv2.imwrite(str(target), item.annotated)
            print(f"  已导出 {target}")

    if args.sweep_resolution is not None:
        sides = args.sweep_resolution or list(SWEEP_DEFAULT)
        print("\n分辨率对比（同一批图，只改处理时长边）：")
        for side in sides:
            sweep_stats = summarize(evaluate(cases, args.mode, params, side))
            print(format_summary(f"max_side={side}", sweep_stats))

    if args.json:
        print(json.dumps({"max_side": configured, "mode": args.mode, "params": params, **stats}, ensure_ascii=False))

    if args.max_mae is not None and stats["mae"] > args.max_mae:
        print(f"\nMAE {stats['mae']:.2f} 超过阈值 {args.max_mae}，判定为退化。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
