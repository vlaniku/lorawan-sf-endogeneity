# Pre-registration: interpreting X (the replay result) — committed BEFORE wiring

*Written before the allocator is wired, so a small X is an honest finding and a large X isn't over-claimed. Same discipline as the η² decision gate. Updated after tracing Eq. 6's consumption path in the TGCN source.*

## 0. Injection-point trace result (the gate — RESOLVED, and it narrows scope)

Traced `nsga3_optimizer.py` → `isac_system_model.py`. The optimizer's only channel-state input is `get_channel_gain(distance)` → `sinr_comm` (line 237/247), with shadowing + Rayleigh **redrawn iid every evaluation** (line 149). Findings:

- **No spreading factor anywhere.** The decision variables are {tx_power, sensing_freq, bw_fraction, offload_ratio}; the code's `sf` is *sensing frequency* (radar, 1–100 Hz), not LoRa SF. `grep` for spreading/margin/SF-as-state across all files: none.
- **Therefore SF-exogeneity is NOT testable via this replay.** It is established by the **keystone alone** (RWSCP corr(SF, baseline) = −0.92). Adding an SF→margin input to this allocator would construct the strawman in code — explicitly avoided.
- **Device-homogeneity IS testable**, at a single clean injection: the iid shadowing draw (line 149). The allocator assumes no persistent per-device structure; RWSCP proves persistent structure (ICC 0.61, σ_dev≈3.8 dB, time-stability r=0.46).

**Leverage pilot (passed, variance-matched, `pilot_leverage_check.py` v2).** Total shadowing variance held CONSTANT — a fraction ICC (RWSCP-measured 0.61) of the allocator's existing variance is moved from iid to a persistent per-device term, so idealized and measured oracles have identical marginal variance and differ only in structure. Findings:
- **Determinism null:** idealized-vs-idealized τ=+1.00, |Δ|=0.00 (3 seeds).
- **RNG-alignment null (Bug-1 check, PASSED):** idealized vs matched-at-**ICC=0** = τ=+1.000, |Δ|=0.0000 dBm (both seeds). The hand-rolled `matched` path is byte-for-byte aligned with the original, so the signal at ICC>0 is real, not desync. *Committed: this null is re-run and must be exactly 0 before trusting any full-build magnitude.*
- **Effect:** structure-only per-device power |Δ|≈6 dBm, rank-τ≈0 → leverage is **from structure, not added variance**.
- **Dose-response is THRESHOLD/SATURATING, not graded** (seed-averaged |Δ|: ICC 0.30→6.64, 0.61→6.06, 0.90→6.12 dBm; ICC 0→0 exactly). Any persistence switches the effect on at ~6 dBm; more persistence does not increase it. **Robustness gift:** X is insensitive to the exact ICC in [0.3,0.9], so the result does NOT hinge on the precise injected fraction. Report the step response honestly (present-vs-absent matters, magnitude of fraction does not); do NOT draw a monotone dose-response figure — it would misrepresent the data.
- (Preview only — min-energy corner, one mapping; not the reportable X.)

## 1. Committed scope (which assumption the replay tests)

**The replay tests device-homogeneity ONLY.** SF-exogeneity is a keystone (data) result, not a replay result, and the paper states so. We commit to this scope now, before seeing X, rather than discovering it mid-build and quietly narrowing.

## 2. The finding is the keystone, not X

The paper's result is the **endogeneity keystone** (−0.92; flat margin = cancellation of SF gain and ADR baseline sorting), which establishes SF-exogeneity is false by itself. X measures *how much* the **device-homogeneity** half biases a real allocator's decisions. A small X with the keystone intact is still publishable ("the homogeneity bias is real and bounded at this size"); only a small X presented *as the headline* would read as null.

## 3. The two oracles (faithful, externally grounded, physically coherent)

Injection point: the shadowing term feeding `sinr_comm` (isac_system_model.py line 149/237).

- **Idealized oracle** = the allocator as written: shadowing iid-redrawn per evaluation (device-homogeneous, no persistent structure). This is TGCN Eq. 6's own channel and matches the SF-allocation literature's homogeneous-statistics assumption.
- **Measured oracle (variance-matched decomposition — concern 2 fix)** = the SAME total shadowing variance, re-partitioned: `shadow = σ·√ICC·z_i + σ·√(1−ICC)·z0`, where `z_i` is a persistent per-device standard normal (held across evaluations) and `z0` is the iid residual. With ICC=0.61 (RWSCP-measured), Var(measured)=σ²=Var(idealized) exactly — the oracles differ ONLY in structure, not amount. We inject RWSCP's *structure* (the dimensionless persistent fraction ICC), not σ_dev in absolute dB and not raw LoRa margins — this also sidesteps the 3.5 GHz-cellular-vs-LoRa unit mismatch.

  **Framing of the injected quantity (committed):** the persistent term is a **persistent per-device link-quality offset**, NOT a claim that cellular shadowing has ICC 0.61. RWSCP's 0.61 was measured on SNR *margin*, which bundles everything persistent about a device (propagation shadowing + antenna/enclosure + firmware/ADR + local interference). We inject that persistence at the allocator's *only* channel-state hook (the shadowing term) because that is where device link quality enters the optimizer — not because we claim propagation shadowing is 61% persistent. State exactly this in the paper, or a propagation reviewer will object that shadowing decorrelation distances don't yield ICC 0.61 at these ranges.

  **Seed/structure variance (Bug-2 note):** `z_i` is redrawn per seed, so each seed is a different structure realization; X is averaged over BOTH iid realizations AND persistent-structure realizations. Report that seed-to-seed spread in X includes structure-draw variance, not only optimizer noise.

The falsified assumption is **iid/homogeneous shadowing** (no persistent per-device term). The contrast is **paired (concern 1):** same iid realization `z0` and same fading/LOS draws in both runs, offset toggled — state in the paper that X is a paired contrast so the variance isn't misread as if draws were independent.

**Build-correctness commitments (concern 3):** the persistent term is keyed per device with a fail-loud assertion that every device receives exactly one offset and there are no key collisions — no silent partial application that would understate X. First checks on the full results: (a) total shadowing variance identical across oracles; (b) every device got exactly one persistent offset.

## 4. Metrics (committed) — ordered so the un-gameable evidence leads

**Framing commitment (concern 1):** X is reported as *the measured magnitude of a real deployment's heterogeneity cost* — NOT as evidence that "heterogeneity has a cost" (correlated-shadowing-changes-allocation is a known generic result). The contribution is the calibrated magnitude tied to RWSCP's measured σ_dev/ICC, not the existence of an effect. The paper states this explicitly.

1. **Primary, direct (concern 4) — per-device allocation-variable divergence.** Distribution of per-device |Δ tx_power| and |Δ bw_fraction| between idealized and measured runs. This is the optimizer's actual output, free of any scalarization/ranking construction. (Pilot already shows ~4–8 dBm power shifts.) Rankings are *derived*; allocation variables are *native* — so they lead.
2. **Primary, summary (concern 3 — PROMOTED) — unconditioned fleet rank-shift rate.** Fraction of devices whose priority rank moves > k positions under the measured oracle, across the **whole fleet**, not conditioned on Δoffset. The headline number the decision rule keys on, precisely because it does not select on the variable the idealized oracle is blind to.
   - **Operating point (concern 5):** rank is read at the **deployed Q-selected Pareto candidate** (what the system actually picks), NOT the convenient min-energy corner the pilot used. Report X at the Q-selected point as primary, plus ≥1 other Pareto anchor, so X is not an artifact of always reading the energy-minimizing vertex. The pilot's min-energy selection is a leverage-preview convenience only.
3. **Companion (concerns 1) — resolvable-set Kendall-τ.** Reported on BOTH the full pair set and the resolvable set (|Δoffset| > 3.19 dB; ~55.8% of pairs). Flagged as biased-low-by-construction; it brackets the primary, it does not arbitrate.
4. **Mapping sensitivity (concern 2 — the load-bearing modeling choice).** Report every metric under ≥2 defensible RWSCP→synthetic-device mappings: (a) offset independent of the simulator's distance; (b) offset partially distance-correlated per RWSCP's RSSI–offset r=0.57. Commit to publishing whether the headline survives both. If X swings materially on the mapping, that is reported, not hidden.
5. **Tertiary — energy/EE mis-estimate** under idealized vs measured.
6. **Reliability is NOT a metric** (survivorship; §6).

## 5. Decision rule (committed BEFORE seeing X)

- **The decision keys on the unconditioned fleet rank-shift rate (§4 item 2)** — the un-gameable metric — NOT on the resolvable-set τ (which is biased low by construction). Pre-registered reading, in terms of fleet rank-shift rate R (fraction of devices moving > k positions, k pre-set to ~10% of fleet size):
  - **R small (≲15% of devices shift)** ⇒ homogeneity bias has *limited operational impact*; report X as real-but-bounded. Keystone carries the paper.
  - **R large (≳15%)** ⇒ homogeneity bias *materially mis-prioritizes*; X is a headline-supporting magnitude.
- **Robustness condition:** the conclusion must hold under BOTH mappings in §4 item 4. If R crosses the threshold under one mapping but not the other, we report the split and conclude "mapping-sensitive," not a clean result.
- The resolvable-set τ and full-set τ are reported as conservative companions that bracket R. Commit to reporting all of them, in these terms, without redefinition after the fact.

## 6. Survivorship makes X a conservative bound (committed, monotonicity-softened)

The measured oracle is fit only on **received** frames; worst-link devices are under-represented (their bad frames went missing), so the oracle is optimistic about exactly the hard cases. Therefore X is **unlikely to narrow, and plausibly widens**, if the missing frames were observed. *We do not claim strict monotonicity* ("can only widen") — there exist mechanisms (e.g., worst-link devices already deprioritized for distance reasons) by which including them might not move τ. We commit to the softer directional claim and, if feasible, a one-line argument bounding the direction.

## 7. Multimodality stays a corollary, not a third headline

The fleet-margin multimodality (dip p=0.020 defeating the benign-distribution assumption) is real but is a *third front* after device-homogeneity and SF-exogeneity. To keep reviewer attention on the keystone, it is held as a one-paragraph corollary, not a co-headline.

## 8. Non-stationarity strengthens the case (committed sentence)

The per-device offset is only moderately time-stable (r=0.46), so the structure the homogeneous model misses is also *drifting* — even an allocator that estimated each device's offset once would partially lose it over 32 days. Not a fixed constant learnable once and cached.

## 9. Open build question for Vullnet (you hold ground truth)

Calibrating the measured oracle's persistent offset requires mapping RWSCP's 59 devices' offsets onto the allocator's synthetic device set (which is distance-generated, no GPS). Decide the mapping deliberately: e.g., draw the utility_meter class's persistent shadowing offsets from RWSCP's empirical offset distribution. This is the one modeling choice that needs your judgment; Claude checks the link-model logic, you own what the allocator does.
