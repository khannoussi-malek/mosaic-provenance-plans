"""How much of the 1946 Red Flag list can the name matcher link to, and what would better linking change?

Every published plan links names with the full-name rule (phase0/scripts/analyze.py, match(tier="fullname")): a listed
surname counts only with the entry's own forename (or its initial) just before it. This script measures how much of
the list that rule can reach, then re-scores saved runs with a repaired linker. It is a sensitivity analysis: the
published numbers do not change, and a new flag outside the 54 labelled cases has no label, so it is listed for
review, not scored.

Repairs (each one seen in a missed or unreachable case):
  word order   "Abetz Otto" (no comma): the words after the surname are the forename
  spelling     list "Muehlmann" also matches text "Muhlmann"; a forename may differ in its last letters
               ("Gustav" / "Gustave", "Hildebrandt" / "Hildebrand")
  common names a surname on the COMMON stop list (Fischer, Bauer, Frank ...) still links when the forename matches
  firms        variant B only: an entry with no person forename ("AWAG", "Wildenstein Paris, ...") links on its
               capitalised name alone (an upper bound: firm flags are the debatable labels)
Usage: python3 linking_gap.py
"""
import json
import re
from unittest import mock

import graph as gm
import score as s
from analyze import COMMON, TITLES, fold, forename, norm_key

LABELS = json.loads((s.HERE / "data" / "labels_reference.json").read_text())["labels"]  # the 54 checked cases


def forename2(entry, key):
    """The published forename, or for "Surname Forename" entries without a comma, the words after the surname."""
    f = forename(entry)
    if f or "," in entry:
        return f
    rest = [t for t in entry.split()[len(key.split()):] if t.strip(".") not in TITLES]
    return rest[0] if rest and rest[0][:1].isupper() and rest[0].isalpha() else None


def repaired_keys(keys):
    """Each key also under its umlaut-less spelling ("muehlmann" -> "muhlmann"), and its regex."""
    out = {}
    for k, names in keys.items():
        for v in {k, k.replace("ue", "u").replace("oe", "o").replace("ae", "a")}:
            out.setdefault(v, [])
            out[v] += [(n, k) for n in names if (n, k) not in out[v]]
    alts = sorted(out, key=len, reverse=True)
    rx = re.compile(r"(?<![\w])(" + "|".join(re.escape(k).replace(r"\ ", r"[\s-]+") for k in alts) + r")(?![\w])", re.I)
    return out, rx


def linker(keys2, rx2, firms):
    """A drop-in for analyze.match(..., tier="fullname") with the repairs above."""
    def link(text, rx=None, keys=None, do_fold=True, tier="fullname"):
        t = fold(text)
        out = set()
        for m in rx2.finditer(t):
            k = norm_key(m.group(1))
            if k not in keys2 or not m.group(1)[0].isupper():
                continue
            before = t[max(0, m.start() - 40):m.start()]
            people = [(forename2(n, orig), orig) for n, orig in keys2[k]]
            for f, orig in people:
                if f:
                    stem = re.escape(fold(f)[:-1] if len(f) >= 5 else fold(f))
                    if re.search(r"\b(?:%s\w{0,2}|%s\.)\s+(?:\S+\s+){0,2}$" % (stem, f[0]), before):
                        out.add(orig)
                elif firms and k not in COMMON:  # an entry naming no person: its capitalised name alone
                    out.add(orig)
        return out
    return link


def verdicts(results, link=None):
    if link is None:
        return {i: s.plan_verdict(r["events"], KEYS, RX) for i, r in results.items()}
    with mock.patch.object(s, "match", link):  # same holding-period rule, only the linking differs
        return {i: s.plan_verdict(r["events"], KEYS, RX) for i, r in results.items()}


KEYS, RX = s.load_keys(s.REDFLAG)


def main():
    docs = json.loads(s.TESTSET.read_text())
    keys2, rx2 = repaired_keys(KEYS)
    reach = lambda fore: sum(any(fore(n, k) for n in names) for k, names in KEYS.items())
    entries = {n for names in KEYS.values() for n in names}
    print(f"The list: {len(entries)} entries under {len(KEYS)} surname keys.")
    print(f"  full-name rule can link {reach(lambda n, k: forename(n))} keys; with word-order repair "
          f"{reach(forename2)}; never (no person forename): {len(KEYS) - reach(forename2)}")
    print(f"  surname keys on the COMMON stop list (never linked above the naive tier): "
          f"{sum(k in COMMON for k in KEYS)}")

    labels = {d["id"]: LABELS.get(d["id"], "not flagged") for d in docs}
    runs = {"P1 (qwen3:8b)": s.prepare(docs, {str(r["id"]): r for r in json.loads((s.HERE / "out" / "run_P1.json").read_text())}),
            "Claude reading": gm.load_events(docs)}
    for name, results in runs.items():
        base = verdicts(results)
        print(f"\n{name}: published linker, screening {s.screening(docs, base, labels)}")
        for variant, firms in (("A people repaired", False), ("B A + firm names", True)):
            v = verdicts(results, linker(keys2, rx2, firms))
            new = sorted(i for i in v if v[i] == "flagged" and base[i] != "flagged")
            lost = sorted(i for i in v if v[i] != "flagged" and base[i] == "flagged")
            print(f"  {variant}: screening on the labelled cases {s.screening(docs, v, labels)}")
            print(f"    newly flagged: {len(new)} = {len([i for i in new if labels[i] == 'flagged'])} labelled flagged, "
                  f"{len([i for i in new if i in LABELS and labels[i] != 'flagged'])} labelled not flagged or uncertain, "
                  f"{len([i for i in new if i not in LABELS])} never labelled {[i for i in new if i not in LABELS]}; "
                  f"no longer flagged: {lost}")


if __name__ == "__main__":
    main()
