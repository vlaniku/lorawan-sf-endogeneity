"""
loed_network_split.py — LoED keystone stats split by DevAddr network prefix
===========================================================================
Follow-up to loed_replication.py. DevAddr embeds a network identifier in its
leading bits, so the first address byte approximates operator membership
(0x26/0x27 = The Things Network). Tests whether the RWSCP cancellation
signature appears in any single-operator subpopulation, as Proposition 1
predicts it should only under converged closed-loop ADR.

Reads the cached parquet written by the first run if present.

RESULT (2026-07-17, recorded):
  fleet ICC = 0.587  [RWSCP 0.61]  -> heterogeneity REPLICATES
  fleet corr(modal SF, baseline) = +0.14, eta2 = 0.18 -> cancellation DOES NOT
  per-network: 0x00 corr +0.16 | 0x01 +0.08 | 0x26 (TTN) +0.06 | 0x27 +0.05
               0x04 (87% multi-SF, most ADR-like): corr = -0.10, eta2 = 0.017
               (flattest margin, only negative corr - directionally consistent, weak)
  Interpretation: persistent per-device structure is general; the proxy-collapse
  signature is conditional on a single converged controller managing the fleet
  (as in RWSCP), and is diluted/absent in mixed multi-operator gateway captures
  (static over-provisioned SF12 fleets at 16-19 dB margin; DevAddr collisions).
"""
import os
import numpy as np, pandas as pd
import loed_replication as L

PARQUET = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       '..', 'external_data', 'loed_filtered.parquet')

def main():
    if os.path.exists(PARQUET):
        d = pd.read_parquet(PARQUET)
    else:
        d = L.load('../external_data/loed/LoED_LoRaWAN_at_edge_dataset')
        d = L.dedupe_best_reception(d)
        d['margin'] = d['snr'] - d['spreading_factor'].map(L.SNR_REQ)
        g = d.groupby('device_address')
        span = (g['time'].max() - g['time'].min()).dt.total_seconds() / 86400
        n = g.size()
        d = d[d['device_address'].isin(n.index[(n >= L.MIN_READINGS) & (span >= L.MIN_SPAN_DAYS)])].copy()
        d.to_parquet(PARQUET)
    d['net'] = d['device_address'].str[:2]
    nd = d.groupby('net')['device_address'].nunique().sort_values(ascending=False)
    print('top network prefixes:\n', nd.head(8).to_string())

    multi = d.groupby('device_address')['spreading_factor'].nunique()
    dm = d[d['device_address'].isin(multi.index[multi >= 2])].copy()
    dm['c'] = dm['margin'] - dm.groupby('device_address')['margin'].transform('mean')
    gamma = dm.groupby('spreading_factor')['c'].mean(); gamma = gamma - gamma[7.0]
    d['adj'] = d['margin'] - d['spreading_factor'].map(gamma)

    for net in nd.head(6).index:
        s = d[d['net'] == net]
        if s['device_address'].nunique() < 40:
            continue
        base = s.groupby('device_address')['adj'].mean()
        msf = s.groupby('device_address')['spreading_factor'].agg(lambda x: x.mode().iloc[0])
        sw = s.groupby('device_address')['spreading_factor'].nunique()
        r = np.corrcoef(msf.loc[base.index], base)[0, 1] if msf.loc[base.index].std() > 0 else float('nan')
        bysf = s.groupby('spreading_factor')['margin'].agg(['mean', 'count'])
        grand = s['margin'].mean()
        eta2 = sum(row['count'] * (row['mean'] - grand) ** 2
                   for _, row in bysf.iterrows()) / (((s['margin'] - grand) ** 2).sum())
        prof = ' '.join(f'SF{int(i)}:{row["mean"]:.1f}' for i, row in bysf.iterrows() if row['count'] > 500)
        print(f'net 0x{net}: dev={s["device_address"].nunique():4d} frames={len(s):8,} '
              f'multiSF={100 * (sw >= 2).mean():.0f}%  corr={r:+.2f} eta2={eta2:.3f}  {prof}')

if __name__ == '__main__':
    main()
