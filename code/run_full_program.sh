#!/bin/bash
# Full-scale replay program: core X (5 seeds, gen=150), full-scale ICC=0 null,
# and the stale-estimate freshness sweep. Resumable: skips cached runs.
cd "$(dirname "$0")"
export REPLAY_FULL=1
CACHE=replay_cache

run() {  # run <seed> <mode> <mapping> <icc> [stale_r]
  local tag="s${1}_${2}_${3}_icc$(printf '%.2f' $4)"
  [ -n "$5" ] && tag="${tag}_stale$(printf '%.2f' $5)"
  if [ -f "$CACHE/$tag.npz" ]; then echo "SKIP $tag (cached)"; return; fi
  echo "=== $(date '+%H:%M:%S') RUN $tag"
  python full_replay.py opt "$@" || { echo "FAILED $tag"; exit 1; }
}

# --- core X: blind + aware(both mappings), 5 seeds
for seed in 0 1 2 3 4; do
  run $seed idealized indep 0.61
  run $seed measured indep 0.61
  run $seed measured distcorr 0.61
done

# --- committed gate: full-scale ICC=0 alignment null (checked in metrics step below)
run 0 measured indep 0.00

# --- freshness sweep (indep mapping), 5 seeds x 5 freshness levels
for seed in 0 1 2 3 4; do
  for r in 0.00 0.20 0.46 0.70 0.90; do
    run $seed measured indep 0.61 $r
  done
done

echo "=== $(date '+%H:%M:%S') all opts done; ICC=0 null check + metrics"
python - <<'EOF'
import numpy as np
a = np.load('replay_cache/s0_idealized_indep_icc0.61.npz')
b = np.load('replay_cache/s0_measured_indep_icc0.00.npz')
pa = a['X'][int(np.argmin(a['F'][:,0]))][0::4]; pb = b['X'][int(np.argmin(b['F'][:,0]))][0::4]
null = float(np.abs(pa-pb).max())
print('FULL-SCALE ICC=0 alignment null |dpower| =', null)
assert null == 0.0, 'ALIGNMENT NULL VIOLATED - do not trust magnitudes'
print('null gate PASSED')
EOF
python full_replay.py metrics
echo "=== $(date '+%H:%M:%S') DONE"
