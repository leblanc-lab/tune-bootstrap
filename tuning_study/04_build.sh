#!/usr/bin/env bash
# 04_build.sh — fit rational approximations to the MC grid
#
# Reads mc_<STUDY>.hdf5 and builds a polynomial approximation (Padé rational
# function) for each observable bin as a function of the tuning parameters.
# Output: approx_<STUDY>.json
#
# Usage:
#   [STUDY=lep|lhc|both] [ORDER=2,2] bash 04_build.sh
#
# ORDER is "numerator_degree,denominator_degree". For a 3-parameter scan with
# 25 points, order 2,2 (10 coefficients) is well-constrained. Increase to 3,2
# once you have ~100+ points.
#
# Must be run from inside a Slurm allocation (interact or sbatch).

set -e

STUDY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${STUDY_DIR}/../setup.sh"

STUDY=${STUDY:-both}
ORDER=${ORDER:-2,2}

run_build() {
    local study=$1
    local h5="${STUDY_DIR}/mc_${study}.hdf5"

    if [[ ! -f "${h5}" ]]; then
        echo "ERROR: ${h5} not found. Run 03_convert.sh first."
        exit 1
    fi

    echo "=== Building ${study} approximations (Padé order ${ORDER}) ==="

    app-build \
        -w  "${STUDY_DIR}/weights_${study}.dat" \
        -o  "${STUDY_DIR}/approx_${study}.json" \
        --order "${ORDER}" \
        "${h5}"

    echo "  → ${STUDY_DIR}/approx_${study}.json"
    echo ""
}

if [[ "$STUDY" == "both" || "$STUDY" == "lep" ]]; then run_build lep; fi
if [[ "$STUDY" == "both" || "$STUDY" == "lhc" ]]; then run_build lhc; fi

echo "=== Step 4 complete ==="
echo "Next: bash ${STUDY_DIR}/05_tune.sh"
