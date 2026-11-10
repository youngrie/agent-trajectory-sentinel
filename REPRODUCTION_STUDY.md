# Reproduction study — FTEC5660

This fork adds a reproducibility study of *Real-Time Detection and Repair of LLM
Agent Failures* to the authors' repository. Nothing in `derail/` is rewritten;
the study is five commits on top of the authors' commit `1b3e07fe`, plus an
out-of-tree `analysis/` directory. The full write-up is a separate 10-page
report; this file is the install-and-run half, so a reader can reproduce every
number in it without reading the report.

**Short version.** Two targets reproduce byte-for-byte, not "within tolerance":
the five-seed behavioural monitor headline row, and the deterministic-checks
versus monitor comparison. One baseline (`tcn`) moves by 0.22σ and is
attributed to a PyTorch wheel ABI difference. The modification widens the
`cusum_k` ablation from four points to eight and finds a plateau and a cliff
where the paper's one-order-of-magnitude sweep saw only the plateau.

No LLM, no API key, no GPU is involved: both targets run on synthetic telemetry
and on traces already committed to this repository.

---

## 1. What is reproduced

| # | Target | Where it lives | Metric |
|---|---|---|---|
| R1 | Five-seed stability of the behavioural monitor | `results/tables/multiseed_summary.csv`, row `esn_cusum_max` | detection rate, mean lead (steps), episode AUC, realised false-alarm rate — each as mean ± SD over 5 seeds |
| R2 | Deterministic checks vs the behavioural monitor | `results/tables/verification_vs_monitor.csv` | recall (with and without coverage), false positives on healthy episodes, at two serving temperatures and on a held-out corpus |

Metrics are defined as the repository defines them; the one thing worth stating
explicitly is the **denominator**. R1 runs over 400 failed episodes and 160
healthy episodes per seed. R2's recall has two legitimate readings — `34/57`
counts only answers that were produced at all, `55/57` also credits the 13
incomplete-topic episodes that only the coverage check can catch. Both are
reported; quoting one without the other is the most common way to get this
number wrong (see §5).

---

## 2. Environment

| | |
|---|---|
| OS | Windows 11, x86-64 |
| Python | **3.13.18** |
| Virtualenv | created by `uv 0.13.7`, which **does not install pip** into it |
| Compute | CPU only. No GPU, no network, no model weights |
| Wall clock, end to end | ~80 minutes (of which 60 is the five-seed run) |

Locked packages that matter here, exactly as installed:

```
numpy==2.4.6      scipy==1.17.1      scikit-learn==1.9.0
pandas==3.0.3     torch==2.12.0+cpu  matplotlib==3.11.0
```

Full list: [`env_actual.txt`](env_actual.txt) (118 packages, `pip freeze`).
`results/multiseed.json` also carries a provenance block recording the
interpreter, the platform and all five per-seed configuration hashes.

**Deviation from the lock file.** `requirements.lock.txt` was generated on
Python 3.14.5; the README requires 3.13+. I ran 3.13.18. This is not cosmetic:
`torch` ships per-ABI wheels, so `cp313` and `cp314` are different compiled
artifacts, and that is the sole cause of the one non-trivial discrepancy in §5.

---

## 3. Install

Two traps, both of which cost me time, so they are stated as commands rather
than as warnings.

**Trap 1 — `+cpu` is not a PyPI version.** `torch==2.12.0+cpu` uses a PEP 440
local version label and exists only on the PyTorch CPU wheel index. Installing
the lock file against PyPI alone fails with `Could not find a version that
satisfies the requirement`. Add the index; do not edit the lock file.

**Trap 2 — an activated prompt does not mean `pip` belongs to that venv.** If
the venv was made by `uv`, there is no `pip.exe` inside it, and a bare `pip`
falls through to whatever global interpreter is on `PATH`. Every command below
therefore spells out the interpreter.

```powershell
# from the repository root
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip

# pinned set + the CPU wheel index (--extra-index-url, not --index-url:
# the latter would replace PyPI and then numpy/scipy/pandas cannot be found)
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt `
    --extra-index-url https://download.pytorch.org/whl/cpu

# environment evidence — compare it against the block in §2
.\.venv\Scripts\python.exe -m pip freeze > env_actual.txt
```

Check the interpreter before going further:

```powershell
.\.venv\Scripts\python.exe -c "import sys,numpy,scipy,sklearn,torch;print(sys.version.split()[0],numpy.__version__,scipy.__version__,sklearn.__version__,torch.__version__)"
# expected: 3.13.18 2.4.6 1.17.1 1.9.0 2.12.0+cpu
```

If `torch` cannot be installed at all, the study still runs: `torch` is imported
lazily in `derail/monitor/seq_baselines.py` and its absence only removes the
GRU/LSTM/TCN/linear-AR comparison rows, not the ESN monitor that R1 measures.
State that in your notes if you take that route — the eleven-monitor table in
the paper becomes a seven-monitor table.

---

## 4. Run

All four stages are offline and CPU-only. Times are measured on the machine in
§2, not estimated.

```powershell
# S0 · baseline self-check, ~10 min (the test suite dominates)
git status --porcelain                    # expect empty
git log --oneline -1                      # expect 1b3e07fe or a descendant
.\.venv\Scripts\python.exe -m devtools.claims_ledger --check
.\.venv\Scripts\python.exe -m pytest -m "not network and not ollama" -q
# expect: all 121 claims match their artifacts · 869 passed, 20 skipped, ~598 s

# S1 · R1, the five-seed study, ~60 min (README says ~35; it took 3604 s here)
.\.venv\Scripts\python.exe -m derail.experiments.run_multiseed
# writes results/tables/*.csv, results/seed{7,101,202,303}/, results/multiseed.json

# S2 · R2, deterministic checks vs the monitor, ~10 min total
.\.venv\Scripts\python.exe -m derail.verify.run_verification_study
.\.venv\Scripts\python.exe -m derail.verify.run_verification_study --holdout organic_demo7b_cold
.\.venv\Scripts\python.exe -m derail.verify.run_verification_study --holdout organic_demo7b_holdout
# writes results/tables/verification_{vs_monitor,cold,holdout}.csv

# S4 · the modification, ~3 min
.\.venv\Scripts\python.exe -m derail.experiments.run_ablation
# writes results/tables/esn_ablation.csv (8 cusum_k points in this fork)
```

S1 and S2 write **disjoint** sets of files — `run_verification_study` only
touches `verification_*.csv`, which `run_multiseed` never opens — so their order
does not matter. S4 touches only `esn_ablation.csv`.

If you plan to compare against the authors' committed tables, snapshot the
originals first (or just rely on `git diff <baseline>`, which is what the
verification step does):

```powershell
git show 1b3e07fe:results/tables/multiseed_summary.csv | Select-String esn_cusum_max
```

---

## 5. Verify

The two scripts below are the actual evidence, because they check the outputs
rather than re-run the producers. Both live in `analysis/` and neither imports
`derail`.

```powershell
# R1: byte-level and metric-level comparison against the baseline commit
.\.venv\Scripts\python.exe analysis\compare_r1.py 1b3e07fe

# R2: independent recomputation from the episode-level CSVs — reads, counts, divides
.\.venv\Scripts\python.exe analysis\recompute_r2.py
```

`compare_r1.py` takes the baseline commit as an argument **on purpose.** If it
defaulted to `HEAD`, then committing a reproduction would make the check compare
the run against itself and pass while validating nothing. It refuses to run when
the baseline equals `HEAD`.

Expected numbers, against `1b3e07fe`:

| Target | Metric | Reported | Here |
|---|---|---|---|
| R1 | detection rate | 0.7065 ± 0.0682 | **identical string** |
| R1 | mean lead, steps | 4.613 ± 0.974 | **identical string** |
| R1 | episode AUC | 0.87205 ± 0.01529 | **identical string** |
| R1 | false-alarm rate | 0.04375 ± 0.01593 | **identical string** |
| R2 | checks recall (total only / + coverage) | 34/57 = 0.5965 / 55/57 = 0.9649 | identical |
| R2 | monitor recall | 31/57 = 0.5439 | identical |
| R2 | false positives, checks vs monitor | 0/63 vs 11/63 = 0.1746 | identical |
| R2 | held-out corpus | 0.5357 / 0.9286 / 0 of 64 | identical |

What does **not** match, exhaustively:

1. **`tcn` row of `multiseed_summary.csv`.** detection 0.4025 → 0.4135, lead
   2.749 → 2.8195, AUC 0.72902 → 0.72965. The largest move is 0.011, which is
   0.22σ of that monitor's own seed-to-seed SD. `gru` and `lstm` are identical,
   so this is not "torch is broken": TCN is the one baseline trained by SGD
   through `nn.Conv1d`, whose oneDNN kernels differ between the `cp313` and
   `cp314` wheels. Closed-form monitors (the ESN ridge solve) and the
   statistical checks have no such dependence.
2. **`theta` / `mean_confidence` columns** of `h1_main.csv`,
   `delay_fa_curves.csv` and `h3_reliability.csv`: relative error 1e-11 to
   1e-10, i.e. the last printed digits of a calibrated threshold. No discrete
   decision anywhere flips. Seven of the eleven result tables are
   byte-identical.
3. Nothing else. `results/run_meta.json` also differs because it records the
   host, which is expected.

Two facts that look like failures and are not:

- **`seed 7` reports H1 `NOT SUPPORTED`.** That is in the authors' committed
  file too (`all_supported_every_seed = false`); four of five seeds support all
  four hypotheses. Not a reproduction failure, and the paper says so itself.
- **20 tests skip.** Twelve need manuscript sources that are not in the
  checkout, four need a Hugging Face build product, one needs `pyarrow`, one a
  deployment freeze, one a stored audit report, one a dataset build. None touch
  the R1 or R2 code path.

---

## 6. The modification

One line in `derail/experiments/run_ablation.py`: the `cusum_k` grid goes from
`[0.25, 0.5, 0.75, 1.0]` to `[0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 2.0, 5.0]`.
The four original points are kept, so the new run is directly comparable to the
published one, and `esn_ablation.csv` gains four rows and loses none.

| κ | 0.05 | 0.10 | 0.25 | 0.50 | 0.75 | 1.00 | 2.00 | 5.00 |
|---|---|---|---|---|---|---|---|---|
| AUC | .8496 | .8495 | .8493 | .8473 | .8441 | .8407 | .8163 | .7543 |
| detection | .6700 | .6700 | .6950 | .6925 | .6850 | .6600 | .5325 | .2800 |
| mean lead | 4.073 | 4.125 | 4.275 | 4.318 | 4.315 | 4.173 | 3.438 | 2.425 |

A plateau over a 15× span (`κ` in [0.05, 0.75], AUC moves 0.0055) and a cliff
(κ in [1, 5], detection loses 232 of 400 failed episodes). The paper's grid sits
entirely inside the plateau, so its "insensitive to κ" claim is true locally and
false globally. Figure: `results/figures/fig_kappa_sweep.png`, rendered by
`analysis/plot_kappa.py`.

**Do not read the false-alarm column as a κ effect.** `run_ablation.py`
re-fits `pick_threshold` at every κ against a 5% budget on ~40 healthy
validation episodes, so FA is a controlled variable whose observed range
(0.0688–0.1000) is quantisation noise on a 1/160 grid. AUC is threshold-free and
is the only strictly monotone column here.

---

## 7. Commits

| Commit | Contents |
|---|---|
| `1b3e07fe` | authors' baseline — the commit that shipped the published numbers |
| `371b156b` | reproduction run 1: all result tables, five seed directories, provenance |
| `0d91de30` | verification tooling (`analysis/compare_r1.py`, `analysis/recompute_r2.py`, `scripts/run_s3.ps1`) and its output logs |
| `1fc25278` | the κ sweep, its figure, and `logs/S4_ablation.md` |
| `9eb31696` | stage logs re-encoded UTF-16 → UTF-8 so they render on GitHub |

Branch: `repro/run-2026-11-10`. Nothing in `derail/` changes except the one
grid line in `run_ablation.py`; everything else new is additive. The table lists
the commits that carry measurements; one further documentation commit adds this
file and the README entry point, and contains no numbers.

---

## 8. Pointers

| What | Where |
|---|---|
| Stage-by-stage run records, with raw output and readings | `logs/S0_baseline.md` … `logs/S4_ablation.md` |
| Frozen snapshot of the first run's artifacts | `logs/run1_snapshot/` |
| Comparison and recomputation scripts | `analysis/` |
| Stage drivers | `scripts/run_s2.ps1`, `scripts/run_s3.ps1` |
| Environment evidence | `env_actual.txt`, provenance block in `results/multiseed.json` |
| Authors' own reproduction notes | `REPRODUCE.md` |
| Authors' claim-to-artifact ledger | `CLAIMS.md` (121 claims, checked in S0) |

**No secrets are committed and none are required.** The study never calls a
model: `git grep` for token patterns returns only the synthetic fixtures in
`tests/test_security_containment.py` and `tests/test_hf_dataset.py`, which exist
to test redaction. Neither target needs an API key, a base URL or a model name.
