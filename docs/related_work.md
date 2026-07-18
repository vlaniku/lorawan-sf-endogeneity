# Cite-and-distinguish table (gauntlet output, verified 2026-07-16)

*Every neighbor genre with a concrete verified anchor, what it does, and the one-sentence
distinction. Rule: cite generously, distinguish precisely — the reviewer must see we know
each genre and that none of them contains the endogeneity claim.*

| # | Genre / anchor | What it does | How we differ (one sentence) |
|---|---|---|---|
| 1 | **ADR suboptimality & improvement** — Slabicki, Premsankar, Di Francesco, "Adaptive configuration of LoRa networks for dense IoT deployments," IEEE/IFIP NOMS 2018 (FLoRa); + ML-ADR lineage (e.g., LSML-SF, 2026) | Shows ADR converges slowly / mis-tunes under varying channels; proposes better ADR variants | They treat ADR's *output* as the thing to improve; we treat ADR's output (SF) as a **confounded observable** and quantify what believing it costs a *downstream allocator* — the bias persists no matter how good ADR gets, because any converged controller induces the cancellation |
| 2 | **Deterministic SF→SNR-threshold allocation** — SF-allocation via per-SF demodulation thresholds (e.g., "Energy-constrained optimization for SF allocation," Sensors 2020; multi-gateway SF selection, Comput. Netw. 2020) | Allocates SF/power from a fixed per-SF SNR-threshold table (the idealized oracle we test) | This genre *is* the assumption under test — we show the per-SF threshold map explains η²=2.6% of real margin variance and is no better than the grand mean out of sample |
| 3 | **Ideal-vs-realistic LPWAN gap** — "Comparative Analysis of an Urban LoRaWAN Deployment: Real World Versus Simulation," IEEE (Xplore 9844990); scalability sims (Bor et al., MSWiM 2016; Magrin et al., ICC 2017) | Quantifies aggregate capacity/PDR gaps between simulation and deployment | They report *that* reality underperforms simulation at network level; we identify a *mechanism* (ADR-induced SF endogeneity + persistent per-device structure) and propagate it to *per-device allocation decisions* (rank shifts, dBm misallocation), not aggregate throughput |
| 4 | **Trace-driven LPWAN propagation** — urban aerial/ground-gateway measurement datasets (Sci. Data 2025); AERPAW UAV/helikite campaign (arXiv 2604.06444) | Measures RSSI/SNR vs distance/SF to fit propagation models | They model the *marginal* channel; we model the *conditional structure* P(margin \| SF, device) and show the SF-conditional is the wrong conditioning because SF is endogenous |
| 5 | **Real-data ISAC** — DeepSense 6G (Alkhateeb et al., IEEE Commun. Mag. 2023): real multi-modal sensing+comm; UAV-ISAC vehicular RA with trajectory data (Sensors 2025) | Uses real data to *train/validate methods* (beam prediction, trajectory RA) | Method-validation, not assumption-falsification: they ask "does my method work on real data," we ask "is the field's *input model* even measuring what it claims" |
| 6 | **LoRa-as-ISAC sensing** — SenLoRa (ACM IMWUT 2025, DOI 10.1145/3749522), LoSense, LoRadar | Turns LoRa signals into sensors (respiration, motion) — the PHY-bridge genre | Orthogonal: they add sensing to LoRa PHY; our ISAC content is at the *allocation layer* (the resource-allocation assumptions ISAC-IoT optimizers inherit), explicitly not a PHY bridge |
| 7 | **Robust / chance-constrained ISAC allocation** — outage-constrained robust secure ISAC beamforming (IEEE Xplore 9857564); robust ISAC RA frameworks (arXiv 2206.13307) | Allocates under *assumed* uncertainty sets/distributions around a nominal channel | They assume an uncertainty model (usually unimodal, iid, device-homogeneous) and optimize against it; we *measure* the uncertainty structure and find it violates those assumptions (multimodal fleet margin, ICC=0.61 persistent per-device structure, drifting) — our results are the missing *input* to that literature, not a competitor |
| 8 | **CRB-guided energy-efficient ISAC RA** — dense 2024–26 genre (e.g., arXiv 2605.29939) | Replaces phenomenological sensing metrics with CRB in allocation | Ruled out as *our* contribution (saturated); cited to show methodological novelty in ISAC-RA is closed and to motivate the empirical lane |
| 9 | **Our prior framework** — Laniku & Krasniqi (+ Akyildiz), NSGA-III+DRL ISAC-IoT allocation (in review) | The allocator-under-test; already parameterized by RWSCP traffic/RSSI marginals | The new paper tests the *assumption* that framework (and its genre) inherits: device-homogeneous shadowing (σ=7.82 dB iid) and exogenous link-state proxies; using our own published framework as the vehicle is the anti-strawman |

## The claim none of them contain
"The transmission-mode parameter (SF) that LPWAN allocators read as channel state is
**endogenous** — set by ADR in response to a hidden, persistent, drifting per-device
baseline (corr = −0.92) — and treating it as exogenous costs a real allocator ~6.7 dBm
per-device power misallocation and re-ranks ~76% of the fleet."
Exact-phrase and adjacent-field searches (July 16, 2026): no hit on SF-as-confounded-control,
no measurement-grounded falsification of ISAC-IoT allocation inputs. Genres 1–8 all verified live.

## Verification status (updated 2026-07-17 — full-text PDFs checked)
All anchor citations verified against the actual papers: Citoni et al. (IEEE Sensors J. 22(17) 2022);
Liu et al. (IEEE WCL 11(11) 2022); Xu, Yu, Ng, Schmeink, Schober (IEEE TCOM 70(12) 2022);
Narieda/Fujii/Umebayashi (Sensors 20(16) 2020); Loubany/Lahoud/El Chall (Comput. Netw. 182, 2020);
Farhad et al. (Front. AI 9, 2026); Wang et al. SenLoRa (IMWUT 2025); Vargas Villar et al.
(IEEE Aerospace 2026); Liu et al. CRB-ISCC (arXiv 2605.29939); Song/Zhang/Bai (Sensors 25(23) 2025).
**Correction found in verification:** Song et al. is PURE SIMULATION (MINLP+BCD, no real mobility
data) — recategorized in the draft from "real-data ISAC" to "simulation-driven ISAC-RA"; DeepSense
remains the real-data anchor. **IoTJ presence added:** Finnegan/Farrell/Brown (IoTJ 7(8) 2020, ADR
enhancement), Magrin/Capuzzo/Zanella (IoTJ 7(1) 2020), Van den Abeele et al. (IoTJ 4(6) 2017) —
4 IoTJ refs total incl. Lu et al. Remaining tiny checks: Citoni end page; lu2024 vol/pages.
