"""Parse ALIU Red Flag Names from the lootedart.com HTML transcription.
Usage: python -I red_flag_parse.py <page.html> <out.csv>
Each <p>/<div> block after 'ALIU LIST OF RED FLAG NAMES' is one entry; ALL-CAPS blocks are country headers.
match_key = text before first comma (or first '.'), leading lowercase particles dropped,
'(or X)' variants split out. ponytail: heuristic, firms/aliases are imperfect; eyeball the CSV."""
import csv, html, re, sys

PARTICLES = re.compile(r"^(?:(?:von|van|de|da|di|du|der|den|le|la|zu|ten)\s+|d’|l’)+")
ALIAS = re.compile(r"\((?:or |possibly )?([^)?]+)\??\)")
# ponytail: hand fixes for 'Surname Firstname.' entries with no comma; extend when eyeballing finds more
OVERRIDES = {"Abetz Otto": "Abetz", "Adriani Gert": "Adriani", "Welz Friedrich": "Welz", "Wendland Hans": "Wendland",
             "Wuester Adolf": "Wuester", "Weyll Mrs Jane": "Weyll", "Yousoupoff Prince": "Yousoupoff",
             "Bobrowski Lt Col": "Bobrowski", "Boehm Dr Franz": "Boehm", "Wildenstein Paris": "Wildenstein",
             "Wannieck Paris": "Wannieck", "Wilkinson Tudor Paris": "Wilkinson Tudor", "Nuss Reported to be a member of ERR": "Nuss"}
FIRM_SUFFIX = re.compile(r"\s+(?:et Cie|& Co|Gallery|Galerie|Bank|Company|Freres|Soeurs|NV|SA)$")
CONTINUATION = ("Reported ", "Former director", "Dealer, ", "Dealers. ")


def blocks(raw):
    start = raw.find("ALIU LIST OF RED FLAG NAMES")
    end = raw.find("Back to top", start)
    body = re.sub(r"(?is)<script.*?</script>", "", raw[start:end])
    body = re.sub(r"(?i)<br\s*/?>\s*<br\s*/?>|</p>|</div>", "\n", body)
    body = re.sub(r"<[^>]+>", "", body)
    for line in html.unescape(body).replace("\xa0", " ").split("\n"):
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            yield line


def keys(entry):
    head = entry.split(",")[0] if "," in entry.split(".")[0] else entry.split(".")[0]
    variants = ALIAS.findall(head)
    head = ALIAS.sub("", head).strip()
    head = OVERRIDES.get(head, head).strip("‘’ ")
    out = [FIRM_SUFFIX.sub("", PARTICLES.sub("", head)).strip("‘’ ")] + [v.strip() for v in variants]
    return [k for k in out if len(k) >= 3]


def parse(raw):
    country, rows, seen = "Germany", [], set()  # GERMANY header shares a block with the title
    for line in blocks(raw):
        if line.startswith("ALIU LIST"):
            continue
        if line.startswith("Source") or line.startswith("NARA") or line.startswith("http") or line.startswith("accessed"):
            continue
        if line.isupper() and len(line.split()) <= 2:
            country = line.title()
            continue
        if line in seen:  # page repeats some entries verbatim (e.g. Bachstitz)
            continue
        seen.add(line)
        if line.startswith(CONTINUATION) and rows:  # paragraph split mid-entry in the HTML
            rows[-1]["notes"] = (rows[-1]["notes"] + " " + line)[:400]
            continue
        ks = keys(line)
        if ks:
            rows.append({"name": line.split(".")[0].strip(), "match_key": "|".join(ks),
                         "country_of_activity": country, "notes": line[:400],
                         "how_obtained": "parsed from HTML transcription at https://www.lootedart.com/MVI3RM469661 (source: NARA)"})
    return rows


def demo():
    assert keys("von Behr, Baron Kurt. As head of ERR") == ["Behr"]
    assert keys("Barthel (or Bartel), Dr Gustav. Took part") == ["Barthel", "Bartel"]
    assert keys("von der Heydt, Eduard. Ascona") == ["Heydt"]
    assert keys("Engrand (Lengrand?). Paris") == ["Engrand", "Lengrand"]
    assert keys("Abetz Otto. German Ambassador") == ["Abetz"]
    assert keys("Knoedler et Cie. Paris, 17 place Vendome") == ["Knoedler"]
    assert keys("Badels. Reported to have worked for ERR, Paris.") == ["Badels"]


if __name__ == "__main__":
    demo()
    raw = open(sys.argv[1], encoding="utf-8", errors="replace").read()
    rows = parse(raw)
    with open(sys.argv[2], "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    from collections import Counter
    print(len(rows), "entries", Counter(r["country_of_activity"] for r in rows))
