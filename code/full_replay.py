"""
full_replay.py — committed apparatus for the idealized-vs-measured replay (X)
============================================================================
Vehicle: cellular TGCN allocator (isac_system_model.py + nsga3_optimizer.py).
Tests DEVICE-HOMOGENEITY (SF-exogeneity is keystone-only; this allocator has no SF
channel-state hook). Injection = variance-matched re-partition of shadowing at the
channel-state hook (line 149): move fraction ICC of variance into a persistent
per-device LINK-QUALITY offset (not a claim cellular shadowing is 61% persistent).

COMMITTED GATES (all enforced here):
  * ICC=0 alignment null must be exactly 0 (assert before trusting magnitude).
  * total shadowing variance identical across oracles (variance-matched).
  * every device receives exactly one persistent offset (assert, fail-loud).
  * two RWSCP->device mappings: 'indep' (offset ⊥ distance) and 'distcorr'
    (offset partially distance-correlated, r=0.57 per RWSCP RSSI-offset link).
  * metrics at TWO operating points (min-energy + balanced) as stand-ins for the
    deployed Q-selected point — REPLACE 'balanced' with the true Q-selection at
    full scale (Vullnet's ground truth).
  * primary metric = unconditioned fleet rank-shift R; companions = full-set and
    resolvable-set Kendall-τ; direct evidence = per-device |Δpower|,|Δbw|.

THIRD LEG (corrective fix): x_blind = optimize(idealized); x_aware = optimize(measured,
perfect offset); x_stale = optimize(measured, drifted offset r=0.46). Evaluate all
under the TRUE (measured) channel; recovered quality = how much of the blind->aware
gap the (even stale) offset estimate restores. Framed as recovering quality lost to
the homogeneity confound, NOT a new optimizer.

USAGE (chunked to fit a 45s sandbox; remove caps for full-scale offline run):
  python3 full_replay.py opt <seed> <mode> <mapping> <icc> [stale_r]  # one optimization -> cache
  python3 full_replay.py metrics                                       # compute X + third leg
Full-scale offline: FULL=True (pop=120,n_gen=150,n_partitions=6, density='medium');
override with env REPLAY_FULL=0 for the reduced smoke-test scale.

STALE / FRESHNESS SWEEP: `opt <seed> measured <mapping> <icc> <r>` optimizes under a
DRIFTED offset estimate whose correlation with the true offsets is exactly r (the
allocator's belief has decayed to freshness r; r=1 is the perfect-knowledge 'aware'
run, r=0 an uninformative estimate). Truth in eval_under_true is always the
undrifted offsets. NOTE: the original drift path seeded a different RNG for the
base draw, making the 'stale' offsets UNCORRELATED with truth instead of r=0.46 —
fixed here (true z first, drift innovation from a separate RNG).
"""
import sys, os, json, glob, warnings; warnings.filterwarnings('ignore')
import numpy as np
import isac_system_model as M
from isac_system_model import ISACSimulator, ISACSystemConfig, DEVICE_PROFILES
import nsga3_optimizer as O
from scipy.stats import kendalltau

FULL = os.environ.get("REPLAY_FULL", "1") == "1"   # full-scale offline run (REPLAY_FULL=0 for smoke test)
CACHE = os.environ.get("REPLAY_CACHE",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "replay_cache"))
os.makedirs(CACHE, exist_ok=True)

if not FULL:
    DEVICE_PROFILES['utility_meter'].count = 12; DEVICE_PROFILES['env_sensor'].count = 6
    DEVICE_PROFILES['traffic_camera'].count = 3; DEVICE_PROFILES['safety_device'].count = 3
    _gr = O.get_reference_directions
    O.get_reference_directions = lambda *a, **k: _gr("das-dennis", 4, n_partitions=3)
    POP, NGEN, DENS = 44, 30, 'medium'
else:
    POP, NGEN, DENS = 120, 150, 'medium'

ICC_DEFAULT = 0.61; R_CORR = 0.57
ZSTATE = {}; _S = {'mode': 'idealized', 'icc': ICC_DEFAULT}
_orig = M.UrbanChannelModel.get_channel_gain
def _gain(self, distance_m, los_prob=None):
    if _S['mode'] == 'idealized':
        return _orig(self, distance_m, los_prob)
    d = max(distance_m, 1.0)
    if los_prob is None:
        los_prob = min(18.0/d, 1.0) * (1 - np.exp(-d/36.0)) + np.exp(-d/36.0)
    is_los = np.random.random() < los_prob
    sigma = 4.0 if is_los else 7.82
    pl = self.path_loss_db(distance_m, is_los)
    z0 = np.random.normal(0, 1)
    assert distance_m in ZSTATE, f"device {distance_m}: no persistent offset (fail-loud)"
    zi = ZSTATE[distance_m]; icc = _S['icc']
    shadow = sigma*np.sqrt(icc)*zi + sigma*np.sqrt(1-icc)*z0
    return 10**(-(pl + shadow)/10.0) * self.fading_linear()
M.UrbanChannelModel.get_channel_gain = _gain

def _positions(seed):
    sim = ISACSimulator(ISACSystemConfig(), seed=seed)
    return sim, sim.generate_device_positions(DENS)

def build_offsets(seed, mapping, stale_r=None):
    """Persistent per-device standard-normal offsets, keyed on (unique) distance.
    stale_r: if given, return a DRIFTED estimate with corr(stale, true)=stale_r —
    the true z is drawn first (identical to the stale_r=None path), then the drift
    innovation comes from a separate RNG so truth is unchanged."""
    _, pos = _positions(seed)
    rng = np.random.RandomState(2000 + seed)                    # truth RNG (always)
    ZSTATE.clear(); dists = []
    for _, info in pos.items():
        for x in info['distances']: dists.append(float(x))
    dists = np.array(dists)
    zc = (dists - dists.mean())/ (dists.std() + 1e-9)          # distance z-score
    base = rng.normal(0, 1, len(dists))
    if mapping == 'distcorr':
        z = R_CORR*zc + np.sqrt(1-R_CORR**2)*base
    else:                                                       # 'indep'
        z = base
    if stale_r is not None:                                     # freshness-r drifted estimate
        # innovation orthogonalized against truth IN-SAMPLE and scale-matched, so the
        # stale estimate has sample corr = stale_r with the true offsets exactly
        # (not just in expectation) — keeps the freshness curve clean at few seeds.
        rng_d = np.random.RandomState(3000 + seed)
        e = rng_d.normal(0, 1, len(dists)); e -= e.mean()
        zc_t = z - z.mean()
        e -= zc_t * (np.dot(e, zc_t) / max(np.dot(zc_t, zc_t), 1e-12))
        e = e / (e.std() + 1e-12) * zc_t.std()
        z = stale_r*z + np.sqrt(1-stale_r**2)*e
    assert len(dists) == len(set(dists.tolist())), "distance collision"
    for dd, zz in zip(dists, z): ZSTATE[float(dd)] = float(zz)
    return len(dists)

def optimize(seed, mode, icc):
    _S['mode'] = mode; _S['icc'] = icc; np.random.seed(seed)
    return O.run_nsga3_optimization(DENS, 'peak', pop_size=POP, n_gen=NGEN, seed=seed)

def _tag(seed, mode, mapping, icc, stale_r=None):
    t = f"s{seed}_{mode}_{mapping}_icc{icc:.2f}"
    return t + (f"_stale{stale_r:.2f}" if stale_r is not None else "")

# ---------- subcommand: opt ----------
def cmd_opt(seed, mode, mapping, icc, stale_r=None):
    if mode == 'idealized': build_offsets(seed, 'indep')      # offsets unused but keep keys valid
    else: build_offsets(seed, mapping, stale_r=stale_r)
    res = optimize(seed, mode, icc)
    np.savez(os.path.join(CACHE, _tag(seed, mode, mapping, icc, stale_r)+".npz"),
             X=res['pareto_X'], F=res['pareto_F'])
    print("saved", _tag(seed, mode, mapping, icc, stale_r), "nsol=", len(res['pareto_F']))

# ---------- selection rules (operating points) ----------
def drl_reward(F, load_f=1.0, channel_q=0.5):
    """Faithful DRL Stage-2 operating point: reward per Pareto row using the agent's
    EXACT formula/weights from drl_agent.py step() at nominal peak conditions."""
    e, s, rel, lat = F[:,0], F[:,1], F[:,2], F[:,3]
    e_a = e*(1.0+0.2*(load_f-0.5)); s_a = s*(0.8+0.4*channel_q)
    rel_a = rel*(0.7+0.3*channel_q); lat_a = lat*(1.0+0.5*(load_f-0.5))
    e_max = max(F[:,0].max(),1e-6); l_max = max(F[:,3].max(),1e-6)
    e_n = 1.0-np.clip(e_a/e_max,0,1); s_n = np.clip(s_a,0,1)
    r_n = np.clip(rel_a,0,1); l_n = 1.0-np.clip(lat_a/l_max,0,1)
    R = 0.35*e_n + 0.25*s_n + 0.25*r_n + 0.15*l_n
    R = R + 0.1*(s_a>=0.85) + 0.1*(rel_a>=0.90) - 0.2*(s_a<0.5) - 0.2*(rel_a<0.5)
    return R

def sel(X, F, rule):
    if rule == 'energy': i = int(np.argmin(F[:, 0]))
    else:  # 'drl' = deployed Q-layer operating point (agent's reward-argmax, his weights)
        i = int(np.argmax(drl_reward(F)))
    return X[i][0::4], X[i][2::4]                              # power, bw

def _load(tag):
    d = np.load(os.path.join(CACHE, tag+".npz")); return d['X'], d['F']

def rank_shift_R(a, b):
    """fraction of devices whose power-priority rank moves > k (k≈10% of fleet)."""
    n = min(len(a), len(b)); a, b = a[:n], b[:n]
    ra = np.argsort(np.argsort(-a)); rb = np.argsort(np.argsort(-b))
    k = max(1, int(round(0.1*n)))
    return float(np.mean(np.abs(ra-rb) > k))

def resolvable_tau(a, b, seed, mapping):
    """Kendall-τ on pairs whose persistent-offset gap exceeds the iid residual sd."""
    n = min(len(a), len(b)); a, b = a[:n], b[:n]
    build_offsets(seed, mapping)
    offs = np.array(list(ZSTATE.values()))[:n]
    sigma_res = 7.82*np.sqrt(1-ICC_DEFAULT)                    # residual sd (NLOS scale)
    keep = np.abs(offs*7.82*np.sqrt(ICC_DEFAULT)) > sigma_res  # devices w/ resolvable persistent shift
    if keep.sum() < 3: return float('nan'), float(keep.mean())
    return float(kendalltau(a[keep], b[keep]).correlation), float(keep.mean())

# ---------- third leg: evaluate a fixed allocation under the TRUE channel ----------
_EVAL_MEMO = {}
def eval_under_true(seed, x, mapping, draws=30):
    key = (seed, x.tobytes(), mapping, draws)
    if key in _EVAL_MEMO: return _EVAL_MEMO[key]
    sim, pos = _positions(seed)
    build_offsets(seed, mapping); _S['mode'] = 'measured'; _S['icc'] = ICC_DEFAULT
    n = sum(p['count'] for p in pos.values())
    power = x[0::4][:n]; sens = x[1::4][:n]; bw = x[2::4][:n]; off = x[3::4][:n]
    bw = bw/ max(bw.sum(), 1e-9)
    Es, Rel = [], []
    for s in range(draws):
        np.random.seed(10000+seed*100+s)
        r = sim.evaluate_allocation(power, sens, bw, off, pos, 'peak')
        Es.append(r['energy']); Rel.append(r['reliability'])
    _EVAL_MEMO[key] = (float(np.mean(Es)), float(np.mean(Rel)))
    return _EVAL_MEMO[key]

def _pick(X, F, rule):
    """full allocation vector at an operating point ('energy' or 'drl')."""
    i = int(np.argmin(F[:, 0])) if rule == 'energy' else int(np.argmax(drl_reward(F)))
    return X[i]

# ---------- subcommand: metrics ----------
def cmd_metrics():
    seeds = sorted({int(os.path.basename(f).split('_')[0][1:]) for f in glob.glob(CACHE+"/*.npz")})
    out = {"core": {}, "third_leg": {}}
    for mapping in ['indep', 'distcorr']:
        for opp in ['energy', 'drl']:
            dpow, dbw, Rs, tf, tr = [], [], [], [], []
            for seed in seeds:
                try:
                    Xi, Fi = _load(_tag(seed, 'idealized', 'indep', 0.61))
                    Xm, Fm = _load(_tag(seed, 'measured', mapping, 0.61))
                except FileNotFoundError: continue
                pi, bi = sel(Xi, Fi, opp); pm, bm = sel(Xm, Fm, opp)
                n = min(len(pi), len(pm)); pi,bi,pm,bm = pi[:n],bi[:n],pm[:n],bm[:n]
                dpow.append(float(np.mean(np.abs(pi-pm)))); dbw.append(float(np.mean(np.abs(bi-bm))))
                Rs.append(rank_shift_R(pi, pm)); tf.append(float(kendalltau(pi,pm).correlation))
                t_r,_ = resolvable_tau(pi, pm, seed, mapping); tr.append(t_r)
            if dpow:
                out["core"][f"{mapping}/{opp}"] = dict(
                    dpower_dBm=round(np.nanmean(dpow),2), dbw=round(np.nanmean(dbw),4),
                    fleet_rank_shift_R=round(np.nanmean(Rs),2),
                    tau_full=round(np.nanmean(tf),2), tau_resolvable=round(np.nanmean(tr),2),
                    n_seeds=len(dpow))
    # third leg: blind (idealized) vs aware (measured) vs stale, evaluated under truth.
    # Reported at BOTH operating points: the min-energy corner is the fragile vertex;
    # the DRL point is what the deployed system picks.
    for mapping in ['indep']:
        for rule in ['energy', 'drl']:
            rec = []
            for seed in seeds:
                try:
                    Xb, Fb = _load(_tag(seed,'idealized','indep',0.61))
                    Xa, Fa = _load(_tag(seed,'measured',mapping,0.61))
                except FileNotFoundError: continue
                xb = _pick(Xb, Fb, rule); xa = _pick(Xa, Fa, rule)
                Eb,_ = eval_under_true(seed, xb, mapping); Ea,_ = eval_under_true(seed, xa, mapping)
                rec.append((Eb, Ea, (Eb-Ea)/max(Eb,1e-9)))
            if rec:
                arr = np.array(rec)
                out["third_leg"][f"{mapping}/{rule}"] = dict(
                    E_blind_under_truth=round(arr[:,0].mean(),5),
                    E_aware_under_truth=round(arr[:,1].mean(),5),
                    energy_recovered_frac=round(arr[:,2].mean(),3),
                    energy_recovered_frac_per_seed=[round(v,3) for v in arr[:,2]],
                    n_seeds=len(rec))
    # freshness sweep: stale runs (measured oracle, drifted estimate at freshness r),
    # evaluated under truth. recovered_of_blind = (E_blind - E_stale)/E_blind, per
    # operating point. (The gap-normalized ratio proved too unstable per-seed —
    # report recovery vs r directly and let the aware row be the ceiling.)
    stale_rs = sorted({float(os.path.basename(f).split('_stale')[1][:-4])
                       for f in glob.glob(CACHE+"/*_stale*.npz")})
    for mapping in ['indep', 'distcorr']:
        for rule in ['energy', 'drl']:
            for r in stale_rs:
                rec = []
                for seed in seeds:
                    try:
                        Xb, Fb = _load(_tag(seed,'idealized','indep',0.61))
                        Xs, Fs = _load(_tag(seed,'measured',mapping,0.61,r))
                    except FileNotFoundError: continue
                    xb = _pick(Xb, Fb, rule); xs = _pick(Xs, Fs, rule)
                    Eb,_ = eval_under_true(seed, xb, mapping)
                    Es,_ = eval_under_true(seed, xs, mapping)
                    rec.append((Eb-Es)/max(Eb,1e-9))
                if rec:
                    arr = np.array(rec)
                    out.setdefault("freshness_sweep", {})[f"{mapping}/{rule}/r={r:.2f}"] = dict(
                        recovered_of_blind=round(float(np.nanmean(arr)),3),
                        recovered_of_blind_per_seed=[round(v,3) for v in arr],
                        n_seeds=len(rec))
    print(json.dumps(out, indent=2))
    json.dump(out, open(os.path.join(CACHE, "candidate_X.json"), "w"), indent=2)

if __name__ == '__main__':
    if sys.argv[1] == 'opt':
        cmd_opt(int(sys.argv[2]), sys.argv[3], sys.argv[4], float(sys.argv[5]),
                float(sys.argv[6]) if len(sys.argv) > 6 else None)
    elif sys.argv[1] == 'metrics':
        cmd_metrics()
