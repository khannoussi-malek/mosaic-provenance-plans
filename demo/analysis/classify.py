"""First-cause labels (mosaic-eval taxonomy) for every owner FP/FN of P1-P3. Read-only: reuses score.py, changes nothing.
Usage: python3 analysis/dump_errors.py P1 P2 P3 && python3 analysis/classify.py P1 P2 P3
Writes analysis/labels_<plans>.json and prints counts.

How labels are made: ordered rules below, then OVERRIDES. Every 'named party not in gold' FP and every FN in the
2026-10-07 run outputs was read against its source text; OVERRIDES record the cases where the rule's label was wrong.
ponytail: rule order + override table; new run outputs need a fresh read of the residual 'gold omits' bucket."""
import difflib
import json
import re
import sys
from pathlib import Path

DEMO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DEMO))
import score  # noqa: E402

GENERIC = {"new", "york", "london", "paris", "art", "market", "private", "estate", "heirs", "heir", "sons", "son", "ltd",
           "company", "inc", "fund", "foundation", "trust", "his", "her", "their", "widow", "wife", "husband", "daughter",
           "family", "possibly", "probably", "nga", "national", "berlin", "munich", "vienna", "sir", "lord", "lady",
           "duke", "earl", "bt", "bart", "fine", "arts", "galleries", "zurich", "geneva", "amsterdam", "boston",
           "philadelphia", "washington", "museum", "jr", "sr"}
ABBR = {"thos": "thomas", "generale": "general", "georges": "george", "educational": "education"}
NGA = re.compile(r"^(the )?(nga|national gallery( of art)?)( \(nga\))?(, washington(, d\.?c\.?)?)?$", re.I)
ESTATE = re.compile(r"^(his|her|their)( \w+)? (estate|heirs)$|estate$|^(the )?estate of|^\w+ estate$|heirs$", re.I)
ARTIST = re.compile(r"^the (artist|sitter)\b", re.I)
UNNAMED = re.compile(r"private collection|art market|anonymous|one of her sons|a church|family$|^nazi", re.I)
CUSTODIAN = re.compile(r"collecting point|government|embassy|office des|zentraldepot|^france$", re.I)
SALE_EVENT = re.compile(r"^\(?(\w+ )?(his |her )?(estate )?sale\b|^\(sale", re.I)
AUCTION = re.compile(r"georges petit|drouot|christie|sotheby|american art association|knight, frank|hollstein|manzi|^sale, ", re.I)
FOOTNOTE = re.compile(r"\n\s*\[1\]")
ws = lambda s: re.sub(r"\s+", " ", s or "")

# (doc id, kind, regex on name) -> (category, note). Each one read against the source text.
OVERRIDES = [
    ("52199|119049", "FP", r"Je[a-z]* de Paume", "role-wrong", "ERR depot named instead of the agency (gold: ERR)"),
    ("73852", "FP", r"People's Commissars|salt mine", "hallucinated-owner", "decree issuer / storage place, not a holder"),
    ("34659", "FP", r"Alt Aussee", "hallucinated-owner", "storage place, not a holder"),
    ("139276", "FP", r"zone$|Allied forces|Control Council", "hallucinated-owner", "occupation zone / army, not a holder"),
    ("172", "FP", r"Christie|Sotheby|Cassirer", "hallucinated-owner", "text says the work was NOT in these sales"),
    ("126155", "FP", r"National Academy", "hallucinated-owner", "exhibition venue"),
    ("195291", "FP", r"Detroit", "hallucinated-owner", "exhibition venue"),
    ("139202", "FP", r"studio stamp", "hallucinated-owner", "collector's mark taken as owner"),
    ("3748", "FP", r"^\[1\]$", "hallucinated-owner", "footnote marker taken as owner"),
    ("119049", "FP", r"Feldpolizei", "hallucinated-owner", "unit not stated as holder"),
    ("143662", "FP", r"Koenig$|McCrindle$", "gold-disagrees-with-text", "text: 'Wilhelm Koenig'; gold: 'Koenigs, Franz Wilhelm' / omits McCrindle"),
    ("139276|139213", "FP", r"^Wolfgang Ratjen", "gold-disagrees-with-text", "text names Wolfgang Ratjen; gold has only Stiftung Ratjen"),
    ("139213", "FP", r"Ratjen Foundation", "matcher-error", "Ratjen Foundation = Stiftung Ratjen (translation)"),
    ("3199", "FP", r"Burlett", "gold-disagrees-with-text", "text 'De Burlett'; gold resolves to Charles A. de Burlet, a note says only 'possibly'"),
    ("1262", "FP", r"Widener", "split-or-merged-owner", "Joseph E. Widener folded into Peter A.B. Widener's estate"),
    ("157925", "FP", r"^Paul Mellon", "gold-disagrees-with-text", "text names Paul Mellon; gold omits him"),
    ("72164", "FP", r"Salm", "gold-disagrees-with-text", "her son Count Peter A. Salm, omitted by gold"),
    ("1512", "FP", r"Alfred Charles", "gold-disagrees-with-text", "nephew who inherited, omitted by gold"),
    ("139202", "FP", r"Beatrice", "gold-disagrees-with-text", "named holder omitted by gold"),
    ("130843", "FP", r"^Galka", "split-or-merged-owner", "second form of Emmy (Galka) Scheyer"),
    ("69390", "FP", r"H\.M\. Clark\)$", "split-or-merged-owner", "two dealers merged into one owner"),
    ("69390", "FP", r"^Thos\. Agnew & Sons, Ltd\.$", "matcher-error", "Thos. = Thomas"),
    ("51136", "FP", r"Knoed,ler", "split-or-merged-owner", "Knoedler listed twice (text twice, gold once)"),
    ("229508", "FP", r"private collection", "matcher-error", "gold 'Private Collection (NGA Former Owner)', taken by the NGA event"),
    ("46081", "FP", r"Sattler sale", "role-wrong", "sale event used as owner"),
    ("46081", "FP", r"Munich art market", "gold-disagrees-with-text", "text 'Munich art market'; gold 'Art market, Paris' x2"),
    ("41639", "FN", r"Kleinberger", "gold-disagrees-with-text", "note: 'no convincing evidence' Pratt acquired it from Kleinberger"),
    ("46081", "FN", r"Art market, Paris", "gold-disagrees-with-text", "text says Munich art market"),
    ("32679", "FN", r"Sale, Paris", "matcher-error", "placeholder gold name for an anonymous sale"),
    ("32679", "FN", r"Orlowski, Mieczyslaw|Wildenstein", "matcher-error", "Wildenstein event matched gold 'Sale, Paris' on token 'paris'; chain shifts"),
    ("3155", "FN", r"Mrs\.", "gold-disagrees-with-text", "gold lists the couple and the wife separately"),
    ("95|34068|1117|34105", "FN", r"Garcia, Sabasa|Melvill|Stow, Edward|Huntington", "gold-disagrees-with-text",
     "text says 'the sitter'/'the artist'; gold uses the name from object metadata"),
    ("34105", "FN", r"American Art Association", "gold-disagrees-with-text", "text: Anderson Galleries sale"),
    ("47182", "FN", r"Viscount", "gold-disagrees-with-text", "not named as owners in the text"),
    ("111", "FN", r"Willoughby", "gold-disagrees-with-text", "note [1]: 2nd-4th Bts added to the database, not in text"),
    ("139202", "FN", r"Ratjen", "gold-disagrees-with-text", "text names Wolfgang Ratjen; gold has Stiftung Ratjen"),
    ("46090", "FN", r"Levy Fund", "gold-disagrees-with-text", "no Fund in the text"),
    ("1117", "FN", r"Hyatt", "matcher-error", "gold misspells 'Adalaide'"),
    ("46258", "FN", r".", "omitted-main-text", "P2 output stops after 3 of 7 owners"),
    ("277", "FN", r"Kress", "gold-disagrees-with-text", "text names only the Foundation; its event was assigned to gold 'Kress, Samuel H.'"),
    ("73398", "FN", r"hler, Julius", "split-or-merged-owner", "'Karl Haberstock and Julius Boehler' extracted as one owner"),
    ("119049", "FN", r"Seligmann", "name-variant", "P2 wrote 'Ånder J. Seligmann' for 'André J. Seligmann' (name and span)"),
    ("73852", "FN", r"Library of the Ukrainian", "omitted-main-text", "named in main text (spelled 'Ukranian'), not extracted"),
]


def toks(name):
    return {ABBR.get(x, x) for x in re.findall(r"[a-z]+", score.fold(name).lower()) if len(x) > 1 and x not in score.STOP}


def core(name):
    return toks(name) - GENERIC


def near(a, b):
    """Same entity by fuzzy distinctive tokens (spelling, initials, Co./Company, Thos./Thomas)."""
    ca, cb = core(a), core(b)
    return bool(ca and cb) and any(difflib.SequenceMatcher(None, x, y).ratio() >= 0.8
                                   for x in ca for y in cb if min(len(x), len(y)) >= 4)


def where(name, text):
    """'main', 'footnote' or 'absent': where the name's distinctive tokens occur."""
    body = score.fold(text).lower()
    cut = FOOTNOTE.search(body)
    main, notes = (body[:cut.start()], body[cut.start():]) if cut else (body, "")
    words = [w for w in core(name) if len(w) >= 3] or [w for w in toks(name) if len(w) >= 3]
    hit = lambda part: any(re.search(r"\b" + re.escape(w), part) for w in words)
    return "main" if hit(main) else "footnote" if hit(notes) else "absent"


def override(did, kind, name):
    return next(((c, n) for ids, k, rx, c, n in OVERRIDES
                 if k == kind and did in ids.split("|") and re.search(rx, name)), None)


def label_fp(e, text, r):
    owner = e["owner"].strip()
    if NGA.match(owner):
        return "matcher-error", "receiving museum (NGA): gold lists previous owners only"
    if any(near(owner, g) for g in r["fn"]):
        verbatim = all(re.search(r"\b" + re.escape(w), score.fold(text).lower()) for w in core(owner) - set(ABBR.values()))
        return ("matcher-error", "same entity; token-subset match misses it") if verbatim else \
               ("name-variant", "model changed the name")
    if ESTATE.search(owner) or any(near(owner, g) or score.same_owner(owner, g) for _, g in r["tp"]):
        return "split-or-merged-owner", "duplicate of a matched owner (estate, heirs, repeat mention)"
    if ARTIST.match(owner):
        return "gold-disagrees-with-text", "artist/sitter holds it in the text; gold omits"
    if SALE_EVENT.match(owner):
        return "role-wrong", "sale event used as owner"
    if CUSTODIAN.search(owner):
        return "gold-disagrees-with-text", "custodian/state named in text; gold omits"
    if UNNAMED.search(owner):
        return "gold-disagrees-with-text", "unnamed holder in text; gold omits"
    return "gold-disagrees-with-text", "named holder in text (read); gold omits"


def label_fn(g, text, r, fp_labels):
    if r["error"] and not r["events"]:
        return "run-error", "parse failure or truncation: no events"
    pairs = [fp_labels[o] for o in fp_labels if near(g, o)]
    if pairs:
        rank = ["matcher-error", "name-variant", "role-wrong", "gold-disagrees-with-text"]
        return min(pairs, key=lambda c: rank.index(c[0]) if c[0] in rank else 9)
    uns = [u for u in r["unsupported"] if score.same_owner(u["owner"], g) or near(u["owner"], g)]
    if uns:
        only_ws = any(u["span"] and ws(u["span"]) in ws(text) for u in uns)
        return "span-not-verbatim", "differs from text only in whitespace" if only_ws else "span not in text"
    kress = re.match(r"Kress( Foundation)?, Samuel H\.", g)
    if kress and not (re.search(r"Kress Foundation", text) if kress.group(1) else re.search(r"Samuel H\. Kress(?! Foundation)", text)):
        return "gold-disagrees-with-text", "gold lists both Kress and Kress Foundation; text names one"
    loc = where(g, text)
    if loc == "absent":
        return "gold-disagrees-with-text", "gold owner not named in the text"
    if AUCTION.search(g):
        return "role-wrong", "auction house not treated as an owner"
    if loc == "footnote":
        return "footnote-missed", "named only in a footnote"
    if any(near(g, o) or score.same_owner(g, o) for o, _ in r["tp"]):
        return "split-or-merged-owner", "merged into another extracted owner"
    return "omitted-main-text", "named in main text, not extracted (no taxonomy cause fits)"


def main(plans):
    docs = {d["id"]: d for d in json.loads(score.TESTSET.read_text())}
    rows = json.loads((DEMO / "analysis" / f"per_doc_{'-'.join(plans)}.json").read_text())
    out = []
    for did, row in rows.items():
        text = docs[did]["provenance_text"]
        for p in plans:
            r = row["plans"][p]
            fp_labels = {}
            for e in r["fp"]:
                cat, why = override(did, "FP", e["owner"]) or label_fp(e, text, r)
                fp_labels[e["owner"]] = (cat, why)
                out.append({"id": did, "plan": p, "kind": "FP", "name": e["owner"], "cat": cat, "why": why,
                            "stratum": row["stratum"]})
            for g in r["fn"]:
                cat, why = override(did, "FN", g) or label_fn(g, text, r, fp_labels)
                out.append({"id": did, "plan": p, "kind": "FN", "name": g, "cat": cat, "why": why,
                            "stratum": row["stratum"]})
    (DEMO / "analysis" / f"labels_{'-'.join(plans)}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return out


def _check():
    assert near("Thos. Agnew & Sons, Ltd.", "Agnew & Sons, Ltd., Thomas")
    assert near("Gustave Rochlitz", "Rochlitz, Gustav") and not near("Wildenstein", "Rochlitz, Gustav")
    assert NGA.match("National Gallery of Art (NGA)") and NGA.match("National Gallery") and not NGA.match("National Gallery, London")
    assert ESTATE.search("his estate") and SALE_EVENT.match("(his sale)") and not SALE_EVENT.match("Sotheby's")


if __name__ == "__main__":
    _check()
    from collections import Counter
    res = main(sys.argv[1:] or ["P1", "P2", "P3"])
    for p in sorted({r["plan"] for r in res}):
        for k in ("FP", "FN"):
            print(p, k, sum(r["kind"] == k for r in res if r["plan"] == p),
                  Counter(r["cat"] for r in res if r["plan"] == p and r["kind"] == k).most_common())
