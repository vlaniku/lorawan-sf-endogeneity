# Full-scale X — FINAL replay results (cellular TGCN allocator)

*Produced by `full_replay.py` on Vullnet's machine, 2026-07-16. Full paper fidelity:
gen=150, pop=120, 100 devices, 84 reference directions, **10 seeds**. Supersedes the
earlier 3-seed gen=120 preview. All committed gates passed. These are the reportable numbers.*

## Gates (all passed on this build)
- **ICC=0 alignment null = exactly 0.0** at full scale (byte-identical Pareto fronts) —
  the measured code path is aligned with the original allocator; magnitudes are pure
  structural effect.
- Variance-matched by construction (`σ√ICC·z_i + σ√(1−ICC)·z0`); one-offset-per-device
  asserted fail-loud; same-seed idealized determinism verified.
- **Stale-offset construction fixed and verified:** the estimate now has *exact* sample
  correlation r with the true offsets per seed (innovation orthogonalized in-sample,
  scale-matched). The previously persisted drift path had a decorrelation bug (fresh RNG
  for the base draw → stale ⊥ truth); any earlier stale numbers are superseded.

## Core X (idealized vs measured, 10 seeds)

| mapping / operating point | per-device \|Δpower\| | fleet rank-shift R | τ (full) | τ (resolvable) |
|---|---|---|---|---|
| indep / min-energy    | **6.74 dBm** | **0.77** | 0.07 | 0.06 |
| indep / DRL           | **6.79 dBm** | **0.77** | 0.06 | 0.04 |
| distcorr / min-energy | **6.74 dBm** | **0.76** | 0.06 | 0.10 |
| distcorr / DRL        | **6.71 dBm** | **0.75** | 0.07 | 0.08 |

**Verdict (per the pre-registered decision rule):** R ≈ 0.76 ≫ 0.15 under BOTH mappings
and BOTH operating points — the device-homogeneity bias **materially mis-prioritizes** at
full scale. ~6.7 dBm mean per-device power misallocation; priority orderings essentially
uncorrelated (τ ≈ 0).

## Live PPO cross-check (to-do #2 — DONE, `ppo_crosscheck.json`)
Real PPO (drl_agent.py, 50k timesteps, seed=42) trained on each of 15 cached fronts:
- Picks the **exact same** Pareto solution as the `drl_reward` proxy in **9/15** fronts;
  where it differs, live-vs-proxy picks are only **2.1 dBm** apart (small vs the ~6.7 dBm effect).
- X recomputed under live-PPO selections: **indep 7.0 dBm / R=0.76; distcorr 6.6 dBm / R=0.76**
  — indistinguishable from proxy-based X. The operating point is not a source of artifact.

## Third leg — freshness sweep (to-do #3 — DONE, 10 seeds, `fig5_freshness_sweep.png`)
Allocations optimized under an offset *estimate* of freshness r = corr(estimate, truth),
all evaluated under the TRUE channel (30 draws, memoized). Recovery = (E_blind − E_est)/E_blind.

**Min-energy operating point** (Wilcoxon signed-rank, n=10):
| freshness r | mean | median | seeds > 0 | p |
|---|---|---|---|---|
| 0.00 | −14.7% | −1.2% | 5/10 | 0.63 |
| 0.20 | −7.3% | +12.8% | 6/10 | 0.32 |
| 0.46 (= RWSCP 32-day drift) | **+18.9%** | +17.9% | 9/10 | **0.010** |
| 0.70 | +2.8% | +2.2% | 5/10 | 0.77 |
| 0.90 | **+19.9%** | +21.5% | 9/10 | **0.037** |
| 1.00 (perfect) | **+21.2%** | +23.4% | 8/10 | **0.020** |

**DRL operating point:** same directional pattern but weaker — perfect knowledge +12.9%
(p=0.084), r=0.46 +7.5% (p=0.56); nothing individually significant at n=10.

**Honest reading (fold into the paper this way):**
1. **Perfect per-device knowledge recovers ~13–21% energy on average** — the bias is
   genuinely recoverable, but even the perfect fix is not positive on every run
   (8–9/10 seeds): per-run optimizer variance is large at realistic budgets.
2. **A near-uninformative estimate (r ≲ 0.2) recovers nothing on average and carries a
   catastrophic tail** (worst seed −152%: optimizing for wrong structure burned 2.5× the
   blind energy under truth). Wrong beliefs about structure are worse than none.
3. **At RWSCP's actually-measured 32-day drift (r=0.46), mean recovery ≈ +19% at the
   min-energy point (p=0.01)** — i.e., at the staleness a real deployment exhibits after
   a month, a once-estimated offset still retains most of its corrective value *on
   average*, but run-level variance rules out per-deployment guarantees.
4. The sweep is **not a smooth monotone curve at n=10** (the r=0.70 cell dips to ~0 on
   both operating points — consistent with the large per-run variance, and reported as
   such, not smoothed away). Claim the coarse contrast (r≲0.2 useless/harmful vs r≥0.46
   useful-in-mean), NOT a calibrated recovery-vs-freshness function.
5. Recovery is systematically weaker at the DRL-selected point than the min-energy
   vertex — the deployed selection partially hedges, absorbing some recoverable loss.
   State this; it pre-empts the "your fix only works at a corner" review.

**Paper sentence:** the homogeneity bias is *recoverable with sufficiently fresh
per-device tracking; a stale or wrong offset estimate is not merely useless but can be
harmful* — which turns the third leg into an estimation-cadence requirement (future work),
not a free fix.

## Remaining before submission
1. Reliability stays out of scope (survivorship; X is a conservative lower bound — state directionally).
2. Cite-and-distinguish table: re-read the closest neighbors in full (trace-driven LPWAN
   propagation, ideal-vs-realistic capacity papers, IoV real-data ISAC-RA, DeepSense) at draft time.
3. Draft the paper: keystone leads (η²=0.026, corr=−0.92 cancellation), X is the magnitude,
   third leg is the conditional fix. Novelty claim = the endogeneity framing, stated narrowly.

## Reproduction
`bash run_full_program.sh` then `bash run_more_seeds.sh` (resumable; skips cache), then
`python full_replay.py metrics`; PPO check: `python ppo_crosscheck.py`; figure:
`python fig5_freshness_sweep.py`. Cache in `replay_cache/` (~5 MB, kept in the project folder).
Env: Python 3.12, numpy/scipy, pymoo 0.6.2, torch (CPU), stable-baselines3 2.9.0, gymnasium.
Allocator modules extracted from "Simulation and figures.zip".
