#!/usr/bin/env python3
"""
extract_refdata.py — extract experimental reference data for Apprentice tuning.

Reads the per-analysis reference YODA files from the Rivet data directory
(local/share/Rivet/<ANALYSIS>.yoda.gz) and writes all /REF/ bins to an
Apprentice-compatible JSON file:

    { "/ANALYSIS/histname#N": [central_value, total_error], ... }

Usage:
    python3 extract_refdata.py refdata.json ANALYSIS1 [ANALYSIS2 ...]

    Example:
    python3 extract_refdata.py refdata_lep.json \\
        ALEPH_1996_I428072 OPAL_2004_I669402 DELPHI_1996_I424112 ALEPH_1991_I319520
"""

import sys, json, os, glob, gzip
from pathlib import Path

try:
    import yoda
except ImportError:
    sys.exit("yoda not found — source setup.sh first")


def err_avg(lo, hi):
    return 0.5 * (abs(lo) + abs(hi))


def total_err_from_bin(b):
    """Sum stat and sys errors in quadrature. Fall back gracefully."""
    stat = sys_ = 0.0
    for key in ('stat', ''):
        try:
            ep = b.errPos(key); en = b.errNeg(key)
            stat = 0.5 * (abs(ep) + abs(en))
            break
        except Exception:
            pass
    for key in ('sys', 'syst'):
        try:
            ep = b.errPos(key); en = b.errNeg(key)
            sys_ = 0.5 * (abs(ep) + abs(en))
            break
        except Exception:
            pass
    return (stat**2 + sys_**2) ** 0.5


def find_rivet_data_dir():
    """Locate the Rivet share directory using rivet-config or PATH."""
    import subprocess, shutil
    rc = shutil.which("rivet-config")
    if rc:
        try:
            prefix = subprocess.check_output([rc, "--prefix"], text=True).strip()
            d = os.path.join(prefix, "share", "Rivet")
            if os.path.isdir(d):
                return d
        except Exception:
            pass
    # Fallback: walk up from the rivet binary
    rivet = shutil.which("rivet")
    if rivet:
        d = os.path.join(Path(rivet).parent.parent, "share", "Rivet")
        if os.path.isdir(d):
            return d
    return None


def extract(analyses, out_json):
    data_dir = find_rivet_data_dir()
    if not data_dir:
        sys.exit("Cannot find Rivet data directory — source setup.sh first")

    refdata = {}
    for analysis in analyses:
        # Try .yoda.gz first, then .yoda
        candidates = [
            os.path.join(data_dir, analysis + ".yoda.gz"),
            os.path.join(data_dir, analysis + ".yoda"),
        ]
        yoda_file = next((c for c in candidates if os.path.exists(c)), None)
        if yoda_file is None:
            print(f"Warning: no reference data found for {analysis}", file=sys.stderr)
            continue

        aos = yoda.read(yoda_file, asdict=True)
        n_before = len(refdata)

        for path, ao in sorted(aos.items()):
            if "/REF/" not in path:
                continue
            # "/REF/ANALYSIS/histname" -> "/ANALYSIS/histname"
            analysis_path = path.replace("/REF/", "/", 1)

            # Try Scatter2D interface first (points with yErrMinus/Plus)
            # then fall back to BinnedEstimate1D (bins with val + named error keys)
            try:
                pts = list(ao.points())
                for i, pt in enumerate(pts):
                    try:
                        y     = pt.y()
                        ye_lo = pt.yErrMinus()
                        ye_hi = pt.yErrPlus()
                        key = "{}#{}".format(analysis_path, i)
                        refdata[key] = [y, err_avg(ye_lo, ye_hi)]
                    except Exception:
                        pass
            except AttributeError:
                # BinnedEstimate1D — use named error keys (stat, sys)
                try:
                    bns = list(ao.bins())
                    for i, b in enumerate(bns):
                        try:
                            val = b.val()
                            err = total_err_from_bin(b)
                            key = "{}#{}".format(analysis_path, i)
                            refdata[key] = [val, err]
                        except Exception:
                            pass
                except Exception as e:
                    print(f"Warning: skipping {path}: {e}", file=sys.stderr)

        added = len(refdata) - n_before
        print(f"  {analysis}: {added} bins from {os.path.basename(yoda_file)}")

    with open(out_json, "w") as f:
        json.dump(refdata, f, indent=2)

    print(f"Total: {len(refdata)} reference bins -> {out_json}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out_json",   help="Output JSON path")
    ap.add_argument("analyses",   nargs="+", metavar="ANALYSIS",
                    help="Rivet analysis names (e.g. ALEPH_1996_I428072)")
    args = ap.parse_args()
    extract(args.analyses, args.out_json)

