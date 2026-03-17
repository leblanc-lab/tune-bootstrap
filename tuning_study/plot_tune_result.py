#!/usr/bin/env python3
"""
plot_tune_result.py — show the best-fit MC prediction vs data after tuning.

Reads:
  - The Apprentice best-fit parameter values from results_<study>/minimum_0.txt
  - The nearest MC run (the parameter point closest to the best fit)
  - Reference data from refdata_<study>.json

Usage:
    python3 plot_tune_result.py --study lep
    python3 plot_tune_result.py --study lhc
    python3 plot_tune_result.py --study lep --study lhc  # side-by-side

Produces:
    tune_result_<study>.pdf   — one page per observable
    chi2_summary_<study>.pdf  — bar chart of per-observable chi² contributions

Requires: numpy, matplotlib, yoda, apprentice (available after source setup.sh)
"""

import argparse, json, re
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


try:
    import yoda
except ImportError:
    raise SystemExit("yoda Python module not found — did you run: source setup.sh ?")


# ── helpers ────────────────────────────────────────────────────────────────────

def scatter_to_xy(ao):
    xs, ys, yes = [], [], []
    try:
        for pt in ao.points():
            xs.append(pt.x()); ys.append(pt.y())
            yes.append(0.5 * (pt.yErrMinus() + pt.yErrPlus()))
    except AttributeError:
        try:
            for b in ao.bins():
                xs.append(0.5 * (b.xMin() + b.xMax()))
                ys.append(b.height()); yes.append(b.heightErr())
        except AttributeError:
            return None, None, None
    return np.array(xs), np.array(ys), np.array(yes)


def parse_minimum(path: Path) -> dict[str, float]:
    """Parse Apprentice minimum_*.txt → {param: value}."""
    best = {}
    for line in path.read_text().splitlines():
        m = re.match(r"\s*(\w+)\s*[=:]\s*([-+\d.eE]+)", line)
        if m:
            best[m.group(1)] = float(m.group(2))
    return best


def load_params(pdat: Path) -> dict[str, float]:
    p = {}
    for line in pdat.read_text().splitlines():
        parts = line.split()
        if len(parts) == 2:
            p[parts[0]] = float(parts[1])
    return p


def closest_run(runs_dir: Path, best: dict, yoda_name: str) -> Path:
    """Return the run dir whose params.dat is closest (L2) to best-fit."""
    best_dist, best_rd = float("inf"), None
    for rd in sorted(runs_dir.iterdir()):
        pf = rd / "params.dat"
        yf = rd / yoda_name
        if not pf.exists() or not yf.exists():
            continue
        p = load_params(pf)
        common = set(p) & set(best)
        if not common:
            continue
        dist = sum((p[k] - best[k]) ** 2 for k in common) ** 0.5
        if dist < best_dist:
            best_dist, best_rd = dist, rd
    return best_rd


def chi2_contributions(ref_json: dict, mc_yoda: dict) -> dict[str, float]:
    """Return {obs_path: chi2/ndf} using reference data vs MC prediction."""
    results = {}
    for path, (val, err) in ref_json.items():
        mc_path = path.split("#")[0]  # strip bin index
        mc_ao = mc_yoda.get(mc_path)
        if mc_ao is None:
            continue
        _, ys, _ = scatter_to_xy(mc_ao)
        if ys is None or len(ys) == 0:
            continue
        # Use the bin matching #N if present
        m = re.search(r"#(\d+)$", path)
        idx = int(m.group(1)) if m else 0
        if idx < len(ys):
            chi2 = ((ys[idx] - val) / err) ** 2 if err > 0 else 0.0
            results[path] = chi2
    return results


# ── main ───────────────────────────────────────────────────────────────────────

def process_study(study: str, here: Path, yoda_name: str):
    runs_dir    = here / f"runs_{study}"
    results_dir = here / f"results_{study}"
    refdata_file = here / f"refdata_{study}.json"
    min_files = sorted(results_dir.glob("minimum_*.txt")) if results_dir.exists() else []

    if not min_files:
        print(f"[{study.upper()}] No minimum_*.txt in {results_dir} — skipping tune overlay.")
        best = {}
        best_rd = next((d for d in sorted(runs_dir.iterdir())
                        if d.is_dir() and (d / yoda_name).exists()), None)
    else:
        min_file = min_files[0]
        best = parse_minimum(min_file)
        print(f"[{study.upper()}] Best fit from {min_file.name}: {best}")
        best_rd = closest_run(runs_dir, best, yoda_name)

    if best_rd is None:
        print(f"[{study.upper()}] No completed MC runs found — cannot plot.")
        return

    print(f"[{study.upper()}] Using nearest run: {best_rd.name}")
    mc_yoda = yoda.read(str(best_rd / yoda_name))

    # ── chi² summary ──────────────────────────────────────────────────────────
    if refdata_file.exists():
        ref_json = json.loads(refdata_file.read_text())
        chi2s = chi2_contributions(ref_json, mc_yoda)
        if chi2s:
            obs   = [p.split("/")[-1][:30] for p in chi2s]
            vals  = list(chi2s.values())
            fig, ax = plt.subplots(figsize=(max(8, len(obs) * 0.4), 4))
            ax.bar(range(len(obs)), vals, color="steelblue", edgecolor="white")
            ax.set_xticks(range(len(obs)))
            ax.set_xticklabels(obs, rotation=70, ha="right", fontsize=6)
            ax.set_ylabel(r"$\chi^2$ per bin")
            ax.set_title(f"{study.upper()} — per-observable χ² (nearest-to-best-fit MC)")
            fig.tight_layout()
            chi2_path = here / f"chi2_summary_{study}.pdf"
            fig.savefig(chi2_path)
            plt.close(fig)
            print(f"[{study.upper()}] Chi² summary → {chi2_path}")

    # ── MC vs data overlay (best-fit-like run) ────────────────────────────────
    out_dir = here / f"plots_tuned_{study}"
    out_dir.mkdir(exist_ok=True)
    n_plots = 0
    for path, ao in sorted(mc_yoda.items()):
        if "/REF/" in path or "/TMP/" in path or "BEAMPZ" in path:
            continue
        xs, ys, yes = scatter_to_xy(ao)
        if xs is None: continue

        fig, ax = plt.subplots(figsize=(7, 4))
        ax.step(np.append(xs, xs[-1]), np.append(ys, ys[-1]),
                where="post", color="steelblue", linewidth=1.2, label="MC (best fit)")

        ref_ao = mc_yoda.get("/REF" + path)
        if ref_ao is None:
            # try reconstructing from refdata JSON
            pass
        if ref_ao is not None:
            rx, ry, rye = scatter_to_xy(ref_ao)
            if rx is not None:
                ax.errorbar(rx, ry, yerr=rye, fmt="ko", markersize=3,
                            linewidth=1, label="Data")

        parts = path.split("/")
        analysis = parts[1] if len(parts) > 1 else path
        hist_id  = "/".join(parts[2:]) if len(parts) > 2 else ""
        if best:
            param_str = "  ".join(f"{k}={v:.3f}" for k, v in best.items())
            ax.set_title(f"{analysis} / {hist_id}\n{param_str}", fontsize=8)
        else:
            ax.set_title(f"{analysis} / {hist_id}", fontsize=9)
        ax.set_xlabel("x"); ax.set_ylabel("Value")
        ax.legend(fontsize=8)
        fig.tight_layout()

        fname = re.sub(r"[^A-Za-z0-9_\-]", "_", path.strip("/")) + ".pdf"
        fig.savefig(out_dir / fname)
        plt.close(fig)
        n_plots += 1

    print(f"[{study.upper()}] {n_plots} tuned-overlay plots → {out_dir}/")


def main():
    ap = argparse.ArgumentParser(description="Post-tune MC vs data overlay")
    ap.add_argument("--study", required=True, nargs="+", choices=["lep", "lhc"],
                    help="Study/studies to plot (lep, lhc, or both)")
    ap.add_argument("--yoda-name", default="main144.yoda")
    args = ap.parse_args()

    here = Path(__file__).parent
    for study in args.study:
        process_study(study, here, args.yoda_name)


if __name__ == "__main__":
    main()
