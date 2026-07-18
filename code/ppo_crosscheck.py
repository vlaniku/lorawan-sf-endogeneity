"""
ppo_crosscheck.py — live PPO cross-check of the DRL operating point (to-do #2)
===============================================================================
full_replay.drl_reward() emulates the Stage-2 PPO's selection with the agent's
exact reward formula at nominal peak (load_f=1.0, channel_q=0.5). This script
trains the REAL PPO (drl_agent.py, paper settings: 50k timesteps, seed=42) on
each cached Pareto front and checks:
  1. does the live policy at the nominal-peak state pick the same solution as
     the reward-argmax proxy (and if not, how far apart in power space)?
  2. does X (per-device |dpower|, fleet rank-shift R) change when selections
     come from the live PPO instead of the proxy?
Run AFTER run_full_program.sh has populated replay_cache/.
"""
import os, json
import numpy as np
os.environ.setdefault('REPLAY_FULL', '1')
import full_replay as FR
from isac_system_model import ISACSimulator, ISACSystemConfig
from drl_agent import train_drl_agent, evaluate_drl_agent

SEEDS = [0, 1, 2, 3, 4]
FRONTS = [('idealized', 'indep'), ('measured', 'indep'), ('measured', 'distcorr')]

def nominal_state():
    # matches FR.drl_reward's nominal peak: channel_q=0.5, load_f=1.0;
    # avg_distance mid-range, medium density, t=0, prev_* at reset values
    return np.array([0.5, 1.0, 0.5, 0.5, 0.0, 1.0, 0.5, 0.5], dtype=np.float32)

def main():
    results, agg = {}, {'same_action': 0, 'total': 0, 'dpow_live_proxy': [],
                        'X_live_R': {'indep': [], 'distcorr': []},
                        'X_live_dpower': {'indep': [], 'distcorr': []}}
    for seed in SEEDS:
        sim = ISACSimulator(ISACSystemConfig(), seed=seed)
        live_power = {}
        for mode, mapping in FRONTS:
            tag = FR._tag(seed, mode, mapping, 0.61)
            path = os.path.join(FR.CACHE, tag + '.npz')
            if not os.path.exists(path):
                continue
            d = np.load(path); X, F = d['X'], d['F']
            model, env, _ = train_drl_agent(X, F, sim, total_timesteps=50000, seed=42)
            ev = evaluate_drl_agent(model, env, n_episodes=20)
            modal = int(np.argmax(ev['action_distribution']))
            nom = int(model.predict(nominal_state(), deterministic=True)[0])
            nom = min(nom, len(X) - 1)
            proxy = int(np.argmax(FR.drl_reward(F)))
            pw_nom, pw_proxy = X[nom][0::4], X[proxy][0::4]
            results[tag] = dict(
                live_nominal_action=nom, live_modal_action=modal, proxy_action=proxy,
                n_solutions=int(len(F)),
                dpower_live_vs_proxy_dBm=round(float(np.mean(np.abs(pw_nom - pw_proxy))), 3))
            agg['total'] += 1; agg['same_action'] += int(nom == proxy)
            agg['dpow_live_proxy'].append(float(np.mean(np.abs(pw_nom - pw_proxy))))
            live_power[(mode, mapping)] = pw_nom
        if ('idealized', 'indep') in live_power:
            pi = live_power[('idealized', 'indep')]
            for mapping in ['indep', 'distcorr']:
                if ('measured', mapping) in live_power:
                    pm = live_power[('measured', mapping)]
                    n = min(len(pi), len(pm))
                    dp = float(np.mean(np.abs(pi[:n] - pm[:n])))
                    R = FR.rank_shift_R(pi[:n], pm[:n])
                    results[f's{seed}_X_under_livePPO_{mapping}'] = dict(
                        dpower_dBm=round(dp, 2), fleet_rank_shift_R=round(R, 2))
                    agg['X_live_dpower'][mapping].append(dp)
                    agg['X_live_R'][mapping].append(R)
    results['SUMMARY'] = dict(
        live_picks_same_solution_as_proxy=f"{agg['same_action']}/{agg['total']}",
        mean_dpower_live_vs_proxy_dBm=round(float(np.mean(agg['dpow_live_proxy'])), 3)
            if agg['dpow_live_proxy'] else None,
        X_under_live_PPO={m: dict(dpower_dBm=round(float(np.mean(v)), 2),
                                  R=round(float(np.mean(agg['X_live_R'][m])), 2),
                                  n=len(v))
                          for m, v in agg['X_live_dpower'].items() if v})
    out = os.path.join(FR.CACHE, 'ppo_crosscheck.json')
    json.dump(results, open(out, 'w'), indent=2)
    print(json.dumps(results['SUMMARY'], indent=2)); print('saved', out)

if __name__ == '__main__':
    main()
