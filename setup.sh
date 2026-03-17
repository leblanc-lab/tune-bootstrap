#!/usr/bin/env bash
# setup.sh — activate the full tune_v2 software environment
#
# Usage (from any directory):
#   source /path/to/tune_v2/setup.sh
#
# Activates: Python venv, YODA, Rivet, LHAPDF, Pythia8, Apprentice

## Resolve the install prefix relative to this script, regardless of cwd
TUNE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="$TUNE_DIR/local"

## 1. Activate the Python venv (sets PATH to $PREFIX/bin, etc.)
source "$PREFIX/bin/activate"

## 2. YODA paths (LD_LIBRARY_PATH, PYTHONPATH, texmf)
source "$PREFIX/yodaenv.sh"

## 3. Rivet paths (LD_LIBRARY_PATH, PYTHONPATH, bash completion)
source "$PREFIX/rivetenv.sh"

## 4. LHAPDF paths (LD_LIBRARY_PATH, LHAPDF_DATA_PATH)
source "$PREFIX/lhapdfenv.sh"

## 5. Pythia8 xmldoc path (needed for pythia8-main* to find Settings/ParticleData)
export PYTHIA8DATA="$PREFIX/share/Pythia8/xmldoc"

## 6. MPI — required by Apprentice (app-yoda2h5, app-build, app-tune2)
##    Load hpcx-mpi if no MPI library is already in LD_LIBRARY_PATH
if ! python3 -c "from mpi4py import MPI" 2>/dev/null; then
    module load hpcx-mpi 2>/dev/null || module load openmpi 2>/dev/null || true
fi

## 7. Apprentice — already on PATH via venv bin/, but make the source tree importable
##    if installed in editable mode (pip install -e)
if [[ -d "$TUNE_DIR/apprentice" ]]; then
    export PYTHONPATH="$TUNE_DIR/apprentice:$PYTHONPATH"
fi

echo "tune_v2 environment active."
echo "  Prefix : $PREFIX"
echo "  Rivet  : $(rivet --version 2>/dev/null || echo 'not found')"
echo "  LHAPDF : $(lhapdf-config --version 2>/dev/null || echo 'not found')"
echo "  Python : $(python --version 2>&1)"
