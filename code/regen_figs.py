"""
regen_figs.py — publication-clean regeneration of figs 1-4 (+ restyled fig 5 is in
fig5_freshness_sweep.py). IEEE column style: no in-figure titles (captions do that),
large fonts for column-width shrink, concise legends, bold markers.
"""
import json, os, collections
import numpy as np
import openpyxl
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
P = json.load(open(os.path.join(HERE, 'measured_link_params.json')))
plt.rcParams.update({'font.size': 15, 'axes.labelsize': 16, 'xtick.labelsize': 14,
                     'ytick.labelsize': 14, 'legend.fontsize': 13, 'axes.grid': True,
                     'grid.alpha': 0.25, 'figure.dpi': 200})
BLUE, RED, DARK = '#2b6a99', '#c0392b', '#222222'

# ---- load readings (margins per SF, per device) ----
wb = openpyxl.load_workbook(os.path.join(HERE, '..', 'RWSCP_Water_Meters_Export.xlsx'), read_only=True)
ws = wb['All Readings']; rows = ws.iter_rows(values_only=True)
hdr = next(rows); ix = {c: i for i, c in enumerate(hdr)}
by_sf = collections.defaultdict(list); dev = collections.defaultdict(list)
for r in rows:
    if r[ix['spreading_factor']] is not None and r[ix['snr_margin_db']] is not None:
        s, m = int(r[ix['spreading_factor']]), float(r[ix['snr_margin_db']])
        by_sf[s].append(m); dev[str(r[ix['dev_eui']]).lower()].append((s, m))
SFS = sorted(by_sf)

# ---- fig1: flat margin by SF (box + jitter) ----
fig, ax = plt.subplots(figsize=(7.0, 4.4))
data = [by_sf[s] for s in SFS]
bp = ax.boxplot(data, positions=SFS, widths=0.55, showfliers=False, patch_artist=True,
                boxprops=dict(facecolor='#dce8f2', color=BLUE, linewidth=1.8),
                medianprops=dict(color=RED, linewidth=2.4),
                whiskerprops=dict(color=BLUE, linewidth=1.8), capprops=dict(color=BLUE, linewidth=1.8))
rng = np.random.RandomState(0)
for s in SFS:
    ax.scatter(s + rng.uniform(-0.16, 0.16, len(by_sf[s])), by_sf[s], s=16, alpha=0.35, color=BLUE, zorder=1)
gm = np.mean([m for v in data for m in v])
ax.axhline(gm, color=DARK, ls='--', lw=2, label=f'fleet mean ({gm:.1f} dB)')
ax.set_xlabel('Spreading factor'); ax.set_ylabel('SNR margin (dB)')
ax.text(0.02, 0.965, f'$\\eta^2$ = {P["eta2_sf_only"]:.3f}', transform=ax.transAxes,
        fontsize=16, va='top', bbox=dict(fc='white', ec='0.6'))
ax.legend(loc='upper right', framealpha=0.95)
fig.tight_layout(); fig.savefig(os.path.join(HERE, 'fig1_margin_by_sf.png')); plt.close(fig)

# ---- fig2: the keystone cancellation ----
gain = [P['sf_fixed_effect_vs_sf7'][str(s)] for s in SFS]
base = [P['baseline_of_devices_at_sf'][str(s)] for s in SFS]
obs  = [P['per_sf'][str(s)]['mean_margin'] if isinstance(P['per_sf'][str(s)], dict)
        and 'mean_margin' in P['per_sf'][str(s)] else np.mean(by_sf[s]) for s in SFS]
fig, ax = plt.subplots(figsize=(7.0, 4.6))
ax.plot(SFS, gain, 'o-', color=BLUE, lw=3, ms=10, label='within-device SF gain')
ax.plot(SFS, base, 's-', color=RED, lw=3, ms=10, label='baseline of devices at SF')
ax.plot(SFS, obs, '^--', color=DARK, lw=2.6, ms=10, label='observed fleet margin')
ax.fill_between(SFS, gain, base, color='0.9', zorder=0)
ax.axhline(0, color='0.5', lw=1)
ax.annotate('these two cancel', xy=(10.4, 3.4), fontsize=15, color='0.35', ha='center')
ax.annotate('corr(SF, baseline) = $-$0.92', xy=(0.35, 0.86), xycoords='axes fraction',
            fontsize=15, bbox=dict(fc='white', ec='0.6'))
ax.set_xlabel('Spreading factor'); ax.set_ylabel('contribution to SNR margin (dB)')
ax.legend(loc='lower left', framealpha=0.95)
fig.tight_layout(); fig.savefig(os.path.join(HERE, 'fig2_cancellation_keystone.png')); plt.close(fig)

# ---- fig3: idealized point vs measured per-device spread ----
ideal = [P['idealized_margin_db'][str(s)] for s in SFS]
fig, ax = plt.subplots(figsize=(7.0, 4.4))
rng = np.random.RandomState(1)
seen = False
for d, lst in dev.items():
    cnt = collections.Counter(s for s, m in lst)
    ms = cnt.most_common(1)[0][0]
    mm = np.mean([m for s, m in lst if s == ms])
    ax.scatter(ms + rng.uniform(-0.18, 0.18), mm, s=90, alpha=0.6, color=BLUE,
               edgecolor='white', linewidth=0.8, zorder=2,
               label='measured per-device margin' if not seen else None); seen = True
ax.plot(SFS, ideal, 's--', color=RED, lw=2.6, ms=12, zorder=3, label='idealized SF$\\to$margin map')
ax.set_xlabel('Spreading factor'); ax.set_ylabel('SNR margin (dB)')
ax.legend(loc='upper left', framealpha=0.95)
fig.tight_layout(); fig.savefig(os.path.join(HERE, 'fig3_idealized_vs_measured.png')); plt.close(fig)

# ---- fig4: hold-out RMSE (protocol-explicit; values from holdout recompute 2026-07-19) ----
names = ['SF-only map\n(new devices)', 'grand mean\n(new devices)', 'device baseline\n(fresh)', 'device baseline\n(stale)']
vals = [3.94, 3.92, 3.83, 3.96]
fig, ax = plt.subplots(figsize=(6.8, 4.2))
bars = ax.bar(names, vals, color=[RED, '0.55', BLUE, '#9db9cd'], width=0.62)
bars[3].set_hatch('//'); bars[3].set_edgecolor('white')
for b, v in zip(bars, vals):
    ax.text(b.get_x() + b.get_width()/2, v + 0.03, f'{v:.2f}', ha='center', fontsize=15)
ax.set_ylabel('hold-out RMSE (dB)'); ax.set_ylim(3.0, 4.25)
fig.tight_layout(); fig.savefig(os.path.join(HERE, 'fig4_holdout_rmse.png')); plt.close(fig)
print('figs 1-4 regenerated')
