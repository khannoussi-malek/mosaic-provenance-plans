"""P3 escalations: did the large model fix the trigger, and did owners/verdict get better or worse vs P1? (read-only)
Usage: python3 analysis/escalation.py   (needs analysis/per_doc_P1-P2-P3.json from dump_errors.py)"""
import json
import sys
from pathlib import Path

DEMO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DEMO))
import score  # noqa: E402
from cascade import needs_escalation  # noqa: E402  (same free check the cascade used)


def main():
    docs = {d["id"]: d for d in json.loads(score.TESTSET.read_text())}
    p1 = {str(r["id"]): r for r in json.loads((DEMO / "out" / "run_P1.json").read_text())}
    p3 = {str(r["id"]): r for r in json.loads((DEMO / "out" / "run_P3.json").read_text())}
    rows = json.loads((DEMO / "analysis" / "per_doc_P1-P2-P3.json").read_text())
    out = []
    for did, r3 in p3.items():
        if not r3.get("escalated"):
            continue
        a, b = rows[did]["plans"]["P1"], rows[did]["plans"]["P3"]
        still = needs_escalation(docs[did], r3)  # would the free check still fire on the kept output?
        out.append({"id": did, "stratum": rows[did]["stratum"], "reason": r3["escalated"], "check_after": still,
                    "model_kept": r3["model"], "tp": (len(a["tp"]), len(b["tp"])), "fp": (len(a["fp"]), len(b["fp"])),
                    "fn": (len(a["fn"]), len(b["fn"])), "unsupported": (len(a["unsupported"]), len(b["unsupported"])),
                    "verdict": (a["verdict"], b["verdict"]), "silver": rows[did]["silver"],
                    "p1_events": len(p1[did]["events"])})
    (DEMO / "analysis" / "escalation_P3.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    for o in out:
        print(o["id"], o["stratum"], repr(o["reason"]), "-> after:", repr(o["check_after"]), o["model_kept"],
              "TP", o["tp"], "FP", o["fp"], "FN", o["fn"], "uns", o["unsupported"], o["verdict"], "silver=" + o["silver"])
    print("n =", len(out))


if __name__ == "__main__":
    main()
