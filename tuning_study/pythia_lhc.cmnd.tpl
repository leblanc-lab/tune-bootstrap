! Pythia8 pp run at 7 TeV — Z→e+e- event shapes (LHC comparison study)
! Template: {aLund}, {bLund}, {sigma} are substituted by app-sample.
! Literal braces in Pythia8 lists use doubled braces {{...}} here.
!
! ── Beam setup ────────────────────────────────────────────────────────────────
Beams:idA  = 2212      ! proton
Beams:idB  = 2212      ! proton
Beams:eCM  = 7000.     ! 7 TeV
PDF:pSet   = 13        ! NNPDF2.3 LO (Pythia8 built-in, no LHAPDF needed)

! ── Z production with inclusive e+e- decay (to match ATLAS_2016_I1424838) ────
WeakSingleBoson:ffbar2gmZ = on
23:onMode   = off
23:onIfAny  = 11       ! Z → e+e- only (positron+electron)
PhaseSpace:mHatMin = 66.0
PhaseSpace:mHatMax = 116.0

! ── Run settings ──────────────────────────────────────────────────────────────
Main:numberOfEvents   = 10000
Main:timesAllowErrors = 200
Next:numberCount      = 0
Next:numberShowEvent  = 0
Init:showChangedSettings = on

! ── Same hadronization parameters under study as LEP ──────────────────────────
StringZ:aLund  = {aLund}
StringZ:bLund  = {bLund}
StringPT:sigma = {sigma}

! ── Rivet output ──────────────────────────────────────────────────────────────
Main:runRivet         = on
Main:rivetIgnoreBeams = off
Main:rivetDumpPeriod  = -1
! Event shapes in leptonic Z-events: direct analogue of LEP event shapes in pp
Main:rivetAnalyses = {{ATLAS_2016_I1424838}}
