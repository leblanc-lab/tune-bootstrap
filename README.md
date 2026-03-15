Clone as

```
git clone --recurse-submodules git@github.com:leblanc-lab/tune-bootstrap.git
```

To install, you should be able to do the following...

Note that the rivet-bootstrap script will take a very long time to run.

On OSCAR, you should start an interactive session with the interact.sh command before starting the installation, so that you don't violate the login node usage policy.

On subsequent logins, you should be able to run setup.sh to get your working environment.

```
source interact.sh
./rivetbootstrap/rivet-bootstrap
./rivetbootstrap/install-pythia
pip install -e apprentice/
source setup.sh
```
