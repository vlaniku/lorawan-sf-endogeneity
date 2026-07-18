# The Spreading Factor Is Not Channel State — code & derived data release

Companion release for: V. Laniku and B. Krasniqi, "The Spreading Factor Is Not
Channel State: Endogenous Link Proxies and the Cost of Device-Homogeneity in
ISAC-Enabled IoT Resource Allocation" (submitted to IEEE Internet of Things
Journal, 2026).

## Contents
- `data/rwscp_link_readings.csv` — pseudonymized radio-layer readings from the
  RWSCP LoRaWAN water-metering deployment (59 devices, 1,014 uplinks, 32 days).
  Columns: pseudonym device ID (D01..D59), hours since window start, SF, SNR,
  RSSI, per-SF demodulation limit, SNR margin, frame-counter gap, missed frames.
  Application-layer fields (volumes, alarms, temperature) and device identifiers
  are not released.
- `data/rwscp_device_summary.csv` — per-device aggregates incl. mixed-model
  baseline (BLUP).
- `data/measured_link_params.json` — all fitted link-model parameters
  (SF fixed effects, ICC, variances, hold-out RMSEs), device keys pseudonymized.
- `code/` — analysis pipeline: measured link model, pre-registered replay
  apparatus (`full_replay.py`), pilot gates, live-PPO cross-check, LoED external
  replication, figure scripts. `code/allocator/` is the vehicle allocator
  (NSGA-III + PPO ISAC-IoT framework) the replay instruments.
- `results/` — headline result JSONs and the full NSGA-III run cache
  (`replay_cache.zip`; every number in the paper recomputes from these via
  `python full_replay.py metrics`).
- `docs/` — the pre-registration (committed before the replay ran), the link-model
  characterization report, final results, and the cite-and-distinguish table.
- `figures/` — the five paper figures.

## Reproduction
- Replay from cache: unzip `results/replay_cache.zip` into `code/replay_cache/`
  and run `python full_replay.py metrics`.
- Replay from scratch (~1 h CPU): `bash run_full_program.sh` then
  `bash run_more_seeds.sh` (resumable; asserts the ICC=0 alignment null).
- PPO cross-check: `python ppo_crosscheck.py`.
- LoED external replication: download LoED from
  https://doi.org/10.5281/zenodo.4121430 (not redistributed here), then
  `python loed_replication.py <dir-with-daily-csvs>` and
  `python loed_network_split.py`.
- Link-model refit: `measured_link_model.py` consumes the raw utility export,
  which is not included (available from the authors on reasonable request,
  subject to RWSCP permission); all fitted parameters it produces are in
  `data/measured_link_params.json`, and the pseudonymized readings support
  independent re-estimation of every statistic in the paper.

## Environment
Python 3.12; `pip install -r requirements.txt`.

## License
Code: MIT (see LICENSE). Derived data (`data/`): CC BY 4.0. Deployment data released with permission of the Regional Water Supply Company Prishtina (RWSCP).

## Contact
Vullnet Laniku, University of Prishtina — vullnet.laniku@uni-pr.edu
