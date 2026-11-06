#!/usr/bin/env python3
"""Kết luận tình trạng giao thông của từng group trong captured_data.json.

Màu tại mỗi tọa độ được so với 4 ô màu của traffic_defined.png
(xanh, vàng, đỏ, đỏ đậm); màu xám của mặt đường (không có nét traffic)
tính là xanh. Tình trạng group (luật đúng đầu tiên thắng):
  1. xanh chiếm đa số                                -> thông thoáng
  2. không có đỏ/đỏ đậm (xanh = vàng, vàng > xanh)   -> di chuyển chậm
  3. vàng >= đỏ + đỏ đậm                             -> ùn tắc nhẹ
  4. đỏ + đỏ đậm >= xanh + vàng, có đỏ đậm           -> ùn tắc nặng
  5. đỏ + đỏ đậm >= xanh + vàng, không đỏ đậm        -> ùn tắc
  6. còn lại (có đỏ nhưng xanh + vàng vẫn nhiều hơn) -> ùn tắc nhẹ
Ảnh đọc từ captured/<key>.png cạnh script.

Cần Pillow: pip install pillow
"""

import argparse
import json
import math
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    sys.exit("Thiếu thư viện Pillow. Cài bằng: pip install pillow")

ROOT = Path(__file__).resolve().parent
LEGEND_PNG = ROOT / "traffic_defined.png"
CAPTURED_DIR = ROOT / "captured"

# Same order as the swatches in traffic_defined.png, left (Fast) to right (Slow)
COLORS = ["xanh", "vàng", "đỏ", "đỏ đậm"]

# RGB distance: a stroke's fill is ~30 from its swatch and its outline ~60; white, grey roads and beige buildings are farther
MAX_DISTANCE = 70

# Bare road surface (no traffic line) counts as xanh; beige land and grey buildings are ~40+ away
GREY = (203, 211, 220)
GREY_DISTANCE = 25


def load_legend(path):
    img = Image.open(path).convert("RGB")
    px = img.load()
    runs, run = [], []
    for x in range(img.width):
        # Background and text are grey (R≈G≈B); only the swatches are saturated
        colored = [p for p in (px[x, y] for y in range(img.height)) if max(p) - min(p) > 40]
        if colored:
            run += colored
        elif run:
            runs.append(run)
            run = []
    if run:
        runs.append(run)
    if len(runs) != len(COLORS):
        sys.exit(f"{path.name}: tìm thấy {len(runs)} ô màu, cần {len(COLORS)}")
    # Per-channel median ignores the anti-aliased swatch edges
    return [tuple(sorted(p[i] for p in run)[len(run) // 2] for i in range(3)) for run in runs]


def nearest(color, legend):
    dists = [math.dist(color, ref) for ref in legend]
    level = min(range(len(legend)), key=dists.__getitem__)
    return level, dists[level]


def classify(color, legend):
    """(level, label, distance); level is None when the colour is neither a legend colour nor road grey."""
    level, dist = nearest(color, legend)
    if dist <= MAX_DISTANCE:
        return level, COLORS[level], dist
    grey = math.dist(color, GREY)
    if grey <= GREY_DISTANCE:
        return 0, "xám (tính là xanh)", grey
    return None, "không khớp", dist


def group_status(votes):
    g, y, r, d = (votes.count(i) for i in range(len(COLORS)))
    heavy, light = r + d, g + y
    if g > y + heavy:
        return "thông thoáng"
    if heavy == 0:
        return "di chuyển chậm"
    if y >= heavy:
        return "ùn tắc nhẹ"
    # Ties go to the heavier side
    if heavy >= light:
        return "ùn tắc nặng" if d else "ùn tắc"
    return "ùn tắc nhẹ"


def warn(msg):
    print(f"Cảnh báo: {msg}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("data", nargs="?", type=Path, default=ROOT / "captured_data.json",
                    help="file JSON tọa độ (mặc định: captured_data.json)")
    ap.add_argument("-v", "--verbose", action="store_true", help="in thêm màu đo được tại từng tọa độ")
    args = ap.parse_args()

    if not args.data.is_file():
        sys.exit(f"Không tìm thấy {args.data}")
    legend = load_legend(LEGEND_PNG)
    data = json.loads(args.data.read_text(encoding="utf-8"))

    failed = False
    for i, (key, groups) in enumerate(data.items()):
        if i:
            print()
        print(f"[{key}]")
        if not groups:
            print("(không có group nào)")
            continue
        path = CAPTURED_DIR / f"{key}.png"
        if not path.is_file():
            print(f"Không tìm thấy ảnh {path}", file=sys.stderr)
            failed = True
            continue
        img = Image.open(path).convert("RGB")

        for name, points in groups.items():
            votes, details = [], []
            for x, y in points:
                if not (0 <= x < img.width and 0 <= y < img.height):
                    warn(f"[{key}] {name} ({x}, {y}) nằm ngoài ảnh {img.width}x{img.height}, bỏ qua")
                    details.append(f"  ({x}, {y}) -> ngoài ảnh")
                    continue
                color = img.getpixel((x, y))
                level, label, dist = classify(color, legend)
                if level is None:
                    warn(f"[{key}] {name} ({x}, {y}) rgb{color} không khớp màu nào trong legend, bỏ qua")
                else:
                    votes.append(level)
                details.append(f"  ({x}, {y}) rgb{color} -> {label} (cách {dist:.1f})")

            status = group_status(votes) if votes else "không xác định"
            print(f"{name} có tình trạng {status}")
            if args.verbose:
                print("  " + " | ".join(f"{c} {votes.count(i)}" for i, c in enumerate(COLORS)))
                for line in details:
                    print(line)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
