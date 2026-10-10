"""Final numbers for every plan, with 95% bootstrap intervals, in one file: out/results.json.
The figure, the results page and the write-up all read from it, so they cannot disagree.

Usage: python3 results.py
"""
import json
import random
from pathlib import Path

import score as s

OUT = s.HERE / "out"
PLANS = [("P1", "run_P1.json"), ("P1r", "run_P1r.json"), ("P2", "run_P2.json"),
         ("P3", "run_P3.json"), ("P4", "run_P4.json")]
B, SEED = 1000, 0


def ci(xs):
    xs = sorted(xs)
    return [round(xs[int(0.025 * len(xs))], 3), round(xs[int(0.975 * len(xs)) - 1], 3)]


def main():
    docs = json.loads(s.TESTSET.read_text())
    keys, rx = s.load_keys(s.REDFLAG)
    ref = json.loads((s.HERE / "data" / "labels_reference.json").read_text())
    labels = {d["id"]: ref["labels"].get(d["id"], "not flagged") for d in docs}
    plans = {"P0": {"results": None, "verdicts": {d["id"]: s.p0_verdict(d, keys, rx) for d in docs}, "seconds": 0, "calls": 0}}
    for name, f in PLANS:
        path = OUT / f
        if not path.exists() or len(json.loads(path.read_text())) < len(docs):
            continue  # incomplete run: leave the plan out rather than score part of it
        res = s.prepare(docs, {str(r["id"]): r for r in json.loads(path.read_text())})
        events = [e for r in res.values() for e in r["events"]]
        plans[name] = {"results": res,
                       "verdicts": {d["id"]: s.plan_verdict(res.get(d["id"], {}).get("events", []), keys, rx) for d in docs},
                       "seconds": round(sum(r["seconds"] for r in res.values())),
                       "errors": sum(bool(r["error"]) for r in res.values()),
                       "unsupported": round(sum(not e["span_ok"] for e in events) / max(len(events), 1), 3)}
    p5 = OUT / "run_P5.json"
    if p5.exists() and "P3" in plans:
        rows = {r["id"]: r for r in json.loads(p5.read_text())}
        plans["P5"] = dict(plans["P3"], verdicts={i: rows.get(i, {}).get("verdict", v) for i, v in plans["P3"]["verdicts"].items()},
                           seconds=plans["P3"]["seconds"] + round(sum(r["seconds"] for r in rows.values())))
    rng = random.Random(SEED)
    boot = {n: {"owners": [], "screen": []} for n in plans}
    for _ in range(B):
        sample = [rng.choice(docs) for _ in docs]
        for n, p in plans.items():
            boot[n]["screen"].append(s.screening(sample, p["verdicts"], labels)["F1"])
            if p["results"] is not None:
                boot[n]["owners"].append(s.owner_scores(sample, p["results"])["F1"])
    out = {"n_docs": len(docs), "labels": {"agreement": ref["agreement"], "kappa": ref["kappa"],
                                            "left_out": len(ref["disagreements"])}, "plans": {}}
    for n, p in plans.items():
        scr = s.screening(docs, p["verdicts"], labels)
        own = s.owner_scores(docs, p["results"]) if p["results"] is not None else None
        out["plans"][n] = {"seconds": p["seconds"], "errors": p.get("errors"), "unsupported": p.get("unsupported"),
                           "owners": own, "owners_ci": ci(boot[n]["owners"]) if own else None,
                           "screen": scr, "screen_ci": ci(boot[n]["screen"])}
    (OUT / "results.json").write_text(json.dumps(out, indent=1))
    for n, r in out["plans"].items():
        print(f"{n:4s} owners F1 {r['owners']['F1'] if r['owners'] else '—':>5}  {r['owners_ci'] or ''}  "
              f"screen F1 {r['screen']['F1']}  {r['screen_ci']}  {r['seconds']} s")


if __name__ == "__main__":
    main()
