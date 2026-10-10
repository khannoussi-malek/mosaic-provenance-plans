"""Reference screening labels from two independent LLM labelers, with their agreement (Cohen's kappa).

Agree on flag / no_flag -> reference label. Anything else -> 'uncertain' (left out of screening P/R/F1).
Test docs outside the 54 checked cases (no listed name at any tier) -> 'not flagged'.
"""
import json
from collections import Counter

import score as s

DATA = s.HERE / "data"


def kappa(pairs):
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / n / n
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def main():
    first = {x["id"]: x for x in json.loads((DATA / "label_proposals.json").read_text())}
    second = {x["id"]: x for x in json.loads((DATA / "labels_second.json").read_text())}
    pairs = [(first[i]["proposal"], second[i]["label"]) for i in first]
    ref = {}
    for i in first:
        a, b = first[i]["proposal"], second[i]["label"]
        ref[i] = {"flag": "flagged", "no_flag": "not flagged"}[a] if a == b and a != "unsure" else "uncertain"
    roles = sum(first[i]["role"] == second[i]["role"] for i in first)
    out = {"agreement": round(sum(a == b for a, b in pairs) / len(pairs), 3), "kappa": round(kappa(pairs), 3),
           "role_agreement": round(roles / len(first), 3), "n": len(pairs), "labels": ref,
           "disagreements": sorted(i for i in first if ref[i] == "uncertain")}
    (DATA / "labels_reference.json").write_text(json.dumps(out, indent=1))
    print(f"{len(pairs)} cases: raw agreement {out['agreement']}, Cohen's kappa {out['kappa']}, role agreement {out['role_agreement']}")
    print("reference:", dict(Counter(ref.values())), "| uncertain ids:", out["disagreements"])


if __name__ == "__main__":
    main()
