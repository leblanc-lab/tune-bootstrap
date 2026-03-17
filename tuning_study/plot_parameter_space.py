#!/usr/bin/env python3
"""
plot_parameter_space.py — visualise the sampled parameter grid and tuning result.

Usage:
    # Show the sampled grid (before or after tuning):
    python3 plot_parameter_space.py --study lep

    # Overlay the best-fit point from 05_tune.sh output:
    python3 plot_parameter_space.py --study lep --result results_lep/minimum_0.txt

Produces a corner-plot (all 2-D parameter projections) as a PDF.

Requires: numpy, matplotlib
"""

import argparse, re
from pathlib import Path
from itertools import combinations

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def load_params(runs_dir: Path) -> tuple[list[str], np.ndarray]:
    """Return (param_names, values_array shape [N, P]) from runs_*/params.dat."""
    rows = []
    names = None
    for rd in sorted(runs_dir.iterdir()):
        pf = rd / "params.dat"
        if not pf.exists():
            continue
        this_names, vals = [], []
        for line in pf.read_text().splitlines():
            parts = line.split()
            if len(parts) == 2:
                this_names.append(parts[0])
                vals.append(float(parts[1]))
        if names is None:
            names = this_names
        rows.append(vals)
    return names, np.array(rows)


def load_result(result_file: Path) -> dict[str, float]:
    """Parse Apprentice minimum_*.txt for best-fit parameter values."""
    best = {}
    text = result_file.read_text()
    # Format varies; look for lines like:  aLund : 0.1234
    for line in text.splitlines():
        m = re.match(r"\s*(\w+)\s*[=:]\s*([-+\d.eE]+)", line)
        if m:
            best[m.group(1)] = float(m.group(2))
    return best


def corner_plot(names, values, best=None, out_path="parameter_space.pdf", ranges=None):
    n = len(names)
    fig, axes = plt.subplots(n, n, figsize=(3.5 * n, 3.5 * n))
    if n == 1:
        axes = np.array([[axes]])

    for i in range(n):      # row = y-axis param
        for j in range(n):  # col = x-axis param
            ax = axes[i, j]
            if j > i:
                ax.set_visible(False)
                continue
            if i == j:
                # Diagonal: 1-D histogram
                ax.hist(values[:, i], bins=max(5, int(len(values) ** 0.5)),
                        color="steelblue", edgecolor="white", linewidth=0.5)
                if best and names[i] in best:
                    ax.axvline(best[names[i]], color="red", linewidth=1.5,
                               linestyle="--", label="Best fit")
                    ax.legend(fontsize=7)
                if ranges and names[i] in ranges:
                    ax.set_xlim(ranges[names[i]])
            else:
                # Off-diagonal: scatter
                ax.scatter(values[:, j], values[:, i], s=18,
                           color="steelblue", alpha=0.7, edgecolors="none")
                if best and names[j] in best and names[i] in best:
                    ax.plot(best[names[j]], best[names[i]], "r*",
                            markersize=12, label="Best fit", zorder=5)
                    ax.legend(fontsize=7)
                if ranges:
                    if names[j] in ranges:
                        ax.set_xlim(ranges[names[j]])
                    if names[i] in ranges:
                        ax.set_ylim(ranges[names[i]])

            # Axis labels only on edges
            if j == 0:
                ax.set_ylabel(names[i], fontsize=9)
            else:
                ax.set_yticklabels([])
            if i == n - 1:
                ax.set_xlabel(names[j], fontsize=9)
            else:
                ax.set_xticklabels([])

    fig.suptitle("Parameter space (sampled points"
                 + (", ★ best fit)" if best else ")"),
                 fontsize=11, y=1.01)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out_path}")


def main():
    ap = argparse.ArgumentParser(description="Corner plot of tuning parameter space")
    ap.add_argument("--study", required=True, choices=["lep", "lhc"],
                    help="Which study to plot")
    ap.add_argument("--runs", default=None,
                    help="Path to runs_<study>/ directory (default: auto-detect)")
    ap.add_argument("--result", default=None,
                    help="Path to Apprentice minimum_*.txt to overlay best-fit point")
    ap.add_argument("--params-json", default=None,
                    help="Path to params.json to use as axis limits")
    ap.add_argument("--out", default=None,
                    help="Output PDF filename")
    args = ap.parse_args()

    here = Path(__file__).parent
    runs_dir = Path(args.runs) if args.runs else here / f"runs_{args.study}"
    out_path = args.out or str(here / f"parameter_space_{args.study}.pdf")

    names, values = load_params(runs_dir)
    if values.size == 0:
        raise SystemExit(f"No params.dat files found in {runs_dir}")

    print(f"Loaded {len(values)} parameter points, {len(names)} parameters: {names}")

    best = None
    if args.result:
        best = load_result(Path(args.result))
        if best:
            print(f"Best-fit values: {best}")
        else:
            print(f"Warning: could not parse best-fit from {args.result}")

    ranges = None
    if args.params_json:
        import json
        raw = json.loads(Path(args.params_json).read_text())
        ranges = {k: tuple(v) for k, v in raw.items()}

    corner_plot(names, values, best=best, out_path=out_path, ranges=ranges)


if __name__ == "__main__":
    main()
