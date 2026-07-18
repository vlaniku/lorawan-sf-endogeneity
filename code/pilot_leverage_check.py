"""
pilot_leverage_check.py  (v3 — variance-matched + alignment null + ICC sweep)
============================================================================
GATE before the full replay: does perturbing the channel at the injection point
(isac_system_model.py line 149, the shadowing draw) move the NSGA-III optimizer's
per-device allocations because of PERSISTENT STRUCTURE — verified clean of both a
variance confound and an RNG-desync confound?

Variance-matched decomposition (total shadowing variance held CONSTANT):
    idealized: shadow = σ · z0                          (fully iid, as coded)
    measured : shadow = σ·√ICC · z_i  +  σ·√(1−ICC) · z0
    Var(measured) = σ² = Var(idealized).   Oracles differ ONLY in structure.

What the injected term IS: a PERSISTENT PER-DEVICE LINK-QUALITY OFFSET entering at
the allocator's only channel-state hook. RWSCP's ICC=0.61 was measured on SNR
*margin* (bundling shadowing + antenna/enclosure + firmware/ADR + interference), so
this is NOT a claim that cellular shadowing is 61% persistent — it is device link
quality that is 61% persistent, injected where link quality enters the optimizer.

Two nulls (both must pass before trusting magnitude):
  * Determinism null:  idealized vs idealized           -> τ=1.00, |Δ|=0.
  * RNG-ALIGNMENT null: idealized vs matched @ ICC=0     -> τ=1.00, |Δ|=0.
    (At ICC=0 the decomposition collapses to σ·z0, which must reproduce the original
     byte-for-byte IFF the hand-rolled draw sequence is aligned. This is the check
     that the determinism null alone does NOT provide.)

RESULTS (n=24 devices):
  Determinism null  τ=+1.00 |Δ|=0.00 (3 seeds)
  ALIGNMENT null    τ=+1.000 |Δ|=0.0000 dBm (2 seeds)   <-- Bug-1 cleared
  Structure effect  per-device power |Δ| ≈ 6 dBm, rank-τ ≈ 0
  ICC sweep (seed-avg, 3 seeds):  ICC 0→0.00 | 0.30→6.64 | 0.61→6.06 | 0.90→6.12 dBm
    => THRESHOLD/SATURATING, not graded: any persistence switches the effect on at
       ~6 dBm; more does not increase it. X is INSENSITIVE to the exact ICC in
       [0.3,0.9] (robustness gift — result doesn't hinge on the precise fraction).
  This is a leverage/robustness preview, NOT the reportable X (see X_preregistration.md:
  deployed Q-selected operating point, both RWSCP->device mappings, full pop_size,
  unconditioned fleet rank-shift as the primary metric).

Requires the TGCN sources on path + pymoo. Vullnet holds ground truth on the wiring.
"""
import numpy as np, warnings; warnings.filterwarnings('ignore')
import isac_system_model as M
from isac_system_model import ISACSimulator, ISACSystemConfig, DEVICE_PROFILES
import nsga3_optimizer as O
from scipy.stats import kendalltau

DEVICE_PROFILES['utility_meter'].count = 12; DEVICE_PROFILES['env_sensor'].count = 6
DEVICE_PROFILES['traffic_camera'].count = 3; DEVICE_PROFILES['safety_device'].count = 3
_gr = O.get_reference_directions
O.get_reference_directions = lambda *a, **k: _gr("das-dennis", 4, n_partitions=3)  # 20 ref-dirs

ZSTATE = {}; _S = {'mode': 'idealized', 'icc': 0.61}
_orig = M.UrbanChannelModel.get_channel_gain

def _gain(self, distance_m, los_prob=None):
    if _S['mode'] == 'idealized':
        return _orig(self, distance_m, los_prob)
    d = max(distance_m, 1.0)
    if los_prob is None:
        los_prob = min(18.0/d, 1.0) * (1 - np.exp(-d/36.0)) + np.exp(-d/36.0)
    is_los = np.random.random() < los_prob                  # aligned draw #1 (LOS)
    sigma = 4.0 if is_los else 7.82
    pl = self.path_loss_db(distance_m, is_los)
    z0 = np.random.normal(0, 1)                             # aligned draw #2 (iid part)
    assert distance_m in ZSTATE, f"device {distance_m} has no persistent offset (fail-loud)"
    zi = ZSTATE[distance_m]; icc = _S['icc']
    shadow = sigma*np.sqrt(icc)*zi + sigma*np.sqrt(1-icc)*z0   # variance-matched
    return 10**(-(pl + shadow)/10.0) * self.fading_linear()    # aligned draw #3 (fading)
M.UrbanChannelModel.get_channel_gain = _gain

def build_offsets(seed):
    sim = ISACSimulator(ISACSystemConfig(), seed=seed)
    pos = sim.generate_device_positions('medium')
    rng = np.random.RandomState(2000 + seed); ZSTATE.clear(); dd = []
    for _, info in pos.items():
        for x in info['distances']:
            dd.append(float(x)); ZSTATE[float(x)] = rng.normal(0, 1)
    assert len(dd) == len(set(dd)), "distance collision — keying unsafe"   # concern 3
    return len(dd)

def run(seed, mode, icc=0.61):
    _S['mode'] = mode; _S['icc'] = icc; np.random.seed(seed)
    return O.run_nsga3_optimization('medium', 'peak', pop_size=44, n_gen=30, seed=seed)

def power_of(res):
    F, X = res['pareto_F'], res['pareto_X']
    return X[int(np.argmin(F[:, 0]))][0::4]      # min-energy corner (preview only)
def tau(a, b): n = min(len(a), len(b)); return kendalltau(a[:n], b[:n]).correlation
def dp(a, b):  n = min(len(a), len(b)); return float(np.mean(np.abs(a[:n] - b[:n])))

if __name__ == '__main__':
    print(">> ALIGNMENT NULL (must be τ=1.000, |Δ|=0): idealized vs matched@ICC=0")
    for seed in [1, 2]:
        build_offsets(seed)
        b = power_of(run(seed, 'idealized')); m0 = power_of(run(seed, 'matched', 0.0))
        print(f"   seed {seed}: τ={tau(b,m0):+.3f}  |Δ|={dp(b,m0):.4f} dBm")
    print("\n>> ICC dose-response (seed 1):")
    build_offsets(1); b = power_of(run(1, 'idealized'))
    for icc in [0.0, 0.3, 0.61, 0.9]:
        m = power_of(run(1, 'matched', icc))
        print(f"   ICC={icc:.2f}: |Δ|={dp(b,m):.2f} dBm  τ={tau(b,m):+.2f}")
