#!/usr/bin/env python3
"""Generate inline SVG charts for the back of growth-rate cards.

A chart makes the card's own claim visible: bars() for constant-ratio steps (a
doubling card shows "×2" arrows between bars; n² at inputs 1, 2, 4 shows "×4"),
log_line() for log n on a to-scale x-axis with "+1" arrows, so the flattening shows.
Keep the numbers small. Every bar or point carries its value, and an arrow too
narrow for its label is left off rather than overlapping text.

Text, axes and arrows use currentColor, with opacity for secondary ink, so the
chart follows Anki's night mode; only the bars and line are a fixed blue. Give
each chart its own id: it prefixes the arrowhead marker, and two charts sharing
one on a screen would share the marker. Verified on 2026-10-25 in Anki desktop
and mobile, light and night mode.

    growth_chart.py bars --id sq --x 1 2 4 --y 1 4 16 --step ×4 --label "…"
    growth_chart.py log --id log --label "…"

The SVG goes to stdout. --preview PATH also writes an HTML page showing the chart
on a light and a dark background.
"""
from __future__ import annotations

import argparse
import math
import pathlib
import re
import sys
from typing import cast
from xml.sax.saxutils import escape, quoteattr

BLUE = "#2a78d6"
W, H = 560, 320
BASE = 250          # y of the x-axis baseline
TOP = 70            # y reached by the tallest mark
LEFT, RIGHT = 70, 540
MIN_ARROW = 30      # narrowest arrow span that leaves room for its label
FONT = "font-family:-apple-system,Helvetica,Arial,sans-serif"


def open_svg(cid: str, label: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" '
        + f'role="img" aria-label={quoteattr(label)} style="max-width:{W}px;color:currentColor;{FONT}">',
        f'<defs><marker id="{cid}-ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" '
        + 'markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" '
        + 'fill="currentColor" fill-opacity="0.6"/></marker></defs>',
        f'<line x1="{LEFT - 10}" y1="{BASE}" x2="{RIGHT}" y2="{BASE}" stroke="currentColor" '
        + 'stroke-opacity="0.35" stroke-width="1.5"/>',
    ]


def axis_titles(xtitle: str) -> list[str]:
    mid_y = (BASE + TOP) / 2
    return [
        f'<text x="{(LEFT + RIGHT) / 2}" y="{BASE + 58}" text-anchor="middle" font-size="17" '
        + f'fill="currentColor" fill-opacity="0.75">{xtitle}</text>',
        f'<text x="24" y="{mid_y}" text-anchor="middle" font-size="17" fill="currentColor" '
        + f'fill-opacity="0.75" transform="rotate(-90 24 {mid_y})">work (steps)</text>',
    ]


def arrow(cid: str, x1: float, y1: float, x2: float, y2: float, label: str,
          lift: float = 34) -> list[str]:
    """Curved arrow from (x1, y1) to (x2, y2) arcing above both, with a label at its peak.

    Returns nothing when the span is too narrow for the label."""
    if x2 - x1 < MIN_ARROW:
        return []
    cx, cy = (x1 + x2) / 2, min(y1, y2) - lift
    peak = (y1 + 2 * cy + y2) / 4           # y of the quadratic curve's midpoint
    return [
        f'<path d="M{x1},{y1} Q{cx},{cy} {x2},{y2}" fill="none" stroke="currentColor" '
        + f'stroke-opacity="0.6" stroke-width="1.5" marker-end="url(#{cid}-ah)"/>',
        f'<text x="{cx}" y="{peak - 14}" text-anchor="middle" font-size="17" font-weight="600" '
        + f'fill="currentColor" fill-opacity="0.8">{escape(label)}</text>',
    ]


def bars(cid: str, xs: list[int], vals: list[int], step_label: str, label: str) -> str:
    n = len(xs)
    slot = (RIGHT - LEFT) / n
    w = min(64, slot * 0.5)
    vmax = max(vals)
    out = open_svg(cid, label)
    centers: list[float] = []
    tops: list[float] = []
    for i, (x, v) in enumerate(zip(xs, vals)):
        c = LEFT + slot * (i + 0.5)
        t = BASE - (BASE - TOP) * v / vmax
        l = c - w / 2
        r = min(4, (BASE - t) / 2)       # a bar shorter than the corners stays above the axis
        centers.append(c)
        tops.append(t)
        out.append(f'<path d="M{l},{BASE} V{t + r} Q{l},{t} {l + r},{t} H{l + w - r} '
                   + f'Q{l + w},{t} {l + w},{t + r} V{BASE} Z" fill="{BLUE}"/>')
        out.append(f'<text x="{c}" y="{t - 8}" text-anchor="middle" font-size="20" '
                   + f'font-weight="600" fill="currentColor">{v}</text>')
        out.append(f'<text x="{c}" y="{BASE + 26}" text-anchor="middle" font-size="17" '
                   + f'fill="currentColor" fill-opacity="0.75">{x}</text>')
    for i in range(n - 1):
        out += arrow(cid, centers[i] + w / 2 - 4, tops[i] - 32,
                     centers[i + 1] - w / 2 + 4, tops[i + 1] - 32, step_label)
    out += axis_titles("items in the input (n)")
    out.append("</svg>")
    return "".join(out)


def log_line(cid: str, label: str) -> str:
    xmax = 32
    def X(n: float) -> float: return LEFT + (RIGHT - LEFT - 10) * n / xmax
    def Y(v: float) -> float: return BASE - (BASE - TOP) * v / 5
    out = open_svg(cid, label)
    curve = " ".join(f"{X(n):.1f},{Y(math.log2(n)):.1f}"
                     for n in [1 + i * 0.25 for i in range(int((xmax - 1) / 0.25) + 1)])
    out.append(f'<polyline points="{curve}" fill="none" stroke="{BLUE}" stroke-width="2.5" '
               + 'stroke-linejoin="round" stroke-linecap="round"/>')
    pts = [2, 4, 8, 16, 32]
    for n in pts:
        v = int(math.log2(n))
        out.append(f'<circle cx="{X(n)}" cy="{Y(v)}" r="5" fill="{BLUE}"/>')
        out.append(f'<text x="{X(n)}" y="{Y(v) - 14}" text-anchor="middle" font-size="20" '
                   + f'font-weight="600" fill="currentColor">{v}</text>')
        out.append(f'<text x="{X(n)}" y="{BASE + 26}" text-anchor="middle" font-size="17" '
                   + f'fill="currentColor" fill-opacity="0.75">{n}</text>')
    # "+1" between neighbouring points; arrow() drops the 2→4 gap, too narrow for a label
    for a, b in zip(pts, pts[1:]):  # noqa: RUF007 -- pairwise needs 3.10; the system python3 is 3.9
        out += arrow(cid, X(a) + 8, Y(math.log2(a)) - 36, X(b) - 8, Y(math.log2(b)) - 36, "+1", lift=26)
    out += axis_titles("items in the input (n)")
    out.append("</svg>")
    return "".join(out)


def preview(svg: str) -> str:
    """An HTML page showing the chart on a light and a dark background, like Anki's two modes."""
    pane = '<div style="background:{};color:{};padding:16px;margin-bottom:16px">{}</div>'
    return ('<!doctype html><meta charset="utf-8"><title>Chart preview</title>'
            + '<body style="margin:16px;background:#888">'
            + pane.format("#fff", "#000", svg) + pane.format("#2c2c2c", "#fff", svg)
            + "</body>")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Write an inline SVG growth chart to stdout.")
    kinds = parser.add_subparsers(dest="kind", required=True)
    for name in ("bars", "log"):
        kind = kinds.add_parser(name)
        _ = kind.add_argument("--id", required=True, help="unique per chart; prefixes the marker id")
        _ = kind.add_argument("--label", required=True, help="aria-label stating the data in words")
        _ = kind.add_argument("--preview", type=pathlib.Path, help="also write an HTML preview here")
        if name == "bars":
            _ = kind.add_argument("--x", type=int, nargs="+", required=True, help="inputs, one per bar")
            _ = kind.add_argument("--y", type=int, nargs="+", required=True, help="work, one per bar")
            _ = kind.add_argument("--step", required=True, help='arrow label, e.g. "×2"')
    args = parser.parse_args(argv)
    cid, label = cast(str, args.id), cast(str, args.label)
    if not re.fullmatch(r"[A-Za-z][\w-]*", cid):
        parser.error("--id must start with a letter and hold only letters, digits, _ and -")
    preview_path = cast("pathlib.Path | None", args.preview)

    if cast(str, args.kind) == "bars":
        xs, ys = cast("list[int]", args.x), cast("list[int]", args.y)
        if len(xs) != len(ys):
            parser.error("--x and --y need the same number of values")
        if min(ys) < 0 or max(ys) == 0:
            parser.error("--y needs non-negative values, at least one above 0")
        svg = bars(cid, xs, ys, cast(str, args.step), label)
    else:
        svg = log_line(cid, label)
    if preview_path:
        _ = preview_path.write_text(preview(svg), encoding="utf-8")
    _ = sys.stdout.write(svg + "\n")


if __name__ == "__main__":
    main()
