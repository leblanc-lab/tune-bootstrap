! Pythia8 LEP e+e- run at 91.2 GeV — hadronization parameter scan
! Template: {aLund}, {bLund}, {sigma} are substituted by app-sample.
! Literal braces in Pythia8 lists use doubled braces {{...}} here.

! ── Beam setup ────────────────────────────────────────────────────────────────
Beams:idA         = 11     ! electron
Beams:idB         = -11    ! positron
Beams:eCM         = 91.2   ! Z pole
WeakSingleBoson:ffbar2gmZ = on
PDF:lepton        = off    ! no lepton PDFs needed for e+e-

! ── Run settings ──────────────────────────────────────────────────────────────
Main:numberOfEvents   = 5000
Main:timesAllowErrors = 100
Next:numberCount      = 0
Next:numberShowEvent  = 0
Init:showChangedSettings = on

! ── Hadronization parameters under study ──────────────────────────────────────
! Pythia8 defaults: aLund=0.68, bLund=0.98, sigma=0.335
StringZ:aLund  = {aLund}
StringZ:bLund  = {bLund}
StringPT:sigma = {sigma}

! ── Rivet output ──────────────────────────────────────────────────────────────
Main:runRivet         = on
Main:rivetIgnoreBeams = off
Main:rivetDumpPeriod  = -1
! Analyses: event shapes + jet rates + multiplicity at LEP1
! Most sensitive to string fragmentation parameters
Main:rivetAnalyses = {{ALEPH_1991_I319520,ALEPH_1996_I428072,DELPHI_1996_I424112,OPAL_2004_I669402}}
