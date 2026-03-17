#!/usr/bin/env bash
# 01_sample.sh — sample the parameter grid and create per-run directories
#
# Creates runs_lep/ and runs_lhc/ with identical parameter points.
# Each subdirectory contains params.dat and an instantiated Pythia8 cmnd file.
#
# Usage:
#   [NPOINTS=25] bash 01_sample.sh
#
# Must be run from inside a Slurm allocation (interact or sbatch).

set -e

STUDY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${STUDY_DIR}/../setup.sh"

NPOINTS=${NPOINTS:-25}

if [[ -d "${STUDY_DIR}/runs_lep" || -d "${STUDY_DIR}/runs_lhc" ]]; then
    echo "ERROR: run directories already exist. Remove them first:"
    echo "  rm -rf ${STUDY_DIR}/runs_lep ${STUDY_DIR}/runs_lhc"
    exit 1
fi

cd "${STUDY_DIR}"

echo "=== Sampling ${NPOINTS} parameter points ==="

# Step A: generate runs_lep/ — app-sample creates newscan/ then we rename it
app-sample params.json "${NPOINTS}" pythia_lep.cmnd.tpl
mv newscan runs_lep

# app-sample keeps the template filename (.cmnd.tpl); rename to .cmnd so Pythia8 can read it
for d in "${STUDY_DIR}/runs_lep"/*/; do
    [[ -f "$d/pythia_lep.cmnd.tpl" ]] && mv "$d/pythia_lep.cmnd.tpl" "$d/pythia_lep.cmnd"
done

echo "Created ${NPOINTS} LEP run directories in ${STUDY_DIR}/runs_lep/"

# Step B: create runs_lhc/ with IDENTICAL parameter points by re-instantiating
# the LHC template from the params.dat files already written in runs_lep/.
# (app-sample doesn't expose a seed, so we mirror manually to guarantee same grid.)

export STUDY_DIR
python3 - <<'PYEOF'
import os, shutil
from pathlib import Path

study_dir = Path(os.environ["STUDY_DIR"])
runs_lep  = study_dir / "runs_lep"
runs_lhc  = study_dir / "runs_lhc"
runs_lhc.mkdir(exist_ok=True)

with open(study_dir / "pythia_lhc.cmnd.tpl") as f:
    tmpl = f.read()

n = 0
for rundir in sorted(runs_lep.iterdir()):
    if not rundir.is_dir():
        continue

    # Read params.dat written by app-sample
    params = {}
    with open(rundir / "params.dat") as f:
        for line in f:
            parts = line.split()
            if len(parts) == 2:
                params[parts[0]] = float(parts[1])

    lhc_rundir = runs_lhc / rundir.name
    lhc_rundir.mkdir(exist_ok=True)

    # Copy params.dat (same parameter values, different cmnd)
    shutil.copy(rundir / "params.dat", lhc_rundir / "params.dat")

    # Instantiate LHC template with the same parameters
    txt = tmpl.format(**params)
    with open(lhc_rundir / "pythia_lhc.cmnd", "w") as f:
        f.write(txt)
    n += 1

print(f"Mirrored {n} run directories to runs_lhc/")
PYEOF

N_DIRS=$(ls -d "${STUDY_DIR}/runs_lep"/*/ 2>/dev/null | wc -l)

echo ""
echo "Done. ${N_DIRS} parameter points in runs_lep/ and runs_lhc/."
echo ""
echo "Next — submit MC generation (array indices 0 to $((N_DIRS - 1))):"
echo ""
echo "  mkdir -p ${STUDY_DIR}/logs"
echo "  sbatch --array=0-$((N_DIRS - 1))%20 \\"
echo "    --output=\"${STUDY_DIR}/logs/generate_%A_%a.out\" \\"
echo "    --error=\"${STUDY_DIR}/logs/generate_%A_%a.err\" \\"
echo "    --export=ALL,STUDY=lep,STUDY_DIR=${STUDY_DIR} \\"
echo "    ${STUDY_DIR}/02_generate.sbatch"
echo ""
echo "  sbatch --array=0-$((N_DIRS - 1))%20 \\"
echo "    --output=\"${STUDY_DIR}/logs/generate_%A_%a.out\" \\"
echo "    --error=\"${STUDY_DIR}/logs/generate_%A_%a.err\" \\"
echo "    --export=ALL,STUDY=lhc,STUDY_DIR=${STUDY_DIR} \\"
echo "    ${STUDY_DIR}/02_generate.sbatch"
