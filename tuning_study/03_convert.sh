#!/usr/bin/env bash
# 03_convert.sh — collect Rivet YODA outputs → HDF5, extract reference data
#
# Reads all runs_<STUDY>/*/main144.yoda files, applies observable weights,
# and writes:
#   mc_<STUDY>.hdf5      — MC predictions at each parameter point (for app-build)
#   refdata_<STUDY>.json — experimental reference data (for app-tune2)
#
# Usage:
#   [STUDY=lep|lhc|both] bash 03_convert.sh
#
# Must be run from inside a Slurm allocation (interact or sbatch).

set -e

STUDY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${STUDY_DIR}/../setup.sh"

STUDY=${STUDY:-both}

run_convert() {
    local study=$1
    local runs_dir="${STUDY_DIR}/runs_${study}"

    echo "=== Converting ${study} YODA files → HDF5 ==="

    # Report any missing YODA outputs
    local missing=0
    for d in "${runs_dir}"/*/; do
        if [[ ! -f "${d}params.dat" ]]; then
            continue  # not a run dir (e.g. logs/ subdir)
        fi
        if [[ ! -f "${d}main144.yoda" ]]; then
            echo "  Missing: ${d}main144.yoda"
            missing=$((missing + 1))
        fi
    done
    if [[ $missing -gt 0 ]]; then
        echo "Warning: ${missing} incomplete runs. Continuing with available outputs."
    fi

    # Count completed run dirs (must have both params.dat and main144.yoda)
    local n_complete=0
    for d in "${runs_dir}"/*/; do
        [[ -f "${d}params.dat" && -f "${d}main144.yoda" ]] && n_complete=$((n_complete + 1))
    done

    if [[ $n_complete -eq 0 ]]; then
        echo "ERROR: no completed runs found in ${runs_dir}"
        exit 1
    fi

    echo "  Found ${n_complete} completed runs."

    # app-yoda2h5: convert ALL observables to HDF5.
    # Observable weighting/filtering is done later by app-build and app-tune2.
    app-yoda2h5 \
        -o  "${STUDY_DIR}/mc_${study}.hdf5" \
        --pname params.dat \
        "${runs_dir}"

    echo "  → ${STUDY_DIR}/mc_${study}.hdf5"

    # Extract experimental reference data from the Rivet data directory.
    # Parse analysis names from the weights file (non-comment lines starting with /ANALYSIS_NAME)
    local analyses
    analyses=$(grep -v '^#' "${STUDY_DIR}/weights_${study}.dat" | grep -oP '^/\K[A-Z][A-Z0-9_]+' | sort -u | tr '\n' ' ')
    echo "  Analyses for reference data: ${analyses}"

    python3 "${STUDY_DIR}/extract_refdata.py" \
        "${STUDY_DIR}/refdata_${study}.json" \
        ${analyses}

    # Filter reference data to only keep bins that exist in the MC approximation
    # (reference YODA files sometimes use coarser binning than the MC output)
    python3 - <<PYEOF
import json, h5py
rd = json.load(open("${STUDY_DIR}/refdata_${study}.json"))
with h5py.File("${STUDY_DIR}/mc_${study}.hdf5", "r") as f:
    mc_bins = set(x.decode() for x in f["index"][:])
filtered = {k: v for k, v in rd.items() if k in mc_bins}
removed  = len(rd) - len(filtered)
json.dump(filtered, open("${STUDY_DIR}/refdata_${study}.json", "w"), indent=2)
print(f"  Filtered refdata: kept {len(filtered)}/{len(rd)} bins (removed {removed} with no MC counterpart)")
PYEOF

    echo "  → ${STUDY_DIR}/refdata_${study}.json"
    echo ""
}

if [[ "$STUDY" == "both" || "$STUDY" == "lep" ]]; then run_convert lep; fi
if [[ "$STUDY" == "both" || "$STUDY" == "lhc" ]]; then run_convert lhc; fi

echo "=== Step 3 complete ==="
echo "Next: bash ${STUDY_DIR}/04_build.sh"
