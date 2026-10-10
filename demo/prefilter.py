"""Filter first, then read: the model reads only texts the cheap name matcher keeps; the rest count as not flagged.

Measured offline from saved runs (no model calls): how many texts the filter keeps, how much model time that saves,
and what it costs in screening F1 and in flagged objects lost.
Usage: python3 prefilter.py            # test set, reference labels
       python3 prefilter.py --dev      # dev set, silver labels (filter tiers were not chosen on it)
"""
import json
import sys

import score
from analyze import match


def main():
    dev = "--dev" in sys.argv
    docs = json.loads((score.DEVSET if dev else score.TESTSET).read_text())
    run = score.HERE / "out" / ("fresh_P1.json" if dev else "run_P1.json")
    keys, rx = score.load_keys(score.REDFLAG)
    results = score.prepare(docs, {str(r["id"]): r for r in json.loads(run.read_text())})
    labels = {d["id"]: score.silver_label(d, keys, rx) for d in docs}
    if not dev:
        ref = json.loads((score.HERE / "data" / "labels_reference.json").read_text())["labels"]
        labels = {i: ref.get(i, "not flagged") for i in labels}
    full = {d["id"]: score.plan_verdict(results[d["id"]]["events"], keys, rx) for d in docs}
    total = sum(results[d["id"]]["seconds"] for d in docs)
    print(f"{'dev (silver labels)' if dev else 'test (reference labels)'}: {len(docs)} texts, "
          f"P1 reads all in {total:.0f} s, screening {score.screening(docs, full, labels)}")
    flagged = {i for i, v in labels.items() if v == "flagged"}
    # the filter keeps a text only if it holds a listed name: the verdict needs one anyway (a full-name hit on an
    # extracted owner), so this pushes a necessary condition before the model call. It shares the matcher's blind spots.
    for tier in ("naive", "cased", "fullname"):  # no year check: every text was selected for a 1933-45 year
        keep = {d["id"] for d in docs if match(d["provenance_text"], rx, keys, tier=tier)}
        verdicts = {i: (v if i in keep else "not flagged") for i, v in full.items()}
        secs = sum(results[i]["seconds"] for i in keep)
        lost = sum(full[i] == "flagged" and i not in keep for i in full)
        print(f"  filter {tier:8s} keeps {len(keep):3d} texts, {secs:5.0f} s ({secs / total:4.0%}), "
              f"labelled-flagged kept {len(flagged & keep)}/{len(flagged)}, P1 flags lost {lost}, "
              f"screening F1 {score.screening(docs, verdicts, labels)['F1']}")


if __name__ == "__main__":
    main()
