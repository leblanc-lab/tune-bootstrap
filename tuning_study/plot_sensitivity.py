#!/usr/bin/env python3
"""
plot_sensitivity.py — which observables are most sensitive to each parameter?

Two complementary views are produced in a single PDF:

  Page 1 — Sensitivity heatmap
    Rows = observables (one per fitted histogram), columns = tuning parameters.
    Colour = fractional sensitivity: how much does this histogram's mean value
    change (relative to its value at the best-fit point) when the parameter
    moves by its full tuning range?  Computed as:

        S_ij = |∂f_i/∂X_j| × ΔX_j / |f_i(X_best)|

    where the gradient is obtained by finite differences on the polynomial
    approximation.

  Pages 2-N — Per-parameter ranking
    For each parameter, a horizontal bar chart showing the top-K histograms
    sorted by S_ij (default K = 20).

  Page N+1 — Parameter cross-correlation
    Pearson correlation between parameter values and MC bin values across the
    training runs (one row per parameter; column = mean across all bins in a
    histogram).  This shows whether the parameters are coupled (whether tuning
    one also shifts observations sensitive to another).

Usage
-----
    python3 plot_sensitivity.py --study lep
    python3 plot_sensitivity.py --study lhc --top 30
    python3 plot_sensitivity.py --study lep --out sensitivity_lep.pdf

Requires: numpy, matplotlib, h5py, apprentice (loaded via setup.sh)
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
import matplotlib.colors as mcolors
from matplotlib.backends.backend_pdf import PdfPages
import h5py
import json


# ─────────────────────────────────────────────────────────────────────────────
# Apprentice polynomial evaluation (finite-difference gradients)
# ─────────────────────────────────────────────────────────────────────────────

def _build_approx_evaluators(approx_json):
    """Return (keys, evaluator_list) where evaluator(X) → float."""
    sys.path.insert(0, str(Path(__file__).parent.parent / "apprentice"))
    import apprentice

    with open(approx_json) as f:
        data = json.load(f)

    keys = list(data.keys())
    evaluators = []
    valid_keys = []
    for k in keys:
        d = data[k]
        # Skip metadata entries (e.g. "__xmin", "__xmax") which are lists not dicts
        if not isinstance(d, dict) or "pcoeff" not in d:
            continue
        try:
            if "qcoeff" not in d:
                pa = apprentice.PolynomialApproximation(initDict=d)
            else:
                pa = apprentice.RationalApproximation(initDict=d)
        except Exception:
            continue
        valid_keys.append(k)
        evaluators.append(pa)

    return valid_keys, evaluators


def _finite_diff_gradient(pa, X_best, h_frac=1e-3):
    """Central finite difference gradient of pa at X_best.

    Uses h = max(h_frac * |Xi|, 1e-6) for each coordinate.
    Returns array of shape (n_params,).
    """
    X = np.array(X_best, dtype=float)
    grad = np.zeros_like(X)
    for i in range(len(X)):
        h = max(h_frac * abs(X[i]), 1e-6)
        Xp = X.copy(); Xp[i] += h
        Xm = X.copy(); Xm[i] -= h
        grad[i] = (pa(Xp) - pa(Xm)) / (2.0 * h)
    return grad


# ─────────────────────────────────────────────────────────────────────────────
# Data loading helpers
# ─────────────────────────────────────────────────────────────────────────────

def load_hdf5(hdf5_path):
    with h5py.File(hdf5_path, "r") as f:
        bin_keys = [b.decode() for b in f["index"][:]]
        values   = f["values"][:]   # (n_bins, n_runs)
        params   = f["params"][:]   # (n_runs, n_params)
        pnames   = list(f["params"].attrs.get("names", []))
        xmin     = f["xmin"][:]
        xmax     = f["xmax"][:]
    return bin_keys, values, params, pnames, xmin, xmax


def parse_bestfit_params(results_dir):
    results_dir = Path(results_dir)
    txts = sorted(results_dir.glob("minimum_*.txt"))
    if not txts:
        return {}
    out = {}
    for line in open(txts[-1]):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            try:
                out[parts[0]] = float(parts[1])
            except ValueError:
                pass
    return out


def group_bins_by_hist(bin_keys):
    """Return {hist_path: [bin_indices]}, ordering preserved."""
    d = defaultdict(list)
    for i, k in enumerate(bin_keys):
        hist = k.rsplit("#", 1)[0]
        d[hist].append(i)
    return dict(d)


# ─────────────────────────────────────────────────────────────────────────────
# Sensitivity computation
# ─────────────────────────────────────────────────────────────────────────────

def compute_sensitivities(approx_json, bin_keys, pnames, X_best, param_ranges):
    """Compute per-bin fractional sensitivity matrix S[n_bins, n_params].

    S_ij = |grad_j(f_i)| × ΔX_j / max(|f_i(X_best)|, tiny)

    where ΔX_j = param_ranges[j] = Xmax_j - Xmin_j.
    """
    print("  Loading and evaluating approximations …")
    keys_approx, evs = _build_approx_evaluators(approx_json)

    # Build index mapping: approx key → bin position in HDF5 index
    key_to_hdf5 = {k: i for i, k in enumerate(bin_keys)}
    n_bins   = len(bin_keys)
    n_params = len(pnames)
    S = np.zeros((n_bins, n_params))

    n = len(keys_approx)
    for i_ev, (k, ev) in enumerate(zip(keys_approx, evs)):
        if (i_ev + 1) % 200 == 0:
            print(f"    {i_ev+1}/{n} …")
        if k not in key_to_hdf5:
            continue
        hdf5_idx = key_to_hdf5[k]

        f0 = ev(X_best)
        denom = max(abs(f0), 1e-12)
        grad  = _finite_diff_gradient(ev, X_best)

        for j in range(n_params):
            S[hdf5_idx, j] = abs(grad[j]) * param_ranges[j] / denom

    return S


def aggregate_by_hist(S, bin_keys, hist_order):
    """Mean sensitivity per histogram: S_hist[n_hists, n_params]."""
    d = defaultdict(list)
    for i, k in enumerate(bin_keys):
        hist = k.rsplit("#", 1)[0]
        d[hist].append(i)

    S_hist = np.zeros((len(hist_order), S.shape[1]))
    for h_idx, hist in enumerate(hist_order):
        idxs = d[hist]
        if idxs:
            S_hist[h_idx] = S[idxs, :].mean(axis=0)
    return S_hist


# ─────────────────────────────────────────────────────────────────────────────
# Pearson correlation from MC samples
# ─────────────────────────────────────────────────────────────────────────────

def compute_pearson_by_hist(values, params, bin_keys, hist_order):
    """For each histogram, compute mean |Pearson r| between each param and bin values.

    Returns corr_hist[n_hists, n_params] ∈ [-1, 1].
    """
    n_params = params.shape[1]
    d = defaultdict(list)
    for i, k in enumerate(bin_keys):
        d[k.rsplit("#", 1)[0]].append(i)

    corr_hist = np.zeros((len(hist_order), n_params))
    for h_idx, hist in enumerate(hist_order):
        idxs = d[hist]
        if not idxs:
            continue
        # For each bin in this histogram, compute correlation with each param
        r_matrix = np.zeros((len(idxs), n_params))
        for b_pos, b_idx in enumerate(idxs):
            y = values[b_idx, :]   # shape (n_runs,)
            if np.std(y) < 1e-15:
                continue
            for j in range(n_params):
                x = params[:, j]
                if np.std(x) < 1e-15:
                    continue
                r = np.corrcoef(x, y)[0, 1]
                r_matrix[b_pos, j] = r
        corr_hist[h_idx] = r_matrix.mean(axis=0)

    return corr_hist


# ─────────────────────────────────────────────────────────────────────────────
# Plotting helpers
# ─────────────────────────────────────────────────────────────────────────────

def short_label(hist_path):
    """Return a compact label for a histogram path."""
    parts = hist_path.strip("/").split("/")
    if len(parts) >= 2:
        return f"{parts[0]}\n{parts[1]}"
    return hist_path.strip("/")


def plot_heatmap(pdf, S_hist, hist_order, pnames, title, cmap, vmin=None, vmax=None):
    """One-page heatmap: rows = histograms, columns = parameters."""
    n_hists, n_params = S_hist.shape
    fig_h = max(6, n_hists * 0.22 + 2)
    fig, ax = plt.subplots(figsize=(max(4, n_params * 1.5 + 2), fig_h))

    labels = [short_label(h) for h in hist_order]
    im = ax.imshow(S_hist, aspect="auto", cmap=cmap,
                   vmin=vmin, vmax=vmax, interpolation="nearest")

    ax.set_xticks(range(n_params))
    ax.set_xticklabels(pnames, fontsize=10, fontweight="bold")
    ax.set_yticks(range(n_hists))
    ax.set_yticklabels(labels, fontsize=max(4, min(8, 9 - n_hists // 30)))
    ax.set_title(title, fontsize=11)

    cbar = fig.colorbar(im, ax=ax, fraction=0.02, pad=0.02)
    cbar.ax.tick_params(labelsize=8)

    plt.tight_layout()
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def plot_parameter_ranking(pdf, S_hist, hist_order, pnames, top_k):
    """One page per parameter: horizontal bar chart of top-K histograms."""
    for j, pname in enumerate(pnames):
        sv = S_hist[:, j]
        # Sort descending
        order = np.argsort(sv)[::-1][:top_k]
        labels_k = [short_label(hist_order[i]) for i in order]
        vals_k   = sv[order]

        fig, ax = plt.subplots(figsize=(8, max(4, len(labels_k) * 0.35 + 1.5)))
        colors = plt.cm.RdYlGn_r(np.linspace(0.1, 0.9, len(vals_k)))
        bars = ax.barh(range(len(labels_k)), vals_k, color=colors, edgecolor="white",
                       linewidth=0.5)
        ax.set_yticks(range(len(labels_k)))
        ax.set_yticklabels(labels_k, fontsize=8)
        ax.invert_yaxis()
        ax.set_xlabel("Fractional sensitivity  |∂f/∂X| · ΔX / |f|", fontsize=9)
        ax.set_title(f"Most sensitive observables — {pname}", fontsize=11)
        ax.grid(axis="x", alpha=0.3)

        # Annotate values
        for bar, v in zip(bars, vals_k):
            ax.text(bar.get_width() + max(vals_k) * 0.01, bar.get_y() + bar.get_height() / 2,
                    f"{v:.2f}", va="center", ha="left", fontsize=7)

        plt.tight_layout()
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)


def plot_pearson_heatmap(pdf, corr_hist, hist_order, pnames):
    """Heatmap of mean Pearson r between param values and bin values across runs."""
    n_hists, n_params = corr_hist.shape
    fig_h = max(6, n_hists * 0.22 + 2)
    fig, ax = plt.subplots(figsize=(max(4, n_params * 1.5 + 2), fig_h))

    labels = [short_label(h) for h in hist_order]
    im = ax.imshow(corr_hist, aspect="auto", cmap="RdBu_r",
                   vmin=-1, vmax=1, interpolation="nearest")

    ax.set_xticks(range(n_params))
    ax.set_xticklabels(pnames, fontsize=10, fontweight="bold")
    ax.set_yticks(range(n_hists))
    ax.set_yticklabels(labels, fontsize=max(4, min(8, 9 - n_hists // 30)))
    ax.set_title("Pearson correlation: parameter ↔ bin value (across MC runs)", fontsize=11)

    cbar = fig.colorbar(im, ax=ax, fraction=0.02, pad=0.02)
    cbar.set_label("r", fontsize=9)
    cbar.ax.tick_params(labelsize=8)

    plt.tight_layout()
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def plot_summary_scatter(pdf, S_hist, corr_hist, hist_order, pnames):
    """For each param pair, scatter of sensitivities to show coupling."""
    n_params = len(pnames)
    if n_params < 2:
        return
    fig, axes = plt.subplots(n_params, n_params,
                              figsize=(3.5 * n_params, 3.5 * n_params))
    for i in range(n_params):
        for j in range(n_params):
            ax = axes[i, j] if n_params > 1 else axes
            if i == j:
                ax.hist(S_hist[:, i], bins=30, color="steelblue", edgecolor="white")
                ax.set_xlabel(pnames[i], fontsize=9)
                ax.set_ylabel("# histograms", fontsize=8)
            elif i < j:
                ax.scatter(S_hist[:, j], S_hist[:, i],
                           alpha=0.5, s=10, color="steelblue")
                ax.set_xlabel(f"Sensitivity to {pnames[j]}", fontsize=8)
                ax.set_ylabel(f"Sensitivity to {pnames[i]}", fontsize=8)
            else:
                ax.scatter(corr_hist[:, j], corr_hist[:, i],
                           alpha=0.5, s=10, color="tomato")
                ax.set_xlabel(f"Pearson r w/ {pnames[j]}", fontsize=8)
                ax.set_ylabel(f"Pearson r w/ {pnames[i]}", fontsize=8)
                ax.axhline(0, color="gray", linewidth=0.5)
                ax.axvline(0, color="gray", linewidth=0.5)
            ax.tick_params(labelsize=7)

    fig.suptitle("Parameter coupling: sensitivity (top) & Pearson r (bottom)",
                 fontsize=11, y=1.01)
    plt.tight_layout()
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--study",   required=True, choices=["lep", "lhc"])
    ap.add_argument("--top",     type=int, default=20,
                    help="Number of top histograms to show per parameter (default: 20)")
    ap.add_argument("--out",     default=None,
                    help="Output PDF path (default: sensitivity_<study>.pdf)")
    ap.add_argument("--no-approx", action="store_true",
                    help="Skip sensitivity from approximation (only Pearson from MC runs). "
                         "Faster but less precise.")
    args = ap.parse_args()

    here     = Path(__file__).parent
    hdf5     = here / f"mc_{args.study}.hdf5"
    approx   = here / f"approx_{args.study}.json"
    res_dir  = here / f"results_{args.study}"
    out_pdf  = Path(args.out) if args.out else (here / f"sensitivity_{args.study}.pdf")

    if not hdf5.exists():
        sys.exit(f"HDF5 not found: {hdf5}\n  Run 03_convert.sh first.")

    print(f"Loading HDF5: {hdf5}")
    bin_keys, values, params, pnames, xmin, xmax = load_hdf5(hdf5)
    n_runs, n_params = params.shape
    print(f"  {len(bin_keys)} bins, {n_runs} runs, params: {pnames}")

    # Best-fit parameter point
    bf = parse_bestfit_params(res_dir)
    if bf:
        X_best = [bf.get(p, params[:, j].mean()) for j, p in enumerate(pnames)]
        print(f"  Best-fit: {dict(zip(pnames, [f'{v:.4g}' for v in X_best]))}")
    else:
        X_best = list(params.mean(axis=0))
        print(f"  No results found; using mean of training params as reference point.")

    # Parameter ranges (for normalization of sensitivity)
    param_ranges = params.max(axis=0) - params.min(axis=0)
    for j, (p, dr) in enumerate(zip(pnames, param_ranges)):
        if dr < 1e-12:
            param_ranges[j] = 1.0    # avoid division by zero for fixed params

    # Group bins into histograms (ordered)
    seen = set()
    hist_order = []
    for k in bin_keys:
        h = k.rsplit("#", 1)[0]
        if h not in seen:
            seen.add(h)
            hist_order.append(h)

    # ── Sensitivity from approximation gradient ───────────────────────────────
    S_hist = None
    if not args.no_approx and approx.exists():
        print("Computing approximation-based sensitivities …")
        try:
            S_raw = compute_sensitivities(str(approx), bin_keys, pnames, X_best, param_ranges)
            S_hist = aggregate_by_hist(S_raw, bin_keys, hist_order)
            print(f"  Sensitivities computed for {len(hist_order)} histograms.")
        except Exception as e:
            print(f"  Warning: sensitivity computation failed ({e}); skipping.")
    elif not approx.exists():
        print(f"Approx file not found ({approx}); skipping gradient sensitivities.")

    # ── Pearson correlation from MC runs ─────────────────────────────────────
    print("Computing Pearson correlations from MC runs …")
    corr_hist = compute_pearson_by_hist(values, params, bin_keys, hist_order)
    print(f"  Done ({n_runs} runs × {len(hist_order)} histograms).")
    if n_runs < 5:
        print("  Warning: Pearson correlations with <5 points are very noisy.")

    # ── Write PDF ─────────────────────────────────────────────────────────────
    print(f"Writing {out_pdf} …")
    with PdfPages(out_pdf) as pdf:

        if S_hist is not None:
            # Clamp outliers for colour scale
            vmax = np.percentile(S_hist[S_hist > 0], 95) if S_hist.max() > 0 else 1.0
            plot_heatmap(pdf, S_hist, hist_order, pnames,
                         title=("Fractional sensitivity  |∂f/∂X| · ΔX / |f|  "
                                "(best-fit point, approximation gradient)"),
                         cmap="hot_r", vmin=0, vmax=vmax)
            plot_parameter_ranking(pdf, S_hist, hist_order, pnames, top_k=args.top)

        # Pearson map (always)
        plot_pearson_heatmap(pdf, corr_hist, hist_order, pnames)

        # Cross-coupling scatter (only when we have both)
        if S_hist is not None:
            plot_summary_scatter(pdf, S_hist, corr_hist, hist_order, pnames)

    print(f"Done. → {out_pdf}")


if __name__ == "__main__":
    main()
