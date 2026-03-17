#!/usr/bin/env bash
#SBATCH --job-name=tune-mc
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=01:00:00
#
# Run one Pythia8+Rivet MC point as part of a SLURM array job.
#
# SLURM copies this script to /var/spool/slurmd/, so paths must come from env.
# Submit via 01_sample.sh output, or manually:
#
#   sbatch --array=0-24%20 \
#     --output="$STUDY_DIR/logs/generate_%A_%a.out" \
#     --error="$STUDY_DIR/logs/generate_%A_%a.err" \
#     --export=ALL,STUDY=lep,STUDY_DIR=/abs/path/to/tuning_study \
#     /abs/path/to/tuning_study/02_generate.sbatch
#
# STUDY_DIR and STUDY must be set via --export.

set -e

STUDY=${STUDY:-lep}

if [[ -z "${STUDY_DIR}" ]]; then
    echo "ERROR: STUDY_DIR env var not set. Pass via --export=ALL,STUDY_DIR=..."
    exit 1
fi

source "${STUDY_DIR}/../setup.sh"

# Zero-padded run index matching the directory names created by app-sample
NPAD=$(python3 -c "
import math, sys
n = ${SLURM_ARRAY_TASK_ID}
ntotal = len(list(__import__('pathlib').Path('${STUDY_DIR}/runs_${STUDY}').iterdir()))
width  = 1 + int(math.ceil(math.log10(max(ntotal, 2))))
print(str(n).zfill(width))
")

RUNDIR="${STUDY_DIR}/runs_${STUDY}/${NPAD}"

if [[ ! -d "${RUNDIR}" ]]; then
    echo "ERROR: run directory not found: ${RUNDIR}"
    exit 1
fi

echo "Host      : $(hostname)"
echo "Study     : ${STUDY}"
echo "Run dir   : ${RUNDIR}"
echo "SLURM job : ${SLURM_JOB_ID}, array task: ${SLURM_ARRAY_TASK_ID}"
echo ""

cd "${RUNDIR}"

# Run Pythia8 with the instantiated command file.
# Rivet writes output to Rivet.yoda (default) in the current directory.
pythia8-main144 -c "pythia_${STUDY}.cmnd" 2>&1

# Verify output was produced (pythia8-main144 writes main144.yoda by default)
if [[ ! -f main144.yoda ]]; then
    echo "ERROR: main144.yoda not produced in ${RUNDIR}"
    exit 1
fi

echo ""
echo "Done. Output: ${RUNDIR}/Rivet.yoda"
