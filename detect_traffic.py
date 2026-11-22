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
Ảnh đọc từ ../screenshot/<key>.png (ngoài folder traffic-live).

Cần Pillow: pip install pillow
"""

import argparse
import json
import math
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    sys.exit("Thiếu thư viện Pillow. Cài bằng: pip install pillow")

ROOT = Path(__file__).resolve().parent
LEGEND_PNG = ROOT / "traffic_defined.png"
CAPTURED_DIR = ROOT.parent / "screenshot"

# Same order as the swatches in traffic_defined.png, left (Fast) to right (Slow)
COLORS = ["xanh", "vàng", "đỏ", "đỏ đậm"]

# RGB distance: a stroke's fill is ~30 from its swatch and its outline ~60; white, grey roads and beige buildings are farther
MAX_DISTANCE = 70

# Bare road surface (no traffic line) counts as xanh; beige land and grey buildings are ~40+ away
GREYS = [(203, 211, 220), (0xBA, 0xC8, 0xD6)]  # road grey, #bac8d6
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
    grey = min(math.dist(color, ref) for ref in GREYS)
    if grey <= GREY_DISTANCE:
        return 0, "xám (tính là xanh)", grey
    level, dist = nearest(color, legend)
    if dist <= MAX_DISTANCE:
        return level, COLORS[level], dist
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


def load_data(arg):
    """arg là chuỗi JSON, '-' (đọc stdin) hoặc đường dẫn file JSON."""
    if arg == "-":
        text = sys.stdin.read()
    elif arg.lstrip().startswith("{"):
        text = arg
    else:
        path = Path(arg)
        if not path.is_file():
            sys.exit(f"Không tìm thấy {path}")
        text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        sys.exit(f"JSON không hợp lệ: {e}")


def post_result(url, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"POST {url} -> {resp.status}", file=sys.stderr)
            return True
    except (urllib.error.URLError, OSError) as e:
        print(f"POST {url} thất bại: {e}", file=sys.stderr)
        return False


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("data", nargs="?", default=str(ROOT / "captured_data.json"),
                    help="chuỗi JSON, '-' (stdin) hoặc file JSON (mặc định: captured_data.json)")
    ap.add_argument("--api", default=os.environ.get("LIVE_TRAFFIC_API", "https://thordang-mcp-orchestrator.hf.space/vinfast/api/live-traffic"),
                    help="URL API nhận kết quả (mặc định: $LIVE_TRAFFIC_API hoặc https://thordang-mcp-orchestrator.hf.space/vinfast/api/live-traffic)")
    ap.add_argument("--no-post", action="store_true", help="không gọi API sau khi detect")
    ap.add_argument("-v", "--verbose", action="store_true", help="in thêm màu đo được tại từng tọa độ")
    args = ap.parse_args()

    legend = load_legend(LEGEND_PNG)
    data = load_data(args.data)
    # Record format: {"name": "C1", "data": {group: points}, "current_status": {...}} (or a list of them)
    if isinstance(data, list) or "data" in data:
        records = data if isinstance(data, list) else [data]
        cameras = [(r["name"], r.get("data") or {}, r) for r in records]
    else:
        data.pop("current_status", None)
        records = None
        cameras = [(k, g, None) for k, g in data.items()]
    current_status = {}

    failed = False
    for i, (key, groups, record) in enumerate(cameras):
        current_status[key] = {}
        if record is not None:
            record["current_status"] = current_status[key]
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
            current_status[key][name] = {
                "label": status,
                "data": [votes.count(i) for i in range(len(COLORS))],
            }
            print(f"{name} có tình trạng {status}")
            if args.verbose:
                print("  " + " | ".join(f"{c} {votes.count(i)}" for i, c in enumerate(COLORS)))
                for line in details:
                    print(line)

    if records is None:
        data["current_status"] = current_status
        payloads = [data]
    else:
        # Existing records only need id + current_status; updated_at is set by the server
        payloads = [{"id": r["id"], "current_status": r["current_status"]} if r.get("id")
                    else {k: v for k, v in r.items() if k != "updated_at"} for r in records]
    if not args.no_post:
        for payload in payloads:
            if not post_result(args.api, payload):
                failed = True
            if args.verbose:
                print(json.dumps(payload, ensure_ascii=False))

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
