"""fig5: energy recovery vs estimate freshness r (10 seeds, both operating points).
Publication-clean restyle: no in-figure titles (A/B panel labels), large fonts/markers."""
import json, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.rcParams.update({'font.size': 15, 'axes.labelsize': 16, 'xtick.labelsize': 14,
                     'ytick.labelsize': 14, 'legend.fontsize': 13, 'axes.grid': True,
                     'grid.alpha': 0.25, 'figure.dpi': 200})
d = json.load(open('replay_cache/candidate_X.json'))
RS = [0.0, 0.2, 0.46, 0.7, 0.9]

fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.8), sharey=True)
for ax, rule, label in [(axes[0], 'energy', 'A'), (axes[1], 'drl', 'B')]:
    data = [np.array(d['freshness_sweep'][f'indep/{rule}/r={r:.2f}']['recovered_of_blind_per_seed'])
            for r in RS]
    aware = np.array(d['third_leg'][f'indep/{rule}']['energy_recovered_frac_per_seed'])
    data.append(aware); xs = RS + [1.0]
    for x, a in zip(xs, data):
        ax.scatter(np.full(len(a), x), 100*a, s=48, alpha=0.5, color='#4878a8',
                   edgecolor='white', linewidth=0.6, zorder=2)
    med = [100*np.median(a) for a in data]
    mean = [100*np.mean(a) for a in data]
    ax.plot(xs, med, 'o-', color='#1f4e79', lw=3, ms=10, label='median', zorder=3)
    ax.plot(xs, mean, 's--', color='#c0392b', lw=2.4, ms=9, label='mean', zorder=3)
    ax.axhline(0, color='0.4', lw=1)
    ax.axvline(0.46, color='0.55', lw=1.4, ls=':')
    ax.set_xlabel('estimate freshness $r$')
    ax.set_xticks(xs); ax.set_xticklabels(['0', '0.2', '0.46', '0.7', '0.9', '1'])
    ax.set_yticks([-150, -100, -50, 0, 50])
    ax.text(0.03, 0.955, label, transform=ax.transAxes, fontsize=20, fontweight='bold', va='top')
axes[0].set_ylabel('energy recovered vs blind (%)')
axes[0].annotate('RWSCP 32-day drift\n($r=0.46$)', xy=(0.46, -60), xytext=(0.13, -110),
                 fontsize=14, ha='center',
                 arrowprops=dict(arrowstyle='->', color='0.35', lw=1.6))
axes[0].set_ylim(-165, 80)
axes[0].legend(loc='lower right', framealpha=0.95)
fig.tight_layout()
fig.savefig('fig5_freshness_sweep.png')
print('saved fig5_freshness_sweep.png')
