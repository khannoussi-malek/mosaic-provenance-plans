"""Build the Chicago owner-check page: union of owners extracted by P1-P3 on the 20 AIC texts.

Usage: python3 make_aicpage.py TEMPLATE.html OUT.html
Each owner gets a stable key (normalised name), so answers can be scored per plan afterwards.
"""
import json
import sys
from pathlib import Path

import score as s

OUT = s.HERE / "out"


def key(name):
    return " ".join(sorted(s.tokens(name))) or name.lower().strip()


def main():
    template, out = sys.argv[1:3]
    docs = json.loads((s.HERE / "data" / "aic20.json").read_text())
    runs = {p: {str(r["id"]): r for r in json.loads((OUT / f"aic_{p}.json").read_text())} for p in ("P1", "P2", "P3")}
    cases = []
    for d in docs:
        owners = {}
        for p, res in runs.items():
            for e in res.get(str(d["id"]), {}).get("events", []):
                k = key(e["owner"])
                o = owners.setdefault(k, {"key": k, "name": e["owner"], "role": e.get("role"), "date": e.get("date"), "plans": []})
                if p not in o["plans"]:
                    o["plans"].append(p)
        cases.append({"id": str(d["id"]), "title": d["title"], "artist": d["artist"], "text": d["provenance_text"],
                      "owners": list(owners.values())})
    (s.HERE / "data" / "aic_cases.json").write_text(json.dumps(cases, indent=1, ensure_ascii=False))
    html = Path(template).read_text().replace("__CASES__", json.dumps(cases, ensure_ascii=False).replace("</", "<\\/"))
    Path(out).write_text(html)
    print(f"{len(cases)} AIC cards, {sum(len(c['owners']) for c in cases)} distinct owners -> {out}")


if __name__ == "__main__":
    main()
