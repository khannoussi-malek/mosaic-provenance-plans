#!/bin/sh
# Remaining model runs, one after another (fair timing). Run with: caffeinate -i sh run_queue.sh
cd "$(dirname "$0")"
mkdir -p .fresh
up() {  # Ollama quit once at 05:29 on 10 Oct; restart the app if it is not answering
  curl -s -m 3 localhost:11434/api/tags >/dev/null && return
  open -a Ollama; i=0; until curl -s -m 2 localhost:11434/api/tags >/dev/null || [ $i -ge 60 ]; do sleep 1; i=$((i+1)); done
}

for attempt in 1 2; do  # P4 test (resumes from cache); a second pass retries any refused verifier call
  up; python3 -u verify.py qwen3:8b qwen3:8b data/testset_nga.json out/run_P4.json > out/run_P4.log 2>&1
  grep -q "Connection refused" out/run_P4.log || break
done
up; MOSAIC_CACHE=.fresh/repro python3 -u repro_check.py 10 > out/repro.log 2>&1                          # QR-6: recompute into an empty cache
up; python3 -u retry.py qwen3:8b data/testset_nga.json out/run_P1r.json > out/run_P1r.log 2>&1           # P1r: same-model retry baseline

# Fresh timing on the dev split: empty cache per plan, models unloaded first, wall clock includes loading and swaps.
: > out/timing.txt
timed() {  # name, cache dir, command...
  name=$1; cache=$2; shift 2
  up; ollama stop qwen3:8b >/dev/null 2>&1; ollama stop qwen2.5:14b >/dev/null 2>&1
  start=$(date +%s)
  MOSAIC_CACHE=$cache "$@" > "out/fresh_$name.log" 2>&1
  echo "$name $(( $(date +%s) - start ))" >> out/timing.txt
}
timed P1 .fresh/t_P1 python3 -u extract.py qwen3:8b data/devset_nga.json out/fresh_P1.json
timed P2 .fresh/t_P2 python3 -u extract.py qwen2.5:14b data/devset_nga.json out/fresh_P2.json
timed P3 .fresh/t_P3 python3 -u cascade.py qwen3:8b qwen2.5:14b data/devset_nga.json out/fresh_P3.json
echo "QUEUE DONE $(date +%H:%M)"
