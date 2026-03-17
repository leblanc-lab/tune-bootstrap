# Hadronization Tuning Study — Getting Started

This guide walks you through running a Pythia8 hadronization parameter tuning
study using Rivet and Apprentice on the Oscar HPC cluster.

The three parameters under study are:

| Parameter | Pythia8 name | Description | Default range |
|-----------|-------------|-------------|---------------|
| *a* | `StringZ:aLund` | Lund fragmentation *a* | 0.2 – 1.2 |
| *b* | `StringZ:bLund` | Lund fragmentation *b* | 0.5 – 2.0 |
| σ | `StringPT:sigma` | String transverse momentum width | 0.15 – 0.50 |

---

## 1. Connect and activate the environment

```bash
ssh <your-username>@ssh.ccv.brown.edu
cd /users/mleblan6/work/tune_v2
source setup.sh          # activates Python venv + Rivet + LHAPDF + Pythia8
```

Verify everything loaded:

```bash
rivet --version          # should print rivet v4.1.2
pythia8-main144 --help   # should print usage
app-build --help         # Apprentice build tool
```

---

## 2. Explore available Rivet analyses

List all installed Rivet analyses that are relevant to hadronization:

```bash
# LEP e+e- event shapes
rivet --list-analyses | grep -i "ALEPH\|DELPHI\|OPAL\|L3\|SLD" | grep "e+e-\|91\|event"

# LHC pp event shapes / UE
rivet --list-analyses | grep -i "ATLAS\|CMS\|LHCB" | grep "UE\|shape\|Z\|W"
```

To get a detailed description of a specific analysis:

```bash
rivet --show-analysis ALEPH_1996_I428072
```

---

## 3. Customise: choose your analyses and parameters

All configuration lives in `tuning_study/`:

### 3a. Change the Rivet analyses

Edit the `Main:rivetAnalyses` line in the template files:

```bash
# LEP:
nano tuning_study/pythia_lep.cmnd.tpl      # edit Main:rivetAnalyses = {...}

# LHC:
nano tuning_study/pythia_lhc.cmnd.tpl      # edit Main:rivetAnalyses = {...}
```

Braces in the analysis list must be **doubled** (`{{...}}`) because the template
uses Python `.format()` substitution for the physics parameters.

### 3b. Change which histograms are weighted in the tune

Edit the weights files — one line per analysis:

```bash
nano tuning_study/weights_lep.dat    # LEP observable weights
nano tuning_study/weights_lhc.dat    # LHC observable weights
```

Format: `/ANALYSIS_NAME   weight`. A weight of `0` excludes the analysis.

> **Important format rules** (Apprentice will silently fail otherwise):
> - One entry per line: `/ANALYSIS_NAME   weight` — no path suffix, no wildcards
> - No blank lines anywhere in the file
> - ASCII only — no special characters (`→`, `–`, etc.) in comments
> - Analysis name must match the Rivet ID exactly (e.g. `/ALEPH_1996_I428072`)

### 3c. Change the parameter range or add parameters

Edit `tuning_study/params.json`:

```json
{
    "aLund": [0.2, 1.2],
    "bLund": [0.5, 2.0],
    "sigma": [0.15, 0.50]
}
```

Then add the matching Pythia8 setting in **both** template files:

```
StringZ:aLund  = {aLund}
StringZ:bLund  = {bLund}
StringPT:sigma = {sigma}
```

The `{name}` tokens must match the keys in `params.json` exactly.

---

## 4. Run the tuning workflow

### Step 0 — get an interactive compute allocation

```bash
interact -n 4 -m 8g -t 2:00:00
source /users/mleblan6/work/tune_v2/setup.sh
cd /users/mleblan6/work/tune_v2/tuning_study
```

### Step 1 — sample the parameter grid

```bash
# Start with 25 points (increase to 50–100 for production)
NPOINTS=25 bash 01_sample.sh
```

This creates `runs_lep/` and `runs_lhc/` with identical parameter points.

### Step 2 — generate MC events (batch)

Copy the exact `sbatch` commands printed by Step 1 and run them:

```bash
mkdir -p /users/mleblan6/work/tune_v2/tuning_study/logs

sbatch --array=0-24%20 \
  --output=".../logs/generate_%A_%a.out" \
  --error=".../logs/generate_%A_%a.err" \
  --export=ALL,STUDY=lep,STUDY_DIR=... \
  .../02_generate.sbatch

sbatch --array=0-24%20 \   # same but STUDY=lhc
  ...
```

Monitor progress:

```bash
watch "squeue --me"

# Check for errors once jobs finish:
grep -l "ERROR" tuning_study/logs/generate_*.err
```

Each job takes ~5 min (LEP, 5k events) or ~15 min (LHC, 10k events).

### Step 3 — convert YODA → HDF5

```bash
STUDY=lep bash 03_convert.sh   # also extracts refdata_lep.json
STUDY=lhc bash 03_convert.sh
```

### Step 4 — build rational approximations

```bash
# ORDER=m,n means Padé rational polynomial (degree m numerator, n denominator)
# 2,2 works well for 3 parameters. Try 3,3 for more accuracy with 50+ points.
ORDER=2,2 STUDY=lep bash 04_build.sh
ORDER=2,2 STUDY=lhc bash 04_build.sh
```

### Step 5 — minimise χ² and find best-fit parameters

```bash
STUDY=lep bash 05_tune.sh      # prints best-fit values to screen
STUDY=lhc bash 05_tune.sh
```

Results land in `results_lep/` and `results_lhc/`:
- `minimum_tnc_200_100.txt` — best-fit parameter values and χ²/ndf
- `predictions_tnc_200_100.yoda` — Apprentice prediction at best fit
- `tnc_200_100_corr.pdf` — parameter correlation matrix from the minimiser

---

## 5. Visualise the results

All scripts live in `tuning_study/` and write PDFs to the same directory.
Run them from an interactive session after sourcing `setup.sh`.

### 5a. Distributions with parameter-coloured lines vs data  ← **start here**

`plot_distributions.py` produces one PDF per analysis.  Each page shows one
histogram with:
- A coloured line for every MC parameter-point (colour ∝ chosen parameter)
- Black error bars for the HEPData reference points
- A thick dashed black line for the Apprentice best-fit prediction
- An optional ratio-to-data panel

```bash
# All analyses, colour = aLund, no ratio panel
python3 plot_distributions.py --study lep

# Colour by bLund, add ratio panel
python3 plot_distributions.py --study lep --color-by bLund --ratio

# Only one analysis, only histograms matching "thrust" in the path
python3 plot_distributions.py --study lep --analysis ALEPH_1996 --hist thrust --ratio

# Custom output directory
python3 plot_distributions.py --study lep --out my_plots
```

Available options: `--color-by PARAM`, `--analysis REGEX`, `--hist REGEX`,
`--ratio`, `--cmap COLORMAP`, `--out DIR`.

### 5b. Parameter sensitivity and correlations

`plot_sensitivity.py` produces a single PDF with:
1. **Sensitivity heatmap** — rows = observables, columns = parameters;
   colour = fractional shift |∂f/∂X|·ΔX/|f| at the best-fit point.
   Shows at a glance which observables constrain which parameters.
2. **Per-parameter ranking** — horizontal bar chart of the top-K most sensitive
   histograms for each parameter.
3. **Pearson correlation heatmap** — sign and magnitude of the correlation
   between each parameter and each histogram's bin values across the MC runs.
   Red = positive, blue = negative.
4. **Cross-coupling scatter** — reveals parameter degeneracies: if two parameters
   have the same set of sensitive observables they are hard to disentangle.

```bash
python3 plot_sensitivity.py --study lep

# Show top 30 instead of default 20
python3 plot_sensitivity.py --study lep --top 30

# Skip the approximation gradient (Pearson from MC runs only, much faster)
python3 plot_sensitivity.py --study lep --no-approx

# Custom output path
python3 plot_sensitivity.py --study lep --out sensitivity_lep_v2.pdf
```

### 5c. Parameter space corner plot

See where your samples sit and (after tuning) where the best fit landed:

```bash
# Before tuning — just the grid
python3 plot_parameter_space.py --study lep --params-json params.json

# After tuning — with best-fit star
python3 plot_parameter_space.py --study lep \
  --params-json params.json \
  --result results_lep/minimum_tnc_200_100.txt
```

### 5d. Tuned MC vs data

Show the nearest-to-best-fit MC run overlaid on data, plus a per-observable
χ² bar chart:

```bash
python3 plot_tune_result.py --study lep
python3 plot_tune_result.py --study lhc
```

### 5e. MC spread vs data (quick overview)

```bash
python3 plot_mcvdata.py --study lep --out plots_mcvdata_lep
python3 plot_mcvdata.py --study lhc --out plots_mcvdata_lhc
```

---

## 6. Tips and common issues

| Problem | Fix |
|---------|-----|
| `rivet: command not found` | Run `source setup.sh` again |
| YODA file is empty or 0 bytes | Check `logs/generate_*.err` for Pythia8 error messages |
| `app-build` complains about too few points | Increase `NPOINTS` (recommend ≥ 25 for 3 params) |
| Best-fit is at edge of range | Expand that parameter's range in `params.json`, re-run |
| χ² is very large for one analysis | Lower its weight in the weights file or check the analysis name |
| LHC analysis needs a PDF set | Use Pythia8's built-in PDFs (`PDF:pSet = 13`) — already set |

---

## 7. Workflow cheat-sheet

```
source setup.sh
↓
NPOINTS=25 bash 01_sample.sh          # sample grid
↓
sbatch ... 02_generate.sbatch         # generate events (×2: LEP + LHC)
↓
STUDY=lep bash 03_convert.sh          # YODA → HDF5 + reference data
↓
ORDER=2,2 STUDY=lep bash 04_build.sh  # build approximations
↓
STUDY=lep bash 05_tune.sh             # find best fit

# Visualise — sensitivity first to check observables, then distributions:
python3 plot_sensitivity.py     --study lep
python3 plot_distributions.py   --study lep --color-by aLund --ratio
python3 plot_parameter_space.py --study lep --result results_lep/minimum_tnc_200_100.txt
python3 plot_tune_result.py     --study lep
```
