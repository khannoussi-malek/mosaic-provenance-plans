"""Build the NGA test set: 100 distinct 1933-45 provenance texts with gold previous owners.

Gold = NGA's own structured owner list (objects_constituents.csv, role 'previous owner'),
ordered by displayorder, names from constituents.csv.
"""
import csv
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

csv.field_size_limit(10**8)
P0 = Path(__file__).parent.parent / "phase0" / "data"
OUT = Path(__file__).parent / "data" / "testset_nga.json"
DEV_OUT = Path(__file__).parent / "data" / "devset_nga.json"
DEV_N, DEV_SEED = 30, 7  # dev split for prompt/threshold work; never overlaps the test set
SEED = 42
MAX_CHARS = 3000  # ponytail: keeps local runs tractable; stated as a limit in the write-up
STRATA = [("p0_miss", 6), ("redflag_fullname", 30), ("footnote", 20), ("vague_date", 15), ("random", 29)]
VAGUE = re.compile(r"\b(by|c\.|before|after)\s+\d{4}|\?")


def rows(path):
    return csv.DictReader(open(path, encoding="utf-8"))


def main():
    if OUT.exists() and "--force" not in sys.argv:
        raise SystemExit(f"{OUT} exists; the test set is frozen. Pass --force only to rebuild it on purpose.")
    from score import load_keys, p0_verdict, silver_label, REDFLAG  # flagged docs the baseline misses
    keys, rx = load_keys(REDFLAG)
    texts = {r["id"]: r for r in rows(P0 / "nga_1933_45.csv")}
    names = {r["constituentid"]: r["preferreddisplayname"] for r in rows(P0 / "nga" / "constituents.csv")}
    gold = defaultdict(list)
    for r in rows(P0 / "nga" / "objects_constituents.csv"):
        if r["objectid"] in texts and r["role"] == "previous owner":
            gold[r["objectid"]].append({
                "order": int(r["displayorder"] or 0), "constituentid": r["constituentid"],
                "name": names.get(r["constituentid"], ""), "suffix": r["suffix"],
                "beginyear": int(r["beginyear"]) if r["beginyear"] else None,
                "endyear": int(r["endyear"]) if r["endyear"] else None,
            })
    redflag = {r["id"] for r in rows(P0 / "matches_nga.csv") if r["tier"] == "fullname"}

    # one object per distinct text (many prints share a text), must have gold, bounded length
    seen, pool = set(), []
    for oid, r in sorted(texts.items(), key=lambda kv: int(kv[0])):
        t = r["provenance_text"].strip()
        if t in seen or not gold[oid] or len(t) > MAX_CHARS:
            continue
        seen.add(t)
        d = {"id": oid, "title": r["title"], "artist": r["artist"], "provenance_text": t,
             "gold_owners": sorted(gold[oid], key=lambda g: g["order"])}
        tags = {"redflag_fullname": oid in redflag, "footnote": "[1]" in t, "vague_date": bool(VAGUE.search(t)),
                "p0_miss": silver_label(d, keys, rx) == "flagged" and p0_verdict(d, keys, rx) != "flagged"}
        pool.append(dict(d, tags=[k for k, v in tags.items() if v]))

    rng, chosen = random.Random(SEED), {}
    for stratum, n in STRATA:
        cands = [d for d in pool if d["id"] not in chosen and (stratum == "random" or stratum in d["tags"])]
        for d in rng.sample(cands, min(n, len(cands))):
            chosen[d["id"]] = dict(d, stratum=stratum)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(list(chosen.values()), indent=1, ensure_ascii=False))
    dev = random.Random(DEV_SEED).sample([d for d in pool if d["id"] not in chosen], DEV_N)
    DEV_OUT.write_text(json.dumps(dev, indent=1, ensure_ascii=False))
    print(f"dev split: {len(dev)} docs -> {DEV_OUT}")
    print(f"pool {len(pool)} distinct texts with gold; wrote {len(chosen)} to {OUT}")
    for s, _ in STRATA:
        print(f"  {s}: {sum(d['stratum'] == s for d in chosen.values())}")
    print(f"  gold owners total: {sum(len(d['gold_owners']) for d in chosen.values())}")


if __name__ == "__main__":
    main()
