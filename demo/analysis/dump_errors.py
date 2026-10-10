"""Per-document error picture for extraction plans (read-only; reuses score.py, does not change it).
Usage: python3 dump_errors.py P1 P2 P3  -> analysis/per_doc_<plans>.json + stdout overview."""
import json
import sys
from pathlib import Path

DEMO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DEMO))
import score  # noqa: E402


def match_doc(gold, events):
    """Same one-to-one greedy match as score.owner_scores, but returns the pairs."""
    pred = sorted([e for e in events if e.get("span_ok")], key=lambda e: len(score.tokens(e["owner"])), reverse=True)
    used, tp, fp = set(), [], []
    for e in pred:
        hit = next((i for i, g in enumerate(gold) if i not in used and score.same_owner(e["owner"], g)), None)
        if hit is None:
            fp.append(e)
        else:
            used.add(hit)
            tp.append((e["owner"], gold[hit]))
    fn = [g for i, g in enumerate(gold) if i not in used]
    return tp, fp, fn


def main(plans):
    docs = json.loads(score.TESTSET.read_text())
    keys, rx = score.load_keys(score.REDFLAG)
    out = {}
    for d in docs:
        gold = [g["name"] for g in d["gold_owners"]]
        row = {"stratum": d["stratum"], "tags": d["tags"], "silver": score.silver_label(d, keys, rx),
               "p0": score.p0_verdict(d, keys, rx), "gold": gold, "plans": {}}
        out[d["id"]] = row
    for p in plans:
        runs = {str(r["id"]): r for r in json.loads((DEMO / "out" / f"run_{p}.json").read_text())}
        for d in docs:
            r = runs.get(d["id"], {"events": [], "error": "missing"})
            tp, fp, fn = match_doc(out[d["id"]]["gold"], r["events"])
            out[d["id"]]["plans"][p] = {
                "verdict": score.plan_verdict(r["events"], keys, rx), "error": r.get("error"),
                "escalated": r.get("escalated"), "tp": tp,
                "fp": [{k: e.get(k) for k in ("owner", "role", "date", "year", "source_span")} for e in fp],
                "fn": fn,
                "unsupported": [{"owner": e["owner"], "span": e.get("source_span")} for e in r["events"] if not e.get("span_ok")],
                "rf_hits": sorted({k for e in r["events"] if e.get("span_ok")
                                   for k in score.match(score.forward(e["owner"]), rx, keys, tier="fullname")}),
                "events": [(e["owner"], e.get("year"), e.get("span_ok")) for e in r["events"]],
            }
    path = DEMO / "analysis" / f"per_doc_{'-'.join(plans)}.json"
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    for p in plans:
        tot = {k: sum(len(v["plans"][p][k]) for v in out.values()) for k in ("tp", "fp", "fn", "unsupported")}
        print(p, tot)
    print("wrote", path)


if __name__ == "__main__":
    main(sys.argv[1:] or ["P1", "P2", "P3"])
