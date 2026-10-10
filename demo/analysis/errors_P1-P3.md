# Error analysis: P1 (qwen3:8b), P2 (qwen2.5:14b), P3 (cascade) on the NGA test set

n = 100 documents, 540 gold owners (NGA's structured owner list), 31 silver-flagged documents. Screening labels are **silver** (gold owners + Red Flag full-name matcher, `score.silver_label`), not checked by a human. Nothing was tuned or rerun; `score.py` and `out/run_*.json` are unchanged (`score.py --ci` was run once to read intervals; it rewrites `out/plan_table.json` with the same values).

How the labels were made: `analysis/classify.py` applies ordered rules, then a table of hand-checked overrides. Every false positive (FP) the rules could not attribute to the matcher, duplicates or NGA itself (about 160 unique (doc, name) items), and every false negative (FN) were read against the source text. One first cause per error. Categories outside the taxonomy: `run-error` (parse failure or truncation, no events) and `omitted-main-text` (owner named in the main text, not extracted, no other cause fits).

Scripts (all read-only): `dump_errors.py` (per-document TP/FP/FN, same matching as `score.owner_scores`), `classify.py`, `screening_diff.py`, `escalation.py`, `tables.py`. Outputs: `per_doc_P1-P2-P3.json`, `labels_P1-P2-P3.json`, `screening_P1-P2-P3.json`, `escalation_P3.json`.

## Headline

1. **Most owner "errors" come from the evaluation, not the models.** For P1, 217 of 266 FPs and 45 of 99 FNs are `matcher-error` or `gold-disagrees-with-text`. Proportions are similar for P2 and P3.
2. **Of the matcher errors, 87-96 per plan are one thing: the event for NGA itself.** The prompt asks for "every owner or custodian", and the texts end with "purchased ... by NGA", but gold lists previous owners only. Dropping that event alone moves owners F1 from 0.707 to 0.766 (P1), 0.724 to 0.779 (P2) and 0.732 to 0.792 (P3).
3. **Model-side errors are few and of four kinds:** duplicates or merged owners, auction houses not treated as owners, spans that are not verbatim, and two parse failures in P1 and three in P2. Footnote misses, the expected main failure, are rare (1-2 per plan). In footnotes the models extract **too much**, not too little.
4. **Screening: P2 loses 3 silver-flagged documents relative to P1 and gains none.** The causes are two date errors and one early stop (Q2). About half of the misses shared by all plans are silver-label or Red Flag matcher problems.
5. **Escalation (P3) fixed what triggered it in 7 of 21 documents.** Almost all of the owner gain over P1 comes from the 2 P1 parse failures (+19 of +23 TP). No verdict changed. Escalation made 3-4 documents slightly worse.

## Q1. Owner errors by first cause

| category | P1 FP | P1 FN | P2 FP | P2 FN | P3 FP | P3 FN |
|---|---|---|---|---|---|---|
| matcher-error | 117 | 23 | 104 | 20 | 116 | 21 |
| gold-disagrees-with-text | 100 | 22 | 97 | 22 | 101 | 22 |
| split-or-merged-owner | 32 | 5 | 33 | 6 | 36 | 7 |
| role-wrong | 5 | 11 | 4 | 9 | 2 | 12 |
| hallucinated-owner | 12 | 0 | 5 | 0 | 9 | 0 |
| span-not-verbatim | 0 | 6 | 0 | 11 | 0 | 4 |
| footnote-missed | 0 | 1 | 0 | 2 | 0 | 1 |
| name-variant | 0 | 0 | 0 | 1 | 0 | 0 |
| omitted-main-text | 0 | 9 | 0 | 7 | 0 | 9 |
| run-error | 0 | 22 | 0 | 18 | 0 | 0 |
| **total** | 266 | 99 | 243 | 96 | 264 | 76 |

Category definitions, as applied here: `role-wrong` is mostly an auction house or ERR depot not treated as the owner, or a sale event used as the owner. `hallucinated-owner` is an entity that is in the text but is not a holder: a place, an exhibition venue, a collector's mark, a negated sale.

### Evaluation-side findings (report prominently)

**matcher-error (scorer)**
- *Receiving museum*: the "NGA" / "National Gallery" event (P1 95, P2 87, P3 96 FPs). Example 229508, "...acquired 2023 by Galerie Kugel, Paris; purchased 2024 by NGA." In this document the NGA event is also matched to gold "Private Collection (NGA Former Owner)" on the token `nga`. That is a false TP, and the real "Belgian private collection" event becomes an FP.
- *Same entity, token-subset fails* (P1 22 FP / 23 FN pairs; P2 17/20; P3 20/21):
  - 52199: "Gustave Rochlitz" vs gold "Rochlitz, Gustav".
  - 69390: "Thos. Agnew & Sons, Ltd." vs "Agnew & Sons, Ltd., Thomas".
  - 34068: "Thomas B. Clarke [1848-1931], New York" vs "Clarke, Thomas Benedict".
  - 72164: "Millicent Rogers [1902-1953]" vs "Rogers, Huttleston, Mrs.".
  - 563: the text says "Mellon Education and Charitable Trust", gold says "Educational".
  - 1117: gold misspells "Adalaide".
- *Wrong assignments by the greedy subset match*: 32679 "Wildenstein & Co., Inc., Paris, New York, and London" is scored as a hit for gold "Sale, Paris" (token `paris`). Wildenstein then counts as missed.
- *Whitespace*: 13 of the 37 unsupported events across plans (P1 5/11, P2 4/20, P3 4/6) fail the substring test only because the source has a double space. Example 139202, "sold 1972 to  Wolfgang Ratjen". These are counted under `span-not-verbatim` but are a scorer artefact.

**gold-disagrees-with-text** (about 100 FPs and 22 FNs per plan; P1 counts below). Most of these (87 of 100 for P1) are named holders **in the main text** that NGA's list omits:
- Named holder omitted by gold (64): 119837, gold is only "Rifkind, Robert Gore"; the text is "The artist [1880-1938]; his estate; (Galerie Roman Norbert Ketterer, Campione d'Italia, Switzerland); (Galleria Henze, Campione d'Italia); purchased c. 1979 by Robert Gore Rifkind". 73851, gold omits the Goya family, Paul Lebas and Alfred Strölin. Print documents (3773, 3592, 10566) omit "(C.G. Boerner, Leipzig ...)" and "(Charles Sessler, Philadelphia)".
- Red Flag names omitted by gold: 66424, note [1], "Goering is documented as having traded the painting to Gustav Rochlitz, who claimed to have sold it to Hans Wendland". 46682, "sold 1916 to Hans Wendland [b. 1880]". Hans Wendland is on the Red Flag list. A screening plan that extracts him is penalised on owners.
- Custodians (7) and unnamed holders (11): 139276 "Collecting Point at Marburg"; 119049 "Office des Biens Privés"; 73852 "private collection, Nuremberg". Gold is inconsistent here: it lists "Munich Central Collecting Point" in 73398 and 52199, but not the Marburg or Wiesbaden collecting points.
- Artist or sitter (8 FP + 4 FN): the text says "The sitter [b. 1790]" (95) and gold uses the name from the object metadata ("Garcia, Sabasa"). The same happens in 34068, 1117 and 34105.
- Gold names not in the text:
  - 111, note [1]: "The 2nd through 4th Baronets Willoughby added to the former owner table in the NGA collection database are pe[rhaps]...".
  - 143662: the text has "Wilhelm Koenig [1881-1941], Vienna (Lugt 2653b)", gold has "Koenigs, Franz Wilhelm".
  - 46081: the text has "Munich art market", gold has "Art market, Paris" twice.
  - 41639: gold lists Kleinberger, the note says "there is no convincing evidence that Pratt actually acquired the work from Kleinberger's".
  - 277 / 165: gold lists both "Kress, Samuel H." and "Kress Foundation"; the text names only one of them.

**Upper bound, for illustration only (not a score).** Dropping NGA and resolving the matcher pairs gives owners F1 0.805 (P1), 0.812 (P2) and 0.827 (P3). If the gold-disagrees items were also accepted, the figures would be about 0.90, 0.91 and 0.92. That last step rests on my reading of the text, so it is an upper bound.

### Model-side errors

- **split-or-merged-owner** (32-36 FP, 5-7 FN). 34105: "his estate" listed as its own owner, twice. 73398: "Karl Haberstock and Julius Boehler" extracted as one owner, so Böhler, a Red Flag dealer, is missed. 69390 (P2/P3): "(Thos. Agnew & Sons, Ltd., London, and the dealer H.M. Clark)" as one owner.
- **role-wrong** (P1 16, P2 13, P3 14). The auction house is not treated as an owner when the text gives "(his sale, ...)": 11589 "(his sale, Hôtel Drouot, Paris, 12-16 April 1880, no. 228)", where P2's owner is "(his sale)"; 47182 and 66424 Sotheby's. The ERR depot is named instead of the agency: 52199 P1 "Jeume de Paume" (also misspelled; gold has ERR).
- **hallucinated-owner** (P1 12, P2 5, P3 9; for P1, 9 of the 12 come from footnotes). 172: Christie's, Sotheby's and Cassirer & Helbing are extracted from "The painting was not included in sales from Fairfax Murray's estate held at Christie's ... Sotheby's ... Cassirer & Helbing". 139202 P1: "Blechen's studio stamp (Lugt 263b)" as owner. 34659: "salt mine at Alt Aussee" as owner.
- **span-not-verbatim** (FN P1 6, P2 11, P3 4). 139276 P2: the span "; his son-in-law, Fred Triest ..." is not in the text, because the text has a footnote marker between the semicolon and "his". 61369 P1: the owner "William A. Cargill" is paired with a span about Montandon.
- **run-error.** P1: 46090 ("JSONDecodeError ... truncated at 2048 tokens") and 46681. P2: 182, 41639, 1117. Together these explain 22 P1 FNs and 18 P2 FNs.
- **omitted-main-text** (7-9). 73852 P1/P3: "took the Lubomirski Dürer drawings to Adolf Hitler in Berlin", and Hitler is not extracted. 46258 P2: output stops after 3 of 7 owners (198 output tokens, no error).
- **footnote-missed** (1-2). 119049: "ERR card no. SEL 545" in a note, so ERR is missed by all plans.
- **name-variant** (1). 119049 P2: "Ånder J. Seligmann" for "André J. Seligmann", in both the owner and the span.

## Q2. Why P2 is not better than P1 at screening

P1 and P2 disagree on **3 of 100** documents. All 3 are silver-flagged; P1 flags them and P2 does not. P2 flags nothing that P1 misses. The bootstrap interval for screening F1 P2 − P1 is (−0.179, 0.0), so there is no clear difference, but all of the observed mass is ≤ 0.

| doc | silver trigger | P1 | P2 | first cause (P2) |
|---|---|---|---|---|
| 46488 | Bignou 1930-33 | "Étienne Bignou" year null, next dated 1933 → flagged | Events reordered: Bignou given 1933 (the Chester Dale sale date) and placed before "Raphael Gérard, May 1930". The holding period runs backwards (1933→1930), so not flagged | date-wrong (ordering) |
| 46258 | Contini Bonacossi 1935 | flagged (an event "1878-1955" lifespan used as year; the period still meets 1935) | output stops after Cicognara, Conti, Trivulzio; Contini is never extracted | omitted (early stop) |
| 66424 | Rochlitz 1941 | "Gustav Rochlitz" 1941, "Hans Wendland" 1941 → flagged | both extracted with year null; the next dated event is 1951 → not flagged | date-wrong (footnote year not carried) |

Pattern: P2 leaves more years empty (242 null years vs 210 for P1). It almost never copies lifespans as dates (9 events vs 56 for P1). Its error is missing dates, where P1's is wrong ones. Under the current verdict rule, P1's wrong dates sometimes land inside the period anyway. `plan_verdict` also has no guard against out-of-order years: 12-17 documents per plan have non-monotone year sequences.

Misses shared by all plans (P1 misses 11 silver-flagged documents):
- **Silver label not supported by the text (5).** 229508: Galerie J. Kugel matched Red Flag "Kugel, M Jacques" on the initial J., and the dealer is undated in gold; the text says "acquired 2023". 11589: Hôtel Drouot, undated in gold; the text gives an 1880 sale. 139276: gold "Hirschland, Georg S." matched Red Flag "Hirschland, Simeon" on the middle initial "S.". 143662: gold "Koenigs" vs the text "Wilhelm Koenig". 51136: Bignou has gold years 1935, while the text puts him before a 1929 sale. Cause: `silver_label` treats undated gold owners as in-war, and the full-name tier accepts any initial.
- **Red Flag matcher fails on a correct extraction (3).** 52199 "Gustave Rochlitz" (the forename must be followed by whitespace). 73852 "K. Muhlmann" (the text has no umlaut, so the folded form does not equal the key `muehlmann`). 53128 "Buchholz Gallery, Berlin" (a firm; the full-name tier needs a forename).
- **Run error (2).** P1 46090 and 46681. P3 still misses both: P2 omits Bignou in 46090, and in 46681 Bignou is undated with the next dated event 1931.
- **Verdict rule (1).** 61369: "(Ambroise Vollard), by 1922 until at least 1936.[2] possibly (Etienne Bignou, Paris).[3] William A. Cargill ..., by 1956". Bignou is undated, and the rule uses only the next year (1956) instead of the window 1936-1956, so the result is not flagged rather than not decided.

Silver FPs (2, same for all plans):
- 46163: "(Karl Haberstock, Berlin), possibly until 1936". The text supports an overlap with the period, so the silver label looks wrong.
- 52183: "(sale, Hôtel Drouot, Paris, 23 November 1910)". The plan holds Drouot until the next dated event (1955). This is a verdict-rule error, and also `redflag-role`: Drouot is an auction firm.

## Q3. Escalation in P3 (21 documents)

| trigger | n | trigger cleared after escalation | owners P1 → P3 (TP / FP / FN) | verdict changed |
|---|---|---|---|---|
| error or empty | 2 | 2 (46681 then fails the span check) | +19 / +6 / −19 | 0 |
| span not in text | 8 | 3 (1609, 95, 1216); 61369 now fails "no dated event" | +4 / −4 / −4 | 0 |
| no dated 1933-45 event | 11 | 3 (34047, 11642, 130843); 61248 now fails the span check | 0 / −4 / 0 | 0 |

- **Did the large model fix the trigger?** Only in 7 of 21 cases. Of the 4 span cases still failing, 3 are whitespace artefacts: 1184, 139202 and 52161 have double spaces in the source, and no model output passes the strict test there unless the model copies the double space. The "no dated 1933-45 event" check matches any 1933-45 year in the text, including lifespans such as "Susan Macdowell Eakins [Mrs. Thomas Eakins, 1851-1938]" (72164), so a better extraction cannot clear it.
- **Did any escalation make things worse?** Yes, slightly, in 4 documents:
  - 139276: TP 3→2. P2 loses Fred Triest to a non-verbatim span.
  - 1609: FP +1.
  - 11642: FP +1.
  - 52161: TP +1 but FP +1.
  No verdict changed in any of the 21. The 2 silver FPs (46163, 52183) were escalated and stayed flagged.
- **Cost:** P3 used 2852.5 s vs 2136.7 s for P1 (+33%). The owners gain over P1 is +0.025 F1 (95% CI +0.005..+0.05). Escalating only the 2 "error or empty" documents would have given F1 0.723; the other 19 escalations add about +0.009.

## Q4. By stratum

Owners (F1, with TP/FP/FN):

| stratum | docs | gold | P1 | P2 | P3 |
|---|---|---|---|---|---|
| p0_miss | 6 | 38 | 0.602 (31/34/7) | 0.638 (30/26/8) | 0.600 (30/32/8) |
| redflag_fullname | 30 | 177 | 0.703 (130/63/47) | 0.736 (142/67/35) | 0.758 (150/69/27) |
| footnote | 20 | 138 | 0.731 (118/67/20) | 0.767 (122/58/16) | 0.733 (118/66/20) |
| vague_date | 15 | 77 | 0.716 (68/45/9) | 0.714 (65/40/12) | 0.730 (69/43/8) |
| random | 29 | 110 | 0.720 (94/57/16) | 0.688 (85/52/25) | 0.743 (97/54/13) |

Error counts per stratum, evaluation side (matcher + gold) vs model side:

| stratum | P1 eval / model | P2 eval / model | P3 eval / model | main model-side cause |
|---|---|---|---|---|
| p0_miss | 26 / 15 | 22 / 12 | 25 / 15 | split-or-merged 6-7, hallucinated 3-5 (139276 zones and forces, 73852 decree issuer) |
| redflag_fullname | 68 / 42 | 78 / 24 | 75 / 21 | P1 run-error 22 (46090, 46681); role-wrong (auction houses) 4-8 |
| footnote | 63 / 24 | 50 / 24 | 60 / 26 | split-or-merged 16-19 (estates, repeated dealers) |
| vague_date | 46 / 8 | 40 / 12 | 44 / 7 | role-wrong / span 2-5 |
| random | 59 / 14 | 53 / 24 | 56 / 11 | P2 run-error 15 (41639, 1117) |

Screening (silver TP/FP):

| stratum | docs | silver flagged | P0 | P1 | P2 | P3 |
|---|---|---|---|---|---|---|
| p0_miss | 6 | 6 | 0/0 | 0/0 | 0/0 | 0/0 |
| redflag_fullname | 30 | 17 | 17/13 | 13/1 | 10/1 | 13/1 |
| footnote | 20 | 1 | 1/1 | 1/0 | 1/0 | 1/0 |
| vague_date | 15 | 6 | 6/3 | 5/0 | 5/0 | 5/0 |
| random | 29 | 1 | 1/2 | 1/1 | 1/1 | 1/1 |

`p0_miss` is 0/6 for every plan. Its six silver labels are 229508, 52199, 143662, 73852, 53128 and 139276; of these, 3 are silver-label problems and 3 are Red Flag matcher failures on correct extractions (see Q2). The stratum measures the matcher and the labels more than the models. The `footnote` stratum is the models' best on owners; its errors are over-extraction (estates, duplicates), not misses.

## Three changes most likely to help (develop on the dev split, never on these 100)

1. **Fix the evaluation before comparing models further (scorer + silver labels).**
   - Exclude the receiving museum from scoring, or tell the extractor to omit it.
   - Make owner matching one-to-one by best similarity (folded, abbreviation-aware: Thos./Thomas, Co./Company, initials, Stiftung/Foundation) instead of a greedy token subset, and never match on generic tokens alone (`paris`, `nga`).
   - Normalise whitespace in the span check.
   - In `silver_label`, stop treating undated gold owners as in-war, and require the forename to match, not any initial.
   - Route `gold-disagrees-with-text` cases to the label-check page.

   Expected effect: about 110-120 FPs and 20-25 FNs per plan, plus 5 of the 11 screening misses.
2. **Make the Red Flag matcher and the verdict rule robust.**
   - Matcher: fold "u" to "ue" for list keys (Muhlmann), allow forename variants (Gustave/Gustav), and add a firm tier (`Buchholz Gallery` → Buchholz, Karl) that yields `not decided` rather than `flagged`.
   - Verdict rule: bound an undated event by the previous and next dated events, sort or flag out-of-order years, and treat auction sales as point events.

   Expected effect: about 4-5 of the 11 shared screening misses (52199, 73852, 53128, 61369) and 1 of the 2 FPs (52183). P2's 2 date-order losses (46488, 66424) are also partly a symptom of this rule.
3. **Prompt and output-schema changes for the remaining model errors.**
   - Separate the consignor from the auction house in a sale event ("(his sale, Hôtel Drouot ...)" → two events).
   - Do not emit "his estate" or "heirs" as separate owners.
   - Emit one event per party ("X and Y" → 2).
   - Never emit places, exhibitions, marks, or parties a sentence negates.
   - Raise `MAX_OUT` or ask for compact JSON (46090 truncated at 2048 tokens).
   - Make the cascade check ignore lifespans in brackets.

   Expected effect: targets 87 of P1's 103 model-side errors (split 37, role 16, hallucinated 12, run-error 22), and it removes the escalations that cannot succeed.
