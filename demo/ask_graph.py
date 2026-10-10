"""Ask the provenance graph in plain language. The local model only turns the question into a lookup (about 2 s);
plain code answers it from graph/graph.json in milliseconds, quoting the museum text for every step.

Usage: python3 ask_graph.py "Who owned Saint Jerome in the Wilderness?"
       python3 ask_graph.py "Which works passed through Karl Haberstock?"
       python3 ask_graph.py "From whom did Samuel H. Kress buy?"
       python3 ask_graph.py "Which works passed through a Red Flag dealer between 1938 and 1942?"
"""
import csv
import json
import re
import sys
import time

import extract
import score as s
from analyze import forename  # score puts phase0/scripts on the path
from ask import select_docs

GRAPH = s.HERE / "graph" / "graph.json"
KEYS, RX = s.load_keys(s.REDFLAG)
NOTES = {r["name"]: r["notes"] for r in csv.DictReader(open(s.REDFLAG, encoding="utf-8"))}
KINDS = ("history", "owner_works", "sellers", "red_flag")
GENERIC = re.compile(r"\b(red[\s-]*flag|dealers?|lists?|names?|someone|anyone|anybody|people|persons?|owners?)\b", re.I)
SCOPE = ("This demo answers four kinds of question about 100 National Gallery of Art provenance texts:\n"
         "  who owned an artwork · which works passed through an owner · from whom an owner acquired works ·\n"
         "  which works passed through a name on the 1946 Red Flag list (optionally one owner, optionally a period).")
MODEL = "qwen3:8b"
PROMPT = """Turn a question about artwork ownership into a JSON lookup. Fields:
"kind": one of
  "history"      - who owned one artwork (needs "artwork"),
  "owner_works"  - which artworks passed through one person or firm (needs "owner"),
  "sellers"      - from whom one person or firm acquired works (needs "owner"),
  "red_flag"     - which artworks passed through someone on the Red Flag list of Nazi-era looting suspects,
                   or whether one named person or firm is on that list or was involved in Nazi-era looting
                   (the list's own note answers; put the name in "owner"),
  "none"         - anything else (prices, who painted it, where it is now, opinions, general knowledge),
"artwork": the artwork title named in the question, or null,
"owner": a specific person or firm named in the question, or null (never a category such as "a Red Flag dealer"),
"period": [first_year, last_year] if the question gives years, else null.
Answer with JSON only.

Question: {q}"""


class OutOfScope(ValueError):
    """The question is not one of the lookups the graph can answer."""


def parse(q):
    """Local model reads the question; every field of its answer is checked, never trusted blindly."""
    resp = extract.call_raw(MODEL, PROMPT.format(q=q), max_out=200)  # OSError here means the model is unreachable
    content = resp["message"]["content"]
    try:
        spec = json.loads(content[content.find("{"): content.rfind("}") + 1])
    except ValueError:
        raise OutOfScope("the model did not map the question to a lookup")
    if not isinstance(spec, dict) or spec.get("kind") not in KINDS:
        raise OutOfScope(f"lookup kind {spec.get('kind') if isinstance(spec, dict) else spec!r}")
    p = spec.get("period")
    ok = isinstance(p, list) and len(p) == 2 and all(isinstance(y, int) for y in p) and p[0] <= p[1]
    spec["period"] = p if ok else None  # a half or inverted period from the model is ignored, not trusted
    for field in ("artwork", "owner"):
        v = spec.get(field)
        spec[field] = v.strip() if isinstance(v, str) and v.strip() else None
    if spec["owner"] and not s.tokens(GENERIC.sub(" ", spec["owner"])):
        spec["owner"] = None  # "Red Flag dealer" is a category, not an owner
    return spec


def find_artworks(graph, title):
    """Same title rule as ask.py: case, accents and punctuation ignored; an exact title wins over partial ones."""
    if not title:
        return []
    docs = [{"id": i, "title": a["title"]} for i, a in graph["artworks"].items()]
    return [d["id"] for d in select_docs({"object": title}, docs)]


def find_owners(graph, name):
    """Canonical owners whose name or a written variant matches. An exact name wins (Samuel H. Kress, not also his
    Foundation); otherwise the token rule of the owner scores."""
    exact = sorted(o for o, v in graph["owners"].items() if name and name.lower() in {n.lower() for n in [o] + v["names"]})
    return exact or sorted(o for o, v in graph["owners"].items() if name and any(s.same_owner(name, n) for n in [o] + v["names"]))


def steps(graph, artwork):
    return sorted((h for h in graph["holdings"] if h["artwork"] == artwork), key=lambda h: h["order"])


def seller_step(graph, h):
    """The step before h's acquisition, skipping the co-buyers the reader marked as joint ("sold in 1942 ... to the
    dealers Karl Haberstock and Julius Boehler": Boehler did not buy from Haberstock)."""
    chain = steps(graph, h["artwork"])
    i = next(k for k, x in enumerate(chain) if x is h or x == h)
    while i > 0 and chain[i]["joint"]:
        i -= 1  # back to the first party of the joint group
    return chain[i - 1] if i > 0 else None


def list_entries(owner):
    """Red Flag entries that name this owner: the surname key matches AND the entry's own forename (or its initial)
    is in the owner's name. Entries that share only a surname (Charlotte vs Hans Wendland) are left out; entries that
    stay ambiguous (Julius Boehler Sr and Jr) are all returned, and none is chosen."""
    name = s.fold(s.forward(owner)).lower()
    out = set()
    for k in s.match(s.forward(owner), RX, KEYS, tier="fullname"):
        for n in KEYS[k]:
            f = s.fold(forename(n) or "").lower()
            if f:
                ok = re.search(r"\b%s\b" % re.escape(f), name) or re.search(r"\b%s\." % re.escape(f[0]), name)
            else:  # an entry written without a comma ("Wendland Hans"): all its words must be in the owner's name
                ok = s.tokens(n) <= s.tokens(owner)
            if ok:
                out.add(n)
    return sorted(out)


def surname_entries(owner):
    """List entries that only share a surname with this owner (any case, common surnames included): candidates for
    an expert, never a match."""
    return sorted({n for k in s.match(s.forward(owner), RX, KEYS, tier="naive") for n in KEYS[k]})


def red_flag_steps(graph, artwork, years):
    """Same rule as the scored plans (score.flag_events): a listed owner whose holding period meets the years."""
    chain = steps(graph, artwork)
    events = [{"owner": h["owner"], "year": h["year"], "span_ok": True} for h in chain]  # merged name, as tagged
    flagged = {id(e) for e in s.flag_events(events, KEYS, RX, years)}
    return [h for h, e in zip(chain, events) if id(e) in flagged]


def overlaps(h, period):
    if not period:
        return True
    # a dated holding with no later dated step is open-ended; an undated one lies between the dated steps around it
    # (Rochlitz, undated, between Goering 1941 and 1951), so a period question shows it instead of hiding it
    lo = h["year"] if h["year"] is not None else h.get("since") if h.get("since") is not None else h["until"]
    hi = h["until"] if h["until"] is not None else (9999 if h["year"] is not None else None)
    return lo is not None and lo <= period[1] and hi >= period[0]


def acquired_in(h, period):
    return not period or (h["year"] is not None and period[0] <= h["year"] <= period[1])


def line(graph, h):
    nxt = next((x for x in steps(graph, h["artwork"]) if x["order"] == h["order"] + 1), None) if "artwork" in h else None
    end = h["until"] if nxt is None or nxt["year"] is not None else None  # next holder undated: the end is unknown
    span = f"{h['year'] or '?'}–{end or '?'}"
    flag = "  [RED FLAG LIST]" if s.match(s.forward(h["owner"]), RX, KEYS, tier="fullname") else ""  # same test as red_flag_steps
    weak = "" if s.tokens(h["as_written"]) & s.tokens(h["quote"]) else "  (the quote does not name this owner)"
    hedge = f"[{h['hedge']}] " if h.get("hedge") else ""
    return f"   {hedge}{h['owner']} ({h['role']}, {span}){flag}: \"{h['quote'][:150]}\"{weak}"


def owner_on_list(graph, owner):
    """What the 1946 list says about one named owner, in its own words, without a verdict."""
    names = find_owners(graph, owner) or [owner]  # the graph's full names ("Count Alessandro ...") beat the words typed
    listed = sorted({n for o in names for n in list_entries(o)})
    out = []
    if len(listed) > 1:
        out.append(f"NOTE  {len(listed)} list entries match this name; the text does not say which one is meant.")
    out += [f"LIST ENTRY  {n}: \"{NOTES[n]}\"" for n in listed]
    if not listed:
        near = sorted({n for o in names for n in surname_entries(o)})
        out += [f"SAME SURNAME ON THE LIST (not confirmed as this person)  {n}: \"{NOTES[n]}\"" for n in near]
        out.append(f"NO LIST ENTRY MATCHED  \"{owner}\" by the full-name rule. This is not proof of absence: "
                   "the matcher misses some spellings and list entries.")
    return out + ["The list records suspicion by 1946 investigators, not a verdict on the person."]


def answer(graph, spec):
    """Lines of the answer; every claim carries the quote it rests on."""
    kind, period = spec["kind"], spec["period"]
    title = lambda i: f"NGA {i} · {graph['artworks'][i]['title']}"
    if kind == "history":
        ids = find_artworks(graph, spec.get("artwork"))
        if not ids:
            return [f"NOT IN GRAPH  no artwork titled \"{spec.get('artwork')}\" among the {len(graph['artworks'])} records"]
        museum = lambda i: [f"   then National Gallery of Art ({graph['museum'][i]['year'] or '?'}): \"{graph['museum'][i]['quote'][:150]}\""]
        return [x for i in ids for x in [title(i)] + [line(graph, h) for h in steps(graph, i) if overlaps(h, period)]
                + (museum(i) if i in graph.get("museum", {}) and not period else [])]
    if kind == "red_flag":
        lo, hi = period or [1933, 1945]
        hits = [h for i in graph["artworks"] for h in red_flag_steps(graph, i, range(lo, hi + 1))]
        out = []
        if spec.get("owner"):
            out = owner_on_list(graph, spec["owner"])
            owners = find_owners(graph, spec["owner"])
            hits = [h for h in hits if h["owner"] in owners]
        out += [f"{len({h['artwork'] for h in hits})} artworks passed through "
                f"{'this owner as a listed name' if spec.get('owner') else 'a Red Flag name'} in {lo}-{hi}"]
        return out + [x for i in dict.fromkeys(h["artwork"] for h in hits)
                      for x in [title(i)] + [line(graph, h) for h in hits if h["artwork"] == i]]
    owners = find_owners(graph, spec.get("owner"))
    if not owners:
        return [f"NOT IN GRAPH  no owner matching \"{spec.get('owner')}\""]
    out = [f"matched owner(s): {', '.join(owners)}"]
    for h in [h for h in graph["holdings"] if h["owner"] in owners]:
        if kind == "owner_works" and overlaps(h, period):
            out += [title(h["artwork"]), line(graph, h)]
        elif kind == "sellers" and acquired_in(h, period):  # a period here means: acquired in those years
            prev = seller_step(graph, h)
            if prev and prev["owner"] not in owners:  # Kress -> Kress Foundation is not a purchase from a seller
                out += [title(h["artwork"]), line(graph, prev), line(graph, h)]
    return out if len(out) > 1 else out + ["   no matching holdings"]


def main():
    q = " ".join(sys.argv[1:])
    if not q:
        raise SystemExit(__doc__)
    graph = json.loads(GRAPH.read_text())
    t0 = time.time()
    try:
        spec = parse(q)
    except OSError as e:
        raise SystemExit(f"could not reach {MODEL} ({e}); is Ollama running?")
    except (ValueError, KeyError, TypeError) as e:  # includes OutOfScope
        raise SystemExit(f"QUESTION  {q}\nOUT OF SCOPE  ({e})\n{SCOPE}")
    t1 = time.time()
    lines = answer(graph, spec)
    print(f"QUESTION  {q}\nLOOKUP    {json.dumps(spec)}  (read by {MODEL} in {t1 - t0:.1f} s)\n")
    print("\n".join(lines))
    print(f"\nanswered from the graph in {(time.time() - t1) * 1000:.0f} ms. Candidates and evidence for an expert, "
          "not a finding about any person or a restitution claim.")


if __name__ == "__main__":
    main()
