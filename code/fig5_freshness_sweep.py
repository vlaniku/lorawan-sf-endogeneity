"""fig5: energy recovery vs estimate freshness r (10 seeds, both operating points)."""
import json, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

d = json.load(open('replay_cache/candidate_X.json'))
RS = [0.0, 0.2, 0.46, 0.7, 0.9]

fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), sharey=True)
for ax, rule, label in [(axes[0], 'energy', 'min-energy operating point'),
                        (axes[1], 'drl', 'DRL-selected operating point')]:
    data = [np.array(d['freshness_sweep'][f'indep/{rule}/r={r:.2f}']['recovered_of_blind_per_seed'])
            for r in RS]
    aware = np.array(d['third_leg'][f'indep/{rule}']['energy_recovered_frac_per_seed'])
    # aware = perfect knowledge ceiling at r=1
    data.append(aware); xs = RS + [1.0]
    for x, a in zip(xs, data):
        ax.scatter(np.full(len(a), x), 100*a, s=18, alpha=0.45, color='#4878a8', zorder=2)
    med = [100*np.median(a) for a in data]
    mean = [100*np.mean(a) for a in data]
    ax.plot(xs, med, 'o-', color='#1f4e79', lw=2, ms=6, label='median (10 seeds)', zorder=3)
    ax.plot(xs, mean, 's--', color='#c05555', lw=1.5, ms=5, label='mean', zorder=3)
    ax.axhline(0, color='0.4', lw=0.8)
    ax.axvline(0.46, color='0.6', lw=0.8, ls=':')
    ax.text(0.46, ax.get_ylim()[0], '', fontsize=8)
    ax.set_xlabel('estimate freshness  r = corr(estimated offset, true offset)')
    ax.set_title(label, fontsize=11)
    ax.set_xticks(xs); ax.grid(alpha=0.25)
axes[0].set_ylabel('energy recovered vs blind allocation (%)')
axes[0].annotate('RWSCP drift over 32 days\n(r = 0.46)', xy=(0.46, -95), fontsize=8.5,
                 ha='center', color='0.35')
axes[0].set_ylim(-160, 80)
axes[0].legend(fontsize=9, loc='lower right')
fig.suptitle('Offset-aware allocation under the true channel: recovery is conditional on estimate freshness',
             fontsize=12)
fig.tight_layout()
fig.savefig('fig5_freshness_sweep.png', dpi=200)
print('saved fig5_freshness_sweep.png')

# supporting stats
from scipy.stats import wilcoxon
for rule in ['energy', 'drl']:
    print(f'--- {rule}')
    aware = np.array(d['third_leg'][f'indep/{rule}']['energy_recovered_frac_per_seed'])
    print(f'aware r=1: mean {aware.mean():+.3f} median {np.median(aware):+.3f} '
          f'pos {int((aware>0).sum())}/10 wilcoxon p={wilcoxon(aware).pvalue:.3f}')
    for r in RS:
        a = np.array(d['freshness_sweep'][f'indep/{rule}/r={r:.2f}']['recovered_of_blind_per_seed'])
        print(f'r={r:.2f}: mean {a.mean():+.3f} median {np.median(a):+.3f} '
              f'pos {int((a>0).sum())}/10 wilcoxon p={wilcoxon(a).pvalue:.3f}')
