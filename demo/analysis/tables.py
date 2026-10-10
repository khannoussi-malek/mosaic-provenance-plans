"""Markdown tables for errors_<plans>.md from labels/per_doc/screening/escalation JSON (read-only).
Usage: python3 analysis/tables.py P1 P2 P3"""
import json
import sys
from collections import Counter
from pathlib import Path

DEMO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DEMO))
import score  # noqa: E402

CATS = ["matcher-error", "gold-disagrees-with-text", "split-or-merged-owner", "role-wrong", "hallucinated-owner",
        "span-not-verbatim", "footnote-missed", "name-variant", "date-wrong", "omitted-main-text", "run-error"]
STRATA = ["p0_miss", "redflag_fullname", "footnote", "vague_date", "random"]


def table(head, rows):
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(map(str, r)) + " |" for r in rows])


def main(plans):
    tag = "-".join(plans)
    labels = json.loads((DEMO / "analysis" / f"labels_{tag}.json").read_text())
    rows = json.loads((DEMO / "analysis" / f"per_doc_{tag}.json").read_text())
    scr = json.loads((DEMO / "analysis" / f"screening_{tag}.json").read_text())
    # 1. category x plan, FP and FN
    c = Counter((r["plan"], r["kind"], r["cat"]) for r in labels)
    print(table(["category"] + [f"{p} {k}" for p in plans for k in ("FP", "FN")],
                [[cat] + [c[(p, k, cat)] for p in plans for k in ("FP", "FN")] for cat in CATS if any(c[(p, k, cat)] for p in plans for k in ("FP", "FN"))]
                + [["**total**"] + [sum(c[(p, k, x)] for x in CATS) for p in plans for k in ("FP", "FN")]]))
    # matcher-error subtypes
    sub = Counter((r["plan"], r["why"][:40]) for r in labels if r["cat"] in ("matcher-error", "span-not-verbatim", "gold-disagrees-with-text"))
    print()
    for (p, w), n in sorted(sub.items()):
        print(f"- {p}: {w} ... {n}")
    # 2. owners by stratum
    print()
    out = []
    for s in STRATA:
        ids = [i for i, v in rows.items() if v["stratum"] == s]
        line = [s, len(ids), sum(len(rows[i]["gold"]) for i in ids)]
        for p in plans:
            tp = sum(len(rows[i]["plans"][p]["tp"]) for i in ids)
            fp = sum(len(rows[i]["plans"][p]["fp"]) for i in ids)
            fn = sum(len(rows[i]["plans"][p]["fn"]) for i in ids)
            line.append(f"{score.prf(tp, fp, fn)['F1']:.3f} ({tp}/{fp}/{fn})")
        out.append(line)
    print(table(["stratum", "docs", "gold"] + [f"{p} F1 (TP/FP/FN)" for p in plans], out))
    # 3. model-error categories by stratum (FP+FN)
    print()
    model_cats = ["split-or-merged-owner", "role-wrong", "hallucinated-owner", "span-not-verbatim", "footnote-missed",
                  "name-variant", "omitted-main-text", "run-error"]
    eval_cats = ["matcher-error", "gold-disagrees-with-text"]
    out = []
    for s in STRATA:
        for p in plans:
            sel = [r for r in labels if r["stratum"] == s and r["plan"] == p]
            cc = Counter(r["cat"] for r in sel)
            out.append([s, p, sum(cc[x] for x in eval_cats), sum(cc[x] for x in model_cats),
                        ", ".join(f"{k} {v}" for k, v in cc.most_common() if k in model_cats)])
    print(table(["stratum", "plan", "eval-side (matcher+gold)", "model-side", "model-side breakdown"], out))
    # 4. screening by stratum
    print()
    out = []
    for s in STRATA:
        sel = [r for r in scr if r["stratum"] == s]
        line = [s, len(sel), sum(r["silver"] == "flagged" for r in sel)]
        for p in ["P0"] + plans:
            tp = sum(r[p] == "flagged" and r["silver"] == "flagged" for r in sel)
            fp = sum(r[p] == "flagged" and r["silver"] != "flagged" for r in sel)
            line.append(f"{tp}/{fp}")
        out.append(line)
    print(table(["stratum", "docs", "silver flagged"] + [f"{p} TP/FP" for p in ["P0"] + plans], out))


if __name__ == "__main__":
    main(sys.argv[1:] or ["P1", "P2", "P3"])
