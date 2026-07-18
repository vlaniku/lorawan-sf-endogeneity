# RWSCP Measured Link-Headroom Model — Characterization

*The "measured oracle" for the idealized-vs-measured replay. Built on RWSCP `All Readings` (1,008 readings, 59 devices). All numbers computed directly on the data; nothing assumed.*

## 1. What this delivers

Two oracles over SNR margin (dB), to be fed into your TGCN allocator's link sub-model:

- **Idealized oracle** — `idealized_margin(sf)`: the field's assumption, a deterministic SF→margin map with zero device/residual spread. This is what an ISAC-IoT allocator that treats SF as a channel-state proxy believes.
- **Measured oracle** — `measured_margin_dist(sf, device, load)`: the real conditional distribution P(margin | SF, device, load), with the per-device baseline and residual the idealized map omits.

The gap between them, propagated through the allocator, is **X** (the cross-device allocation error). This module gives you the inputs; the replay wiring is yours.

## 1a. Framing (read before building the replay)

- **The keystone (§3) is the finding; X is its consequence, not its proof.** The −0.92 endogeneity result establishes the problem by itself. X measures *how much and in which direction* the confounding biases a real allocator. Lead with the keystone; present X as the magnitude. A small X with the keystone intact is still publishable ("real but bounded"); only a small X presented *as the headline* would read as a null result. See `X_preregistration.md`.
- **The idealized oracle is the field's, not ours (anti-strawman).** It is the link model the allocator-under-test already uses — TGCN Eq. 6, `R = B·log₂(1+SINR)`, device-homogeneous composite channel (path-loss + shadowing σ=7.82 dB + Rayleigh), SF exogenous — and the SF-allocation literature's deterministic per-SF SNR-threshold maps. The `idealized_margin_db` fleet-means in this module are a convenient instance; in the paper, justify the oracle by quoting Eq. 6 and ≥1 external allocator, so X is the gap to the field's assumption, not to something we computed for convenience. The falsified assumptions are **device-homogeneity** and **SF-exogeneity**.

## 2. The headline (the falsification)

Fleet-wide, **SF explains η² = 0.026 of SNR-margin variance** (95% CI 1.4–5.3%). Out of sample, the idealized SF-only map (RMSE 3.56 dB) is **no better than guessing the grand mean** (3.67 dB). As a channel-state proxy — the role allocators give it — SF carries essentially nothing. See `fig1_margin_by_sf.png` and `fig4_holdout_rmse.png`.

## 3. The mechanism (why the proxy fails — the keystone)

This is the part that is *yours* and that no synthetic study can produce. The flat fleet margin is not "SF doesn't matter." It is an exact **cancellation**:

| SF | within-device SF gain (+) | baseline of devices parked at SF (−) | observed fleet margin |
|----|--------------------------|--------------------------------------|-----------------------|
| 7  | +0.0 | +6.6 | 11.55 |
| 8  | +2.1 | +3.7 | 10.89 |
| 9  | +5.0 | +1.9 | 11.95 |
| 10 | +5.9 | +0.9 | 11.83 |
| 11 | +6.7 | −0.4 | 11.30 |
| 12 | +7.0 | −1.8 | 10.23 |

**corr(SF, device baseline) = −0.92.** ADR parks low-baseline (poor-link) devices at high SF; the SF gain then almost exactly offsets their low baseline, leaving ~11 dB everywhere. So **SF is endogenous** — it reflects ADR's control action in response to the hidden baseline, not the residual channel state the allocator needs. An allocator reading SF as an exogenous channel observation is reading a control variable as if it were a state measurement. See `fig2_cancellation_keystone.png` (the central figure). The counterfactual in the module self-test confirms it: force all devices to a common SF and margin rises 4.9→11.9 dB — the pure SF gain the sorting hides.

> **Framing guard (carry into Section VI):** state X as *the gap between the input the field actually uses (SF-only, exogenous) and ground truth from a real deployment* — i.e. the field's blind spot — not as "a model is sensitive to its inputs." The endogeneity result is what makes it a blind spot rather than a tautology.

## 4. Distribution shape (defeats the benign-distribution assumption — carefully)

Fleet-level margin is **multimodal** (Hartigan dip p = 0.020), consistent with a mixture over device baselines — so the distribution a fleet allocator faces is not the benign unimodal one robust/chance-constrained ISAC allocation assumes. *Honest scope:* conditioned on (SF, device) the residual is approximately Gaussian (per-SF Shapiro p > 0.05 for SF8–12; SF7 mildly left-skewed). So the multimodality is a marginal/mixture effect, not heavy-tailed conditionals. Claim it at the fleet level only.

## 5. Honest ceilings and caveats (bake these into the paper)

- **Irreducible residual sd ≈ 3.2 dB.** Even the full (SF + device + load) model bottoms out near this floor; margin is intrinsically noisy. This bounds how precise X can be — report X with this ceiling stated, not as a sharp point estimate.
- **The device baseline is not static path-loss — and it moves.** It is only moderately time-stable (first/second-half r = 0.46) and partly RSSI-linked (r = 0.57). Claim "a per-device offset SF cannot see," not "static siting." The non-stationarity *strengthens* the case: the thing SF misses is also drifting, so even an allocator that estimated each device's baseline once would partially lose it over the 32 days — it is not a fixed constant learnable once and cached.
- **Reliability not modeled — and this makes X a conservative lower bound.** SNR exists only for *received* frames; missed frames have no SNR (survivorship). The measured oracle is therefore fit on the optimistic subset, *under-representing exactly the worst-link devices whose mis-allocation matters most*. Consequence: the idealized-vs-measured gap **X is a lower bound** on the true allocation error — the unobserved missing frames can only widen it. State this directionally in the paper (X ≥ floor) so survivorship reads as a bound in your favor, not a flaw. The per-device margin↔missed-rate correlation is weak/confounded (~0.25–0.36, sign mediated by SF airtime); handle reliability separately, never as a clean margin→reliability map.
- **SF-overshoot stays supporting, not headline.** The within-device +7 dB SF gain is a clean ADR-mis-tuning fingerprint but sits next to the saturated "ADR is suboptimal" literature. Use it to *explain* the endogeneity; do not center it, or a reviewer reclassifies the paper.
- **External validity.** One deployment, 32 days, 59 devices, no GPS. The transferable claim is the *mechanism* (endogenous SF → proxy failure), evidenced by the magnitude, not the single magnitude alone.
- **Novelty claim — NARROWED after June-2026 lit-scan (state it this precise way).** Do NOT claim "first real-data ISAC resource allocation" (false — IoV ISAC-RA uses real mobility data) or "first ideal-vs-realistic LPWAN comparison" (false — trace-driven propagation + the 95%→40% capacity-gap genre exist). The uncontested claim is the **endogeneity framing**: "we frame the transmission-mode (SF) as *endogenous to channel state* — set by ADR in response to the hidden per-device baseline — and quantify the resulting allocation-layer error against an operational deployment." Nothing in the LoRa/ISAC literature frames SF as a confounded control variable; that is the clean core, and it keeps the keystone (not X) at the center of novelty. Cite & distinguish: trace-driven LPWAN propagation studies, ideal-vs-realistic capacity papers, IoV real-data ISAC-RA (method-validation, not assumption-falsification), DeepSense-style PHY channel-sounding. Re-read the closest in full at draft time.
- **Saturation mechanism (state one sentence).** The ICC dose-response saturates because the allocator's power response is bounded/coarse (0–23 dBm caps): any persistent structure re-sorts devices and saturates the mean mis-allocation at ~6 dBm, while the *specific* devices absorbing it shift with perturbation size (Δpower@0.3 vs @0.9 corr≈0.55, low top-mover overlap). It is optimizer-response saturation, not a channel artifact.

## 6. Files

- `measured_link_model.py` — the two oracles + sampler (`python3 measured_link_model.py` self-tests).
- `measured_link_params.json` — all fitted parameters (mixed-effects fixed effects, device baselines/BLUPs, variances, demod limits, hold-out RMSEs).
- `fig1_margin_by_sf.png` — flat margin across SF (the falsification).
- `fig2_cancellation_keystone.png` — SF gain vs ADR baseline sorting cancelling (the mechanism).
- `fig3_idealized_vs_measured.png` — deterministic point vs measured per-device spread.
- `fig4_holdout_rmse.png` — SF-only ≈ grand mean out of sample.

## 7. How it plugs into the replay (your step)

For each device-reading in RWSCP, feed the allocator's link sub-model:
- **idealized run:** `idealized_margin(sf)` (deterministic), and let the allocator rank/assign as it does today.
- **measured run:** `measured_margin_dist(sf, device, load)` (or `sample_measured_margin`) so reality's per-device baseline and residual enter.

Then X = divergence in (a) device priority ranking (Kendall-τ), (b) predicted vs realized energy, (c) predicted reliability — with the §5 ceilings reported alongside. You hold ground truth on what the allocator actually does; I check the link-model side.
