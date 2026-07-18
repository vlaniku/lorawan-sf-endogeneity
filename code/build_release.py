"""
build_release.py — assemble the public release package for the endogeneity paper
================================================================================
Produces  ../release/  (and ../release.zip) containing code, docs, figures, result
JSONs, and PSEUDONYMIZED derived RWSCP link data. Privacy rules:
  - application-layer fields (volume, alarms, temperature) are NEVER exported;
  - DevEUI / serial / device name replaced by stable pseudonyms D01..D59;
  - the pseudonym map is written OUTSIDE the release (private_pseudonym_map.csv)
    for the authors' audit only;
  - timestamps released as hours relative to window start (window dates are public
    in the paper); raw frame counters dropped (gap/missed derivatives kept);
  - the raw RWSCP export itself is NOT included (pending utility permission).
Deterministic: safe to re-run after RWSCP confirmation.
"""
import os, json, csv, shutil, zipfile
import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REL = os.path.join(ROOT, 'release')
XLSX = os.path.join(ROOT, 'RWSCP_Water_Meters_Export.xlsx')

READING_COLS = ['spreading_factor', 'snr', 'rssi', 'snr_demod_limit',
                'snr_margin_db', 'f_cnt_gap', 'missed_frames']

def fresh_dir(p):
    if os.path.exists(p): shutil.rmtree(p)
    os.makedirs(p)

def main():
    fresh_dir(REL)
    for sub in ['data', 'code', 'code/allocator', 'results', 'figures', 'docs']:
        os.makedirs(os.path.join(REL, sub), exist_ok=True)

    # ---------- pseudonymized data ----------
    wb = openpyxl.load_workbook(XLSX, read_only=True)
    ws = wb['All Readings']
    rows = ws.iter_rows(values_only=True)
    hdr = next(rows); ix = {c: i for i, c in enumerate(hdr)}
    readings = [r for r in rows if r[ix['dev_eui']] is not None]
    euis = sorted({r[ix['dev_eui']] for r in readings})
    pseud = {e: f'D{i+1:02d}' for i, e in enumerate(euis)}
    t0 = min(r[ix['timestamp']] for r in readings if r[ix['timestamp']])

    with open(os.path.join(ROOT, 'private_pseudonym_map.csv'), 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['dev_eui', 'pseudonym'])
        for e, p in pseud.items(): w.writerow([e, p])

    with open(os.path.join(REL, 'data', 'rwscp_link_readings.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['device', 't_rel_hours'] + READING_COLS)
        for r in sorted(readings, key=lambda r: (pseud[r[ix['dev_eui']]], r[ix['timestamp']] or t0)):
            ts = r[ix['timestamp']]
            trel = round((ts - t0).total_seconds() / 3600, 2) if ts else ''
            w.writerow([pseud[r[ix['dev_eui']]], trel] + [r[ix[c]] for c in READING_COLS])

    # per-device summary
    from collections import defaultdict, Counter
    agg = defaultdict(lambda: {'n': 0, 'sf': Counter(), 'margins': [], 'missed': 0})
    for r in readings:
        a = agg[pseud[r[ix['dev_eui']]]]
        a['n'] += 1
        if r[ix['spreading_factor']] is not None: a['sf'][int(r[ix['spreading_factor']])] += 1
        if r[ix['snr_margin_db']] is not None: a['margins'].append(float(r[ix['snr_margin_db']]))
        if r[ix['missed_frames']]: a['missed'] += int(r[ix['missed_frames']])
    params = json.load(open(os.path.join(HERE, 'measured_link_params.json')))
    base = {pseud[k]: v for k, v in params['device_baselines'].items()}
    with open(os.path.join(REL, 'data', 'rwscp_device_summary.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['device', 'n_readings', 'modal_sf', 'mean_margin_db',
                    'baseline_blup_db', 'missed_frames_total'])
        for d in sorted(agg):
            a = agg[d]
            w.writerow([d, a['n'], a['sf'].most_common(1)[0][0] if a['sf'] else '',
                        round(sum(a['margins'])/len(a['margins']), 2) if a['margins'] else '',
                        round(base.get(d, float('nan')), 3), a['missed']])

    params['device_baselines'] = {k: round(v, 4) for k, v in sorted(base.items())}
    json.dump(params, open(os.path.join(REL, 'data', 'measured_link_params.json'), 'w'), indent=2)

    # ---------- full-fleet daily link metrics (added with RWSCP permission) ----------
    # Pseudonyms: analyzed devices keep D01..D59 (consistent with readings CSV);
    # remaining base-app devices continue D60..; Tophane devices get T0001.. .
    fleet_path = os.path.join(ROOT, 'external_data', 'rwscp_daily_link_metrics.json')
    if os.path.exists(fleet_path):
        fleet = json.load(open(fleet_path, encoding='utf-8'))
        fmap = dict(pseud)                                     # existing D01..D59 by dev_eui
        base_rest = sorted(x['eui'] for x in fleet['devices']
                           if x['zone'] == 'base' and x['eui'] not in fmap)
        for i, e in enumerate(base_rest):
            fmap[e] = f'D{len(pseud) + i + 1:02d}'
        toph = sorted(x['eui'] for x in fleet['devices'] if x['zone'] == 'tophane')
        for i, e in enumerate(toph):
            fmap[e] = f'T{i + 1:04d}'
        out_devices = []
        for x in sorted(fleet['devices'], key=lambda x: fmap[x['eui']]):
            out_devices.append({'device': fmap[x['eui']], 'zone': x['zone'],
                                'profile': x['profile'], 'days': x['days']})
        json.dump({'exported': fleet['exported'], 'source': fleet['source'],
                   'fields': fleet['fields'], 'devices': out_devices},
                  open(os.path.join(REL, 'data', 'fleet_daily_link_metrics.json'), 'w'))
        with open(os.path.join(ROOT, 'private_pseudonym_map.csv'), 'w', newline='') as f:
            w = csv.writer(f); w.writerow(['dev_eui', 'pseudonym'])
            for e, p in sorted(fmap.items(), key=lambda kv: kv[1]): w.writerow([e, p])

    # ---------- code ----------
    for s in ['measured_link_model.py', 'pilot_leverage_check.py', 'full_replay.py',
              'ppo_crosscheck.py', 'fig5_freshness_sweep.py', 'loed_replication.py',
              'loed_network_split.py', 'fleet_metrics_analysis.py', 'regen_figs.py',
              'run_full_program.sh', 'run_more_seeds.sh', 'build_release.py']:
        shutil.copy(os.path.join(HERE, s), os.path.join(REL, 'code', s))
    for s in ['isac_system_model.py', 'nsga3_optimizer.py', 'drl_agent.py']:
        shutil.copy(os.path.join(HERE, s), os.path.join(REL, 'code', 'allocator', s))

    # ---------- results ----------
    for s in ['loed_replication_results.json', 'drift_curve.json']:
        if os.path.exists(os.path.join(HERE, s)):
            shutil.copy(os.path.join(HERE, s), os.path.join(REL, 'results', s))
    for s in ['candidate_X.json', 'ppo_crosscheck.json']:
        shutil.copy(os.path.join(HERE, 'replay_cache', s), os.path.join(REL, 'results', s))
    with zipfile.ZipFile(os.path.join(REL, 'results', 'replay_cache.zip'), 'w',
                         zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(os.path.join(HERE, 'replay_cache'))):
            if f.endswith('.npz'):
                z.write(os.path.join(HERE, 'replay_cache', f), f)

    # ---------- figures & docs ----------
    for i, f in enumerate(['fig1_margin_by_sf.png', 'fig2_cancellation_keystone.png',
                           'fig3_idealized_vs_measured.png', 'fig4_holdout_rmse.png',
                           'fig5_freshness_sweep.png']):
        shutil.copy(os.path.join(HERE, f), os.path.join(REL, 'figures', f))
    for f in ['X_preregistration.md', 'RWSCP_measured_link_model_report.md',
              'candidate_X_results.md', 'related_work.md']:
        shutil.copy(os.path.join(HERE, f), os.path.join(REL, 'docs', f))

    # ---------- README + requirements ----------
    open(os.path.join(REL, 'requirements.txt'), 'w').write(
        'numpy\nscipy\npandas\nopenpyxl\nmatplotlib\npymoo==0.6.2\n'
        'torch\nstable-baselines3\ngymnasium\npyarrow\n')
    open(os.path.join(REL, 'README.md'), 'w', encoding='utf-8').write(README)

    # ---------- zip ----------
    out = os.path.join(ROOT, 'release.zip')
    if os.path.exists(out): os.remove(out)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(REL):
            for f in files:
                p = os.path.join(root, f)
                z.write(p, os.path.relpath(p, ROOT))
    print('release/ built;', out, f'({os.path.getsize(out)/1e6:.1f} MB)')

README = """# The Spreading Factor Is Not Channel State — code & derived data release

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
- `data/fleet_daily_link_metrics.json` — daily aggregated link metrics (rx packets,
  mean SNR/RSSI, packets per data rate) for the full 2,033-device fleet, May–July
  2026, harvested from the network server with RWSCP's permission. Devices D01–D59
  are the analyzed meters (same pseudonyms as the readings CSV); D60+ are the
  remaining first-vendor devices; T0001+ are the second-vendor (device-side-ADR)
  expansion. Supports the within-deployment natural experiment and the
  calendar-time drift curve (`code/fleet_metrics_analysis.py`,
  `results/drift_curve.json`).
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
Code: MIT. Derived data: CC BY 4.0.

## Contact
Vullnet Laniku, University of Prishtina — vullnet.laniku@uni-pr.edu
"""

if __name__ == '__main__':
    main()
