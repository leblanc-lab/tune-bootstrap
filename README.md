# tune-bootstrap

A reproducible scaffolding for Pythia8 hadronization parameter tuning using
[Rivet](https://rivet.hepforge.org/) and [Apprentice](https://github.com/HEPonHPC/apprentice),
targeting the Oscar HPC cluster at Brown University.

## Installation

```bash
git clone --recurse-submodules git@github.com:leblanc-lab/tune-bootstrap.git
```

Start an interactive compute node before running the bootstrap — 
it should not be run on the login node.

```bash
source interact.sh
```

Then install the full software stack:

```bash
./rivetbootstrap/rivet-bootstrap   # builds Rivet, YODA, LHAPDF, Pythia8 (~30–60 min)
./rivetbootstrap/install-pythia    # installs Pythia8
pip install -e apprentice/         # installs the Apprentice tuning library
source setup.sh                    # activates the environment
```

On subsequent logins, only `source setup.sh` is needed.

## License

MIT — see [LICENSE](LICENSE).
