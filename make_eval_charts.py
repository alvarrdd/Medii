"""Generate slide-ready charts from evaluation_results.csv.

This implementation uses Pillow only (no matplotlib dependency).
"""

from __future__ import annotations

import csv
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main() -> None:
    src = Path("evaluation_results.csv")
    if not src.exists():
        raise FileNotFoundError("Run evaluate_medi.py first to create evaluation_results.csv")

    rows = read_rows(src)
    labels = [r["Experiment"] for r in rows]

    top1 = [float(r["Top-1 Relevance"]) for r in rows]
    top3 = [float(r["Top-3 Relevance"]) for r in rows]
    spec = [float(r["Specialist Correctness"]) for r in rows]
    lat = [float(r["Avg Latency (ms)"]) for r in rows]

    out_dir = Path("slide_assets")
    out_dir.mkdir(exist_ok=True)

    # Basic font fallback
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 18)
        title_font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 26)
    except Exception:
        font = ImageFont.load_default()
        title_font = ImageFont.load_default()

    # Chart 1: grouped bars for quality metrics
    w, h = 1300, 760
    img = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(img)
    d.text((30, 20), "Medi Evaluation Metrics by Experiment", fill="black", font=title_font)
    plot_left, plot_top, plot_right, plot_bottom = 90, 90, 1240, 640
    d.rectangle((plot_left, plot_top, plot_right, plot_bottom), outline="#666", width=2)
    for y in range(0, 101, 20):
        yy = plot_bottom - (plot_bottom - plot_top) * y / 100
        d.line((plot_left, yy, plot_right, yy), fill="#e6e6e6", width=1)
        d.text((45, yy - 10), f"{y}", fill="#444", font=font)

    group_w = (plot_right - plot_left) / max(1, len(labels))
    bar_w = int(group_w * 0.18)
    colors = ["#6a5acd", "#32a852", "#ffb347"]  # top1, top3, spec
    for i, lab in enumerate(labels):
        gx = plot_left + i * group_w + group_w * 0.2
        vals = [top1[i], top3[i], spec[i]]
        for j, v in enumerate(vals):
            x0 = int(gx + j * (bar_w + 10))
            x1 = x0 + bar_w
            y1 = plot_bottom
            y0 = int(plot_bottom - (plot_bottom - plot_top) * v / 100)
            d.rectangle((x0, y0, x1, y1), fill=colors[j], outline=colors[j])
            d.text((x0 - 3, y0 - 22), f"{v:.1f}", fill="#222", font=font)
        d.text((int(gx), plot_bottom + 12), lab, fill="#333", font=font)

    # Legend
    legend = [("Top-1 Relevance", colors[0]), ("Top-3 Relevance", colors[1]), ("Specialist Correctness", colors[2])]
    lx, ly = 860, 30
    for name, c in legend:
        d.rectangle((lx, ly, lx + 20, ly + 20), fill=c, outline=c)
        d.text((lx + 28, ly - 2), name, fill="#222", font=font)
        ly += 28

    img.save(out_dir / "medi_eval_quality.png")

    # Chart 2: latency bars
    w2, h2 = 1000, 600
    img2 = Image.new("RGB", (w2, h2), "white")
    d2 = ImageDraw.Draw(img2)
    d2.text((30, 20), "Medi Average Response Latency (ms)", fill="black", font=title_font)
    l, t, r, b = 90, 90, 940, 520
    d2.rectangle((l, t, r, b), outline="#666", width=2)
    max_lat = max(lat) if lat else 1.0
    for i, lab in enumerate(labels):
        gx = l + (r - l) * (i + 0.2) / len(labels)
        bw = int((r - l) / len(labels) * 0.5)
        x0 = int(gx)
        x1 = x0 + bw
        y1 = b
        y0 = int(b - (b - t) * (lat[i] / max_lat))
        d2.rectangle((x0, y0, x1, y1), fill="#6a5acd")
        d2.text((x0, y0 - 24), f"{lat[i]:.1f}", fill="#222", font=font)
        d2.text((x0, b + 10), lab, fill="#333", font=font)

    img2.save(out_dir / "medi_eval_latency.png")

    print(f"Saved: {(out_dir / 'medi_eval_quality.png').resolve()}")
    print(f"Saved: {(out_dir / 'medi_eval_latency.png').resolve()}")


if __name__ == "__main__":
    main()
