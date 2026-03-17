#!/usr/bin/env bash
# 05_tune.sh — minimize chi² to find best-fit hadronic parameters
#
# Uses app-tune2 to minimize the chi² between the rational approximations
# (built in step 4) and the experimental reference data (from step 3).
#
# Outputs (under results_<STUDY>/):
#   minimum_*.txt        — best-fit parameter values and chi²/ndf
#   predictions_*.yoda   — YODA file with approximation predictions at best fit
#   corr.pdf             — parameter correlation matrix plot
#   weights_*.txt        — copy of the weights file used
#
# Usage:
#   [STUDY=lep|lhc|both] [RESTARTS=100] [ALG=tnc] bash 05_tune.sh
#
# Must be run from inside a Slurm allocation (interact or sbatch).

set -e

STUDY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${STUDY_DIR}/../setup.sh"

STUDY=${STUDY:-both}
RESTARTS=${RESTARTS:-100}   # minimiser restarts from random start points
SURVEY=${SURVEY:-200}       # random survey points to find a good start region
ALG=${ALG:-tnc}             # tnc | ncg | lbfgsb | trust

run_tune() {
    local study=$1
    local weights="${STUDY_DIR}/weights_${study}.dat"
    local refdata="${STUDY_DIR}/refdata_${study}.json"
    local approx="${STUDY_DIR}/approx_${study}.json"
    local outdir="${STUDY_DIR}/results_${study}"

    for f in "${weights}" "${refdata}" "${approx}"; do
        if [[ ! -f "${f}" ]]; then
            echo "ERROR: required file not found: ${f}"
            exit 1
        fi
    done

    echo "=== Tuning with ${study} data (${RESTARTS} restarts, algorithm=${ALG}) ==="

    app-tune2 \
        "${weights}" \
        "${refdata}" \
        "${approx}" \
        -o  "${outdir}" \
        -s  "${SURVEY}" \
        -r  "${RESTARTS}" \
        -a  "${ALG}" \
        -f

    echo "  → Results in ${outdir}/"
    echo ""
    echo "  Best-fit summary:"
    cat "${outdir}"/minimum_*.txt 2>/dev/null | grep -v "^#" | head -10
    echo ""
}

if [[ "$STUDY" == "both" || "$STUDY" == "lep" ]]; then run_tune lep; fi
if [[ "$STUDY" == "both" || "$STUDY" == "lhc" ]]; then run_tune lhc; fi

echo "=== Step 5 complete ==="
if [[ "$STUDY" == "both" ]]; then
    echo ""
    echo "Compare LEP vs LHC best-fit parameters:"
    echo "  LEP: $(grep -v '^#' ${STUDY_DIR}/results_lep/minimum_*.txt 2>/dev/null | head -3)"
    echo "  LHC: $(grep -v '^#' ${STUDY_DIR}/results_lhc/minimum_*.txt 2>/dev/null | head -3)"
fi
