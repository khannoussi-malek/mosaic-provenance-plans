"""Per-plan precision and recall on the 20 Chicago texts, from the blind LLM judge (data/aic_judged.json).

Recall's denominator = every owner judged correct (found by any plan) + owners the judge says all plans missed.
"""
import json

import score as s
from make_aicpage import key

DATA, OUT = s.HERE / "data", s.HERE / "out"


def main():
    judged = {j["id"]: j for j in json.loads((DATA / "aic_judged.json").read_text())}
    truth = sum(sum(v == "correct" for v in j["verdicts"].values()) + len(j["missing"]) for j in judged.values())
    print(f"Chicago: {len(judged)} texts, {truth} true owners (judged correct or missing), LLM-judged\n")
    for plan in ("P1", "P2", "P3"):
        runs = json.loads((OUT / f"aic_{plan}.json").read_text())
        c = w = u = 0
        for r in runs:
            v = judged[str(r["id"])]["verdicts"]
            for k in {key(e["owner"]) for e in r["events"]}:  # one vote per distinct owner, as on the judge's list
                c, w, u = c + (v.get(k) == "correct"), w + (v.get(k) == "wrong"), u + (v.get(k) == "unclear")
        secs = sum(r["seconds"] for r in runs)
        print(f"{plan}: precision {c / max(c + w, 1):.3f} ({w} wrong, {u} unclear left out) · recall {c / truth:.3f} · "
              f"errors {sum(bool(r['error']) for r in runs)} · {secs:.0f} s")


if __name__ == "__main__":
    main()
