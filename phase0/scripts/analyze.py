"""Phase-0 numbers: filter NGA + AIC provenance to 1933-45, match ALIU Red Flag names.
Usage: python -I analyze.py <phase0/data dir>
Writes nga_1933_45.csv, aic_1933_45.csv, matches_*.csv, prints the report numbers."""
import csv, json, random, re, statistics, sys, unicodedata
from collections import Counter
from pathlib import Path

YEAR = re.compile(r"\b19(?:3[3-9]|4[0-5])\b")
# ponytail: hand-picked keys that are months, given names, common words, or (Lugt, Kress) almost always another
# referent (Lugt mark numbers, Samuel H. Kress Foundation). Only used by the "cased" tier; extend after eyeballing.
COMMON = {"may", "ham", "dam", "martin", "simon", "frank", "ernst", "andre", "bernard", "colin", "lang", "michel",
          "engel", "kraft", "baron", "weber", "meyer", "mueller", "schmidt", "fischer", "bauer", "becker", "wolff",
          "frey", "rudolph", "gerard", "voltaire", "jansen", "art ancien", "kramer", "krueger", "unger",
          "zimmermann", "heim", "pohl", "abb", "mak", "dik", "pope", "lange", "berger", "petit", "blanc", "roux",
          "john", "thomas", "hermann", "herbert", "turner", "roy", "lugt", "kress", "albert", "louis", "henri",
          "paul", "charles", "robert", "walter", "georges", "pierre", "jean", "max", "otto", "karl", "hans", "franz"}
TITLES = {"Dr", "Prof", "Frau", "Frl", "Mme", "Mlle", "M", "Mrs", "Mr", "Major", "Count", "Baron", "General", "Lt",
          "Col", "Graf", "Countess", "Prince", "Princess", "Captain", "Colonel", "Herr", "Dott", "Comte", "Abbe"}


def forename(name):
    """'Haberstock, Prof Dr Karl' -> 'Karl'; None if no usable forename."""
    if "," not in name:
        return None
    toks = [t.strip("().") for t in name.split(",", 1)[1].split()]
    toks = [t for t in toks if t and t not in TITLES and not t.startswith("(")]
    return toks[0] if toks and toks[0][:1].isupper() else None


def fold(s):
    """German umlauts -> ue/oe/ae (the list's spelling), then strip remaining accents."""
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("Ä", "Ae"), ("Ö", "Oe"), ("Ü", "Ue"), ("ß", "ss")):
        s = s.replace(a, b)
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def load_keys(path):
    """key -> list of list-entry names sharing that surname key."""
    keys = {}
    for row in csv.DictReader(open(path, encoding="utf-8")):
        for k in row["match_key"].split("|"):
            keys.setdefault(norm_key(fold(k)), []).append(row["name"])
    alts = sorted(keys, key=len, reverse=True)
    pat = r"(?<![\w])(" + "|".join(re.escape(k).replace(r"\ ", r"[\s-]+") for k in alts) + r")(?![\w])"
    return keys, re.compile(pat, re.I)


def norm_key(m):
    return re.sub(r"[\s-]+", " ", m.lower())


def match(text, rx, keys, do_fold=True, tier="naive"):
    """naive: case-insensitive surname. cased: capitalised surname, minus COMMON.
    fullname: cased + the entry's forename (or its initial) within 2 tokens before the surname."""
    t = fold(text) if do_fold else text
    out = set()
    for m in rx.finditer(t):
        k = norm_key(m.group(1))
        if k not in keys:
            continue
        if tier != "naive" and (not m.group(1)[0].isupper() or k in COMMON):
            continue
        if tier == "fullname" and not any(
                re.search(r"\b(?:%s|%s\.)\s+(?:\S+\s+){0,2}$" % (re.escape(fold(f)), f[0]), t[max(0, m.start() - 40):m.start()])
                for f in filter(None, map(forename, keys[k]))):
            continue
        out.add(k)
    return out


def nga(data):
    csv.field_size_limit(10**9)
    rows = list(csv.DictReader(open(data / "nga/objects.csv", encoding="utf-8")))
    withp = [r for r in rows if r["provenancetext"].strip()]
    hits = [{"id": r["objectid"], "title": r["title"], "artist": r["attribution"], "provenance_text": r["provenancetext"],
             "source": "NGA"} for r in withp if YEAR.search(r["provenancetext"])]
    return len(rows), len(withp), hits


def aic(data):
    rows = [json.loads(l) for l in open(data / "aic/aic_provenance.jsonl")]
    rows = list({r["id"]: r for r in rows}.values())
    withp = [r for r in rows if (r.get("provenance_text") or "").strip()]
    hits = [{"id": r["id"], "title": r["title"], "artist": r.get("artist_display") or "", "provenance_text": r["provenance_text"],
             "source": "AIC"} for r in withp if YEAR.search(r["provenance_text"])]
    return len(rows), len(withp), hits


def write(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def context(text, key, width=90):
    m = re.search(re.escape(key).replace(r"\ ", r"[\s-]+"), fold(text), re.I)
    return fold(text)[max(0, m.start() - width): m.end() + width].replace("\n", " ") if m else ""


TIERS = ("naive", "cased", "fullname")


def summarize(label, total, withp, hits, rx, keys, data):
    lens = [len(h["provenance_text"]) for h in hits]
    print(f"\n== {label}: total={total} with_provenance={withp} mention_1933_45={len(hits)} "
          f"median_len={statistics.median(lens):.0f} mean_len={statistics.mean(lens):.0f}")
    per = {t: Counter() for t in TIERS}
    n = Counter()
    rows = []
    for h in hits:
        text = h["provenance_text"]
        n["nofold_cased"] += bool(match(text, rx, keys, do_fold=False, tier="cased"))
        found = {t: match(text, rx, keys, tier=t) for t in TIERS}
        for t in TIERS:
            n[t] += bool(found[t])
            per[t].update(found[t])
        rows.extend({"id": h["id"], "tier": "fullname" if k in found["fullname"] else "cased", "key": k,
                     "list_entry": " / ".join(keys[k]), "context": context(text, k)} for k in found["cased"])
    for t in TIERS:
        print(f"[{t}] texts with >=1 Red Flag name: {n[t]} ({n[t] / len(hits):.1%}); distinct names: {len(per[t])}")
        print(f"[{t}] top15:", per[t].most_common(15))
    print(f"[cased] without umlaut/accent folding: {n['nofold_cased']}")
    write(data / f"matches_{label.lower()}.csv", rows)
    random.seed(7)
    for t in ("cased", "fullname"):
        pool = [r for r in rows if t == "cased" or r["tier"] == "fullname"]
        print(f"-- 20 random [{t}] matches for eyeballing:")
        for r in random.sample(pool, min(20, len(pool))):
            print(f"  [{r['id']}] {r['key']!r} -> {r['list_entry'][:50]!r}: ...{r['context'][:200]}...")
    return per


def main(data):
    data = Path(data)
    keys, rx = load_keys(data / "red_flag_names.csv")
    print("red flag entries -> distinct match keys:", len(keys))
    res = {}
    for label, fn in (("NGA", nga), ("AIC", aic)):
        total, withp, hits = fn(data)
        write(data / f"{label.lower()}_1933_45.csv", hits)
        res[label] = summarize(label, total, withp, hits, rx, keys, data)
    for t in TIERS:
        both = set(res["NGA"][t]) & set(res["AIC"][t])
        print(f"\n[{t}] Red Flag names in BOTH collections: {len(both)}")
        print(sorted(both, key=lambda k: -(res["NGA"][t][k] + res["AIC"][t][k]))[:40])


def demo():
    keys = {"haberstock": ["Haberstock, Prof Karl"], "muehlmann": ["Muehlmann, Dr Kajetan"], "bernheim jeune": ["Bernheim Jeune"],
            "kress": ["Kress, Karl"], "may": ["May, Frau Wismer"]}
    rx = re.compile(r"(?<![\w])(bernheim[\s-]+jeune|haberstock|muehlmann|kress|may)(?![\w])", re.I)
    assert match("Karl Haberstock, Berlin", rx, keys, tier="fullname") == {"haberstock"}
    assert match("K. Haberstock, Berlin", rx, keys, tier="fullname") == {"haberstock"}
    assert match("(Haberstock, Berlin)", rx, keys, tier="fullname") == set()
    assert match("Samuel H. Kress Foundation, May 1938", rx, keys, tier="cased") == set()
    assert match("Samuel H. Kress Foundation", rx, keys) == {"kress"}
    assert match("sold to Karl Haberstock, Berlin, 1938", rx, keys) == {"haberstock"}
    assert match("Kajetan Mühlmann, Vienna", rx, keys) == {"muehlmann"}
    assert match("Galerie Bernheim-Jeune, Paris", rx, keys) == {"bernheim jeune"}
    assert match("Haberstocks", rx, keys) == set()
    assert YEAR.search("(sale, 1938)") and not YEAR.search("1932-1946") and not YEAR.search("19380")


if __name__ == "__main__":
    demo()
    main(sys.argv[1])
