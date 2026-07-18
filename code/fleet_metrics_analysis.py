"""
fleet_metrics_analysis.py — first-look analysis of the full-fleet daily link metrics
====================================================================================
Input: external_data/rwscp_daily_link_metrics.json (harvested 2026-07-18 from the
ChirpStack console API; daily aggregates per device: rx packets, mean SNR, mean RSSI,
packets per DR). Two products:

1. REGIME COMPARISON (natural experiment): base app (Apator, server-ADR with adr=true)
   vs Tophane app (Baylan, observed adr=false / device-side). Predictions from the
   paper's mechanism: the ADR-managed fleet shows SF spread + margin regulation;
   the device-managed fleet parks at SF12.
2. CALENDAR-TIME DRIFT CURVE for the analyzed 59 Apator meters: per-device 14-day
   mean SNR, then across-device correlation between time bins at increasing lags.
   This turns the export's single-lag r=0.46 (32 d) into r(lag) in days — the
   freshness axis of fig5 in calendar units.
"""
import json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    HERE, '..', 'external_data', 'rwscp_daily_link_metrics.json')
DR_TO_SF = {0: 12, 1: 11, 2: 10, 3: 9, 4: 8, 5: 7}
SNR_REQ = {7: -7.5, 8: -10.0, 9: -12.5, 10: -15.0, 11: -17.5, 12: -20.0}

d = json.load(open(DATA, encoding='utf-8'))
devs = d['devices']

def dominant_sf(drs):
    if not drs: return None
    dr = int(max(drs.items(), key=lambda kv: kv[1])[0])
    return DR_TO_SF.get(dr)

print('=== 1. regime comparison (devices with >=10 active days) ===')
for zone in ['base', 'tophane']:
    zd = [x for x in devs if x['zone'] == zone and len(x['days']) >= 10]
    n_sf, margins, sf_modes, multi_dr = [], [], [], 0
    for x in zd:
        sfs, m = set(), []
        for day in x['days']:
            ts, rx, snr, rssi, drs = day
            sf = dominant_sf(drs)
            if sf: sfs.add(sf); m.append(snr - SNR_REQ[sf])
        if len(sfs) >= 2: multi_dr += 1
        if sfs: sf_modes.append(max(sfs, key=lambda s: sum(1 for day in x['days'] if dominant_sf(day[4]) == s)))
        if m: margins.append(np.mean(m))
        n_sf.append(len(sfs))
    from collections import Counter
    print(f'{zone:8s}: n={len(zd):4d}  SF-mobile devices (>=2 SFs): {100*multi_dr/max(len(zd),1):.0f}%  '
          f'mean margin {np.mean(margins):+.1f} dB (sd {np.std(margins):.1f})')
    print(f'          modal-SF distribution: {dict(sorted(Counter(sf_modes).items()))}')

print()
print('=== 2. calendar-time drift curve (base-app Apator devices) ===')
BIN = 14 * 86400
zd = [x for x in devs if x['zone'] == 'base' and len(x['days']) >= 20]
print(f'devices in analysis: {len(zd)}')
t0 = min(day[0] for x in zd for day in x['days'])
series = {}
for x in zd:
    bins = {}
    for ts, rx, snr, rssi, drs in x['days']:
        sf = dominant_sf(drs)
        if sf is None: continue
        b = int((ts - t0) // BIN)
        bins.setdefault(b, []).append(snr - SNR_REQ[sf])
    series[x['eui']] = {b: np.mean(v) for b, v in bins.items() if len(v) >= 3}
n_bins = max(b for s in series.values() for b in s) + 1 if series else 0
print(f'14-day bins spanning the retention window: {n_bins}')
lags = [1, 2, 3, 4, 6, 8, 12, 16, 20]
print(f"{'lag (days)':>10s} {'mean r':>7s} {'n pairs':>8s} {'n bin-pairs':>11s}")
for L in lags:
    rs, total_pairs = [], 0
    for t in range(n_bins - L):
        a, b = [], []
        for s in series.values():
            if t in s and t + L in s: a.append(s[t]); b.append(s[t + L])
        if len(a) >= 15:
            rs.append(np.corrcoef(a, b)[0, 1]); total_pairs += len(a)
    if rs:
        print(f'{L*14:>10d} {np.mean(rs):>+7.2f} {total_pairs:>8d} {len(rs):>11d}')

out = {'lags_days': [], 'r': []}
for L in lags:
    rs = []
    for t in range(n_bins - L):
        a, b = [], []
        for s in series.values():
            if t in s and t + L in s: a.append(s[t]); b.append(s[t + L])
        if len(a) >= 15: rs.append(float(np.corrcoef(a, b)[0, 1]))
    if rs: out['lags_days'].append(L * 14); out['r'].append(round(float(np.mean(rs)), 3))
json.dump(out, open(os.path.join(HERE, 'drift_curve.json'), 'w'), indent=2)
print('\nsaved drift_curve.json')
