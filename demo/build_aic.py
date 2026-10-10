"""Second source (FR-4, DR-2): 20 distinct AIC 1933-45 provenance texts, half with a Red Flag full-name match.

AIC has no structured owner list, so these are checked by hand after a model proposes events.
"""
import csv
import json
import random
import sys
from pathlib import Path

P0 = Path(__file__).parent.parent / "phase0" / "data"
OUT = Path(__file__).parent / "data" / "aic20.json"
SEED, N_MATCH, N_RANDOM, MAX_CHARS, MIN_CHARS = 42, 10, 10, 3000, 150


def main():
    if OUT.exists() and "--force" not in sys.argv:
        raise SystemExit(f"{OUT} exists; the AIC sample is frozen. Pass --force only to rebuild it on purpose.")
    csv.field_size_limit(10**8)
    matched = {r["id"] for r in csv.DictReader(open(P0 / "matches_aic.csv")) if r["tier"] == "fullname"}
    seen, pool = set(), []
    for r in csv.DictReader(open(P0 / "aic_1933_45.csv", encoding="utf-8")):
        t = r["provenance_text"].strip()
        if t in seen or not MIN_CHARS <= len(t) <= MAX_CHARS:  # ponytail: drop one-line stubs and very long texts
            continue
        seen.add(t)
        pool.append({"id": r["id"], "title": r["title"], "artist": r["artist"], "provenance_text": t,
                     "source": "AIC", "stratum": "redflag_fullname" if r["id"] in matched else "random"})
    rng = random.Random(SEED)
    pick = rng.sample([d for d in pool if d["stratum"] == "redflag_fullname"], N_MATCH)
    pick += rng.sample([d for d in pool if d["stratum"] == "random"], N_RANDOM)
    OUT.write_text(json.dumps(pick, indent=1, ensure_ascii=False))
    print(f"pool {len(pool)} distinct AIC texts ({sum(d['stratum'] == 'redflag_fullname' for d in pool)} with a full-name match); "
          f"wrote {len(pick)} to {OUT}")


if __name__ == "__main__":
    main()
