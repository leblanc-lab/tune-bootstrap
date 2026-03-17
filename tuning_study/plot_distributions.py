#!/usr/bin/env python3
"""
plot_distributions.py — distributions with parameter-coloured MC lines vs data.

For each fitted histogram this script draws:
  • One coloured line per MC parameter-point (colour encodes a chosen parameter).
  • The best-fit Apprentice prediction (thick dashed black line).
  • Experimental reference data (black error bars).
  • Optional ratio-to-data panel below.

Usage
-----
    python3 plot_distributions.py --study lep
    python3 plot_distributions.py --study lhc --color-by bLund --ratio
    python3 plot_distributions.py --study lep --analysis ALEPH_1996_I428072
    python3 plot_distributions.py --study lep --out plots_distributions

Outputs one PDF per analysis into the output directory.
"""

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.colors as mcolors
from matplotlib.backends.backend_pdf import PdfPages
import h5py
import json

# ── colour palette used for fallback (when Apprentice not needed) ────────────
_CMAP = "viridis"


# ─────────────────────────────────────────────────────────────────────────────
# Data loading helpers
# ─────────────────────────────────────────────────────────────────────────────

def load_hdf5(hdf5_path):
    """Return (bin_keys, xmin, xmax, values, params, pnames).

    values shape: (n_bins, n_runs)
    params shape: (n_runs, n_params)
    """
    with h5py.File(hdf5_path, "r") as f:
        bin_keys = [b.decode() for b in f["index"][:]]
        xmin     = f["xmin"][:]
        xmax     = f["xmax"][:]
        values   = f["values"][:]   # (n_bins, n_runs)
        params   = f["params"][:]   # (n_runs, n_params)
        pnames   = list(f["params"].attrs.get("names", []))
    return bin_keys, xmin, xmax, values, params, pnames


def load_refdata(json_path):
    """Return {bin_key: [central, error]}."""
    with open(json_path) as f:
        return json.load(f)


def load_bestfit_preds(results_dir):
    """Return {hist_path: (x_centers, y_vals)} from the Apprentice predictions YODA."""
    try:
        import yoda
    except ImportError:
        return {}

    pred = {}
    results_dir = Path(results_dir)
    yoda_files = sorted(results_dir.glob("predictions_*.yoda"))
    if not yoda_files:
        return {}

    aos = yoda.read(str(yoda_files[-1]), asdict=True)
    for path, ao in aos.items():
        xs, ys = [], []
        try:
            for pt in ao.points():
                xs.append(pt.x())
                ys.append(pt.y())
        except AttributeError:
            try:
                for b in ao.bins():
                    xs.append(0.5 * (b.xMin() + b.xMax()))
                    ys.append(b.height())
            except AttributeError:
                continue
        if xs:
            pred[path] = (np.array(xs), np.array(ys))
    return pred


def parse_bestfit_params(results_dir):
    """Read best-fit parameter values from minimum_*.txt; return dict."""
    results_dir = Path(results_dir)
    txts = sorted(results_dir.glob("minimum_*.txt"))
    if not txts:
        return {}
    params = {}
    for line in open(txts[-1]):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            try:
                params[parts[0]] = float(parts[1])
            except ValueError:
                pass
    return params


# ─────────────────────────────────────────────────────────────────────────────
# Plotting
# ─────────────────────────────────────────────────────────────────────────────

def group_by_analysis_and_hist(bin_keys):
    """Return nested dict: {analysis: {hist_path: [bin_indices]}}."""
    by_analysis = defaultdict(lambda: defaultdict(list))
    for i, key in enumerate(bin_keys):
        hist = key.rsplit("#", 1)[0]                   # e.g. /ALEPH_1996.../d01-x01-y01
        analysis = hist.split("/")[1]                  # e.g. ALEPH_1996_I428072
        by_analysis[analysis][hist].append(i)
    return by_analysis


def plot_one_histogram(ax_main, ax_ratio,
                       hist_path, bin_indices,
                       xmin, xmax, values, params,
                       param_idx, pname, norm,
                       refdata, bestfit_pred,
                       cmap_name=_CMAP):
    """Plot one histogram into ax_main (and optionally ax_ratio)."""
    cmap = matplotlib.colormaps.get_cmap(cmap_name)

    x_lo  = xmin[bin_indices]
    x_hi  = xmax[bin_indices]
    x_cen = 0.5 * (x_lo + x_hi)
    n_runs = values.shape[1]

    # ── MC coloured lines (one per run) ──────────────────────────────────────
    for r in range(n_runs):
        pval  = params[r, param_idx]
        color = cmap(norm(pval))
        y_mc  = values[bin_indices, r]
        # step plot: need to append last edge
        x_step = np.append(x_lo, x_hi[-1])
        y_step = np.append(y_mc, y_mc[-1])
        ax_main.step(x_step, y_step, where="post",
                     color=color, linewidth=1.2, alpha=0.85, zorder=2)

    # ── best-fit prediction ───────────────────────────────────────────────────
    pred = bestfit_pred.get(hist_path)
    if pred is not None:
        xp, yp = pred
        # Align: sort by x and interpolate to our bin centres if needed
        x_step = np.append(x_lo, x_hi[-1])
        # build step from predicted values matched to bins
        yp_matched = np.interp(x_cen, xp, yp)
        y_step = np.append(yp_matched, yp_matched[-1])
        ax_main.step(x_step, y_step, where="post",
                     color="black", linewidth=2.0, linestyle="--",
                     label="Best fit", zorder=4)

    # ── reference data ────────────────────────────────────────────────────────
    ref_y, ref_e = [], []
    ref_x = []
    for i, idx in enumerate(bin_indices):
        key = "{}#{}".format(hist_path, i)
        entry = refdata.get(key)
        if entry is not None:
            ref_x.append(x_cen[i])
            ref_y.append(entry[0])
            ref_e.append(entry[1])

    if ref_y:
        ref_x = np.array(ref_x)
        ref_y = np.array(ref_y)
        ref_e = np.array(ref_e)
        ax_main.errorbar(ref_x, ref_y, yerr=ref_e,
                         fmt="o", color="black", markersize=3.5,
                         linewidth=1.0, capsize=2, zorder=5, label="Data")

        # ── ratio panel ───────────────────────────────────────────────────────
        if ax_ratio is not None and len(ref_y) > 0:
            safe_ref = np.where(np.abs(ref_y) > 0, ref_y, np.nan)
            for r in range(n_runs):
                pval  = params[r, param_idx]
                color = cmap(norm(pval))
                y_mc  = values[bin_indices, r]
                # interpolate MC to ref x positions
                ymc_at_ref = np.interp(ref_x, x_cen, y_mc)
                ratio = ymc_at_ref / safe_ref
                ax_ratio.plot(ref_x, ratio, ".", color=color,
                              markersize=4, alpha=0.7)
            if pred is not None:
                yp_at_ref = np.interp(ref_x, xp, yp)
                ratio_bf  = yp_at_ref / safe_ref
                ax_ratio.plot(ref_x, ratio_bf, "k--",
                              linewidth=1.5, label="Best fit")
            ax_ratio.axhline(1.0, color="gray", linewidth=0.8)
            ax_ratio.set_ylim(0.5, 1.5)
            ax_ratio.set_ylabel("MC / Data", fontsize=8)

    ax_main.set_ylabel("Value", fontsize=9)

    # Axis label improvements: use log if values span >2 decades
    yvals_all = values[bin_indices, :].ravel()
    yvals_all = yvals_all[yvals_all > 0]
    if len(yvals_all) > 1:
        log_range = np.log10(yvals_all.max()) - np.log10(yvals_all.min())
        if log_range > 2:
            ax_main.set_yscale("log")

    # Title: short histogram ID
    short = hist_path.split("/")[-1]
    ax_main.set_title(short, fontsize=9)
    ax_main.tick_params(labelsize=8)


def make_colorbar(fig, ax, norm, cmap_name, pname):
    sm = cm.ScalarMappable(cmap=matplotlib.colormaps.get_cmap(cmap_name), norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, fraction=0.04, pad=0.02)
    cbar.set_label(pname, fontsize=8)
    cbar.ax.tick_params(labelsize=7)


def plot_analysis_pdf(analysis, hists, bin_indices_map,
                      xmin, xmax, values, params, pnames,
                      param_idx, refdata, bestfit_pred,
                      out_path, ratio, cmap_name, filter_re=None):
    """Produce a multi-page PDF for one analysis."""
    pname = pnames[param_idx] if param_idx < len(pnames) else f"param{param_idx}"
    pvals = params[:, param_idx]
    norm  = mcolors.Normalize(vmin=pvals.min(), vmax=pvals.max())

    hist_names = sorted(hists.keys())
    if filter_re:
        pat = re.compile(filter_re, re.IGNORECASE)
        hist_names = [h for h in hist_names if pat.search(h)]
    if not hist_names:
        return 0

    with PdfPages(out_path) as pdf:
        # ── cover page ───────────────────────────────────────────────────────
        fig_cov, ax_cov = plt.subplots(figsize=(8, 2))
        ax_cov.axis("off")
        ax_cov.text(0.5, 0.7,  analysis, ha="center", fontsize=14, fontweight="bold",
                    transform=ax_cov.transAxes)
        ax_cov.text(0.5, 0.35,
                    f"Colour encodes: {pname}  "
                    f"(range [{pvals.min():.3g}, {pvals.max():.3g}])\n"
                    f"Dashed line = best-fit prediction",
                    ha="center", fontsize=10, transform=ax_cov.transAxes)
        pdf.savefig(fig_cov, bbox_inches="tight")
        plt.close(fig_cov)

        # ── one page per histogram ────────────────────────────────────────────
        n_pages = 0
        for hist_path in hist_names:
            bin_idxs = bin_indices_map[hist_path]
            if len(bin_idxs) < 1:
                continue

            if ratio:
                fig, (ax_main, ax_ratio) = plt.subplots(
                    2, 1, figsize=(7, 5),
                    gridspec_kw={"height_ratios": [3, 1], "hspace": 0.05},
                    sharex=True)
            else:
                fig, ax_main = plt.subplots(figsize=(7, 4))
                ax_ratio = None

            plot_one_histogram(ax_main, ax_ratio,
                               hist_path, bin_idxs,
                               xmin, xmax, values, params,
                               param_idx, pname, norm,
                               refdata, bestfit_pred, cmap_name)

            make_colorbar(fig, ax_main, norm, cmap_name, pname)

            if ax_ratio is not None:
                ax_ratio.set_xlabel(
                    "Bin centre" if xmin[bin_idxs[0]] != xmax[bin_idxs[0]] else "Bin",
                    fontsize=9)
            else:
                ax_main.set_xlabel("Bin centre", fontsize=9)

            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)
            n_pages += 1

    return n_pages


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--study",    required=True, choices=["lep", "lhc"],
                    help="Which study (lep or lhc)")
    ap.add_argument("--color-by", default=None, metavar="PARAM",
                    help="Parameter to use for colour axis (default: first param)")
    ap.add_argument("--analysis", default=None, metavar="REGEX",
                    help="Only plot histograms whose analysis name matches this regex")
    ap.add_argument("--hist",     default=None, metavar="REGEX",
                    help="Only plot histograms whose path matches this regex")
    ap.add_argument("--ratio",    action="store_true",
                    help="Add ratio-to-data panel below each histogram")
    ap.add_argument("--cmap",     default="viridis",
                    help="Matplotlib colormap name (default: viridis)")
    ap.add_argument("--out",      default=None,
                    help="Output directory (default: plots_distributions_<study>)")
    args = ap.parse_args()

    here = Path(__file__).parent
    hdf5     = here / f"mc_{args.study}.hdf5"
    refjson  = here / f"refdata_{args.study}.json"
    res_dir  = here / f"results_{args.study}"
    out_dir  = Path(args.out) if args.out else (here / f"plots_distributions_{args.study}")
    out_dir.mkdir(parents=True, exist_ok=True)

    if not hdf5.exists():
        sys.exit(f"HDF5 not found: {hdf5}\n  Run 03_convert.sh first.")
    if not refjson.exists():
        sys.exit(f"Refdata not found: {refjson}\n  Run 03_convert.sh first.")

    print(f"Loading HDF5: {hdf5}")
    bin_keys, xmin, xmax, values, params, pnames = load_hdf5(hdf5)
    print(f"  {len(bin_keys)} bins, {params.shape[0]} runs, params: {pnames}")

    # Choose colour parameter
    if args.color_by:
        if args.color_by not in pnames:
            sys.exit(f"--color-by '{args.color_by}' not in {pnames}")
        param_idx = pnames.index(args.color_by)
    else:
        param_idx = 0
    print(f"Colouring by: {pnames[param_idx]}")

    print(f"Loading refdata: {refjson}")
    refdata = load_refdata(refjson)

    print(f"Loading best-fit predictions from: {res_dir}")
    bestfit_pred = load_bestfit_preds(res_dir)
    print(f"  {len(bestfit_pred)} histogram predictions found")

    by_analysis = group_by_analysis_and_hist(bin_keys)

    # Filter analyses
    analysis_names = sorted(by_analysis.keys())
    if args.analysis:
        pat = re.compile(args.analysis, re.IGNORECASE)
        analysis_names = [a for a in analysis_names if pat.search(a)]
        if not analysis_names:
            sys.exit(f"No analyses match '{args.analysis}'")

    total_pages = 0
    for analysis in analysis_names:
        hists_dict   = dict(by_analysis[analysis])   # hist_path → [bin_idxs]
        out_pdf = out_dir / f"{analysis}.pdf"
        print(f"  Writing {out_pdf} ({len(hists_dict)} histograms) ...", end=" ", flush=True)
        n = plot_analysis_pdf(
            analysis, hists_dict, hists_dict,
            xmin, xmax, values, params, pnames,
            param_idx, refdata, bestfit_pred,
            out_pdf, args.ratio, args.cmap, filter_re=args.hist)
        print(f"{n} pages")
        total_pages += n

    print(f"\nDone. {total_pages} pages across {len(analysis_names)} PDFs → {out_dir}/")


if __name__ == "__main__":
    main()
