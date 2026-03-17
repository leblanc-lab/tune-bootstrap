#!/usr/bin/env python3
"""
plot_mcvdata.py — overlay MC vs experimental reference data for each observable.

Usage:
    python3 plot_mcvdata.py --study lep [--runs runs_lep] [--out plots_mcvdata]
    python3 plot_mcvdata.py --study lhc [--runs runs_lhc] [--out plots_mcvdata]

Produces one PDF per observable showing:
  - All MC parameter-point predictions (grey, semi-transparent)
  - Reference data from /REF/ entries (black points with error bars)

Requires: numpy, matplotlib, yoda (available after source setup.sh)
"""

import argparse, math, re
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    import yoda
except ImportError:
    raise SystemExit("yoda Python module not found — did you run: source setup.sh ?")


def load_yoda_hists(path: Path) -> dict:
    """Return dict of {path_str: yoda_object} from a YODA file."""
    return yoda.read(str(path))


def scatter_to_xy(ao):
    """Extract (x_mid, y, yerr) arrays from a Scatter2D or Estimate1D/Histo1D."""
    xs, ys, yes = [], [], []
    try:  # Scatter2D / Estimate1D
        for pt in ao.points():
            xs.append(pt.x())
            ys.append(pt.y())
            yes.append(0.5 * (pt.yErrMinus() + pt.yErrPlus()))
    except AttributeError:
        try:  # Histo1D / BinnedHisto1D
            for b in ao.bins():
                xs.append(0.5 * (b.xMin() + b.xMax()))
                ys.append(b.height())
                yes.append(b.heightErr())
        except AttributeError:
            return None, None, None
    return np.array(xs), np.array(ys), np.array(yes)


def main():
    ap = argparse.ArgumentParser(description="MC vs data overlay plots")
    ap.add_argument("--study", required=True, choices=["lep", "lhc"],
                    help="Which study to visualise (lep or lhc)")
    ap.add_argument("--runs", default=None,
                    help="Path to runs_<study>/ directory (default: auto-detect)")
    ap.add_argument("--out", default="plots_mcvdata",
                    help="Output directory for PDF plots")
    ap.add_argument("--yoda-name", default="main144.yoda",
                    help="YODA filename in each run dir (default: main144.yoda)")
    ap.add_argument("--pattern", default="",
                    help="Only plot observables whose path matches this regex")
    args = ap.parse_args()

    here = Path(__file__).parent
    runs_dir = Path(args.runs) if args.runs else here / f"runs_{args.study}"
    out_dir = Path(args.out)
    out_dir.mkdir(exist_ok=True)

    # ── collect run dirs ───────────────────────────────────────────────────────
    run_dirs = sorted(d for d in runs_dir.iterdir()
                      if d.is_dir() and (d / args.yoda_name).exists())
    if not run_dirs:
        raise SystemExit(f"No completed runs found in {runs_dir} "
                         f"(looking for {args.yoda_name})")

    print(f"Found {len(run_dirs)} completed run(s) in {runs_dir}")

    # ── load all YODA files ────────────────────────────────────────────────────
    ref_hists = {}   # path → ao  (from /REF/ entries in first file)
    mc_hists  = {}   # path → list of (xs, ys, yes) across parameter points

    for rd in run_dirs:
        aos = load_yoda_hists(rd / args.yoda_name)
        for path, ao in aos.items():
            if "/REF/" in path:
                clean = re.sub(r"^/REF", "", path)
                if clean not in ref_hists:
                    ref_hists[clean] = ao
            elif "/TMP/" in path or "BEAMPZ" in path:
                continue
            else:
                if args.pattern and not re.search(args.pattern, path):
                    continue
                if path not in mc_hists:
                    mc_hists[path] = []
                xy = scatter_to_xy(ao)
                if xy[0] is not None:
                    mc_hists[path].append(xy)

    if not mc_hists:
        raise SystemExit("No plottable MC histograms found "
                         "(check --pattern or analysis names).")

    # ── plot ───────────────────────────────────────────────────────────────────
    print(f"Plotting {len(mc_hists)} observables → {out_dir}/")
    for path, mc_list in sorted(mc_hists.items()):
        fig, ax = plt.subplots(figsize=(7, 4))

        # MC predictions (grey band)
        for xs, ys, yes in mc_list:
            ax.step(np.append(xs, xs[-1]), np.append(ys, ys[-1]),
                    where="post", color="steelblue", alpha=0.25, linewidth=0.8)

        # Reference data
        ref_ao = ref_hists.get(path)
        if ref_ao is not None:
            rx, ry, rye = scatter_to_xy(ref_ao)
            if rx is not None:
                ax.errorbar(rx, ry, yerr=rye, fmt="ko", markersize=3,
                            linewidth=1, label="Data")

        # Labels
        parts = path.split("/")
        analysis = parts[1] if len(parts) > 1 else path
        hist_id  = "/".join(parts[2:]) if len(parts) > 2 else ""
        ax.set_title(f"{analysis}\n{hist_id}", fontsize=9)
        ax.set_xlabel("x")
        ax.set_ylabel("Value")
        ax.set_xlim(left=0)
        if ref_ao is not None:
            ax.legend(fontsize=8)
        fig.tight_layout()

        # Safe filename
        fname = re.sub(r"[^A-Za-z0-9_\-]", "_", path.strip("/")) + ".pdf"
        fig.savefig(out_dir / fname)
        plt.close(fig)

    print(f"Done. {len(mc_hists)} plots saved to {out_dir}/")


if __name__ == "__main__":
    main()
