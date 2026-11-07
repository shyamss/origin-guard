#!/usr/bin/env python3
"""Render the pilot's stratum effects as a dependency-free SVG."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ORDER = ("target", "secondary", "control")
LABELS = {
    "target": "Target (n=5)",
    "secondary": "Secondary (n=2)",
    "control": "Negative control (n=4)",
}


def scale(value: float) -> float:
    # Fixed scale keeps the exploratory figure comparable after regeneration.
    return 220 + (value + 10) * (600 / 50)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    data = json.loads(args.summary.read_text())
    rows = []
    for index, key in enumerate(ORDER):
        item = data["strata"][key]
        low, high = item["bootstrap_95pct_ci_mean_margin_effect"]
        mean = item["mean_margin_effect"]
        y = 105 + index * 70
        rows.append(
            f'<text x="20" y="{y + 5}" class="label">{LABELS[key]}</text>'
            f'<line x1="{scale(low):.1f}" y1="{y}" x2="{scale(high):.1f}" y2="{y}" class="ci"/>'
            f'<line x1="{scale(low):.1f}" y1="{y - 7}" x2="{scale(low):.1f}" y2="{y + 7}" class="cap"/>'
            f'<line x1="{scale(high):.1f}" y1="{y - 7}" x2="{scale(high):.1f}" y2="{y + 7}" class="cap"/>'
            f'<circle cx="{scale(mean):.1f}" cy="{y}" r="6" class="point"/>'
            f'<text x="{min(scale(high) + 12, 797):.1f}" y="{y + 5}" class="value">{mean:+.2f}</text>'
        )

    ticks = []
    for tick in (-10, 0, 10, 20, 30, 40):
        x = scale(tick)
        ticks.append(
            f'<line x1="{x:.1f}" y1="70" x2="{x:.1f}" y2="270" class="grid"/>'
            f'<text x="{x:.1f}" y="295" text-anchor="middle" class="tick">{tick:+d}</text>'
        )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="860" height="340" viewBox="0 0 860 340">
<style>
  .title {{ font: 600 18px system-ui, sans-serif; fill: #17213a; }}
  .subtitle, .tick, .value {{ font: 12px system-ui, sans-serif; fill: #526079; }}
  .label {{ font: 13px system-ui, sans-serif; fill: #17213a; }}
  .grid {{ stroke: #dfe4ec; stroke-width: 1; }}
  .zero {{ stroke: #6c778d; stroke-width: 1.5; }}
  .ci, .cap {{ stroke: #3f66b5; stroke-width: 2.5; }}
  .point {{ fill: #173f8f; }}
</style>
<rect width="860" height="340" fill="white"/>
<text x="20" y="28" class="title">Combined origin+policy view: paired attack–benign margin effect</text>
<text x="20" y="49" class="subtitle">Mean monitor-score effect and case-bootstrap 95% interval; exploratory pilot</text>
{''.join(ticks)}
<line x1="{scale(0):.1f}" y1="70" x2="{scale(0):.1f}" y2="270" class="zero"/>
{''.join(rows)}
<text x="520" y="325" text-anchor="middle" class="subtitle">Positive favors combined view over placebo</text>
</svg>
'''
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(svg)


if __name__ == "__main__":
    main()
