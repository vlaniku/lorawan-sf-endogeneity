#!/bin/bash
# Seeds 5-9: core X (both mappings) + freshness sweep. Resumable.
cd "$(dirname "$0")"
export REPLAY_FULL=1
CACHE=replay_cache

run() {
  local tag="s${1}_${2}_${3}_icc$(printf '%.2f' $4)"
  [ -n "$5" ] && tag="${tag}_stale$(printf '%.2f' $5)"
  if [ -f "$CACHE/$tag.npz" ]; then echo "SKIP $tag (cached)"; return; fi
  echo "=== $(date '+%H:%M:%S') RUN $tag"
  python full_replay.py opt "$@" || { echo "FAILED $tag"; exit 1; }
}

for seed in 5 6 7 8 9; do
  run $seed idealized indep 0.61
  run $seed measured indep 0.61
  run $seed measured distcorr 0.61
  for r in 0.00 0.20 0.46 0.70 0.90; do
    run $seed measured indep 0.61 $r
  done
done
echo "=== $(date '+%H:%M:%S') seeds 5-9 done"
