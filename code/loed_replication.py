"""
loed_replication.py — external replication of the RWSCP endogeneity keystone on LoED
====================================================================================
LoED (Bhatia et al., DATA'20; Zenodo 10.5281/zenodo.4121430): 9 gateways, dense-urban
London, ~11.3M uplink packets, 8,503 device addresses — an INDEPENDENT deployment,
different city, different network operators, different device mix.

Replication targets (RWSCP reference values):
  - fleet margin ~flat across SF          (eta^2 = 0.026)
  - corr(device modal SF, device baseline) (RWSCP: -0.92)
  - persistent per-device structure        (ICC = 0.61)

Method mirrors the RWSCP pipeline:
  margin = SNR - SNRreq(SF) (EU868 demod floors); multi-gateway receptions deduped to
  best-SNR per transmission (network-server view); within-device SF profile gamma(s)
  from devices observed at >=2 SFs; device baseline b_i = mean(margin - gamma(sf));
  ICC via one-way ANOVA method-of-moments on SF-adjusted margin.

Usage: python loed_replication.py <dir-with-daily-csvs>
"""
import sys, os, glob, json
import numpy as np
import pandas as pd

SNR_REQ = {7: -7.5, 8: -10.0, 9: -12.5, 10: -15.0, 11: -17.5, 12: -20.0}
MIN_READINGS = 30          # device inclusion: enough frames to estimate a baseline
MIN_SPAN_DAYS = 7          # and enough time span for it to count as persistent
UPLINK_MTYPES = {'010', '100'}   # unconfirmed / confirmed data up (MHDR bit strings)

def load(dirpath):
    frames = []
    files = sorted(glob.glob(os.path.join(dirpath, "*.csv")))
    assert files, f"no CSVs under {dirpath}"
    for i, f in enumerate(files):
        try:
            df = pd.read_csv(f, usecols=['time', 'device_address', 'gateway', 'crc_status',
                                         'spreading_factor', 'snr', 'mtype', 'fcnt'],
                             dtype={'device_address': str, 'mtype': str},
                             on_bad_lines='skip')
        except ValueError:
            continue                      # file missing expected columns
        df = df[df['mtype'].isin(UPLINK_MTYPES) & (df['crc_status'] == 1)]
        df = df.drop(columns=['mtype', 'crc_status'])
        df = df[df['device_address'].notna() & (df['device_address'] != '-1')]
        df = df[df['spreading_factor'].isin(SNR_REQ) & df['snr'].notna()]
        if len(df):
            frames.append(df)
        if (i + 1) % 100 == 0:
            print(f"  ...{i+1}/{len(files)} files", flush=True)
    d = pd.concat(frames, ignore_index=True)
    d['time'] = pd.to_datetime(d['time'], format='mixed', utc=True, errors='coerce')
    d = d[d['time'].notna()]
    return d

def dedupe_best_reception(d):
    """Same transmission heard by several gateways -> keep max-SNR copy
    (network-server view, comparable to RWSCP's ChirpStack export)."""
    d['tkey'] = d['time'].dt.floor('10s')
    d = d.sort_values('snr').drop_duplicates(
        subset=['device_address', 'fcnt', 'tkey'], keep='last')
    d = d.sort_values('time')
    return d.drop(columns='tkey')

def main(dirpath):
    print("loading...", flush=True)
    d = load(dirpath)
    print(f"uplinks with valid SNR/SF: {len(d):,} from {d['device_address'].nunique():,} addresses")
    d = dedupe_best_reception(d)
    print(f"after best-reception dedupe: {len(d):,}")
    d['margin'] = d['snr'] - d['spreading_factor'].map(SNR_REQ)

    g = d.groupby('device_address')
    span = (g['time'].max() - g['time'].min()).dt.total_seconds() / 86400
    n = g.size()
    keep = n.index[(n >= MIN_READINGS) & (span >= MIN_SPAN_DAYS)]
    d = d[d['device_address'].isin(keep)]
    print(f"devices kept (>= {MIN_READINGS} frames, >= {MIN_SPAN_DAYS} d span): "
          f"{d['device_address'].nunique():,}  ({len(d):,} frames)")

    # (a) fleet margin by SF + eta^2 with device-cluster bootstrap CI
    by_sf = d.groupby('spreading_factor')['margin'].agg(['mean', 'std', 'count'])
    print("\nfleet margin by SF:\n", by_sf.round(2))
    grand = d['margin'].mean()
    ss_between = sum(r['count'] * (r['mean'] - grand) ** 2 for _, r in by_sf.iterrows())
    ss_total = ((d['margin'] - grand) ** 2).sum()
    eta2 = ss_between / ss_total
    rng = np.random.RandomState(0); devs = d['device_address'].unique(); boots = []
    dev_groups = {k: v for k, v in d.groupby('device_address')}
    for _ in range(200):
        bd = pd.concat([dev_groups[k] for k in rng.choice(devs, len(devs))])
        bs = bd.groupby('spreading_factor')['margin'].agg(['mean', 'count'])
        gm = bd['margin'].mean()
        boots.append(sum(r['count'] * (r['mean'] - gm) ** 2 for _, r in bs.iterrows())
                     / ((bd['margin'] - gm) ** 2).sum())
    print(f"\neta^2(SF) = {eta2:.4f}  (device-bootstrap 95% CI "
          f"{np.percentile(boots, 2.5):.4f}-{np.percentile(boots, 97.5):.4f})   [RWSCP: 0.026]")

    # (b) within-device SF profile from multi-SF devices, then device baselines
    multi = d.groupby('device_address')['spreading_factor'].nunique()
    multi_devs = multi.index[multi >= 2]
    dm = d[d['device_address'].isin(multi_devs)].copy()
    dm['dev_mean'] = dm.groupby('device_address')['margin'].transform('mean')
    dm['centered'] = dm['margin'] - dm['dev_mean']
    gamma = dm.groupby('spreading_factor')['centered'].mean()
    gamma = gamma - gamma.get(7, gamma.iloc[0])          # reference SF7
    print(f"\nwithin-device SF profile gamma(s) (from {len(multi_devs):,} multi-SF devices, ref SF7):")
    print(gamma.round(2).to_string())

    d['adj'] = d['margin'] - d['spreading_factor'].map(gamma).fillna(0.0)
    base = d.groupby('device_address')['adj'].mean()
    modal_sf = d.groupby('device_address')['spreading_factor'].agg(lambda s: s.mode().iloc[0])
    r_keystone = np.corrcoef(modal_sf.loc[base.index], base)[0, 1]
    print(f"\ncorr(modal SF, device baseline) = {r_keystone:+.3f}   [RWSCP: -0.92]")

    # (c) ICC on SF-adjusted margin (one-way ANOVA method of moments)
    grp = d.groupby('device_address')['adj']
    k = grp.size(); m = grp.mean(); gm = d['adj'].mean()
    ssb = (k * (m - gm) ** 2).sum(); ssw = ((d['adj'] - m.loc[d['device_address']].values) ** 2).sum()
    df_b = len(k) - 1; df_w = len(d) - len(k)
    msb, msw = ssb / df_b, ssw / df_w
    k0 = (len(d) - (k ** 2).sum() / len(d)) / df_b
    icc = max((msb - msw) / (msb + (k0 - 1) * msw), 0.0)
    print(f"ICC (persistent per-device fraction) = {icc:.3f}   [RWSCP: 0.61]")
    print(f"sigma_dev = {np.sqrt(max(msb - msw, 0) / k0):.2f} dB, residual sd = {np.sqrt(msw):.2f} dB")

    out = dict(n_frames=int(len(d)), n_devices=int(d['device_address'].nunique()),
               eta2=float(eta2), eta2_ci=[float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))],
               margin_by_sf={int(i): [round(r['mean'], 2), int(r['count'])] for i, r in by_sf.iterrows()},
               gamma={int(i): round(v, 2) for i, v in gamma.items()},
               corr_modalSF_baseline=float(r_keystone), icc=float(icc))
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
              'loed_replication_results.json'), 'w') as f:
        json.dump(out, f, indent=2)
    print("\nsaved loed_replication_results.json")

if __name__ == '__main__':
    main(sys.argv[1])
